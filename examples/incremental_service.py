"""Incrementally update and restore a leaderboard."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from elo_mmr_py import Contest, Rater


def main() -> None:
    rater = Rater()
    rater.add(
        Contest(
            [('Ada', 0, 0), ('Grace', 1, 1), ('Linus', 2, 2)],
            name='Opening round',
            time_seconds=1_700_000_000,
        )
    )
    rater.extend(
        [
            Contest(
                [('Grace', 0, 0), ('Ada', 1, 1), ('Linus', 2, 2)],
                name='Final round',
                time_seconds=1_700_003_600,
            )
        ]
    )

    with TemporaryDirectory(prefix='elo-mmr-example-') as directory:
        checkpoint = Path(directory) / 'ratings.json'
        rater.save(checkpoint)
        restored = Rater.load(checkpoint)

    for player in sorted(restored.ratings.values(), key=lambda item: -item.rating):
        print(player.name, player.rating, round(player.mu, 2), player.update_time_seconds)


if __name__ == '__main__':
    main()
