from collections.abc import Sequence
from typing import Final, Literal, Never, Self, final

CHECKPOINT_FORMAT_VERSION: Final[int]
SUPPORTED_SYSTEMS: Final[tuple[str, ...]]
__version__: Final[str]
__all__ = [
    'Contest',
    'EloMmrConfig',
    'PlayerEvent',
    'PlayerRating',
    'RateResult',
    'rate',
    'rate_latest',
    'CHECKPOINT_FORMAT_VERSION',
    'SUPPORTED_SYSTEMS',
    '__version__',
]

@final
class Contest:
    def __new__(
        cls,
        standings: Sequence[tuple[str, int, int]],
        name: str | None = ...,
        time_seconds: int | None = ...,
        url: str | None = ...,
        *,
        weight: float = ...,
        perf_ceiling: float | None = ...,
    ) -> Contest: ...
    @property
    def name(self) -> str: ...
    @property
    def time_seconds(self) -> int: ...
    @property
    def standings(self) -> list[tuple[str, int, int]]: ...
    @property
    def url(self) -> str | None: ...
    @property
    def weight(self) -> float: ...
    @property
    def perf_ceiling(self) -> float | None: ...

@final
class EloMmrConfig:
    def __new__(
        cls,
        system: Literal['mmr', 'mmr-fast', 'mmx', 'mmx-fast'] = ...,
        *,
        weight_limit: float = ...,
        noob_delay: Sequence[float] | None = ...,
        sig_limit: float = ...,
        drift_per_day: float = ...,
        split_ties: bool = ...,
        subsample_size: int | None = ...,
        subsample_bucket: float | None = ...,
    ) -> EloMmrConfig: ...
    @property
    def system(self) -> Literal['mmr', 'mmr-fast', 'mmx', 'mmx-fast']: ...
    @property
    def weight_limit(self) -> float: ...
    @property
    def noob_delay(self) -> list[float]: ...
    @property
    def sig_limit(self) -> float: ...
    @property
    def drift_per_day(self) -> float: ...
    @property
    def split_ties(self) -> bool: ...
    @property
    def subsample_size(self) -> int | None: ...
    @property
    def subsample_bucket(self) -> float: ...

@final
class PlayerEvent:
    def __new__(cls, _private: Never, /) -> Self: ...
    @property
    def contest_index(self) -> int: ...
    @property
    def rating_mu(self) -> int: ...
    @property
    def rating_sig(self) -> int: ...
    @property
    def perf_score(self) -> int: ...
    @property
    def place(self) -> int: ...

@final
class PlayerRating:
    def __new__(cls, _private: Never, /) -> Self: ...
    @property
    def name(self) -> str: ...
    @property
    def rating(self) -> int: ...
    @property
    def rating_sig(self) -> int: ...
    @property
    def contests_played(self) -> int: ...
    @property
    def mu(self) -> float: ...
    @property
    def sig(self) -> float: ...
    @property
    def update_time_seconds(self) -> int: ...

@final
class RateResult:
    def __new__(cls, _private: Never, /) -> Self: ...
    @property
    def players_events(self) -> dict[str, list[PlayerEvent]]: ...
    @property
    def secs_elapsed(self) -> float: ...

@final
class _Rater:
    def __new__(
        cls,
        system: str | EloMmrConfig,
        mu_noob: float = ...,
        sig_noob: float = ...,
    ) -> _Rater: ...
    @classmethod
    def load(cls, path: str) -> Self: ...
    def add(self, contest: Contest) -> None: ...
    def extend(self, contests: Sequence[Contest]) -> None: ...
    def save(self, path: str) -> None: ...
    @property
    def ratings(self) -> dict[str, PlayerRating]: ...
    @property
    def system(self) -> str: ...
    @property
    def system_config(self) -> EloMmrConfig | None: ...
    @property
    def mu_noob(self) -> float: ...
    @property
    def sig_noob(self) -> float: ...
    @property
    def contests_processed(self) -> int: ...
    @property
    def last_time_seconds(self) -> int | None: ...

def rate(
    system: str | EloMmrConfig,
    contests: Sequence[Contest],
    mu_noob: float = ...,
    sig_noob: float = ...,
    load_checkpoint: str | None = ...,
    save_checkpoint: str | None = ...,
) -> RateResult: ...
def rate_latest(
    system: str | EloMmrConfig,
    contests: Sequence[Contest],
    mu_noob: float = ...,
    sig_noob: float = ...,
    load_checkpoint: str | None = ...,
    save_checkpoint: str | None = ...,
) -> dict[str, PlayerRating]: ...
