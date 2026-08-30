from collections import Counter

import pytest

from benchmarks.benchmark import (
    DEFAULT_REPEAT,
    BenchmarkCase,
    CheckpointMeasurement,
    counterbalanced_orders,
    verify_checkpoint_measurements,
)


def test_execution_order_is_fully_counterbalanced() -> None:
    cases: list[BenchmarkCase] = [
        ('mmr', 'rate'),
        ('mmr', 'rate_latest'),
        ('mmr', 'rater_add'),
        ('mmr', 'rater_extend'),
        ('mmr-fast', 'rate'),
        ('mmr-fast', 'rate_latest'),
        ('mmr-fast', 'rater_add'),
        ('mmr-fast', 'rater_extend'),
    ]

    orders = counterbalanced_orders(cases, repeat=DEFAULT_REPEAT)

    for pair_start in range(0, len(orders), 2):
        assert orders[pair_start + 1] == list(reversed(orders[pair_start]))
    for case in cases:
        positions = Counter(order.index(case) for order in orders)
        appearances_per_position = DEFAULT_REPEAT // len(cases)
        assert positions == Counter(
            {position: appearances_per_position for position in range(len(cases))}
        )


def checkpoint_measurement(*, size_mib: float, write_seconds: float) -> CheckpointMeasurement:
    return CheckpointMeasurement(
        participants=1000,
        contests=100,
        system='mmr',
        repeat=3,
        size_mib=size_mib,
        median_write_seconds=write_seconds,
        median_read_seconds=0.1,
        checksum=1,
    )


def test_checkpoint_verification_gates_large_write_throughput() -> None:
    verify_checkpoint_measurements([checkpoint_measurement(size_mib=10.0, write_seconds=0.5)])
    verify_checkpoint_measurements([checkpoint_measurement(size_mib=1.0, write_seconds=10.0)])

    with pytest.raises(RuntimeError, match='checkpoint write throughput'):
        verify_checkpoint_measurements([checkpoint_measurement(size_mib=10.0, write_seconds=0.51)])
