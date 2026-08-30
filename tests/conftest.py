from __future__ import annotations

from collections.abc import Callable

import pytest

from elo_mmr_py import Contest


@pytest.fixture
def example_contests() -> list[Contest]:
    return [
        Contest(
            [('player_1', 0, 0), ('player_2', 1, 1), ('player_3', 2, 2)],
            name='Round 1',
            time_seconds=10,
        ),
        Contest(
            [('player_1', 0, 1), ('player_2', 0, 1), ('player_3', 2, 2)],
            name='Round 2',
            time_seconds=20,
        ),
        Contest(
            [('player_1', 0, 0), ('player_2', 1, 2), ('player_3', 1, 2)],
            name='Round 3',
            time_seconds=30,
        ),
        Contest(
            [('player_4', 0, 0), ('player_1', 1, 1), ('player_2', 2, 2), ('player_3', 3, 3)],
            name='Round 4',
            time_seconds=40,
        ),
        Contest(
            [('player_4', 0, 0), ('player_1', 1, 1), ('player_2', 2, 2), ('player_3', 3, 3)],
            name='Round 5',
            time_seconds=50,
        ),
    ]


@pytest.fixture
def contest_factory() -> Callable[[int, int], list[Contest]]:
    def make_contests(player_count: int, contest_count: int) -> list[Contest]:
        names = [f'player-{index:04d}' for index in range(player_count)]
        contests: list[Contest] = []
        for contest_index in range(contest_count):
            shift = (contest_index * 37) % player_count
            ordered = names[shift:] + names[:shift]
            if contest_index % 2:
                ordered.reverse()
            contests.append(
                Contest(
                    [(name, place, place) for place, name in enumerate(ordered)],
                    name=f'Round {contest_index + 1}',
                    time_seconds=contest_index + 1,
                )
            )
        return contests

    return make_contests
