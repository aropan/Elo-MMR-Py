#!/usr/bin/env python3

from elo_mmr_py import Contest, RateResult, rate


def test_create_contest():
    contest = Contest(
        name='contest_1', time_seconds=100500,
        standings=[('player_1', 0, 0), ('player_2', 1, 1), ('player_3', 2, 2)],
    )
    assert isinstance(contest, Contest)
    assert contest.name == 'contest_1'
    assert contest.time_seconds == 100500
    assert contest.standings == [('player_1', 0, 0), ('player_2', 1, 1), ('player_3', 2, 2)]


def test_rate_contests():
    contests = [
        Contest(
            name='contest_1', time_seconds=100500,
            standings=[('player_1', 0, 0), ('player_2', 1, 1), ('player_3', 2, 2)],
        ),
        Contest(
            name='contest_2', time_seconds=100500,
            standings=[('player_1', 0, 1), ('player_2', 0, 1), ('player_3', 2, 2)],
        ),
        Contest(
            name='contest_3', time_seconds=100500,
            standings=[('player_1', 0, 0), ('player_2', 1, 2), ('player_3', 1, 2)],
        ),
        Contest(
            name='contest_4', time_seconds=100500,
            standings=[('player_4', 0, 0), ('player_2', 1, 1), ('player_3', 2, 2)],
        ),
    ]
    rate_result = rate(contests)
    assert isinstance(rate_result, RateResult)
    assert len(rate_result.players_events) == 4
    assert sum(len(events) for events in rate_result.players_events.values()) == 12
