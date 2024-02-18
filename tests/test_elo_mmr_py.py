#!/usr/bin/env python3

import tempfile

from elo_mmr_py import Contest, rate


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
