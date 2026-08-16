from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from src.analysis.base import EvidencePacket
from src.llm.sections import SectionNarrative
from src.log import emit

_NUM = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?%?")


def _norm(token: str) -> str:
    cleaned = token.replace(",", "").replace("%", "").lstrip("+").lstrip("-")
    try:
        value = float(cleaned)
    except ValueError:
        return cleaned
    if value.is_integer():
        return str(int(value))
    return f"{value:g}"


@dataclass(frozen=True)
class GroundingReport:
    section_id: str
    status: Literal["pass", "fail"]
    ungrounded_numbers: list[str]
    undeclared_numbers: list[str]
    unknown_analysis_keys: list[str]
    numbers_checked: int


def _prose_numbers(narrative: SectionNarrative) -> list[str]:
    parts = [narrative.summary] + [claim.statement for claim in narrative.claims]
    numbers: list[str] = []
    for part in parts:
        numbers.extend(_norm(match) for match in _NUM.findall(part))
    return numbers


def check_grounding(narrative: SectionNarrative, packet: EvidencePacket) -> GroundingReport:
    allowed = {_norm(token) for token in packet.allowed_numbers()}
    prose = _prose_numbers(narrative)
    declared = {_norm(figure) for claim in narrative.claims for figure in claim.figures}
    keys = {analysis.key for analysis in packet.analyses}
    ungrounded = sorted({number for number in prose if number not in allowed})
    undeclared = sorted({number for number in prose if number not in declared})
    unknown_keys = sorted({claim.analysis_key for claim in narrative.claims if claim.analysis_key not in keys})
    status: Literal["pass", "fail"] = "fail" if ungrounded or unknown_keys else "pass"
    if status == "fail":
        emit(
            "grounding_warn",
            level="warning",
            section=packet.section_id,
            ungrounded=ungrounded,
            unknown_analysis_keys=unknown_keys,
        )
    return GroundingReport(
        section_id=packet.section_id,
        status=status,
        ungrounded_numbers=ungrounded,
        undeclared_numbers=undeclared,
        unknown_analysis_keys=unknown_keys,
        numbers_checked=len(prose),
    )
