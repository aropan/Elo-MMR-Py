from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from elo_mmr_py import SUPPORTED_SYSTEMS


def test_rating_system_guide_covers_every_runtime_name() -> None:
    guide = (Path(__file__).parents[1] / 'docs' / 'rating-systems.md').read_text(encoding='utf-8')

    for system in SUPPORTED_SYSTEMS:
        assert f'`{system}`' in guide


def test_documented_example_runs() -> None:
    root = Path(__file__).parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / 'examples' / 'leaderboard.py')],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.splitlines() == [
        '1. Ada: 1705 ±171 (1 contests)',
        '2. Grace: 1500 ±171 (1 contests)',
        '3. Linus: 1295 ±171 (1 contests)',
    ]


def test_incremental_service_example_runs() -> None:
    root = Path(__file__).parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / 'examples' / 'incremental_service.py')],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.splitlines() == [
        'Ada 1634 1634.33 1700003600',
        'Grace 1589 1589.38 1700003600',
        'Linus 1270 1269.8 1700003600',
    ]


def test_benchmark_creates_output_parent_directory(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    output = tmp_path / 'nested' / 'benchmark.json'

    subprocess.run(
        [
            sys.executable,
            str(root / 'benchmarks' / 'benchmark.py'),
            '--participants',
            '2',
            '--contests',
            '1',
            '--repeat',
            '1',
            '--checkpoint-repeat',
            '1',
            '--systems',
            'mmr',
            '--apis',
            'rate',
            '--output',
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(output.read_text(encoding='utf-8'))
    assert len(payload['ratings']) == 1
    assert payload['ratings'][0]['participants'] == 2
    assert len(payload['checkpoints']) == 1
    assert payload['checkpoints'][0]['participants'] == 2
