from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from elo_mmr_py import Contest, EloMmrConfig, Rater, rate, rate_latest


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
