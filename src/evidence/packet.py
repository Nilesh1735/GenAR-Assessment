from __future__ import annotations

from src.analysis.base import AnalysisResult, EvidencePacket


def build_packet(
    section: dict,
    results: dict[str, AnalysisResult],
    product: str,
    reporting_period: str,
) -> EvidencePacket:
    analyses = [results[key] for key in section["required_analyses"]]
    notes: list[str] = []
    for analysis in analyses:
        for note in analysis.notes:
            if note not in notes:
                notes.append(note)
    return EvidencePacket(
        section_id=section["id"],
        section_title=section["title"],
        product=product,
        reporting_period=reporting_period,
        instructions=section.get("instructions", ""),
        analyses=analyses,
        notes=notes,
    )
