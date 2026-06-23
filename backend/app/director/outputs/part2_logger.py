import logging
from pathlib import Path

_logger = logging.getLogger("theatermaschine.part2")


class Part2Logger:
    def __init__(self, log_path: Path | None = None) -> None:
        self.log_path = log_path or Path("logs/part2_anarchy.log")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: str, **fields: object) -> None:
        parts = [f"event={event}"]
        for key, value in fields.items():
            parts.append(f"{key}={value}")
        line = " ".join(parts)
        _logger.info(line)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


_part2_logger: Part2Logger | None = None


def get_part2_logger() -> Part2Logger:
    global _part2_logger
    if _part2_logger is None:
        _part2_logger = Part2Logger()
    return _part2_logger
