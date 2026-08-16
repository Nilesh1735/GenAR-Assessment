from __future__ import annotations

import hashlib
from pathlib import Path

from src.analysis.base import EvidencePacket

PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"


def _read(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def system_prompt(product: str) -> str:
    return _read("system.md").format(product=product)


def section_prompt(packet: EvidencePacket) -> str:
    notes = "\n".join(f"- {note}" for note in packet.notes) if packet.notes else "None."
    return _read("section.md").format(
        section_title=packet.section_title,
        reporting_period=packet.reporting_period,
        product=packet.product,
        instructions=packet.instructions or "None.",
        packet=packet.render(),
        notes=notes,
    )


def prompts_hash() -> str:
    digest = hashlib.sha256()
    for name in sorted(("system.md", "section.md")):
        digest.update(_read(name).encode("utf-8"))
    return digest.hexdigest()[:16]
