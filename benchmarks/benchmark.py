"""Reproducible wall-time and Python peak-memory benchmark for Elo-MMR-Py."""

from __future__ import annotations

import argparse
import gc
import json
import statistics
import tempfile
import time
import tracemalloc
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

import elo_mmr_py
from elo_mmr_py import Contest, rate

if TYPE_CHECKING:
    from elo_mmr_py import Rater, rate_latest
else:
    Rater = getattr(elo_mmr_py, 'Rater', None)
    rate_latest = getattr(elo_mmr_py, 'rate_latest', None)

ApiName = Literal['rate', 'rate_latest', 'rater_add', 'rater_extend']
RatingSystem = Literal['mmr', 'mmr-fast']
BenchmarkCase = tuple[RatingSystem, ApiName]
DEFAULT_REPEAT = 32
MIN_CHECKPOINT_SIZE_MIB_FOR_THROUGHPUT_CHECK = 5.0
MIN_CHECKPOINT_WRITE_MIB_PER_SECOND = 20.0


@dataclass(frozen=True, slots=True)
class Measurement:
    participants: int
    contests: int
    system: RatingSystem
    api: ApiName
    repeat: int
    median_seconds: float
    min_seconds: float
    median_peak_mib: float
    checksum: int


@dataclass(frozen=True, slots=True)
class CheckpointMeasurement:
    participants: int
    contests: int
    system: RatingSystem
    repeat: int
    size_mib: float
    median_write_seconds: float
    median_read_seconds: float
    checksum: int


def make_contests(participants: int, contest_count: int) -> list[Contest]:
    """Create a deterministic history in which every player enters every contest."""

    names = [f'player-{index:04d}' for index in range(participants)]
    contests: list[Contest] = []
    for contest_index in range(contest_count):
        shift = (contest_index * 37) % participants
        ordered = names[shift:] + names[:shift]
        if contest_index % 2:
            ordered.reverse()
        contests.append(
            Contest(
                [(name, place, place) for place, name in enumerate(ordered)],
                time_seconds=contest_index + 1,
            )
        )
    return contests


def measure_once(
    contests: list[Contest],
    system: RatingSystem,
    api: ApiName,
) -> tuple[float, float, int]:
    gc.collect()
    tracemalloc.start()
    started = time.perf_counter()
    if api == 'rate':
        players = rate(contests, system=system)
        checksum = sum(player.rating + len(player.events) for player in players.values())
    elif api == 'rate_latest':
        if rate_latest is None:
            raise RuntimeError('this installed package has no rate_latest(); use --apis rate')
        latest = rate_latest(contests, system=system)
        checksum = sum(player.rating + player.contests_played for player in latest.values())
    else:
        if Rater is None:
            raise RuntimeError('this installed package has no Rater; choose an older API')
        rater = Rater(system)
        if api == 'rater_add':
            for contest in contests:
                rater.add(contest)
        else:
            rater.extend(contests)
        latest = rater.ratings
        checksum = sum(player.rating + player.contests_played for player in latest.values())
    elapsed = time.perf_counter() - started
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return elapsed, peak_bytes / (1024 * 1024), checksum


def counterbalanced_orders(
    combinations: Sequence[BenchmarkCase],
    repeat: int,
) -> list[list[BenchmarkCase]]:
    """Pair every rotation with its reverse to balance execution positions."""

    cases = list(combinations)
    if not cases:
        raise ValueError('at least one benchmark combination is required')

    orders: list[list[BenchmarkCase]] = []
    for repetition in range(repeat):
        rotation = (repetition // 2) % len(cases)
        order = cases[rotation:] + cases[:rotation]
        if repetition % 2:
            order.reverse()
        orders.append(order)
    return orders


def measure_matrix(
    participants: int,
    contest_count: int,
    systems: Sequence[RatingSystem],
    apis: Sequence[ApiName],
    repeat: int,
) -> list[Measurement]:
    contests = make_contests(participants, contest_count)
    combinations: list[BenchmarkCase] = [(system, api) for system in systems for api in apis]
    for system, api in combinations:
        measure_once(contests, system, api)

    samples: dict[tuple[RatingSystem, ApiName], list[tuple[float, float, int]]] = {
        combination: [] for combination in combinations
    }
    for order in counterbalanced_orders(combinations, repeat):
        for system, api in order:
            samples[(system, api)].append(measure_once(contests, system, api))

    measurements: list[Measurement] = []
    for system, api in combinations:
        combination_samples = samples[(system, api)]
        checksums = {sample[2] for sample in combination_samples}
        if len(checksums) != 1:
            raise RuntimeError('benchmark produced inconsistent results')
        measurements.append(
            Measurement(
                participants=participants,
                contests=contest_count,
                system=system,
                api=api,
                repeat=repeat,
                median_seconds=statistics.median(sample[0] for sample in combination_samples),
                min_seconds=min(sample[0] for sample in combination_samples),
                median_peak_mib=statistics.median(sample[1] for sample in combination_samples),
                checksum=checksums.pop(),
            )
        )
    return measurements


def print_table(measurements: Sequence[Measurement]) -> None:
    print('players  contests  system    api          median(s)  peak(MiB)')
    for item in measurements:
        print(
            f'{item.participants:7d}  {item.contests:8d}  {item.system:8s}  '
            f'{item.api:11s}  {item.median_seconds:9.4f}  {item.median_peak_mib:9.2f}'
        )


def measure_checkpoints(
    participants: int,
    contest_count: int,
    system: RatingSystem,
    repeat: int,
) -> CheckpointMeasurement:
    if Rater is None:
        raise RuntimeError('this installed package has no Rater; use --skip-checkpoints')
    contests = make_contests(participants, contest_count)
    rater = Rater(system)
    rater.extend(contests)
    write_samples: list[float] = []
    read_samples: list[float] = []
    checksums: set[int] = set()
    with tempfile.TemporaryDirectory(prefix='elo-mmr-benchmark-') as directory:
        checkpoint = Path(directory) / 'ratings.json'
        for _ in range(repeat):
            started = time.perf_counter()
            rater.save(checkpoint)
            write_samples.append(time.perf_counter() - started)

            started = time.perf_counter()
            restored = Rater.load(checkpoint)
            latest = restored.ratings
            read_samples.append(time.perf_counter() - started)
            checksums.add(sum(player.rating + player.contests_played for player in latest.values()))
        size_mib = checkpoint.stat().st_size / (1024 * 1024)
    if len(checksums) != 1:
        raise RuntimeError('checkpoint benchmark produced inconsistent results')
    return CheckpointMeasurement(
        participants=participants,
        contests=contest_count,
        system=system,
        repeat=repeat,
        size_mib=size_mib,
        median_write_seconds=statistics.median(write_samples),
        median_read_seconds=statistics.median(read_samples),
        checksum=checksums.pop(),
    )


def print_checkpoint_table(measurements: Sequence[CheckpointMeasurement]) -> None:
    print('\nplayers  contests  system    size(MiB)  write(s)  read(s)')
    for item in measurements:
        print(
            f'{item.participants:7d}  {item.contests:8d}  {item.system:8s}  '
            f'{item.size_mib:9.2f}  {item.median_write_seconds:8.4f}  '
            f'{item.median_read_seconds:7.4f}'
        )


def verify_measurements(measurements: Sequence[Measurement]) -> None:
    grouped: dict[tuple[int, int, RatingSystem], dict[ApiName, Measurement]] = {}
    for item in measurements:
        grouped.setdefault((item.participants, item.contests, item.system), {})[item.api] = item
    for key, by_api in grouped.items():
        checksums = {item.checksum for item in by_api.values()}
        if len(checksums) != 1:
            raise RuntimeError(f'API checksums differ for {key}: {checksums}')
        if {'rate', 'rate_latest'} <= by_api.keys():
            if by_api['rate_latest'].median_peak_mib >= by_api['rate'].median_peak_mib:
                raise RuntimeError(f'rate_latest did not reduce Python peak memory for {key}')


def verify_checkpoint_measurements(measurements: Sequence[CheckpointMeasurement]) -> None:
    """Reject severe write-throughput regressions on sufficiently large files."""

    for item in measurements:
        if item.size_mib < MIN_CHECKPOINT_SIZE_MIB_FOR_THROUGHPUT_CHECK:
            continue
        throughput = item.size_mib / item.median_write_seconds
        if throughput < MIN_CHECKPOINT_WRITE_MIB_PER_SECOND:
            raise RuntimeError(
                f'checkpoint write throughput is {throughput:.2f} MiB/s for '
                f'{item.participants} players with {item.system}; expected at least '
                f'{MIN_CHECKPOINT_WRITE_MIB_PER_SECOND:.2f} MiB/s'
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--participants', nargs='+', type=int, default=[100, 500, 1000])
    parser.add_argument('--contests', type=int, default=100)
    parser.add_argument('--repeat', type=int, default=DEFAULT_REPEAT)
    parser.add_argument(
        '--systems', nargs='+', choices=['mmr', 'mmr-fast'], default=['mmr', 'mmr-fast']
    )
    parser.add_argument(
        '--apis',
        nargs='+',
        choices=['rate', 'rate_latest', 'rater_add', 'rater_extend'],
        default=['rate', 'rate_latest', 'rater_add', 'rater_extend'],
    )
    parser.add_argument('--checkpoint-repeat', type=int, default=5)
    parser.add_argument('--skip-checkpoints', action='store_true')
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--output', type=Path)
    arguments = parser.parse_args()

    participant_counts = cast(list[int], arguments.participants)
    contest_count = cast(int, arguments.contests)
    repeat = cast(int, arguments.repeat)
    systems = cast(list[RatingSystem], arguments.systems)
    apis = cast(list[ApiName], arguments.apis)
    output = cast(Path | None, arguments.output)
    checkpoint_repeat = cast(int, arguments.checkpoint_repeat)
    if (
        any(count <= 1 for count in participant_counts)
        or contest_count <= 0
        or repeat <= 0
        or checkpoint_repeat <= 0
    ):
        parser.error('participants must exceed one; contests and repeat must be positive')

    measurements = [
        measurement
        for participants in participant_counts
        for measurement in measure_matrix(participants, contest_count, systems, apis, repeat)
    ]
    print_table(measurements)
    if arguments.verify:
        verify_measurements(measurements)
    checkpoint_measurements = (
        []
        if arguments.skip_checkpoints
        else [
            measure_checkpoints(participants, contest_count, system, checkpoint_repeat)
            for participants in participant_counts
            for system in systems
        ]
    )
    if checkpoint_measurements:
        print_checkpoint_table(checkpoint_measurements)
        if arguments.verify:
            verify_checkpoint_measurements(checkpoint_measurements)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                {
                    'ratings': [asdict(item) for item in measurements],
                    'checkpoints': [asdict(item) for item in checkpoint_measurements],
                },
                indent=2,
            )
            + '\n',
            encoding='utf-8',
        )


if __name__ == '__main__':
    main()
