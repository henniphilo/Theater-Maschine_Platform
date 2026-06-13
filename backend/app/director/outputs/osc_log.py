import logging
import sys
from pathlib import Path

from app.core.config import settings

_osc_logger = logging.getLogger("theatermaschine.osc")
_configured = False


def _ensure_osc_logger() -> None:
    global _configured
    if _configured:
        return
    formatter = logging.Formatter("%(message)s")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    _osc_logger.addHandler(stream_handler)

    log_path = Path(settings.osc_log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    _osc_logger.addHandler(file_handler)

    _osc_logger.setLevel(logging.INFO)
    _osc_logger.propagate = False
    _configured = True


def log_osc_command(
    host: str,
    port: int,
    address: str,
    args: list[object] | tuple[object, ...] | None = None,
    *,
    dry_run: bool = False,
    bridge: str = "osc",
) -> None:
    if not settings.osc_log_commands:
        return
    _ensure_osc_logger()
    mode = "DRY-RUN" if dry_run else "SEND"
    args_list = list(args or [])
    args_text = " ".join(repr(arg) for arg in args_list)
    target = f"{host}:{port}"
    line = f"[OSC {mode}] [{bridge}] → {target} {address}"
    if args_text:
        line = f"{line} {args_text}"
    _osc_logger.info(line)
