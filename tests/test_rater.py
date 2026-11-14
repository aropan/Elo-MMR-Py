from __future__ import annotations

import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, cast

import pytest

from elo_mmr_py import (
    SUPPORTED_SYSTEMS,
    Contest,
    EloMmrConfig,
    Rater,
    RatingSystemName,
    rate,
    rate_latest,
)


def test_rater_add_and_extend_match_stateless_apis(example_contests: list[Contest]) -> None:
    incremental = Rater()
    for contest in example_contests[:2]:
        assert incremental.add(contest) is None
    assert incremental.extend(example_contests[2:]) is None

    expected = rate_latest(example_contests)
    assert incremental.ratings == expected
    assert incremental.system == 'mmr'
    assert incremental.system_config == EloMmrConfig()
    assert incremental.mu_noob == 1500.0
    assert incremental.sig_noob == 350.0
    assert incremental.contests_processed == len(example_contests)
    assert incremental.last_time_seconds == example_contests[-1].time_seconds


def test_rater_custom_config_matches_stateless(example_contests: list[Contest]) -> None:
    config = EloMmrConfig('mmx-fast', weight_limit=0.3, subsample_size=2)
    incremental = Rater(config, mu_noob=1600.0, sig_noob=300.0)

    incremental.extend(example_contests)

    assert incremental.ratings == rate_latest(
        example_contests,
        system=config,
        mu_noob=1600.0,
        sig_noob=300.0,
    )
    assert incremental.system == 'mmx-fast'
    assert incremental.system_config == config


def test_rater_checkpoint_interoperates_with_stateless_api(
    tmp_path: Path, example_contests: list[Contest]
) -> None:
    first_checkpoint = tmp_path / 'rater.json'
    second_checkpoint = tmp_path / 'stateless.json'
    incremental = Rater()
    incremental.extend(example_contests[:3])
    incremental.save(first_checkpoint)

    continued = rate(
        example_contests[3:],
        load_checkpoint=first_checkpoint,
        save_checkpoint=second_checkpoint,
    )
    restored = Rater.load(second_checkpoint)

    assert restored.ratings == rate_latest(example_contests)
    assert {name: rating.rating for name, rating in restored.ratings.items()} == {
        name: player.rating for name, player in continued.items()
    }


def test_invalid_rater_batch_does_not_mutate_state() -> None:
    rater = Rater()
    first = Contest([('alice', 0, 0), ('bob', 1, 1)], time_seconds=10)
    rater.add(first)
    before = rater.ratings

    with pytest.raises(ValueError, match='before the previous timestamp'):
        rater.extend(
            [
                Contest([('alice', 0, 0), ('bob', 1, 1)], time_seconds=20),
                Contest([('bob', 0, 0), ('alice', 1, 1)], time_seconds=15),
            ]
        )

    assert rater.ratings == before
    assert rater.contests_processed == 1
    assert rater.last_time_seconds == 10


def test_unexpected_panic_poisons_rater() -> None:
    rater = Rater('trueskill', sig_noob=1e308)
    contest = Contest([('alice', 0, 0), ('bob', 1, 1)], time_seconds=1)

    with pytest.raises(RuntimeError, match='poisoned this Rater'):
        rater.add(contest)
    with pytest.raises(RuntimeError, match='unavailable'):
        _ = rater.ratings


def test_read_snapshot_is_safe_while_an_update_runs(
    contest_factory: Callable[[int, int], list[Contest]],
) -> None:
    contests = contest_factory(100, 20)
    rater = Rater('mmr-fast')

    with ThreadPoolExecutor(max_workers=2) as executor:
        update = executor.submit(rater.extend, contests)
        snapshot = executor.submit(lambda: rater.ratings)
        update.result(timeout=30)
        observed = snapshot.result(timeout=30)

    assert observed in ({}, rater.ratings)
    assert rater.ratings == rate_latest(contests, system='mmr-fast')


def test_non_elo_rater_has_no_system_config() -> None:
    rater = Rater('glicko')

    assert rater.system_config is None
    assert rater.ratings == {}


@pytest.mark.parametrize('system', SUPPORTED_SYSTEMS)
@pytest.mark.parametrize(
    'names',
    [[], ['missing'], ['player_1'], ['player_1', 'player_3', 'player_1', 'missing'], ('player_2',)],
)
def test_selected_ratings_match_full_snapshot(
    names: list[str] | tuple[str, ...],
    system: RatingSystemName,
    example_contests: list[Contest],
    tmp_path: Path,
) -> None:
    rater = Rater(system)
    assert rater.ratings_for(names) == {}
    rater.extend(example_contests)
    before = rater.ratings
    checkpoint = tmp_path / 'before.json'
    rater.save(checkpoint)
    expected = {name: before[name] for name in names if name in before}

    assert rater.ratings_for(names) == expected
    restored = Rater.load(checkpoint)
    assert restored.ratings_for(names) == expected
    rater.save(tmp_path / 'after.json')
    assert (tmp_path / 'after.json').read_bytes() == checkpoint.read_bytes()
    assert rater.ratings == before


@pytest.mark.parametrize('names', ['alice', b'alice', [1], [None], None])
def test_selected_ratings_reject_invalid_names(names: object) -> None:
    with pytest.raises(TypeError):
        Rater().ratings_for(cast(Any, names))


def test_selected_snapshot_is_detached_from_later_updates(example_contests: list[Contest]) -> None:
    rater = Rater()
    rater.add(example_contests[0])
    snapshot = rater.ratings_for(['player_1'])
    rater.add(example_contests[1])

    assert snapshot['player_1'].contests_played == 1
    assert rater.ratings_for(['player_1'])['player_1'].contests_played == 2


def test_selected_snapshot_serializes_with_updates(
    contest_factory: Callable[[int, int], list[Contest]],
) -> None:
    contests = contest_factory(100, 20)
    rater = Rater('mmr-fast')
    names = ['player-0000', 'player-0099']
    with ThreadPoolExecutor(max_workers=2) as executor:
        update = executor.submit(rater.extend, contests)
        snapshot = executor.submit(rater.ratings_for, names)
        update.result(timeout=30)
        observed = snapshot.result(timeout=30)
    expected = {name: value for name, value in rater.ratings.items() if name in names}
    assert observed in ({}, expected)


def test_selected_snapshot_rejects_poisoned_rater() -> None:
    rater = Rater('trueskill', sig_noob=1e308)
    with pytest.raises(RuntimeError, match='poisoned this Rater'):
        rater.add(Contest([('alice', 0, 0), ('bob', 1, 1)], time_seconds=1))
    with pytest.raises(RuntimeError, match='unavailable'):
        rater.ratings_for(['alice'])


def test_buffered_restore_retains_exact_state_and_continuation(tmp_path: Path) -> None:
    contests = [
        Contest([('участник-α', 0, 0), ('participant-β', 1, 1)], time_seconds=10),
        Contest([('participant-β', 0, 0), ('участник-α', 1, 1)], time_seconds=20),
    ]
    direct = Rater()
    direct.add(contests[0])
    checkpoint = tmp_path / 'buffered.json'
    direct.save(checkpoint)
    original = json.loads(checkpoint.read_bytes())
    checkpoint.write_bytes(b' ' * (128 * 1024 + 17) + checkpoint.read_bytes())
    restored = Rater.load(checkpoint)
    restored.save(tmp_path / 'restored.json')
    assert json.loads((tmp_path / 'restored.json').read_bytes()) == original
    direct.add(contests[1])
    restored.add(contests[1])
    assert restored.ratings == direct.ratings
    direct.save(tmp_path / 'direct-final.json')
    restored.save(tmp_path / 'restored-final.json')
    assert json.loads((tmp_path / 'direct-final.json').read_bytes()) == json.loads(
        (tmp_path / 'restored-final.json').read_bytes()
    )
