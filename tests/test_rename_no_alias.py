from __future__ import annotations

import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_fls_pilot_is_the_only_source_package() -> None:
    assert (ROOT / "src" / "fls_pilot").is_dir()
    assert not (ROOT / "src" / "fl_studio_mcp").exists()


def test_console_scripts_have_no_old_aliases() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = data["project"]["scripts"]

    assert data["project"]["name"] == "fls-pilot"
    assert scripts == {
        "fls-pilot": "fls_pilot.server:main",
        "fls-pilot-daemon": "fls_pilot.daemon:main",
    }
    assert "fl-studio-mcp" not in scripts
    assert "fl-studio-mcp-daemon" not in scripts
