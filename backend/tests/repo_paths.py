from pathlib import Path


def repo_data_dir() -> Path:
    """Repo `data/` directory — works from backend/ (CI) and repo root."""
    tests_dir = Path(__file__).resolve().parent
    repo_data = tests_dir.parents[1] / "data"
    if repo_data.is_dir():
        return repo_data
    return tests_dir.parent / "data"
