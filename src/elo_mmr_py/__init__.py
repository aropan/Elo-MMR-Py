#!/usr/bin/env python3

from typing import List, Optional

from elo_mmr_py.elo_mmr_python_bindings import Contest, RateResult
from elo_mmr_py.elo_mmr_python_bindings import rate as rust_rate


def rate(
    contests: List[Contest],
    system: str = 'mmr',
    mu_noob: float = 1500.,
    sig_noob: float = 350.,
    load_checkpoint: Optional[str] = None,
    save_checkpoint: Optional[str] = None,
) -> RateResult:
    rate_result = rust_rate(
        system,
        contests,
        mu_noob=mu_noob,
        sig_noob=sig_noob,
        load_checkpoint=load_checkpoint,
        save_checkpoint=save_checkpoint,
    )
    return rate_result
