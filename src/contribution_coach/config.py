from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CONFIG = """# GitHub Contribution Coach never writes to GitHub.
[coach]
period_days = 365
repositories = ["owner/project"]
automated_repositories = []
local_roots = ["~/Code", "~/.config/omarchy/plugins"]
"""


@dataclass(frozen=True)
class Config:
    period_days: int
    repositories: list[str]
    automated_repositories: list[str]
    local_roots: list[Path]


def default_path() -> Path:
    return Path.home() / ".config" / "contribution-coach" / "config.toml"


def load(path: Path | None = None) -> Config:
    config_path = path or default_path()
    if not config_path.exists():
        return Config(period_days=365, repositories=[], automated_repositories=[], local_roots=[])
    with config_path.open("rb") as config_file:
        values = tomllib.load(config_file).get("coach", {})
    return Config(
        period_days=max(1, min(365, int(values.get("period_days", 365)))),
        repositories=[str(repo) for repo in values.get("repositories", [])],
        automated_repositories=[str(repo) for repo in values.get("automated_repositories", [])],
        local_roots=[Path(root).expanduser() for root in values.get("local_roots", [])],
    )


def initialize(path: Path | None = None) -> Path:
    config_path = path or default_path()
    if config_path.exists():
        raise FileExistsError(config_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(DEFAULT_CONFIG)
    return config_path
