#!/usr/bin/env python3

import tempfile
import math

from elo_mmr_py import Contest, ContestRatingParams, rate


def test_create_contest_with_standings():
    standings = [('player_1', 0, 0), ('player_2', 1, 1), ('player_3', 2, 2)]
    contest = Contest(standings=standings)
    assert isinstance(contest, Contest)
    assert contest.standings == standings


def test_create_contest_with_name():
    name = 'contest_1'
    contest = Contest(name=name, standings=[])
    assert isinstance(contest, Contest)
    assert contest.name == name


def test_create_contest_with_time_seconds():
    time_seconds = 100500
    contest = Contest(time_seconds=time_seconds, standings=[])
    assert isinstance(contest, Contest)
    assert contest.time_seconds == time_seconds


def test_create_contest_with_url():
    url = 'https://example.com/'
    contest = Contest(url=url, standings=[])
    assert isinstance(contest, Contest)
    assert contest.url == url


def test_create_contest_with_rating_params():
    rating_params = ContestRatingParams(weight=0.5, perf_ceiling=2000.0)
    contest = Contest(standings=[], rating_params=rating_params)
    assert isinstance(contest, Contest)
    assert contest.rating_params.weight == 0.5
    assert contest.rating_params.perf_ceiling == 2000.0


def test_default_rating_params():
    contest = Contest(standings=[])
    assert contest.rating_params.weight == 1.0
    assert math.isinf(contest.rating_params.perf_ceiling)


def test_rate_contests():
    contests = [
        Contest(standings=[('player_1', 0, 0), ('player_2', 1, 1), ('player_3', 2, 2)]),
        Contest(standings=[('player_1', 0, 1), ('player_2', 0, 1), ('player_3', 2, 2)]),
        Contest(standings=[('player_1', 0, 0), ('player_2', 1, 2), ('player_3', 1, 2)]),
        Contest(standings=[('player_4', 0, 0), ('player_1', 1, 1), ('player_2', 2, 2), ('player_3', 3, 3)]),
        Contest(standings=[('player_4', 0, 0), ('player_1', 1, 1), ('player_2', 2, 2), ('player_3', 3, 3)]),
    ]
    players = rate(contests)

    assert isinstance(players, dict)
    assert len(players) == 4
    assert sum(len(player.events) for player in players.values()) == 17
    ratings = sorted(players.values(), key=lambda player: player.rating, reverse=True)
    ranking = [player.name for player in ratings]
    assert ranking == ['player_4', 'player_1', 'player_2', 'player_3']


def test_rate_contest_with_zero_weight():
    contests = [
        Contest(standings=[('player_1', 0, 0), ('player_2', 1, 1)]),
    ]
    players_before = rate(contests)
    
    # this contest should have no effect on ratings
    contests_zero_weight = [
        Contest(
            standings=[('player_1', 0, 0), ('player_3', 1, 1)],
            rating_params=ContestRatingParams(weight=0.0)
        ),
    ]
    players_after = rate(contests + contests_zero_weight)

    assert players_before['player_1'].rating == players_after['player_1'].rating
    assert 'player_3' not in players_after


def test_rating_change_proportional_to_weight():
    # Initial ratings are mu=1500, sig=350
    mu_noob = 1500.0

    # Test with weight=1.0
    contests_full_weight = [
        Contest(
            standings=[('player_1', 0, 0), ('player_2', 1, 1)],
            rating_params=ContestRatingParams(weight=1.0)
        ),
    ]
    players_full_weight = rate(contests_full_weight, mu_noob=mu_noob)
    rating_change_full_weight = players_full_weight['player_1'].rating - mu_noob

    # Test with weight=0.5
    contests_half_weight = [
        Contest(
            standings=[('player_1', 0, 0), ('player_2', 1, 1)],
            rating_params=ContestRatingParams(weight=0.5)
        ),
    ]
    players_half_weight = rate(contests_half_weight, mu_noob=mu_noob)
    rating_change_half_weight = players_half_weight['player_1'].rating - mu_noob
    
    # Test with weight=0.0
    contests_zero_weight = [
        Contest(
            standings=[('player_1', 0, 0), ('player_2', 1, 1)],
            rating_params=ContestRatingParams(weight=0.0)
        ),
    ]
    players_zero_weight = rate(contests_zero_weight, mu_noob=mu_noob)

    # A lower weight should result in a smaller rating change.
    assert rating_change_half_weight > 0
    assert rating_change_full_weight > rating_change_half_weight
    
    # A zero weight should result in no rating change, and no players returned
    assert 'player_1' not in players_zero_weight
    assert len(players_zero_weight) == 0


def test_save_and_load_checkpoints():
    contests = [
        Contest(standings=[('player_1', 0, 0), ('player_2', 1, 1), ('player_3', 2, 2)]),
        Contest(standings=[('player_1', 0, 1), ('player_2', 0, 1), ('player_3', 2, 2)]),
        Contest(standings=[('player_1', 0, 0), ('player_2', 1, 2), ('player_3', 1, 2)]),
        Contest(standings=[('player_4', 0, 0), ('player_1', 1, 1), ('player_2', 2, 2), ('player_3', 3, 3)]),
        Contest(standings=[('player_4', 0, 0), ('player_1', 1, 1), ('player_2', 2, 2), ('player_3', 3, 3)]),
    ]
    with tempfile.NamedTemporaryFile() as save_checkpoint:
        r1 = rate(contests, save_checkpoint=save_checkpoint.name)
        r2 = rate([], load_checkpoint=save_checkpoint.name)
        r3 = rate(contests, load_checkpoint=save_checkpoint.name)
        assert r1['player_4'].rating == r2['player_4'].rating
        assert r2['player_4'].rating != r3['player_4'].rating
