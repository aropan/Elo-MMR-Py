use std::collections::{HashMap, HashSet};
use std::io::{BufWriter, Write};
#[cfg(unix)]
use std::os::unix::fs::PermissionsExt;
use std::panic::{AssertUnwindSafe, catch_unwind};
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::Instant;

use multi_skill::data_processing::{Contest, ContestRatingParams};
use multi_skill::systems::{
    EloMMR, EloMMRVariant, PlayerEvent, PlayersByName, RatingSystem, get_rating_system_by_name,
    simulate_contest,
};
use pyo3::exceptions::{PyOSError, PyOverflowError, PyRuntimeError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyModule, PyTuple, PyType};
use serde::{Deserialize, Serialize};
use tempfile::NamedTempFile;

const CHECKPOINT_FORMAT_VERSION: u32 = 2;
const PACKAGE_VERSION: &str = env!("CARGO_PKG_VERSION");
const CHECKPOINT_BUFFER_CAPACITY: usize = 64 * 1024;
const SUPPORTED_SYSTEMS: &[&str] = &[
    "bar",
    "glicko",
    "cfsys",
    "tcsys",
    "trueskill",
    "mmx",
    "mmx-fast",
    "mmr",
    "mmr-fast",
    "mmr-simple",
];
const ELO_MMR_SYSTEMS: &[&str] = &["mmx", "mmx-fast", "mmr", "mmr-fast"];

#[derive(Debug)]
enum BindingError {
    Invalid(String),
    Io(String, std::io::Error),
    Runtime(String),
}

impl From<BindingError> for PyErr {
    fn from(error: BindingError) -> Self {
        match error {
            BindingError::Invalid(message) => PyValueError::new_err(message),
            BindingError::Io(context, source) => PyOSError::new_err(format!("{context}: {source}")),
            BindingError::Runtime(message) => PyRuntimeError::new_err(message),
        }
    }
}

fn panic_message(payload: Box<dyn std::any::Any + Send>) -> String {
    if let Some(message) = payload.downcast_ref::<&str>() {
        (*message).to_owned()
    } else if let Some(message) = payload.downcast_ref::<String>() {
        message.clone()
    } else {
        "unknown Rust panic".to_owned()
    }
}

fn numeric_overflow_as_value_error(error: PyErr, py: Python<'_>, argument: &str) -> PyErr {
    if error.is_instance_of::<PyOverflowError>(py) {
        PyValueError::new_err(format!(
            "{argument} contains a value outside the supported numeric range"
        ))
    } else {
        error
    }
}

fn extract_standings_argument(value: &Bound<'_, PyAny>) -> PyResult<Vec<(String, i128, i128)>> {
    value
        .extract()
        .map_err(|error| numeric_overflow_as_value_error(error, value.py(), "standings"))
}

fn extract_time_seconds_argument(value: &Bound<'_, PyAny>) -> PyResult<Option<i128>> {
    value
        .extract()
        .map_err(|error| numeric_overflow_as_value_error(error, value.py(), "time_seconds"))
}

fn extract_mu_noob_argument(value: &Bound<'_, PyAny>) -> PyResult<f64> {
    value
        .extract()
        .map_err(|error| numeric_overflow_as_value_error(error, value.py(), "mu_noob"))
}

fn extract_sig_noob_argument(value: &Bound<'_, PyAny>) -> PyResult<f64> {
    value
        .extract()
        .map_err(|error| numeric_overflow_as_value_error(error, value.py(), "sig_noob"))
}

fn extract_f64_argument(value: &Bound<'_, PyAny>, argument: &str) -> PyResult<f64> {
    value
        .extract()
        .map_err(|error| numeric_overflow_as_value_error(error, value.py(), argument))
}

fn extract_optional_f64_argument(
    value: &Bound<'_, PyAny>,
    argument: &str,
) -> PyResult<Option<f64>> {
    value
        .extract()
        .map_err(|error| numeric_overflow_as_value_error(error, value.py(), argument))
}

fn extract_weight_argument(value: &Bound<'_, PyAny>) -> PyResult<f64> {
    extract_f64_argument(value, "weight")
}

fn extract_perf_ceiling_argument(value: &Bound<'_, PyAny>) -> PyResult<Option<f64>> {
    extract_optional_f64_argument(value, "perf_ceiling")
}

fn extract_weight_limit_argument(value: &Bound<'_, PyAny>) -> PyResult<f64> {
    extract_f64_argument(value, "weight_limit")
}

fn extract_noob_delay_argument(value: &Bound<'_, PyAny>) -> PyResult<Option<Vec<f64>>> {
    value
        .extract()
        .map_err(|error| numeric_overflow_as_value_error(error, value.py(), "noob_delay"))
}

fn extract_sig_limit_argument(value: &Bound<'_, PyAny>) -> PyResult<f64> {
    extract_f64_argument(value, "sig_limit")
}

fn extract_drift_per_day_argument(value: &Bound<'_, PyAny>) -> PyResult<f64> {
    extract_f64_argument(value, "drift_per_day")
}

fn extract_subsample_size_argument(value: &Bound<'_, PyAny>) -> PyResult<Option<i128>> {
    value
        .extract()
        .map_err(|error| numeric_overflow_as_value_error(error, value.py(), "subsample_size"))
}

fn extract_subsample_bucket_argument(value: &Bound<'_, PyAny>) -> PyResult<Option<f64>> {
    extract_optional_f64_argument(value, "subsample_bucket")
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct EloMmrConfigData {
    weight_limit: f64,
    noob_delay: Vec<f64>,
    sig_limit: f64,
    drift_per_day: f64,
    split_ties: bool,
    /// Resolved storage: `None` is unlimited history (`usize::MAX` upstream).
    /// At the Python constructor boundary, an omitted/`None` argument selects
    /// the named mode's default before this value is stored.
    subsample_size: Option<usize>,
    subsample_bucket: f64,
}

impl EloMmrConfigData {
    fn defaults(system: &str) -> Self {
        let upstream = match system {
            "mmr" => EloMMR::default(),
            "mmr-fast" => EloMMR::default_fast(),
            "mmx" => EloMMR::default_gaussian(),
            "mmx-fast" => EloMMR::default_gaussian_fast(),
            _ => unreachable!("defaults are only defined for Elo-MMR systems"),
        };
        Self {
            weight_limit: upstream.weight_limit,
            noob_delay: upstream.noob_delay,
            sig_limit: upstream.sig_limit,
            drift_per_day: upstream.drift_per_day,
            split_ties: upstream.split_ties,
            subsample_size: (upstream.subsample_size != usize::MAX)
                .then_some(upstream.subsample_size),
            subsample_bucket: upstream.subsample_bucket,
        }
    }

    fn validate(&self) -> Result<(), BindingError> {
        if !self.weight_limit.is_finite() || self.weight_limit <= 0.0 {
            return Err(BindingError::Invalid(
                "weight_limit must be a finite number greater than zero".to_owned(),
            ));
        }
        for (index, factor) in self.noob_delay.iter().enumerate() {
            if !factor.is_finite() || *factor <= 0.0 || *factor > 1.0 {
                return Err(BindingError::Invalid(format!(
                    "noob_delay[{index}] must be a finite number in (0, 1]"
                )));
            }
        }
        if !self.sig_limit.is_finite() || self.sig_limit <= 0.0 {
            return Err(BindingError::Invalid(
                "sig_limit must be a finite number greater than zero".to_owned(),
            ));
        }
        if !self.drift_per_day.is_finite() || self.drift_per_day < 0.0 {
            return Err(BindingError::Invalid(
                "drift_per_day must be a finite non-negative number".to_owned(),
            ));
        }
        if self.subsample_size == Some(0) {
            return Err(BindingError::Invalid(
                "subsample_size must be greater than zero".to_owned(),
            ));
        }
        if !self.subsample_bucket.is_finite() || self.subsample_bucket <= 0.0 {
            return Err(BindingError::Invalid(
                "subsample_bucket must be a finite number greater than zero".to_owned(),
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, PartialEq)]
struct SystemSpec {
    name: String,
    config: Option<EloMmrConfigData>,
}

impl SystemSpec {
    fn from_name(name: String) -> Result<Self, BindingError> {
        if !SUPPORTED_SYSTEMS.contains(&name.as_str()) {
            return Err(BindingError::Invalid(format!(
                "unsupported rating system {name:?}; expected one of: {}",
                SUPPORTED_SYSTEMS.join(", ")
            )));
        }
        let config = ELO_MMR_SYSTEMS
            .contains(&name.as_str())
            .then(|| EloMmrConfigData::defaults(&name));
        Ok(Self { name, config })
    }

    fn from_parts(name: String, config: Option<EloMmrConfigData>) -> Result<Self, BindingError> {
        let expected = Self::from_name(name.clone())?;
        match (&expected.config, &config) {
            (Some(_), Some(config)) => config.validate()?,
            (Some(_), None) => {
                return Err(BindingError::Invalid(format!(
                    "checkpoint system {name:?} requires system_config"
                )));
            }
            (None, Some(_)) => {
                return Err(BindingError::Invalid(format!(
                    "checkpoint system {name:?} must not define system_config"
                )));
            }
            (None, None) => {}
        }
        Ok(Self { name, config })
    }

    fn build_rating_system(&self) -> Result<Box<dyn RatingSystem + Send>, BindingError> {
        if let Some(config) = &self.config {
            let variant = match self.name.as_str() {
                "mmr" | "mmr-fast" => EloMMRVariant::Logistic(1.0),
                "mmx" | "mmx-fast" => EloMMRVariant::Gaussian,
                _ => unreachable!("config is only present for Elo-MMR systems"),
            };
            return Ok(Box::new(EloMMR {
                weight_limit: config.weight_limit,
                noob_delay: config.noob_delay.clone(),
                sig_limit: config.sig_limit,
                drift_per_day: config.drift_per_day,
                split_ties: config.split_ties,
                subsample_size: config.subsample_size.unwrap_or(usize::MAX),
                subsample_bucket: config.subsample_bucket,
                variant,
            }));
        }
        get_rating_system_by_name(&self.name).map_err(BindingError::Invalid)
    }
}

/// Immutable configuration for the Elo-MMR and MMX rating systems.
#[pyclass(
    name = "EloMmrConfig",
    frozen,
    from_py_object,
    eq,
    module = "elo_mmr_py.elo_mmr_python_bindings"
)]
#[derive(Clone, PartialEq)]
struct PyEloMmrConfig {
    spec: SystemSpec,
}

#[pymethods]
impl PyEloMmrConfig {
    #[new]
    #[pyo3(signature = (
        system="mmr",
        *,
        weight_limit=0.2,
        noob_delay=None,
        sig_limit=80.0,
        drift_per_day=0.0,
        split_ties=false,
        subsample_size=None,
        subsample_bucket=None,
    ))]
    #[allow(clippy::too_many_arguments)]
    fn new(
        system: &str,
        #[pyo3(from_py_with = extract_weight_limit_argument)] weight_limit: f64,
        #[pyo3(from_py_with = extract_noob_delay_argument)] noob_delay: Option<Vec<f64>>,
        #[pyo3(from_py_with = extract_sig_limit_argument)] sig_limit: f64,
        #[pyo3(from_py_with = extract_drift_per_day_argument)] drift_per_day: f64,
        split_ties: bool,
        #[pyo3(from_py_with = extract_subsample_size_argument)] subsample_size: Option<i128>,
        #[pyo3(from_py_with = extract_subsample_bucket_argument)] subsample_bucket: Option<f64>,
    ) -> PyResult<Self> {
        if !ELO_MMR_SYSTEMS.contains(&system) {
            return Err(BindingError::Invalid(format!(
                "EloMmrConfig system must be one of: {}",
                ELO_MMR_SYSTEMS.join(", ")
            ))
            .into());
        }
        let defaults = EloMmrConfigData::defaults(system);
        let subsample_size = subsample_size
            .map(|value| {
                usize::try_from(value).map_err(|_| {
                    BindingError::Invalid(
                        "subsample_size must be a positive integer in the usize range".to_owned(),
                    )
                })
            })
            .transpose()?;
        let config = EloMmrConfigData {
            weight_limit,
            noob_delay: noob_delay.unwrap_or_default(),
            sig_limit,
            drift_per_day,
            split_ties,
            subsample_size: subsample_size.or(defaults.subsample_size),
            subsample_bucket: subsample_bucket.unwrap_or(defaults.subsample_bucket),
        };
        config.validate()?;
        Ok(Self {
            spec: SystemSpec {
                name: system.to_owned(),
                config: Some(config),
            },
        })
    }

    #[getter]
    fn system(&self) -> &str {
        &self.spec.name
    }

    #[getter]
    fn weight_limit(&self) -> f64 {
        self.config().weight_limit
    }

    #[getter]
    fn noob_delay(&self) -> Vec<f64> {
        self.config().noob_delay.clone()
    }

    #[getter]
    fn sig_limit(&self) -> f64 {
        self.config().sig_limit
    }

    #[getter]
    fn drift_per_day(&self) -> f64 {
        self.config().drift_per_day
    }

    #[getter]
    fn split_ties(&self) -> bool {
        self.config().split_ties
    }

    #[getter]
    fn subsample_size(&self) -> Option<usize> {
        self.config().subsample_size
    }

    #[getter]
    fn subsample_bucket(&self) -> f64 {
        self.config().subsample_bucket
    }

    fn __repr__(&self) -> String {
        let config = self.config();
        format!(
            "EloMmrConfig(system={:?}, weight_limit={}, noob_delay={:?}, sig_limit={}, \
             drift_per_day={}, split_ties={}, subsample_size={:?}, subsample_bucket={})",
            self.spec.name,
            config.weight_limit,
            config.noob_delay,
            config.sig_limit,
            config.drift_per_day,
            config.split_ties,
            config.subsample_size,
            config.subsample_bucket,
        )
    }
}

impl PyEloMmrConfig {
    fn config(&self) -> &EloMmrConfigData {
        self.spec
            .config
            .as_ref()
            .expect("EloMmrConfig always contains configuration")
    }
}

fn extract_system_argument(value: &Bound<'_, PyAny>) -> PyResult<SystemSpec> {
    if let Ok(name) = value.extract::<String>() {
        return SystemSpec::from_name(name).map_err(Into::into);
    }
    if let Ok(config) = value.extract::<PyRef<'_, PyEloMmrConfig>>() {
        return Ok(config.spec.clone());
    }
    Err(PyTypeError::new_err(
        "system must be a supported string name or EloMmrConfig",
    ))
}

fn validate_standings(standings: &[(String, usize, usize)]) -> Result<(), BindingError> {
    let mut names = HashSet::with_capacity(standings.len());
    for (name, _, _) in standings {
        if !names.insert(name.as_str()) {
            return Err(BindingError::Invalid(format!(
                "contest contains duplicate participant {name:?}"
            )));
        }
    }

    let mut group_start = 0;
    while group_start < standings.len() {
        let (_, low, high) = &standings[group_start];
        if *low != group_start {
            return Err(BindingError::Invalid(format!(
                "contest has a non-contiguous rank at position {group_start}: \
                 expected low rank {group_start}, got {low}"
            )));
        }
        if *high < *low || *high >= standings.len() {
            return Err(BindingError::Invalid(format!(
                "contest has an invalid tie range ({low}, {high}) at position \
                 {group_start}"
            )));
        }

        for (position, (_, member_low, member_high)) in standings[*low..=*high].iter().enumerate() {
            if member_low != low || member_high != high {
                let absolute_position = low + position;
                return Err(BindingError::Invalid(format!(
                    "contest has an inconsistent tie range at position \
                     {absolute_position}: expected ({low}, {high}), got \
                     ({member_low}, {member_high})"
                )));
            }
        }
        group_start = high + 1;
    }

    Ok(())
}

fn validate_options(system: &SystemSpec, mu_noob: f64, sig_noob: f64) -> Result<(), BindingError> {
    if let Some(config) = &system.config {
        config.validate()?;
    }
    if !mu_noob.is_finite() {
        return Err(BindingError::Invalid(
            "mu_noob must be a finite number".to_owned(),
        ));
    }
    if !sig_noob.is_finite() || sig_noob <= 0.0 {
        return Err(BindingError::Invalid(
            "sig_noob must be a finite number greater than zero".to_owned(),
        ));
    }

    Ok(())
}

fn validate_chronology(
    contests: &[Contest],
    previous_time: Option<u64>,
) -> Result<(), BindingError> {
    let mut last_time = previous_time;
    for (index, contest) in contests.iter().enumerate() {
        match last_time {
            Some(previous) if contest.time_seconds < previous => {
                return Err(BindingError::Invalid(format!(
                    "contest {index} has time_seconds={} before the previous timestamp {previous}",
                    contest.time_seconds
                )));
            }
            _ => {}
        }
        last_time = Some(contest.time_seconds);
    }

    Ok(())
}

/// A ranked multiplayer competition.
///
/// `standings` contains `(participant, low_rank, high_rank)` tuples. Ranks are zero-based;
/// tied participants share the same inclusive rank interval.
#[pyclass(
    name = "Contest",
    frozen,
    from_py_object,
    module = "elo_mmr_py.elo_mmr_python_bindings"
)]
#[derive(Clone)]
struct PyContest {
    inner: Contest,
}

#[pymethods]
impl PyContest {
    #[new]
    #[pyo3(signature = (
        standings,
        name=None,
        time_seconds=None,
        url=None,
        *,
        weight=1.0,
        perf_ceiling=None,
    ))]
    fn new(
        #[pyo3(from_py_with = extract_standings_argument)] standings: Vec<(String, i128, i128)>,
        name: Option<String>,
        #[pyo3(from_py_with = extract_time_seconds_argument)] time_seconds: Option<i128>,
        url: Option<String>,
        #[pyo3(from_py_with = extract_weight_argument)] weight: f64,
        #[pyo3(from_py_with = extract_perf_ceiling_argument)] perf_ceiling: Option<f64>,
    ) -> PyResult<Self> {
        let standings = standings
            .into_iter()
            .enumerate()
            .map(|(position, (name, low, high))| {
                let low = usize::try_from(low).map_err(|_| {
                    BindingError::Invalid(format!(
                        "contest low rank at position {position} must be a non-negative usize"
                    ))
                })?;
                let high = usize::try_from(high).map_err(|_| {
                    BindingError::Invalid(format!(
                        "contest high rank at position {position} must be a non-negative usize"
                    ))
                })?;
                Ok((name, low, high))
            })
            .collect::<Result<Vec<_>, BindingError>>()?;
        let time_seconds = match time_seconds {
            Some(value) => u64::try_from(value).map_err(|_| {
                BindingError::Invalid(
                    "contest time_seconds must be a non-negative 64-bit integer".to_owned(),
                )
            })?,
            None => 0,
        };
        if !weight.is_finite() || weight <= 0.0 {
            return Err(BindingError::Invalid(
                "contest weight must be a finite number greater than zero".to_owned(),
            )
            .into());
        }
        if perf_ceiling.is_some_and(|value| !value.is_finite()) {
            return Err(BindingError::Invalid(
                "contest perf_ceiling must be None or a finite number".to_owned(),
            )
            .into());
        }
        validate_standings(&standings)?;
        Ok(Self {
            inner: Contest {
                name: name.unwrap_or_default(),
                url,
                rating_params: ContestRatingParams {
                    weight,
                    perf_ceiling: perf_ceiling.unwrap_or(f64::MAX),
                },
                time_seconds,
                standings,
            },
        })
    }

    #[getter]
    fn name(&self) -> &str {
        &self.inner.name
    }

    #[getter]
    fn time_seconds(&self) -> u64 {
        self.inner.time_seconds
    }

    #[getter]
    fn standings(&self) -> Vec<(String, usize, usize)> {
        self.inner.standings.clone()
    }

    #[getter]
    fn url(&self) -> Option<&str> {
        self.inner.url.as_deref()
    }

    #[getter]
    fn weight(&self) -> f64 {
        self.inner.rating_params.weight
    }

    #[getter]
    fn perf_ceiling(&self) -> Option<f64> {
        (self.inner.rating_params.perf_ceiling != f64::MAX)
            .then_some(self.inner.rating_params.perf_ceiling)
    }

    fn __repr__(&self) -> String {
        let url = self
            .inner
            .url
            .as_ref()
            .map_or_else(|| "None".to_owned(), |url| format!("{url:?}"));
        format!(
            "Contest(name={:?}, time_seconds={}, url={}, weight={}, perf_ceiling={:?}, \
             standings={:?})",
            self.inner.name,
            self.inner.time_seconds,
            url,
            self.inner.rating_params.weight,
            self.perf_ceiling(),
            self.inner.standings,
        )
    }
}

/// One participant's rating state after a contest.
#[pyclass(
    name = "PlayerEvent",
    frozen,
    from_py_object,
    get_all,
    eq,
    module = "elo_mmr_py.elo_mmr_python_bindings"
)]
#[derive(Clone, PartialEq)]
struct PyPlayerEvent {
    contest_index: usize,
    rating_mu: i32,
    rating_sig: i32,
    perf_score: i32,
    place: usize,
}

#[pymethods]
impl PyPlayerEvent {
    fn __repr__(&self) -> String {
        format!(
            "PlayerEvent(contest_index={}, rating_mu={}, rating_sig={}, \
             perf_score={}, place={})",
            self.contest_index, self.rating_mu, self.rating_sig, self.perf_score, self.place
        )
    }

    fn __str__(&self) -> String {
        self.__repr__()
    }
}

impl From<PlayerEvent> for PyPlayerEvent {
    fn from(event: PlayerEvent) -> Self {
        Self {
            contest_index: event.contest_index,
            rating_mu: event.rating_mu,
            rating_sig: event.rating_sig,
            perf_score: event.perf_score,
            place: event.place,
        }
    }
}

/// The latest rating state without historical event objects.
#[pyclass(
    name = "PlayerRating",
    frozen,
    from_py_object,
    get_all,
    eq,
    module = "elo_mmr_py.elo_mmr_python_bindings"
)]
#[derive(Clone, PartialEq)]
struct PyPlayerRating {
    name: String,
    rating: i32,
    rating_sig: i32,
    contests_played: usize,
    mu: f64,
    sig: f64,
    update_time_seconds: u64,
}

#[pymethods]
impl PyPlayerRating {
    fn __repr__(&self) -> String {
        format!(
            "PlayerRating(name={:?}, rating={}, rating_sig={}, contests_played={}, mu={}, \
             sig={}, update_time_seconds={})",
            self.name,
            self.rating,
            self.rating_sig,
            self.contests_played,
            self.mu,
            self.sig,
            self.update_time_seconds,
        )
    }

    fn __str__(&self) -> String {
        self.__repr__()
    }
}

/// The low-level full-history result returned by the Rust extension.
#[pyclass(
    name = "RateResult",
    frozen,
    module = "elo_mmr_py.elo_mmr_python_bindings"
)]
struct PyRateResult {
    #[pyo3(get)]
    players_events: HashMap<String, Vec<PyPlayerEvent>>,
    #[pyo3(get)]
    secs_elapsed: f64,
}

#[pymethods]
impl PyRateResult {
    fn __repr__(&self) -> String {
        let total_events: usize = self.players_events.values().map(Vec::len).sum();
        format!(
            "RateResult(n_players={}, n_total_events={}, secs_elapsed={})",
            self.players_events.len(),
            total_events,
            self.secs_elapsed
        )
    }

    fn __str__(&self) -> String {
        self.__repr__()
    }
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct CheckpointV2<P> {
    format_version: u32,
    package_version: String,
    system: String,
    system_config: Option<EloMmrConfigData>,
    mu_noob: f64,
    sig_noob: f64,
    contests_processed: usize,
    last_time_seconds: Option<u64>,
    players: P,
}

struct LoadedState {
    players: PlayersByName,
    contests_processed: usize,
    last_time_seconds: Option<u64>,
}

fn infer_legacy_metadata(players: &PlayersByName) -> (usize, Option<u64>) {
    let mut contests_processed = 0;
    let mut last_time_seconds = None;
    for player in players.values() {
        let player = player.borrow();
        for event in &player.event_history {
            contests_processed = contests_processed.max(event.contest_index.saturating_add(1));
        }
        last_time_seconds = Some(
            last_time_seconds.map_or(player.update_time, |last: u64| last.max(player.update_time)),
        );
    }
    (contests_processed, last_time_seconds)
}

fn validate_checkpoint_state(
    players: &PlayersByName,
    contests_processed: usize,
    last_time_seconds: Option<u64>,
) -> Result<(), BindingError> {
    match (contests_processed, last_time_seconds) {
        (0, Some(_)) => {
            return Err(BindingError::Invalid(
                "checkpoint without processed contests must not define last_time_seconds"
                    .to_owned(),
            ));
        }
        (count, None) if count > 0 => {
            return Err(BindingError::Invalid(format!(
                "checkpoint with contests_processed={count} must define last_time_seconds"
            )));
        }
        _ => {}
    }

    for (name, player) in players {
        let player = player.borrow();
        if player.event_history.is_empty() {
            return Err(BindingError::Invalid(format!(
                "checkpoint player {name:?} has no rating events"
            )));
        }
        if !player.approx_posterior.mu.is_finite()
            || !player.approx_posterior.sig.is_finite()
            || player.approx_posterior.sig <= 0.0
        {
            return Err(BindingError::Invalid(format!(
                "checkpoint player {name:?} has an invalid posterior rating"
            )));
        }
        if let Some(event) = player
            .event_history
            .iter()
            .find(|event| event.contest_index >= contests_processed)
        {
            return Err(BindingError::Invalid(format!(
                "checkpoint player {name:?} has contest_index={} outside the declared \
                 contests_processed={contests_processed}",
                event.contest_index
            )));
        }
        match last_time_seconds {
            Some(last_time) if player.update_time > last_time => {
                return Err(BindingError::Invalid(format!(
                    "checkpoint player {name:?} was updated at {}, after \
                     last_time_seconds={last_time}",
                    player.update_time
                )));
            }
            None => {
                return Err(BindingError::Invalid(
                    "checkpoint with players must define last_time_seconds".to_owned(),
                ));
            }
            Some(_) => {}
        }
    }
    Ok(())
}

fn load_checkpoint(
    path: &Path,
    system: &SystemSpec,
    mu_noob: f64,
    sig_noob: f64,
) -> Result<LoadedState, BindingError> {
    let contents = std::fs::read(path).map_err(|error| {
        BindingError::Io(
            format!("failed to read checkpoint {}", path.display()),
            error,
        )
    })?;
    match serde_json::from_slice::<CheckpointV2<PlayersByName>>(&contents) {
        Ok(checkpoint) => {
            if checkpoint.format_version != CHECKPOINT_FORMAT_VERSION {
                return Err(BindingError::Invalid(format!(
                    "unsupported checkpoint format version {}; expected \
                     {CHECKPOINT_FORMAT_VERSION}",
                    checkpoint.format_version
                )));
            }
            let checkpoint_system =
                SystemSpec::from_parts(checkpoint.system, checkpoint.system_config)?;
            if checkpoint_system.name != system.name {
                return Err(BindingError::Invalid(format!(
                    "checkpoint uses system {:?}, but this run requested {:?}",
                    checkpoint_system.name, system.name
                )));
            }
            if checkpoint_system.config != system.config {
                return Err(BindingError::Invalid(format!(
                    "checkpoint system configuration does not match the requested {:?} \
                     configuration",
                    system.name
                )));
            }
            if checkpoint.mu_noob.to_bits() != mu_noob.to_bits()
                || checkpoint.sig_noob.to_bits() != sig_noob.to_bits()
            {
                return Err(BindingError::Invalid(format!(
                    "checkpoint newbie parameters are mu_noob={} and sig_noob={}, but this run \
                     requested mu_noob={mu_noob} and sig_noob={sig_noob}",
                    checkpoint.mu_noob, checkpoint.sig_noob
                )));
            }
            validate_checkpoint_state(
                &checkpoint.players,
                checkpoint.contests_processed,
                checkpoint.last_time_seconds,
            )?;
            Ok(LoadedState {
                players: checkpoint.players,
                contests_processed: checkpoint.contests_processed,
                last_time_seconds: checkpoint.last_time_seconds,
            })
        }
        Err(v2_error) => {
            let players: PlayersByName =
                serde_json::from_slice(&contents).map_err(|legacy_error| {
                    BindingError::Invalid(format!(
                        "failed to parse checkpoint {} as JSON matching the v2 or legacy schema: \
                     v2 schema: {v2_error}; legacy schema: {legacy_error}",
                        path.display()
                    ))
                })?;
            let (contests_processed, last_time_seconds) = infer_legacy_metadata(&players);
            validate_checkpoint_state(&players, contests_processed, last_time_seconds)?;
            Ok(LoadedState {
                players,
                contests_processed,
                last_time_seconds,
            })
        }
    }
}

fn load_v2_checkpoint(path: &Path) -> Result<(SystemSpec, f64, f64, LoadedState), BindingError> {
    let contents = std::fs::read(path).map_err(|error| {
        BindingError::Io(
            format!("failed to read checkpoint {}", path.display()),
            error,
        )
    })?;
    let checkpoint: CheckpointV2<PlayersByName> =
        serde_json::from_slice(&contents).map_err(|error| {
            BindingError::Invalid(format!(
                "checkpoint {} does not match the v2 schema: {error}",
                path.display()
            ))
        })?;
    if checkpoint.format_version != CHECKPOINT_FORMAT_VERSION {
        return Err(BindingError::Invalid(format!(
            "unsupported checkpoint format version {}; expected {CHECKPOINT_FORMAT_VERSION}",
            checkpoint.format_version
        )));
    }
    let system = SystemSpec::from_parts(checkpoint.system, checkpoint.system_config)?;
    validate_options(&system, checkpoint.mu_noob, checkpoint.sig_noob)?;
    validate_checkpoint_state(
        &checkpoint.players,
        checkpoint.contests_processed,
        checkpoint.last_time_seconds,
    )?;
    Ok((
        system,
        checkpoint.mu_noob,
        checkpoint.sig_noob,
        LoadedState {
            players: checkpoint.players,
            contests_processed: checkpoint.contests_processed,
            last_time_seconds: checkpoint.last_time_seconds,
        },
    ))
}

fn checkpoint_serialization_error(path: &Path, error: serde_json::Error) -> BindingError {
    if error.is_io() {
        let kind = error.io_error_kind().unwrap_or(std::io::ErrorKind::Other);
        BindingError::Io(
            format!(
                "failed to write serialized checkpoint for {}",
                path.display()
            ),
            std::io::Error::new(kind, error.to_string()),
        )
    } else {
        BindingError::Runtime(format!("failed to serialize checkpoint: {error}"))
    }
}

fn write_checkpoint_json<W: Write, T: Serialize>(writer: W, value: &T) -> serde_json::Result<()> {
    let mut writer = BufWriter::with_capacity(CHECKPOINT_BUFFER_CAPACITY, writer);
    serde_json::to_writer(&mut writer, value)?;
    writer.write_all(b"\n").map_err(serde_json::Error::io)?;
    writer.flush().map_err(serde_json::Error::io)
}

#[cfg(unix)]
fn preserve_existing_mode(path: &Path, temporary: &NamedTempFile) -> Result<(), BindingError> {
    match std::fs::symlink_metadata(path) {
        Ok(metadata) if metadata.file_type().is_file() => temporary
            .as_file()
            .set_permissions(std::fs::Permissions::from_mode(
                metadata.permissions().mode(),
            ))
            .map_err(|error| {
                BindingError::Io(
                    format!(
                        "failed to preserve POSIX mode bits for checkpoint {}",
                        path.display()
                    ),
                    error,
                )
            }),
        Ok(_) => Ok(()),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(error) => Err(BindingError::Io(
            format!("failed to inspect existing checkpoint {}", path.display()),
            error,
        )),
    }
}

#[cfg(not(unix))]
fn preserve_existing_mode(_path: &Path, _temporary: &NamedTempFile) -> Result<(), BindingError> {
    Ok(())
}

#[cfg(unix)]
fn sync_parent_directory(parent: &Path, path: &Path) -> Result<(), BindingError> {
    std::fs::File::open(parent)
        .and_then(|directory| directory.sync_all())
        .map_err(|error| {
            BindingError::Io(
                format!(
                    "checkpoint {} was replaced, but its parent directory could not be synced",
                    path.display()
                ),
                error,
            )
        })
}

#[cfg(not(unix))]
fn sync_parent_directory(_parent: &Path, _path: &Path) -> Result<(), BindingError> {
    Ok(())
}

fn save_checkpoint<P: Serialize>(
    path: &Path,
    checkpoint: &CheckpointV2<P>,
) -> Result<(), BindingError> {
    let parent = path
        .parent()
        .filter(|parent| !parent.as_os_str().is_empty())
        .unwrap_or_else(|| Path::new("."));
    let mut temporary = NamedTempFile::new_in(parent).map_err(|error| {
        BindingError::Io(
            format!(
                "failed to create a temporary checkpoint next to {}",
                path.display()
            ),
            error,
        )
    })?;
    write_checkpoint_json(temporary.as_file_mut(), checkpoint)
        .map_err(|error| checkpoint_serialization_error(path, error))?;
    preserve_existing_mode(path, &temporary)?;
    temporary.as_file_mut().sync_all().map_err(|error| {
        BindingError::Io(
            format!("failed to sync temporary checkpoint for {}", path.display()),
            error,
        )
    })?;
    temporary.persist(path).map_err(|error| {
        BindingError::Io(
            format!("failed to atomically replace checkpoint {}", path.display()),
            error.error,
        )
    })?;
    sync_parent_directory(parent, path)
}

struct RaterState {
    system_spec: SystemSpec,
    system: Box<dyn RatingSystem + Send>,
    mu_noob: f64,
    sig_noob: f64,
    players: PlayersByName,
    contests_processed: usize,
    last_time_seconds: Option<u64>,
}

impl RaterState {
    fn new(system_spec: SystemSpec, mu_noob: f64, sig_noob: f64) -> Result<Self, BindingError> {
        validate_options(&system_spec, mu_noob, sig_noob)?;
        let system = system_spec.build_rating_system()?;
        Ok(Self {
            system_spec,
            system,
            mu_noob,
            sig_noob,
            players: HashMap::new(),
            contests_processed: 0,
            last_time_seconds: None,
        })
    }

    fn from_loaded(
        system_spec: SystemSpec,
        mu_noob: f64,
        sig_noob: f64,
        loaded: LoadedState,
    ) -> Result<Self, BindingError> {
        validate_options(&system_spec, mu_noob, sig_noob)?;
        validate_checkpoint_state(
            &loaded.players,
            loaded.contests_processed,
            loaded.last_time_seconds,
        )?;
        let system = system_spec.build_rating_system()?;
        Ok(Self {
            system_spec,
            system,
            mu_noob,
            sig_noob,
            players: loaded.players,
            contests_processed: loaded.contests_processed,
            last_time_seconds: loaded.last_time_seconds,
        })
    }

    fn extend(&mut self, contests: &[Contest]) -> Result<f64, BindingError> {
        validate_chronology(contests, self.last_time_seconds)?;
        let new_count = self
            .contests_processed
            .checked_add(contests.len())
            .ok_or_else(|| BindingError::Invalid("contest count overflowed usize".to_owned()))?;

        let started = Instant::now();
        for (offset, contest) in contests.iter().enumerate() {
            simulate_contest(
                &mut self.players,
                contest,
                self.system.as_ref(),
                self.mu_noob,
                self.sig_noob,
                self.contests_processed + offset,
            );
        }
        let secs_elapsed = started.elapsed().as_secs_f64();
        self.contests_processed = new_count;
        if let Some(contest) = contests.last() {
            self.last_time_seconds = Some(contest.time_seconds);
        }
        Ok(secs_elapsed)
    }

    fn checkpoint(&self) -> CheckpointV2<&PlayersByName> {
        CheckpointV2 {
            format_version: CHECKPOINT_FORMAT_VERSION,
            package_version: PACKAGE_VERSION.to_owned(),
            system: self.system_spec.name.clone(),
            system_config: self.system_spec.config.clone(),
            mu_noob: self.mu_noob,
            sig_noob: self.sig_noob,
            contests_processed: self.contests_processed,
            last_time_seconds: self.last_time_seconds,
            players: &self.players,
        }
    }
}

struct RunResults {
    state: RaterState,
    secs_elapsed: f64,
}

fn run_rating_inner(
    system: SystemSpec,
    contests: Vec<Contest>,
    mu_noob: f64,
    sig_noob: f64,
    load_path: Option<PathBuf>,
    save_path: Option<PathBuf>,
) -> Result<RunResults, BindingError> {
    validate_options(&system, mu_noob, sig_noob)?;
    let mut state = if let Some(path) = load_path.as_deref() {
        let loaded = load_checkpoint(path, &system, mu_noob, sig_noob)?;
        RaterState::from_loaded(system, mu_noob, sig_noob, loaded)?
    } else {
        RaterState::new(system, mu_noob, sig_noob)?
    };
    let secs_elapsed = state.extend(&contests)?;
    if let Some(path) = save_path.as_deref() {
        save_checkpoint(path, &state.checkpoint())?;
    }

    Ok(RunResults {
        state,
        secs_elapsed,
    })
}

fn run_rating(
    system: SystemSpec,
    contests: Vec<Contest>,
    mu_noob: f64,
    sig_noob: f64,
    load_path: Option<PathBuf>,
    save_path: Option<PathBuf>,
) -> Result<RunResults, BindingError> {
    catch_unwind(AssertUnwindSafe(|| {
        run_rating_inner(system, contests, mu_noob, sig_noob, load_path, save_path)
    }))
    .map_err(|payload| {
        BindingError::Runtime(format!(
            "rating calculation failed inside Rust: {}",
            panic_message(payload)
        ))
    })?
}

fn full_result(results: RunResults) -> PyRateResult {
    let players_events = results
        .state
        .players
        .into_iter()
        .map(|(name, player)| {
            let events = player
                .into_inner()
                .event_history
                .into_iter()
                .map(PyPlayerEvent::from)
                .collect();
            (name, events)
        })
        .collect();
    PyRateResult {
        players_events,
        secs_elapsed: results.secs_elapsed,
    }
}

fn latest_snapshot(players: &PlayersByName) -> HashMap<String, PyPlayerRating> {
    players
        .iter()
        .map(|(name, player)| {
            let player = player.borrow();
            let rating = player.event_history.last().map_or_else(
                || player.approx_posterior.mu.round() as i32,
                |event| event.rating_mu,
            );
            let value = PyPlayerRating {
                name: name.clone(),
                rating,
                rating_sig: player.approx_posterior.sig.round() as i32,
                contests_played: player.event_history.len(),
                mu: player.approx_posterior.mu,
                sig: player.approx_posterior.sig,
                update_time_seconds: player.update_time,
            };
            (name.clone(), value)
        })
        .collect()
}

fn latest_result(results: RunResults) -> HashMap<String, PyPlayerRating> {
    latest_snapshot(&results.state.players)
}

/// Rate contests and return complete event histories.
#[pyfunction]
#[pyo3(signature = (
    system,
    contests,
    mu_noob=1500.0,
    sig_noob=350.0,
    load_checkpoint=None,
    save_checkpoint=None,
))]
fn rate(
    py: Python<'_>,
    #[pyo3(from_py_with = extract_system_argument)] system: SystemSpec,
    contests: Vec<PyContest>,
    #[pyo3(from_py_with = extract_mu_noob_argument)] mu_noob: f64,
    #[pyo3(from_py_with = extract_sig_noob_argument)] sig_noob: f64,
    load_checkpoint: Option<String>,
    save_checkpoint: Option<String>,
) -> PyResult<PyRateResult> {
    let contests = contests.into_iter().map(|contest| contest.inner).collect();
    let results = py.detach(move || {
        run_rating(
            system,
            contests,
            mu_noob,
            sig_noob,
            load_checkpoint.map(PathBuf::from),
            save_checkpoint.map(PathBuf::from),
        )
    })?;
    Ok(full_result(results))
}

/// Rate contests and return only the latest state for each participant.
#[pyfunction]
#[pyo3(signature = (
    system,
    contests,
    mu_noob=1500.0,
    sig_noob=350.0,
    load_checkpoint=None,
    save_checkpoint=None,
))]
fn rate_latest(
    py: Python<'_>,
    #[pyo3(from_py_with = extract_system_argument)] system: SystemSpec,
    contests: Vec<PyContest>,
    #[pyo3(from_py_with = extract_mu_noob_argument)] mu_noob: f64,
    #[pyo3(from_py_with = extract_sig_noob_argument)] sig_noob: f64,
    load_checkpoint: Option<String>,
    save_checkpoint: Option<String>,
) -> PyResult<HashMap<String, PyPlayerRating>> {
    let contests = contests.into_iter().map(|contest| contest.inner).collect();
    let results = py.detach(move || {
        run_rating(
            system,
            contests,
            mu_noob,
            sig_noob,
            load_checkpoint.map(PathBuf::from),
            save_checkpoint.map(PathBuf::from),
        )
    })?;
    Ok(latest_result(results))
}

/// Rust-owned incremental rating state.
#[pyclass(name = "_Rater", module = "elo_mmr_py.elo_mmr_python_bindings")]
struct PyRater {
    state: Mutex<Option<RaterState>>,
}

impl PyRater {
    fn with_state<T>(
        &self,
        operation: impl FnOnce(&mut RaterState) -> Result<T, BindingError>,
    ) -> Result<T, BindingError> {
        let mut guard = self
            .state
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let Some(state) = guard.as_mut() else {
            return Err(BindingError::Runtime(
                "Rater is unavailable after an unexpected Rust panic".to_owned(),
            ));
        };
        match catch_unwind(AssertUnwindSafe(|| operation(state))) {
            Ok(result) => result,
            Err(payload) => {
                *guard = None;
                Err(BindingError::Runtime(format!(
                    "rating calculation failed inside Rust and poisoned this Rater: {}",
                    panic_message(payload)
                )))
            }
        }
    }
}

#[pymethods]
impl PyRater {
    #[new]
    #[pyo3(signature = (system, mu_noob=1500.0, sig_noob=350.0))]
    fn new(
        #[pyo3(from_py_with = extract_system_argument)] system: SystemSpec,
        #[pyo3(from_py_with = extract_mu_noob_argument)] mu_noob: f64,
        #[pyo3(from_py_with = extract_sig_noob_argument)] sig_noob: f64,
    ) -> PyResult<Self> {
        Ok(Self {
            state: Mutex::new(Some(RaterState::new(system, mu_noob, sig_noob)?)),
        })
    }

    #[classmethod]
    fn load(_cls: &Bound<'_, PyType>, py: Python<'_>, path: String) -> PyResult<Self> {
        let state = py.detach(move || {
            let (system, mu_noob, sig_noob, loaded) = load_v2_checkpoint(Path::new(&path))?;
            RaterState::from_loaded(system, mu_noob, sig_noob, loaded)
        })?;
        Ok(Self {
            state: Mutex::new(Some(state)),
        })
    }

    fn add(&self, py: Python<'_>, contest: PyContest) -> PyResult<()> {
        py.detach(move || self.with_state(|state| state.extend(&[contest.inner]).map(|_| ())))?;
        Ok(())
    }

    fn extend(&self, py: Python<'_>, contests: Vec<PyContest>) -> PyResult<()> {
        let contests: Vec<Contest> = contests.into_iter().map(|contest| contest.inner).collect();
        py.detach(move || self.with_state(|state| state.extend(&contests).map(|_| ())))?;
        Ok(())
    }

    #[getter]
    fn ratings(&self, py: Python<'_>) -> PyResult<HashMap<String, PyPlayerRating>> {
        py.detach(|| self.with_state(|state| Ok(latest_snapshot(&state.players))))
            .map_err(Into::into)
    }

    fn save(&self, py: Python<'_>, path: String) -> PyResult<()> {
        py.detach(move || {
            self.with_state(|state| save_checkpoint(Path::new(&path), &state.checkpoint()))
        })?;
        Ok(())
    }

    #[getter]
    fn system(&self, py: Python<'_>) -> PyResult<String> {
        py.detach(|| self.with_state(|state| Ok(state.system_spec.name.clone())))
            .map_err(Into::into)
    }

    #[getter]
    fn system_config(&self, py: Python<'_>) -> PyResult<Option<PyEloMmrConfig>> {
        py.detach(|| {
            self.with_state(|state| {
                Ok(state
                    .system_spec
                    .config
                    .as_ref()
                    .map(|config| PyEloMmrConfig {
                        spec: SystemSpec {
                            name: state.system_spec.name.clone(),
                            config: Some(config.clone()),
                        },
                    }))
            })
        })
        .map_err(Into::into)
    }

    #[getter]
    fn mu_noob(&self, py: Python<'_>) -> PyResult<f64> {
        py.detach(|| self.with_state(|state| Ok(state.mu_noob)))
            .map_err(Into::into)
    }

    #[getter]
    fn sig_noob(&self, py: Python<'_>) -> PyResult<f64> {
        py.detach(|| self.with_state(|state| Ok(state.sig_noob)))
            .map_err(Into::into)
    }

    #[getter]
    fn contests_processed(&self, py: Python<'_>) -> PyResult<usize> {
        py.detach(|| self.with_state(|state| Ok(state.contests_processed)))
            .map_err(Into::into)
    }

    #[getter]
    fn last_time_seconds(&self, py: Python<'_>) -> PyResult<Option<u64>> {
        py.detach(|| self.with_state(|state| Ok(state.last_time_seconds)))
            .map_err(Into::into)
    }
}

#[pymodule]
fn elo_mmr_python_bindings(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<PyContest>()?;
    module.add_class::<PyEloMmrConfig>()?;
    module.add_class::<PyPlayerEvent>()?;
    module.add_class::<PyPlayerRating>()?;
    module.add_class::<PyRateResult>()?;
    module.add_class::<PyRater>()?;
    module.add_function(wrap_pyfunction!(rate, module)?)?;
    module.add_function(wrap_pyfunction!(rate_latest, module)?)?;
    module.add("CHECKPOINT_FORMAT_VERSION", CHECKPOINT_FORMAT_VERSION)?;
    module.add(
        "SUPPORTED_SYSTEMS",
        PyTuple::new(module.py(), SUPPORTED_SYSTEMS)?,
    )?;
    module.add("__version__", PACKAGE_VERSION)?;
    module.add(
        "__all__",
        vec![
            "Contest",
            "EloMmrConfig",
            "PlayerEvent",
            "PlayerRating",
            "RateResult",
            "rate",
            "rate_latest",
            "CHECKPOINT_FORMAT_VERSION",
            "SUPPORTED_SYSTEMS",
            "__version__",
        ],
    )?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validates_contiguous_ties() {
        let standings = vec![
            ("winner".to_owned(), 0, 0),
            ("tie-a".to_owned(), 1, 2),
            ("tie-b".to_owned(), 1, 2),
        ];
        assert!(validate_standings(&standings).is_ok());
    }

    #[test]
    fn rejects_duplicate_participants() {
        let standings = vec![("same".to_owned(), 0, 0), ("same".to_owned(), 1, 1)];
        assert!(validate_standings(&standings).is_err());
    }

    #[test]
    fn rejects_inconsistent_ties() {
        let standings = vec![("a".to_owned(), 0, 1), ("b".to_owned(), 1, 1)];
        assert!(validate_standings(&standings).is_err());
    }

    struct FailingWriter;

    impl Write for FailingWriter {
        fn write(&mut self, _buffer: &[u8]) -> std::io::Result<usize> {
            Err(std::io::Error::new(
                std::io::ErrorKind::PermissionDenied,
                "simulated write failure",
            ))
        }

        fn flush(&mut self) -> std::io::Result<()> {
            Ok(())
        }
    }

    #[test]
    fn serialization_io_error_keeps_io_category() {
        let error = serde_json::to_writer(FailingWriter, &vec![1, 2, 3]).unwrap_err();
        let mapped = checkpoint_serialization_error(Path::new("ratings.json"), error);

        assert!(matches!(mapped, BindingError::Io(_, _)));
    }

    #[derive(Default)]
    struct CountingWriter {
        writes: usize,
        bytes: Vec<u8>,
    }

    impl Write for &mut CountingWriter {
        fn write(&mut self, buffer: &[u8]) -> std::io::Result<usize> {
            self.writes += 1;
            self.bytes.extend_from_slice(buffer);
            Ok(buffer.len())
        }

        fn flush(&mut self) -> std::io::Result<()> {
            Ok(())
        }
    }

    #[test]
    fn checkpoint_writer_batches_small_serde_writes() {
        let value: Vec<u64> = (0..100_000).collect();
        let mut output = CountingWriter::default();

        write_checkpoint_json(&mut output, &value).unwrap();

        assert!(output.bytes.len() > 500_000);
        assert!(
            output.writes < 20,
            "unexpected write count: {}",
            output.writes
        );
        assert_eq!(
            serde_json::from_slice::<Vec<u64>>(&output.bytes).unwrap(),
            value
        );
        assert_eq!(output.bytes.last(), Some(&b'\n'));
    }

    #[test]
    fn fast_and_exact_configs_resolve_their_subsampling_defaults() {
        let exact = SystemSpec::from_name("mmr".to_owned()).unwrap();
        let fast = SystemSpec::from_name("mmr-fast".to_owned()).unwrap();

        assert_eq!(exact.config.unwrap().subsample_size, None);
        assert_eq!(fast.config.unwrap().subsample_size, Some(100));
    }

    #[test]
    fn resolved_configs_match_all_upstream_defaults() {
        let upstream_configs = [
            ("mmr", EloMMR::default()),
            ("mmr-fast", EloMMR::default_fast()),
            ("mmx", EloMMR::default_gaussian()),
            ("mmx-fast", EloMMR::default_gaussian_fast()),
        ];

        for (name, upstream) in upstream_configs {
            let config = EloMmrConfigData::defaults(name);
            assert_eq!(config.weight_limit, upstream.weight_limit);
            assert_eq!(config.noob_delay, upstream.noob_delay);
            assert_eq!(config.sig_limit, upstream.sig_limit);
            assert_eq!(config.drift_per_day, upstream.drift_per_day);
            assert_eq!(config.split_ties, upstream.split_ties);
            assert_eq!(
                config.subsample_size.unwrap_or(usize::MAX),
                upstream.subsample_size
            );
            assert_eq!(config.subsample_bucket, upstream.subsample_bucket);
        }
    }

    #[test]
    fn state_engine_keeps_global_indices_for_ignored_contests() {
        let mut state = RaterState::new(
            SystemSpec::from_name("mmr".to_owned()).unwrap(),
            1500.0,
            350.0,
        )
        .unwrap();
        let ignored = Contest {
            name: String::new(),
            url: None,
            rating_params: ContestRatingParams::default(),
            time_seconds: 1,
            standings: Vec::new(),
        };
        let decided = Contest {
            name: String::new(),
            url: None,
            rating_params: ContestRatingParams::default(),
            time_seconds: 2,
            standings: vec![("a".to_owned(), 0, 0), ("b".to_owned(), 1, 1)],
        };

        state.extend(&[ignored, decided]).unwrap();

        assert_eq!(state.contests_processed, 2);
        assert_eq!(
            state.players["a"].borrow().event_history[0].contest_index,
            1
        );
    }
}
