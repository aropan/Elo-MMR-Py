from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any

import pytest

from elo_mmr_py import (
    CHECKPOINT_FORMAT_VERSION,
    Contest,
    EloMmrConfig,
    Rater,
    __version__,
    rate,
    rate_latest,
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding='utf-8'))
    assert isinstance(value, dict)
    return value


def two_contests() -> list[Contest]:
    return [
        Contest([('alice', 0, 0), ('bob', 1, 1)], time_seconds=10),
        Contest([('bob', 0, 0), ('alice', 1, 1)], time_seconds=20),
    ]


def test_v2_round_trip_and_global_contest_indices(tmp_path: Path) -> None:
    checkpoint = tmp_path / 'ratings.json'
    contests = two_contests()

    first = rate(contests[:1], save_checkpoint=checkpoint)
    second = rate(contests[1:], load_checkpoint=checkpoint, save_checkpoint=checkpoint)
    restored = rate([], load_checkpoint=checkpoint)
    latest = rate_latest([], load_checkpoint=checkpoint)
    payload = load_json(checkpoint)

    assert first['alice'].events[-1].contest_index == 0
    assert [event.contest_index for event in second['alice'].events] == [0, 1]
    assert restored == second
    assert latest['alice'].rating == second['alice'].rating
    assert payload.keys() == {
        'format_version',
        'package_version',
        'system',
        'system_config',
        'mu_noob',
        'sig_noob',
        'contests_processed',
        'last_time_seconds',
        'players',
    }
    assert payload['format_version'] == CHECKPOINT_FORMAT_VERSION
    assert payload['package_version'] == __version__
    assert payload['system'] == 'mmr'
    assert payload['system_config'] == {
        'weight_limit': 0.2,
        'noob_delay': [],
        'sig_limit': 80.0,
        'drift_per_day': 0.0,
        'split_ties': False,
        'subsample_size': None,
        'subsample_bucket': 1e-5,
    }
    assert payload['mu_noob'] == 1500.0
    assert payload['sig_noob'] == 350.0
    assert payload['contests_processed'] == 2
    assert payload['last_time_seconds'] == 20
    raw = checkpoint.read_bytes()
    assert raw.endswith(b'\n')
    assert raw.count(b'\n') == 1


def test_batched_checkpoint_run_matches_one_shot_history(
    tmp_path: Path,
    example_contests: list[Contest],
) -> None:
    checkpoint = tmp_path / 'ratings.json'

    rate(example_contests[:3], save_checkpoint=checkpoint)
    batched = rate(example_contests[3:], load_checkpoint=checkpoint)
    one_shot = rate(example_contests)

    assert batched == one_shot


def test_legacy_checkpoint_is_read_and_migrated(tmp_path: Path) -> None:
    checkpoint = tmp_path / 'legacy.json'
    contests = two_contests()
    fixture = Path(__file__).parent / 'fixtures' / 'legacy-v1.0.3.json'
    checkpoint.write_bytes(fixture.read_bytes())

    migrated = rate(contests[1:], load_checkpoint=checkpoint, save_checkpoint=checkpoint)
    payload = load_json(checkpoint)

    assert [event.contest_index for event in migrated['alice'].events] == [0, 1]
    assert payload['format_version'] == 2
    assert payload['contests_processed'] == 2
    assert payload['last_time_seconds'] == 20


def test_fixed_v2_fixture_loads_and_continues_like_one_shot(tmp_path: Path) -> None:
    checkpoint = tmp_path / 'v2.json'
    fixture = Path(__file__).parent / 'fixtures' / 'v2-2.0.0.json'
    checkpoint.write_bytes(fixture.read_bytes())
    initial = [
        Contest([('alice', 0, 0), ('bob', 1, 1), ('carol', 2, 2)], time_seconds=10),
        Contest([('bob', 0, 0), ('alice', 1, 1), ('carol', 2, 2)], time_seconds=20),
    ]
    next_contest = Contest([('carol', 0, 0), ('alice', 1, 1), ('bob', 2, 2)], time_seconds=30)

    continued = rate([next_contest], load_checkpoint=checkpoint)
    one_shot = rate([*initial, next_contest])

    assert continued == one_shot
    assert Rater.load(checkpoint).ratings == rate_latest(initial)


def test_moderately_large_compact_checkpoint_round_trip(tmp_path: Path) -> None:
    checkpoint = tmp_path / 'large.json'
    names = [f'player-{index:03d}' for index in range(100)]
    contests = [
        Contest(
            [(name, place, place) for place, name in enumerate(names[index:] + names[:index])],
            time_seconds=index + 1,
        )
        for index in range(20)
    ]

    expected = rate_latest(contests, save_checkpoint=checkpoint)
    restored = rate_latest([], load_checkpoint=checkpoint)

    assert restored == expected
    assert checkpoint.stat().st_size > 100_000
    assert checkpoint.read_bytes().count(b'\n') == 1


def test_checkpoint_json_preserves_posterior_float_bits(tmp_path: Path) -> None:
    checkpoint = tmp_path / 'precise.json'
    rate(two_contests()[:1], save_checkpoint=checkpoint)
    payload = load_json(checkpoint)
    # This 17-significant-digit value regresses the one-ULP loss that occurs
    # when serde_json parses it without Cargo's `float_roundtrip` feature.
    expected_mu = 1428.1976778509327
    payload['players']['alice']['approx_posterior']['mu'] = expected_mu
    checkpoint.write_text(json.dumps(payload), encoding='utf-8')

    stateless = rate_latest([], load_checkpoint=checkpoint)['alice']
    incremental = Rater.load(checkpoint).ratings['alice']

    assert float(stateless.mu).hex() == expected_mu.hex()
    assert float(incremental.mu).hex() == expected_mu.hex()


def test_player_rating_equality_includes_full_precision_state(tmp_path: Path) -> None:
    checkpoint = tmp_path / 'first.json'
    changed_checkpoint = tmp_path / 'changed.json'
    rate(two_contests()[:1], save_checkpoint=checkpoint)
    payload = load_json(checkpoint)
    original = Rater.load(checkpoint).ratings['alice']
    payload['players']['alice']['approx_posterior']['mu'] += 0.0001
    changed_checkpoint.write_text(json.dumps(payload), encoding='utf-8')
    changed = Rater.load(changed_checkpoint).ratings['alice']

    assert original.rating == changed.rating
    assert original.rating_sig == changed.rating_sig
    assert original.contests_played == changed.contests_played
    assert original != changed


def test_ignored_contests_still_advance_global_index(tmp_path: Path) -> None:
    checkpoint = tmp_path / 'ratings.json'
    rate([Contest([], time_seconds=10)], save_checkpoint=checkpoint)

    players = rate(
        [Contest([('alice', 0, 0), ('bob', 1, 1)], time_seconds=20)],
        load_checkpoint=checkpoint,
    )

    assert players['alice'].events[0].contest_index == 1


def test_checkpoint_rejects_system_and_parameter_mismatches(tmp_path: Path) -> None:
    checkpoint = tmp_path / 'ratings.json'
    rate(two_contests()[:1], save_checkpoint=checkpoint)

    with pytest.raises(ValueError, match='checkpoint uses system'):
        rate([], system='glicko', load_checkpoint=checkpoint)
    with pytest.raises(ValueError, match='newbie parameters'):
        rate([], mu_noob=1600.0, load_checkpoint=checkpoint)
    with pytest.raises(ValueError, match='newbie parameters'):
        rate([], sig_noob=300.0, load_checkpoint=checkpoint)

    with pytest.raises(ValueError, match='configuration'):
        rate(
            [],
            system=EloMmrConfig(weight_limit=0.3),
            load_checkpoint=checkpoint,
        )


def test_custom_system_config_round_trip(tmp_path: Path) -> None:
    checkpoint = tmp_path / 'custom.json'
    config = EloMmrConfig(
        'mmr-fast',
        weight_limit=0.3,
        noob_delay=[0.5],
        sig_limit=70.0,
        drift_per_day=2.0,
        split_ties=True,
        subsample_size=2,
        subsample_bucket=1.0,
    )

    expected = rate(two_contests(), system=config, save_checkpoint=checkpoint)
    restored = rate([], system=config, load_checkpoint=checkpoint)

    assert restored == expected
    assert load_json(checkpoint)['system_config']['weight_limit'] == 0.3


def test_rater_load_requires_canonical_v2(tmp_path: Path) -> None:
    legacy = tmp_path / 'legacy.json'
    fixture = Path(__file__).parent / 'fixtures' / 'legacy-v1.0.3.json'
    legacy.write_bytes(fixture.read_bytes())

    with pytest.raises(ValueError, match='v2 schema'):
        Rater.load(legacy)


def test_rater_load_rejects_unsupported_v2_version(tmp_path: Path) -> None:
    checkpoint = tmp_path / 'future.json'
    rate(two_contests()[:1], save_checkpoint=checkpoint)
    payload = load_json(checkpoint)
    payload['format_version'] = CHECKPOINT_FORMAT_VERSION + 1
    checkpoint.write_text(json.dumps(payload), encoding='utf-8')

    with pytest.raises(ValueError, match='unsupported checkpoint format version'):
        Rater.load(checkpoint)


def test_checkpoint_enforces_chronology_between_batches(tmp_path: Path) -> None:
    checkpoint = tmp_path / 'ratings.json'
    rate(two_contests()[:1], save_checkpoint=checkpoint)

    with pytest.raises(ValueError, match='before the previous timestamp'):
        rate(
            [Contest([('alice', 0, 0), ('bob', 1, 1)], time_seconds=9)],
            load_checkpoint=checkpoint,
        )


@pytest.mark.parametrize(
    'contents',
    [
        '{not-json',
        '[]',
        '{"format_version": 999}',
        '{"format_version": 2}',
    ],
)
def test_malformed_checkpoint_is_value_error(tmp_path: Path, contents: str) -> None:
    checkpoint = tmp_path / 'broken.json'
    checkpoint.write_text(contents, encoding='utf-8')

    with pytest.raises(ValueError):
        rate([], load_checkpoint=checkpoint)


def test_non_utf8_checkpoint_is_a_json_value_error(tmp_path: Path) -> None:
    checkpoint = tmp_path / 'broken.json'
    checkpoint.write_bytes(b'\xff\xfe')

    with pytest.raises(ValueError, match='as JSON'):
        rate([], load_checkpoint=checkpoint)


def test_v2_checkpoint_rejects_unknown_fields_and_invalid_metadata(tmp_path: Path) -> None:
    checkpoint = tmp_path / 'ratings.json'
    rate(two_contests()[:1], save_checkpoint=checkpoint)
    payload = load_json(checkpoint)
    payload['unexpected'] = True
    checkpoint.write_text(json.dumps(payload), encoding='utf-8')

    with pytest.raises(ValueError, match='v2 schema'):
        rate([], load_checkpoint=checkpoint)

    del payload['unexpected']
    payload['contests_processed'] = 0
    payload['last_time_seconds'] = None
    checkpoint.write_text(json.dumps(payload), encoding='utf-8')
    with pytest.raises(ValueError, match='outside the declared'):
        rate([], load_checkpoint=checkpoint)


def test_v2_checkpoint_requires_system_config_only_for_elo_mmr(tmp_path: Path) -> None:
    checkpoint = tmp_path / 'ratings.json'
    rate(two_contests()[:1], save_checkpoint=checkpoint)
    elo_payload = load_json(checkpoint)
    config = elo_payload.pop('system_config')
    checkpoint.write_text(json.dumps(elo_payload), encoding='utf-8')

    with pytest.raises(ValueError, match='requires system_config'):
        rate([], load_checkpoint=checkpoint)

    rate(two_contests()[:1], system='glicko', save_checkpoint=checkpoint)
    non_elo_payload = load_json(checkpoint)
    non_elo_payload['system_config'] = config
    checkpoint.write_text(json.dumps(non_elo_payload), encoding='utf-8')

    with pytest.raises(ValueError, match='must not define system_config'):
        rate([], system='glicko', load_checkpoint=checkpoint)


@pytest.mark.parametrize(
    ('mutation', 'message'),
    [
        ('empty_history', 'has no rating events'),
        ('invalid_posterior', 'has an invalid posterior rating'),
        ('future_update', 'after last_time_seconds'),
    ],
)
def test_v2_checkpoint_rejects_invalid_player_state(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    checkpoint = tmp_path / 'ratings.json'
    rate(two_contests()[:1], save_checkpoint=checkpoint)
    payload = load_json(checkpoint)
    player = payload['players']['alice']
    if mutation == 'empty_history':
        player['event_history'] = []
    elif mutation == 'invalid_posterior':
        player['approx_posterior']['sig'] = 0.0
    else:
        player['update_time'] = payload['last_time_seconds'] + 1
    checkpoint.write_text(json.dumps(payload), encoding='utf-8')

    with pytest.raises(ValueError, match=message):
        rate([], load_checkpoint=checkpoint)


@pytest.mark.parametrize(
    ('contests_processed', 'last_time_seconds'),
    [(0, 10), (1, None)],
)
def test_v2_checkpoint_rejects_impossible_timeline_metadata(
    tmp_path: Path,
    contests_processed: int,
    last_time_seconds: int | None,
) -> None:
    checkpoint = tmp_path / 'ratings.json'
    rate([], save_checkpoint=checkpoint)
    payload = load_json(checkpoint)
    payload['contests_processed'] = contests_processed
    payload['last_time_seconds'] = last_time_seconds
    checkpoint.write_text(json.dumps(payload), encoding='utf-8')

    with pytest.raises(ValueError, match='last_time_seconds'):
        rate([], load_checkpoint=checkpoint)


def test_checkpoint_io_errors_are_os_errors(tmp_path: Path) -> None:
    with pytest.raises(OSError, match='failed to read checkpoint'):
        rate([], load_checkpoint=tmp_path / 'missing.json')

    with pytest.raises(OSError, match='temporary checkpoint'):
        rate([], save_checkpoint=tmp_path / 'missing' / 'ratings.json')


def test_failed_atomic_replace_does_not_damage_target_directory(tmp_path: Path) -> None:
    target = tmp_path / 'ratings.json'
    target.mkdir()
    marker = target / 'keep.txt'
    marker.write_text('unchanged', encoding='utf-8')

    with pytest.raises(OSError, match='atomically replace'):
        rate(two_contests(), save_checkpoint=target)

    assert marker.read_text(encoding='utf-8') == 'unchanged'


def test_atomic_save_replaces_existing_file_with_valid_json(tmp_path: Path) -> None:
    checkpoint = tmp_path / 'ratings.json'
    checkpoint.write_text('old contents', encoding='utf-8')

    rate(two_contests(), save_checkpoint=checkpoint)

    assert load_json(checkpoint)['format_version'] == 2


@pytest.mark.skipif(os.name != 'posix', reason='POSIX permission bits are Unix-specific')
def test_atomic_save_preserves_existing_file_mode_bits(tmp_path: Path) -> None:
    checkpoint = tmp_path / 'ratings.json'
    checkpoint.write_text('old contents', encoding='utf-8')
    checkpoint.chmod(0o644)

    rate(two_contests(), save_checkpoint=checkpoint)

    assert stat.S_IMODE(checkpoint.stat().st_mode) == 0o644


@pytest.mark.skipif(os.name != 'posix', reason='symbolic-link behavior is POSIX-specific')
def test_atomic_save_replaces_symlink_without_touching_its_target(tmp_path: Path) -> None:
    target = tmp_path / 'shared-ratings.json'
    target.write_text('leave this target unchanged', encoding='utf-8')
    checkpoint = tmp_path / 'ratings.json'
    checkpoint.symlink_to(target)

    rate(two_contests(), save_checkpoint=checkpoint)

    assert not checkpoint.is_symlink()
    assert load_json(checkpoint)['format_version'] == 2
    assert target.read_text(encoding='utf-8') == 'leave this target unchanged'
    assert stat.S_IMODE(checkpoint.stat().st_mode) == 0o600


@pytest.mark.skipif(os.name != 'posix', reason='POSIX permission bits are Unix-specific')
def test_new_checkpoint_is_owner_only_by_default(tmp_path: Path) -> None:
    checkpoint = tmp_path / 'ratings.json'

    rate(two_contests(), save_checkpoint=checkpoint)

    assert stat.S_IMODE(checkpoint.stat().st_mode) == 0o600
