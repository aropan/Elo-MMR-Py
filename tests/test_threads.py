from __future__ import annotations

import threading
import time
from collections.abc import Callable

import pytest

from elo_mmr_py import Contest, Rater, rate_latest


def assert_work_releases_gil(work: Callable[[], object]) -> None:
    heartbeat: list[float] = []
    started = threading.Event()
    stop = threading.Event()

    def record_heartbeat() -> None:
        started.set()
        while not stop.is_set():
            heartbeat.append(time.perf_counter())
            time.sleep(0.001)

    thread = threading.Thread(target=record_heartbeat)
    thread.start()
    started.wait(timeout=1)
    start = time.perf_counter()
    work()
    end = time.perf_counter()
    stop.set()
    thread.join(timeout=1)

    assert not thread.is_alive()
    middle_start = start + (end - start) * 0.25
    middle_end = start + (end - start) * 0.75
    assert any(middle_start < tick < middle_end for tick in heartbeat)


@pytest.mark.performance
def test_rust_calculation_releases_the_gil(
    contest_factory: Callable[[int, int], list[Contest]],
) -> None:
    contests = contest_factory(700, 60)

    assert_work_releases_gil(lambda: rate_latest(contests))


@pytest.mark.performance
def test_incremental_rater_releases_the_gil(
    contest_factory: Callable[[int, int], list[Contest]],
) -> None:
    contests = contest_factory(700, 60)
    rater = Rater()

    assert_work_releases_gil(lambda: rater.extend(contests))
