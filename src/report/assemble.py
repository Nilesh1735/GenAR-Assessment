from __future__ import annotations

from src.analysis.base import AnalysisResult, num_token
from src.eval.grounding import GroundingReport
from src.llm.sections import SectionNarrative
from src.report.model import ReportResult


def _cell(value: object) -> str:
    token = num_token(value)
    return token if token is not None else str(value)


def _md_table(columns: list[str], rows: list[dict]) -> str:
    if not columns:
        return ""
    header = "| " + " | ".join(str(column) for column in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(_cell(row.get(column, "")) for column in columns) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def _kv_block(items: dict) -> str:
    return "\n".join(f"- **{name}**: {_cell(value)}" for name, value in items.items())


def _analysis_block(analysis: AnalysisResult) -> str:
    parts: list[str] = []
    if analysis.table:
        parts.append(f"**{analysis.title}**\n\n" + _md_table(analysis.columns, analysis.table))
    elif analysis.facts:
        parts.append(f"**{analysis.title}**\n\n" + _kv_block(analysis.facts))
    if analysis.notes:
        parts.append("\n".join(f"> {note}" for note in analysis.notes))
    return "\n\n".join(parts)


def _narrative_block(narrative: SectionNarrative) -> str:
    parts = [narrative.summary]
    if narrative.observations:
        parts.append("**Observations:**\n" + "\n".join(f"- {item}" for item in narrative.observations))
    if narrative.interpretation_flags:
        parts.append(
            "**Patterns for human review:**\n"
            + "\n".join(f"- {item}" for item in narrative.interpretation_flags)
        )
    if narrative.data_gaps:
        parts.append("**Data not available:**\n" + "\n".join(f"- {item}" for item in narrative.data_gaps))
    return "\n\n".join(parts)


def _grounding_note(grounding: GroundingReport | None) -> str:
    if grounding is None:
        return ""
    if grounding.status == "pass":
        return f"_Grounding check: {grounding.numbers_checked} figures verified against the evidence packet._"
    flagged = ", ".join(grounding.ungrounded_numbers) or "none"
    return f"_⚠ Grounding check failed: ungrounded figure(s) flagged: {flagged}._"


def render_markdown(report: ReportResult) -> str:
    lines = [
        f"# {report.title} — {report.product}",
        "",
        f"**Reporting period:** {report.reporting_period}  ",
        f"**Total cases:** {report.manifest.get('n_cases')}  ",
        f"**Generated:** {report.manifest.get('generated_at')} (model: {report.manifest.get('model')})",
        "",
        "> Every number and table below is computed deterministically from the source data. Narrative "
        "text only frames those pre-computed figures and is automatically grounding-checked so that each "
        "figure it states is traceable to the evidence.",
        "",
    ]
    for index, section in enumerate(report.sections, start=1):
        lines.append(f"## {index}. {section.title}")
        lines.append("")
        if section.narrative is not None:
            lines.append(_narrative_block(section.narrative))
            lines.append("")
        if section.mode in ("table", "both"):
            for analysis in section.analyses:
                block = _analysis_block(analysis)
                if block:
                    lines.append(block)
                    lines.append("")
        elif section.mode == "narrative":
            for analysis in section.analyses:
                if not analysis.table and not analysis.facts and analysis.notes:
                    lines.append("\n".join(f"> {note}" for note in analysis.notes))
                    lines.append("")
        note = _grounding_note(section.grounding)
        if note:
            lines.append(note)
            lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("### Run manifest")
    lines.append("")
    lines.append(_kv_block(report.manifest))
    return "\n".join(lines).rstrip() + "\n"
