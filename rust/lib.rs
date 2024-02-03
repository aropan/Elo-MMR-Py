use std::collections::HashMap;
use pyo3::prelude::*;
use pyo3::wrap_pyfunction;
use multi_skill::systems::{PlayerEvent, get_rating_system_by_name};
use multi_skill::experiment_config::{Experiment, ExperimentResults};
use multi_skill::data_processing::{Dataset, Contest, ContestDataset, BoxedDataset, read_json, ContestRatingParams};

#[pyclass(name="Contest")]
#[derive(Clone)]
struct PyContest {
    inner: Contest,
}

#[pymethods]
impl PyContest {
    #[new]
    #[args(url="None")]
    fn new(
        name: String,
        time_seconds: u64,
        standings: Vec<(String, usize, usize)>,
        url: Option<String>,
    ) -> PyResult<Self> {
        let rating_params = ContestRatingParams::default();
        Ok(PyContest {
            inner: Contest {
                name,
                url,
                rating_params,
                time_seconds,
                standings,
            },
        })
    }

    #[getter]
    fn name(&self) -> PyResult<&str> {
        Ok(&self.inner.name)
    }

    #[getter]
    fn time_seconds(&self) -> PyResult<u64> {
        Ok(self.inner.time_seconds)
    }

    #[getter]
    fn standings(&self) -> PyResult<Vec<(String, usize, usize)>> {
        Ok(self.inner.standings.clone())
    }

    #[getter]
    fn url(&self) -> PyResult<Option<&str>> {
        Ok(self.inner.url.as_deref())
    }
}

struct ContestVec(Vec<Contest>);

impl Dataset for ContestVec {
    type Item = Contest;
    fn len(&self) -> usize { self.0.len() }
    fn get(&self, index: usize) -> Contest { self.0.get(index).unwrap().clone() }
}

#[pyclass(name="PlayerEvent")]
#[derive(Clone)]
struct PyPlayerEvent {
    #[pyo3(get)]
    contest_index: usize,
    #[pyo3(get)]
    rating_mu: i32,
    #[pyo3(get)]
    rating_sig: i32,
    #[pyo3(get)]
    perf_score: i32,
    #[pyo3(get)]
    place: usize,
}

#[pymethods]
impl PyPlayerEvent {
    fn __repr__(&self) -> PyResult<String> {
        Ok(format!(
            "PyPlayerEvent(contest_index={}, rating_mu={}, rating_sig={}, perf_score={}, place={})",
            self.contest_index, self.rating_mu, self.rating_sig, self.perf_score, self.place
        ))
    }

    fn __str__(&self) -> PyResult<String> {
        self.__repr__()
    }
}

impl From<PlayerEvent> for PyPlayerEvent {
    fn from(event: PlayerEvent) -> Self {
        PyPlayerEvent {
            contest_index: event.contest_index,
            rating_mu: event.rating_mu,
            rating_sig: event.rating_sig,
            perf_score: event.perf_score,
            place: event.place,
        }
    }
}

#[pyclass(name="RateResult")]
struct PyRateResult {
    #[pyo3(get)]
    players_events: HashMap<String, Vec<PyPlayerEvent>>,
    #[pyo3(get)]
    secs_elapsed: f64,
}

#[pymethods]
impl PyRateResult {
    fn __repr__(&self) -> PyResult<String> {
        let n_total_events: usize = self.players_events.values().map(|events| events.len()).sum();
        Ok(format!(
            "PyRateResult(n_players={}, n_total_events={}, secs_elapsed={})",
            self.players_events.len(), n_total_events, self.secs_elapsed
        ))
    }

    fn __str__(&self) -> PyResult<String> {
        self.__repr__()
    }
}

fn from_experiment_results(experiment_results: ExperimentResults) -> PyResult<PyRateResult> {
    let players_py: HashMap<String, Vec<PyPlayerEvent>> = experiment_results.players
        .into_iter()
        .map(|(name, player_cell)| {
            let player = player_cell.into_inner();
            let events_py: Vec<PyPlayerEvent> = player.event_history.into_iter().map(PyPlayerEvent::from).collect();
            (name, events_py)
        })
        .collect();

    Ok(PyRateResult {
        players_events: players_py,
        secs_elapsed: experiment_results.secs_elapsed,
    })
}

#[pyfunction]
fn rate(
    system: String,
    contests: Vec<PyContest>,
    mu_noob: f64,
    sig_noob: f64,
    load_checkpoint: Option<String>,
    save_checkpoint: Option<String>,
) -> PyRateResult {
    let contest_vec: Vec<Contest> = contests.into_iter().map(|contest| contest.inner).collect();
    let boxed_dataset: BoxedDataset<Contest> = Box::new(ContestVec(contest_vec));
    let dataset: ContestDataset = boxed_dataset.wrap();

    let system = get_rating_system_by_name(&*system).unwrap();

    let loaded_state = match load_checkpoint {
        Some(filename) => read_json(filename).expect("Failed to read checkpoint"),
        None => HashMap::new(),
    };

    let experiment = Experiment {mu_noob, sig_noob, system, dataset, loaded_state, save_checkpoint};
    let results: ExperimentResults = experiment.eval(experiment.dataset.len());
    let rate_results = from_experiment_results(results).unwrap();
    return rate_results;
}

#[pymodule]
fn elo_mmr_python_bindings(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<PyContest>()?;
    m.add_class::<PyPlayerEvent>()?;
    m.add_class::<PyRateResult>()?;
    m.add_wrapped(wrap_pyfunction!(rate))?;
    Ok(())
}
