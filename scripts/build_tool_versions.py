"""Expose canonical build-tool pins as GitHub Actions outputs."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import cast


def exact_maturin_version(pyproject_path: Path) -> str:
    pyproject = tomllib.loads(pyproject_path.read_text(encoding='utf-8'))
    requirements: object = pyproject['build-system']['requires']
    if not isinstance(requirements, list) or not all(
        isinstance(requirement, str) for requirement in requirements
    ):
        raise ValueError('build-system.requires must be a list of strings')
    string_requirements = cast(list[str], requirements)
    matches: list[str] = []
    for requirement in string_requirements:
        match = re.fullmatch(r'maturin==([^;\s]+)', requirement)
        if match is not None:
            matches.append(str(match.group(1)))
    if len(matches) != 1:
        raise ValueError('build-system.requires must contain one exact maturin pin')
    return matches[0]


def rust_toolchain_version(toolchain_path: Path) -> str:
    toolchain = tomllib.loads(toolchain_path.read_text(encoding='utf-8'))
    channel = toolchain['toolchain']['channel']
    if not isinstance(channel, str) or not channel:
        raise ValueError('rust-toolchain.toml must define a non-empty channel')
    return channel


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    print(f'maturin_version=v{exact_maturin_version(root / "pyproject.toml")}')
    print(f'rust_toolchain={rust_toolchain_version(root / "rust-toolchain.toml")}')


if __name__ == '__main__':
    main()
