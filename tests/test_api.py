from __future__ import annotations

import math
import os
from importlib.resources import files
from pathlib import Path
from types import SimpleNamespace
from typing import Any, get_args

import pytest

import elo_mmr_py
import elo_mmr_py.elo_mmr_python_bindings as native_bindings
from elo_mmr_py import (
    SUPPORTED_SYSTEMS,
    Contest,
    EloMmrConfig,
    PlayerRating,
    RatingSystemName,
    rate,
    rate_latest,
)

GOLDEN_EVENTS = {
    'player_1': [
        (0, 1705, 171, 1744, 0),
        (1, 1663, 130, 1618, 0),
        (2, 1686, 111, 1728, 0),
        (3, 1678, 100, 1660, 1),
        (4, 1675, 94, 1666, 1),
    ],
    'player_2': [
        (0, 1500, 171, 1500, 1),
        (1, 1555, 130, 1618, 0),
        (2, 1500, 111, 1393, 1),
        (3, 1487, 100, 1459, 2),
        (4, 1483, 94, 1471, 2),
    ],
    'player_3': [
        (0, 1295, 171, 1256, 2),
        (1, 1270, 130, 1242, 2),
        (2, 1312, 111, 1393, 1),
        (3, 1291, 100, 1240, 3),
        (4, 1279, 94, 1247, 3),
    ],
    'player_4': [
        (3, 1767, 171, 1819, 0),
        (4, 1809, 130, 1855, 0),
    ],
}


def event_tuple(event: elo_mmr_py.PlayerEvent) -> tuple[int, int, int, int, int]:
    return (
        event.contest_index,
        event.rating_mu,
        event.rating_sig,
        event.perf_score,
        event.place,
    )


def test_public_metadata_is_explicit() -> None:
    assert elo_mmr_py.__version__ == native_bindings.__version__
    assert elo_mmr_py.CHECKPOINT_FORMAT_VERSION == 2
    assert elo_mmr_py.__all__ == [
        'CHECKPOINT_FORMAT_VERSION',
        'SUPPORTED_SYSTEMS',
        'Contest',
        'EloMmrConfig',
        'Player',
        'PlayerEvent',
        'PlayerRating',
        'Rater',
        'RatingSystem',
        'RatingSystemName',
        'Standing',
        '__version__',
        'rate',
        'rate_latest',
    ]
    assert SUPPORTED_SYSTEMS == get_args(RatingSystemName)
    assert files('elo_mmr_py').joinpath('py.typed').is_file()


def test_contest_fields_and_repr() -> None:
    standings = [('alice', 0, 0), ('bob', 1, 1)]
    contest = Contest(
        standings,
        name='Final',
        time_seconds=123,
        url='https://example.com/final',
        weight=0.5,
        perf_ceiling=1800.0,
    )

    assert contest.standings == standings
    assert contest.name == 'Final'
    assert contest.time_seconds == 123
    assert contest.url == 'https://example.com/final'
    assert contest.weight == 0.5
    assert contest.perf_ceiling == 1800.0
    assert repr(contest).startswith('Contest(name="Final"')
    assert 'url="https://example.com/final"' in repr(contest)


def test_default_mmr_matches_1_0_3_golden_history(example_contests: list[Contest]) -> None:
    players = rate(example_contests)

    assert {name: player.rating for name, player in players.items()} == {
        'player_1': 1675,
        'player_2': 1483,
        'player_3': 1279,
        'player_4': 1809,
    }
    assert {
        name: [event_tuple(event) for event in player.events] for name, player in players.items()
    } == GOLDEN_EVENTS


@pytest.mark.parametrize('system', SUPPORTED_SYSTEMS)
def test_supported_rating_system_smoke(system: str) -> None:
    players = rate(
        [Contest([('alice', 0, 0), ('bob', 1, 1), ('carol', 2, 2)], time_seconds=1)],
        system=system,  # type: ignore[arg-type, ty:invalid-argument-type]
    )

    assert set(players) == {'alice', 'bob', 'carol'}
    assert all(len(player.events) == 1 for player in players.values())


def test_latest_matches_full_history(example_contests: list[Contest]) -> None:
    full = rate(example_contests)
    latest = rate_latest(example_contests)

    assert set(latest) == set(full)
    for name, rating in latest.items():
        event = full[name].events[-1]
        assert rating.name == name
        assert rating.rating == full[name].rating == event.rating_mu
        assert rating.rating_sig == event.rating_sig
        assert rating.contests_played == len(full[name].events)
        assert rating.rating == round(rating.mu)
        assert rating.rating_sig == round(rating.sig)
        assert rating.update_time_seconds == example_contests[-1].time_seconds
        assert repr(rating).startswith('PlayerRating(')
        assert str(rating) == repr(rating)


def test_player_rating_is_immutable(example_contests: list[Contest]) -> None:
    rating = rate_latest(example_contests)['player_1']

    assert isinstance(rating, PlayerRating)
    with pytest.raises(AttributeError):
        rating.rating = 0  # type: ignore[misc, ty:invalid-assignment]


def test_native_types_cannot_be_subclassed() -> None:
    for native_type in (
        native_bindings.Contest,
        native_bindings.EloMmrConfig,
        native_bindings.PlayerEvent,
        native_bindings.PlayerRating,
        native_bindings.RateResult,
    ):
        with pytest.raises(TypeError):
            type(
                f'Derived{native_type.__name__}',
                (native_type,),  # type: ignore[ty:unsupported-dynamic-base]
                {},
            )


def test_native_output_types_have_no_public_constructor() -> None:
    for native_type in (
        native_bindings.PlayerEvent,
        native_bindings.PlayerRating,
        native_bindings.RateResult,
    ):
        with pytest.raises(TypeError):
            native_type()  # type: ignore[call-arg, ty:missing-argument]


def test_ties_and_outcome_free_contests() -> None:
    all_tied = Contest([('alice', 0, 1), ('bob', 0, 1)], time_seconds=1)
    empty = Contest([], time_seconds=2)
    decided = Contest([('alice', 0, 0), ('bob', 1, 1)], time_seconds=3)

    players = rate([all_tied, empty, decided])

    assert [event.contest_index for event in players['alice'].events] == [2]
    assert rate([all_tied, empty]) == {}
    assert rate_latest([all_tied, empty]) == {}


@pytest.mark.parametrize(
    'standings',
    [
        [('alice', 0, 0), ('alice', 1, 1)],
        [('alice', 0, 0), ('bob', 2, 2)],
        [('alice', 0, 2), ('bob', 0, 2)],
        [('alice', 0, 1), ('bob', 1, 1)],
        [('alice', 0, 0), ('bob', 1, 0)],
        [('alice', -1, 0)],
    ],
)
def test_malformed_standings_raise_value_error(
    standings: list[tuple[str, int, int]],
) -> None:
    with pytest.raises(ValueError):
        Contest(standings)


def test_negative_contest_time_raises_value_error() -> None:
    with pytest.raises(ValueError, match='time_seconds'):
        Contest([], time_seconds=-1)


@pytest.mark.parametrize(
    ('kwargs', 'message'),
    [
        ({'weight': 0.0}, 'weight'),
        ({'weight': math.inf}, 'weight'),
        ({'perf_ceiling': math.nan}, 'perf_ceiling'),
        ({'perf_ceiling': math.inf}, 'perf_ceiling'),
    ],
)
def test_invalid_contest_rating_parameters_raise_value_error(
    kwargs: dict[str, float], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        Contest([], **kwargs)  # type: ignore[arg-type, ty:invalid-argument-type]


def test_contest_rating_parameters_affect_mmr() -> None:
    standings = [('alice', 0, 0), ('bob', 1, 1), ('carol', 2, 2)]
    normal = rate_latest([Contest(standings, time_seconds=1)])
    weighted = rate_latest([Contest(standings, time_seconds=1, weight=0.2)])
    capped = rate([Contest(standings, time_seconds=1, perf_ceiling=1400.0)])

    assert weighted['alice'].mu != normal['alice'].mu
    assert capped['alice'].events[-1].perf_score <= 1400


@pytest.mark.parametrize('system', ('mmr', 'mmr-fast', 'mmx', 'mmx-fast'))
def test_default_elo_mmr_config_matches_string_mode(
    system: str, example_contests: list[Contest]
) -> None:
    configured = EloMmrConfig(system)  # type: ignore[arg-type, ty:invalid-argument-type]

    assert rate(example_contests, system=configured) == rate(
        example_contests,
        system=system,  # type: ignore[arg-type, ty:invalid-argument-type]
    )


def test_custom_elo_mmr_config_is_immutable_and_used(example_contests: list[Contest]) -> None:
    config = EloMmrConfig(
        weight_limit=0.3,
        noob_delay=[0.5, 0.75],
        sig_limit=70.0,
        drift_per_day=10.0,
        split_ties=True,
        subsample_size=2,
        subsample_bucket=1.5,
    )

    assert config.system == 'mmr'
    assert config.weight_limit == 0.3
    assert config.noob_delay == [0.5, 0.75]
    assert config.sig_limit == 70.0
    assert config.drift_per_day == 10.0
    assert config.split_ties is True
    assert config.subsample_size == 2
    assert config.subsample_bucket == 1.5
    assert rate_latest(example_contests, system=config) != rate_latest(example_contests)
    with pytest.raises(AttributeError):
        config.weight_limit = 1.0  # type: ignore[misc, ty:invalid-assignment]


def test_elo_mmr_subsampling_defaults_are_resolved() -> None:
    assert EloMmrConfig('mmr').subsample_size is None
    assert EloMmrConfig('mmr').subsample_bucket == 1e-5
    assert EloMmrConfig('mmr-fast').subsample_size == 100
    assert EloMmrConfig('mmr-fast').subsample_bucket == 2.0


@pytest.mark.parametrize(
    'kwargs',
    [
        {'weight_limit': 0.0},
        {'noob_delay': [0.0]},
        {'noob_delay': [1.1]},
        {'sig_limit': 0.0},
        {'drift_per_day': -1.0},
        {'subsample_size': 0},
        {'subsample_size': -1},
        {'subsample_bucket': 0.0},
    ],
)
def test_invalid_elo_mmr_config_raises_value_error(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        EloMmrConfig(**kwargs)


def test_elo_mmr_config_rejects_other_systems() -> None:
    with pytest.raises(ValueError, match='must be one of'):
        EloMmrConfig('glicko')  # type: ignore[arg-type, ty:invalid-argument-type]


def test_numeric_overflow_raises_value_error() -> None:
    huge_integer = 10**1000

    with pytest.raises(ValueError, match='supported numeric range'):
        Contest([('alice', huge_integer, huge_integer)])
    with pytest.raises(ValueError, match='supported numeric range'):
        Contest([('alice', 0, huge_integer)])
    with pytest.raises(ValueError, match='supported numeric range'):
        Contest([], time_seconds=huge_integer)
    with pytest.raises(ValueError, match='supported numeric range'):
        rate([], mu_noob=huge_integer)
    with pytest.raises(ValueError, match='supported numeric range'):
        rate_latest([], sig_noob=huge_integer)
    with pytest.raises(ValueError, match='supported numeric range'):
        Contest([], weight=huge_integer)
    with pytest.raises(ValueError, match='supported numeric range'):
        EloMmrConfig(weight_limit=huge_integer)
    with pytest.raises(ValueError, match='supported numeric range'):
        EloMmrConfig(subsample_size=huge_integer)


@pytest.mark.parametrize(
    ('mu_noob', 'sig_noob'),
    [
        (math.nan, 350.0),
        (math.inf, 350.0),
        (1500.0, math.nan),
        (1500.0, math.inf),
        (1500.0, 0.0),
        (1500.0, -1.0),
    ],
)
def test_invalid_initial_parameters_raise_value_error(mu_noob: float, sig_noob: float) -> None:
    with pytest.raises(ValueError):
        rate([], mu_noob=mu_noob, sig_noob=sig_noob)


def test_initial_parameters_reject_structurally_wrong_types() -> None:
    with pytest.raises(TypeError, match='real number'):
        rate([], mu_noob=None)  # type: ignore[arg-type, ty:invalid-argument-type]


def test_unknown_and_removed_systems_raise_value_error() -> None:
    for system in ('unknown', 'endure'):
        with pytest.raises(ValueError, match='unsupported rating system'):
            rate([], system=system)  # type: ignore[arg-type, ty:invalid-argument-type]


def test_rating_system_rejects_structurally_wrong_type() -> None:
    with pytest.raises(TypeError, match='system must be a supported string name or EloMmrConfig'):
        rate([], system=123)  # type: ignore[arg-type, ty:invalid-argument-type]


def test_invalid_options_are_rejected_before_checkpoint_io(tmp_path: Path) -> None:
    missing = tmp_path / 'missing.json'

    with pytest.raises(ValueError, match='unsupported rating system'):
        rate(
            [],
            system='unknown',  # type: ignore[arg-type, ty:invalid-argument-type]
            load_checkpoint=missing,
        )
    with pytest.raises(ValueError, match='sig_noob'):
        rate([], sig_noob=0.0, load_checkpoint=missing)


def test_unexpected_rust_panic_becomes_runtime_error() -> None:
    contest = Contest([('alice', 0, 0), ('bob', 1, 1)], time_seconds=1)

    with pytest.raises(RuntimeError, match='rating calculation failed inside Rust'):
        rate([contest], system='trueskill', sig_noob=1e308)


def test_non_chronological_contests_raise_value_error() -> None:
    contests = [
        Contest([('alice', 0, 0), ('bob', 1, 1)], time_seconds=2),
        Contest([('bob', 0, 0), ('alice', 1, 1)], time_seconds=1),
    ]

    with pytest.raises(ValueError, match='before the previous timestamp'):
        rate(contests)


def test_low_level_compatibility_alias(example_contests: list[Contest]) -> None:
    result = elo_mmr_py.rust_rate('mmr', example_contests)

    assert result.players_events['player_4'][-1].rating_mu == 1809
    assert result.secs_elapsed >= 0.0
    assert repr(result).startswith('RateResult(')
    assert repr(result.players_events['player_4'][-1]).startswith('PlayerEvent(')


def test_empty_native_event_history_is_an_internal_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_rust_rate(*args: object, **kwargs: object) -> object:
        return SimpleNamespace(players_events={'ghost': []})

    monkeypatch.setattr(elo_mmr_py, '_rust_rate', fake_rust_rate)

    with pytest.raises(RuntimeError, match="empty event history for participant 'ghost'"):
        rate([])


def test_path_normalization_rejects_bytes(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match='string path'):
        rate(
            [],
            save_checkpoint=os.fsencode(  # type: ignore[arg-type, ty:invalid-argument-type]
                tmp_path / 'checkpoint.json'
            ),
        )
