"""Both compose files define the scheduled ``fetcher`` service the same way as ``jobs``."""

from pathlib import Path
from typing import Any

import pytest
import yaml

# tests/ -> backend/jobs/ -> backend/ -> repository root (absent when only backend/jobs is mounted).
_PARENTS = Path(__file__).resolve().parents
REPO_ROOT = _PARENTS[3] if len(_PARENTS) > 3 else None
COMPOSE_FILES = ("docker-compose.yml", "dev-docker-compose.yml")


def _services(file_name: str) -> dict[str, Any]:
    path = REPO_ROOT / file_name if REPO_ROOT else None
    if path is None or not path.is_file():
        pytest.skip(f"{file_name} is not available (only backend/jobs is mounted)")
    return yaml.safe_load(path.read_text(encoding="utf-8"))["services"]


@pytest.mark.parametrize("file_name", COMPOSE_FILES)
def test_fetcher_service_runs_the_jobs_image_on_a_schedule_after_jobs_is_healthy(
    file_name: str,
) -> None:
    services = _services(file_name)
    jobs, fetcher = services["jobs"], services["fetcher"]

    assert fetcher["build"] == jobs["build"] == "./backend/jobs"
    assert fetcher["env_file"] == jobs["env_file"] == ".env"
    assert fetcher["volumes"] == jobs["volumes"]
    assert fetcher["depends_on"] == {"jobs": {"condition": "service_healthy"}}
    assert fetcher["command"][0] == "supercronic"
    assert fetcher["command"][-1] == "/app/crontab"
    assert "ports" not in fetcher
