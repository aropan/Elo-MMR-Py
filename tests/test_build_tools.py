from pathlib import Path

import pytest

from scripts.build_tool_versions import locked_pytest_version


def test_artifact_tests_use_the_locked_pytest_version(tmp_path: Path) -> None:
    lock = tmp_path / 'uv.lock'
    lock.write_text(
        '[[package]]\nname = "unrelated"\nversion = "1.0.0"\n'
        '[[package]]\nname = "pytest"\nversion = "9.2.0"\n',
        encoding='utf-8',
    )

    assert locked_pytest_version(lock) == '9.2.0'


@pytest.mark.parametrize('versions', [[], [None], [''], ['9.1.1', '9.2.0']])
def test_artifact_tests_reject_missing_or_ambiguous_pytest_pin(
    tmp_path: Path, versions: list[str | None]
) -> None:
    lock = tmp_path / 'uv.lock'
    contents = ''.join(
        '[[package]]\nname = "pytest"\n'
        + (f'version = "{version}"\n' if version is not None else '')
        for version in versions
    )
    lock.write_text(contents or 'package = []\n', encoding='utf-8')

    with pytest.raises(ValueError, match='exactly one pytest version'):
        locked_pytest_version(lock)
