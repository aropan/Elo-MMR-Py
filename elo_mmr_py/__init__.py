#!/usr/bin/env python3

from typing import Dict, List, Tuple

from elo_mmr_py_bindings import rate as rust_rate
from pydantic import BaseModel


class Contest(BaseModel):
    name: str
    time_seconds: int
    standings: List[Tuple[str, int, int]]
    weight: float = 1.0


class Dataset(BaseModel):
    __root__: List[Contest]


class Rating(BaseModel):
    mu: float
    sig: float


class TanhTerm(BaseModel):
    mu: float
    w_arg: float
    w_out: float


class PlayerEvent(BaseModel):
    contest_index: int
    rating_mu: int
    rating_sig: int
    perf_score: int
    place: int


class Player(BaseModel):
    normal_factor: Rating
    logistic_factors: List[TanhTerm]
    event_history: List[PlayerEvent]
    approx_posterior: Rating
    update_time: float
    delta_time: float


class RateResult(BaseModel):
    players: Dict[str, Player]
    avg_perf: List[Tuple[float, float]]
    secs_elapsed: float


def rate(contests: List[Contest], system: str = 'mmr') -> RateResult:
    contests = Dataset.parse_obj(contests)
    rate_result_raw = rust_rate(system, contests.json())
    rate_result = RateResult.parse_raw(rate_result_raw)
    return rate_result
