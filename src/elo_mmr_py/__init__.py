"""Fast Python bindings for Elo-MMR multiplayer rating systems."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from typing import Literal, Self, TypeAlias, cast, final, overload

from .elo_mmr_python_bindings import (
    CHECKPOINT_FORMAT_VERSION,
    SUPPORTED_SYSTEMS,
    Contest,
    EloMmrConfig,
    PlayerEvent,
    PlayerRating,
)
from .elo_mmr_python_bindings import __version__ as _native_version
from .elo_mmr_python_bindings import _Rater as _NativeRater
from .elo_mmr_python_bindings import rate as _rust_rate
from .elo_mmr_python_bindings import rate_latest as _rust_rate_latest

RatingSystemName: TypeAlias = Literal[
    'bar',
    'glicko',
    'cfsys',
    'tcsys',
    'trueskill',
    'mmx',
    'mmx-fast',
    'mmr',
    'mmr-fast',
    'mmr-simple',
]
RatingSystem: TypeAlias = RatingSystemName | EloMmrConfig
Standing: TypeAlias = tuple[str, int, int]
StrPath: TypeAlias = str | os.PathLike[str]

try:
    __version__ = version('Elo-MMR-Py')
except PackageNotFoundError:  # pragma: no cover - only possible from an uninstalled source tree
    __version__ = _native_version


@dataclass
class Player:
    """A participant's latest rounded rating and complete event history."""

    name: str
    rating: int
    events: list[PlayerEvent]


@overload
def _normalize_path(path: None, argument: str) -> None: ...


@overload
def _normalize_path(path: StrPath, argument: str) -> str: ...


def _normalize_path(path: StrPath | None, argument: str) -> str | None:
    if path is None:
        return None
    normalized = os.fspath(path)
    if isinstance(normalized, bytes):
        raise TypeError(f'{argument} must resolve to a string path, not bytes')
    return normalized


def rate(
    contests: Sequence[Contest],
    system: RatingSystem = 'mmr',
    mu_noob: float = 1500.0,
    sig_noob: float = 350.0,
    load_checkpoint: StrPath | None = None,
    save_checkpoint: StrPath | None = None,
) -> dict[str, Player]:
    """Rate participants and return their complete histories.

    Args:
        contests: Chronologically ordered competitions to process.
        system: Rating system name or an :class:`EloMmrConfig`. ``mmr`` is exact
            and remains the default; ``mmr-fast`` is an opt-in approximation.
        mu_noob: Initial mean rating for newly observed participants.
        sig_noob: Initial rating uncertainty for newly observed participants.
        load_checkpoint: Optional v2 or legacy v1 checkpoint to continue.
        save_checkpoint: Optional path atomically replaced with a v2 checkpoint.

    Returns:
        A mapping from participant names to latest ratings and all event objects.

    Raises:
        ValueError: If inputs or checkpoint contents are invalid.
        OSError: If a checkpoint cannot be read or written.
        RuntimeError: If the underlying Rust calculation fails unexpectedly.
    """

    result = _rust_rate(
        system,
        contests,
        mu_noob=mu_noob,
        sig_noob=sig_noob,
        load_checkpoint=_normalize_path(load_checkpoint, 'load_checkpoint'),
        save_checkpoint=_normalize_path(save_checkpoint, 'save_checkpoint'),
    )
    players: dict[str, Player] = {}
    for name, events in result.players_events.items():
        if not events:
            raise RuntimeError(f'Rust returned an empty event history for participant {name!r}')
        players[name] = Player(name=name, rating=events[-1].rating_mu, events=events)
    return players


def rate_latest(
    contests: Sequence[Contest],
    system: RatingSystem = 'mmr',
    mu_noob: float = 1500.0,
    sig_noob: float = 350.0,
    load_checkpoint: StrPath | None = None,
    save_checkpoint: StrPath | None = None,
) -> dict[str, PlayerRating]:
    """Rate participants without materializing their histories in Python.

    This is the preferred API for leaderboards and services that only need each
    participant's current rating, uncertainty, and number of rated contests.
    Checkpoint semantics and validation are identical to :func:`rate`.
    """

    return _rust_rate_latest(
        system,
        contests,
        mu_noob=mu_noob,
        sig_noob=sig_noob,
        load_checkpoint=_normalize_path(load_checkpoint, 'load_checkpoint'),
        save_checkpoint=_normalize_path(save_checkpoint, 'save_checkpoint'),
    )


@final
class Rater:
    """Incrementally maintain ratings without replaying previous contests."""

    __slots__ = ('_inner',)

    def __init__(
        self,
        system: RatingSystem = 'mmr',
        mu_noob: float = 1500.0,
        sig_noob: float = 350.0,
    ) -> None:
        self._inner = _NativeRater(system, mu_noob=mu_noob, sig_noob=sig_noob)

    @classmethod
    def load(cls, path: StrPath) -> Self:
        """Restore an incremental rater from a canonical v2 checkpoint."""

        instance = cls.__new__(cls)
        instance._inner = _NativeRater.load(_normalize_path(path, 'path'))
        return instance

    def add(self, contest: Contest) -> None:
        """Process one contest in place."""

        self._inner.add(contest)

    def extend(self, contests: Sequence[Contest]) -> None:
        """Validate and process a chronological batch in place."""

        self._inner.extend(contests)

    @property
    def ratings(self) -> dict[str, PlayerRating]:
        """Return a new latest-rating snapshot containing ``O(players)`` objects."""

        return self._inner.ratings

    def save(self, path: StrPath) -> None:
        """Atomically save the current state as a canonical v2 checkpoint."""

        self._inner.save(_normalize_path(path, 'path'))

    @property
    def system(self) -> RatingSystemName:
        return cast(RatingSystemName, self._inner.system)

    @property
    def system_config(self) -> EloMmrConfig | None:
        return self._inner.system_config

    @property
    def mu_noob(self) -> float:
        return self._inner.mu_noob

    @property
    def sig_noob(self) -> float:
        return self._inner.sig_noob

    @property
    def contests_processed(self) -> int:
        return self._inner.contests_processed

    @property
    def last_time_seconds(self) -> int | None:
        return self._inner.last_time_seconds


# Kept as a compatibility escape hatch for callers that used the previously
# undocumented low-level function.
rust_rate = _rust_rate

__all__ = [
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
