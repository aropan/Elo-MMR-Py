#!/usr/bin/env python3

from dataclasses import dataclass
from typing import Dict, List, Optional

from elo_mmr_py.elo_mmr_python_bindings import Contest, PlayerEvent
from elo_mmr_py.elo_mmr_python_bindings import rate as rust_rate


@dataclass
class Player:
    name: str
    rating: int
    events: List[PlayerEvent]


def rate(
    contests: List[Contest],
    system: str = 'mmr',
    mu_noob: float = 1500.,
    sig_noob: float = 350.,
    load_checkpoint: Optional[str] = None,
    save_checkpoint: Optional[str] = None,
) -> Dict[str, Player]:
    rate_result = rust_rate(
        system,
        contests,
        mu_noob=mu_noob,
        sig_noob=sig_noob,
        load_checkpoint=load_checkpoint,
        save_checkpoint=save_checkpoint,
    )
    ret = {
        name: Player(name, events[-1].rating_mu, events)
        for name, events in rate_result.players_events.items()
    }
    return ret
