use pyo3::prelude::*;
use pyo3::wrap_pyfunction;
use serde::ser::{Serialize, Serializer, SerializeStruct};
use multi_skill::systems::get_rating_system_by_name;
use multi_skill::experiment_config::{Experiment, ExperimentResults};
use multi_skill::data_processing::{Dataset, Contest, ContestDataset, BoxedDataset};

struct ContestList(Vec<Contest>);

impl Dataset for ContestList {
    type Item = Contest;
    fn len(&self) -> usize { self.0.len() }
    fn get(&self, index: usize) -> Contest { self.0.get(index).unwrap().clone() }
}

struct RateResult(ExperimentResults);

impl Serialize for RateResult {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error> where S: Serializer {
        let result = &self.0;
        let mut state = serializer.serialize_struct("ExperimentResults", 3)?;
        state.serialize_field("secs_elapsed", &result.secs_elapsed)?;
        state.serialize_field("avg_perf", &result.avg_perf.metrics_wt_sum)?;
        state.serialize_field("players", &result.players)?;
        return state.end();
    }
}

#[pyfunction]
fn rate(system: String, contests_data: String) -> String {
    let contests: ContestList = ContestList(serde_json::from_str(&contests_data).unwrap());
    let boxed_dataset: BoxedDataset<Contest> = Box::new(contests);
    let dataset: ContestDataset = boxed_dataset.wrap();
    let system = get_rating_system_by_name(&*system).unwrap();
    let experiment = Experiment {
        mu_noob: 1500.,
        sig_noob: 350.,
        system,
        dataset,
    };
    let results: ExperimentResults = experiment.eval(experiment.dataset.len());
    let ret = RateResult(results);
    return serde_json::to_string(&ret).unwrap();
}

#[pymodule]
fn elo_mmr_py_bindings(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_wrapped(wrap_pyfunction!(rate))?;
    Ok(())
}
