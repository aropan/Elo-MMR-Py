"""Compile-time checks for constraints that runtime stubtest cannot express."""

from typing import TYPE_CHECKING

from elo_mmr_py.elo_mmr_python_bindings import PlayerEvent, PlayerRating, RateResult

if TYPE_CHECKING:
    # Strict ty rejects an ignore that becomes unnecessary, so these lines
    # protect the deliberately unavailable native constructors in the stub.
    PlayerEvent()  # type: ignore[call-arg, ty:missing-argument]
    PlayerRating()  # type: ignore[call-arg, ty:missing-argument]
    RateResult()  # type: ignore[call-arg, ty:missing-argument]
