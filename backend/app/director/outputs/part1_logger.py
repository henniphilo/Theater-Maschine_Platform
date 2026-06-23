import logging
from pathlib import Path

_logger = logging.getLogger("theatermaschine.part1")


class Part1Logger:
    def __init__(self, log_path: Path | None = None) -> None:
        self.log_path = log_path or Path("logs/part1_baerenklau.log")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: str, **fields: object) -> None:
        parts = [f"event={event}"]
        for key, value in fields.items():
            parts.append(f"{key}={value}")
        line = " ".join(parts)
        _logger.info(line)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


_part1_logger: Part1Logger | None = None


def get_part1_logger() -> Part1Logger:
    global _part1_logger
    if _part1_logger is None:
        _part1_logger = Part1Logger()
    return _part1_logger
