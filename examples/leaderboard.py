"""Build a small leaderboard with the lightweight API."""

from elo_mmr_py import Contest, rate_latest

contests = [
    Contest(
        standings=[('Ada', 0, 0), ('Grace', 1, 1), ('Linus', 2, 2)],
        name='Example final',
        time_seconds=1_700_000_000,
    )
]

leaderboard = sorted(rate_latest(contests).values(), key=lambda player: -player.rating)
for position, player in enumerate(leaderboard, start=1):
    contest_label = 'contest' if player.contests_played == 1 else 'contests'
    print(
        f'{position}. {player.name}: {player.rating} '
        f'±{player.rating_sig} ({player.contests_played} {contest_label})'
    )
