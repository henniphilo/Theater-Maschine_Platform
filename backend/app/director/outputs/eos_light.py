"""ETC EOS OSC helpers for Unter Tieren (Kanal-Übersicht)."""

from __future__ import annotations

import re

EOS_CHAN_FULL = "/eos/chan/{channel}/full"
EOS_KEY_OUT = "/eos/key/out"
EOS_CHAN_ADDRESS_RE = re.compile(r"^/eos/chan/(\d+)/full$")


def expand_channels(specs: list[str]) -> list[int]:
    """Expand channel specs like 11-19, 92+94, 6 into sorted unique channel numbers."""
    channels: list[int] = []
    for spec in specs:
        token = spec.strip()
        if not token:
            continue
        if re.fullmatch(r"\d+\s*-\s*\d+", token):
            start_s, end_s = re.split(r"\s*-\s*", token, maxsplit=1)
            start_n, end_n = int(start_s), int(end_s)
            if start_n > end_n:
                start_n, end_n = end_n, start_n
            channels.extend(range(start_n, end_n + 1))
            continue
        for part in re.split(r"\s*\+\s*", token):
            part = part.strip()
            if part:
                channels.append(int(part))
    return sorted(set(channels))


def eos_chan_full(channel: int) -> tuple[str, list[str]]:
    return EOS_CHAN_FULL.format(channel=channel), []


def eos_key_out() -> tuple[str, list[str]]:
    return EOS_KEY_OUT, []


def parse_eos_chan_address(address: str) -> int | None:
    match = EOS_CHAN_ADDRESS_RE.match(address)
    if not match:
        return None
    return int(match.group(1))
