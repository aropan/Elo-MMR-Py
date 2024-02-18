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
    """
    Rates players based on their performance in contests.

    Args:
        system (str): The name of the rating system to use (e.g., "mmr", "glicko"). Default is "mmr".
        contests (List[PyContest]): A list of contest objects, each representing a single contest.
        mu_noob (float): The initial mean rating for new players. Default is 1500.
        sig_noob (float): The initial rating deviation for new players. Default is 350.
        load_checkpoint (Optional[str]): The path to a file from which to load the rating system state.
                                         If None, the rating system starts without prior state.
        save_checkpoint (Optional[str]): The path to a file where the rating system state will be saved
                                         after processing all contests. If None, the state is not saved.

    Returns:
        Dict[str, Player]: A dictionary mapping player names to their ratings.
    """

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
