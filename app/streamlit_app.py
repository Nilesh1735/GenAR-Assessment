from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.analysis.analyses import period_string
from src.analysis.base import AnalysisResult
from src.data.schema import DatasetError
from src.llm.client import LLMError, NarrativeGenerator
from src.llm.prompting import system_prompt
from src.pipeline import (
    build_manifest,
    build_section,
    load_report_config,
    prepare_analyses,
)
from src.report.assemble import render_markdown
from src.report.model import ReportResult

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "pader.yaml"
DEFAULT_DATA = ROOT / "Bisoprolol_icsr_sample_1068rows.xlsx"

PENDING, APPROVED, FLAGGED = "pending", "approved", "flagged"


def _facts_frame(analysis: AnalysisResult) -> pd.DataFrame:
    return pd.DataFrame(
        {"figure": list(analysis.facts.keys()), "value": list(analysis.facts.values())}
    )


def _table_frame(analysis: AnalysisResult) -> pd.DataFrame:
    return pd.DataFrame(analysis.table, columns=analysis.columns)


def _generate() -> None:
    config = load_report_config(st.session_state.config_path)
    data, results = prepare_analyses(config, st.session_state.data_path)
    product = config["product"]
    period = period_string(data)
    generator = NarrativeGenerator()
    base_prompt = system_prompt(product)

    sections = []
    progress = st.progress(0.0, text="Generating sections")
    section_configs = config["sections"]
    for index, section in enumerate(section_configs, start=1):
        sections.append(build_section(section, results, product, period, generator, base_prompt))
        progress.progress(index / len(section_configs), text=f"Generated {section['title']}")
    progress.empty()

    manifest = build_manifest(config, st.session_state.data_path, data, generator)
    st.session_state.report = ReportResult(
        title=config["title"],
        product=product,
        reporting_period=period,
        sections=sections,
        manifest=manifest,
    )
    st.session_state.context = {
        "section_configs": {section["id"]: section for section in section_configs},
        "results": results,
        "product": product,
        "period": period,
        "generator": generator,
        "base_prompt": base_prompt,
    }
    st.session_state.status = {section.id: PENDING for section in sections}


def _regenerate(section_id: str) -> None:
    context = st.session_state.context
    section_config = context["section_configs"][section_id]
    fresh = build_section(
        section_config,
        context["results"],
        context["product"],
        context["period"],
        context["generator"],
        context["base_prompt"],
    )
    report = st.session_state.report
    report.sections = [fresh if section.id == section_id else section for section in report.sections]
    st.session_state.status[section_id] = PENDING


def _render_sidebar() -> None:
    st.sidebar.header("Run configuration")
    st.session_state.config_path = st.sidebar.text_input("Report config", str(DEFAULT_CONFIG))
    st.session_state.data_path = st.sidebar.text_input("Dataset", str(DEFAULT_DATA))
    if st.sidebar.button("Generate report", type="primary"):
        try:
            with st.spinner("Computing evidence and framing narratives"):
                _generate()
        except LLMError as error:
            st.session_state.report = None
            st.sidebar.error(f"LLM unavailable: {error}")
        except DatasetError as error:
            st.session_state.report = None
            st.sidebar.error(f"Dataset problem: {error}")

    report = st.session_state.get("report")
    if report is not None:
        st.sidebar.subheader("Run manifest")
        manifest = dict(report.manifest)
        manifest["dataset_sha256"] = manifest["dataset_sha256"][:16] + "…"
        st.sidebar.json(manifest)


def _render_grounding(section) -> None:
    grounding = section.grounding
    if grounding is None:
        return
    if grounding.status == "pass":
        st.success(f"Grounding passed — {grounding.numbers_checked} figures traced to the evidence packet.")
        return
    st.error(
        "Grounding failed — the narrative cites figures absent from the evidence packet: "
        + ", ".join(grounding.ungrounded_numbers)
    )
    if grounding.unknown_analysis_keys:
        st.warning("Unknown analysis keys cited: " + ", ".join(grounding.unknown_analysis_keys))


def _render_narrative(section) -> None:
    narrative = section.narrative
    if narrative is None:
        return
    st.markdown(narrative.summary)
    if narrative.observations:
        st.markdown("**Observations**")
        for item in narrative.observations:
            st.markdown(f"- {item}")
    if narrative.interpretation_flags:
        st.markdown("**Patterns for human review**")
        for item in narrative.interpretation_flags:
            st.markdown(f"- {item}")
    if narrative.data_gaps:
        st.markdown("**Data not available**")
        for item in narrative.data_gaps:
            st.markdown(f"- {item}")
    if narrative.claims:
        with st.expander(f"Claim-level traceability ({len(narrative.claims)} claims)"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "statement": claim.statement,
                            "figures": ", ".join(claim.figures),
                            "analysis_key": claim.analysis_key,
                        }
                        for claim in narrative.claims
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )


def _render_evidence(section) -> None:
    for analysis in section.analyses:
        if analysis.facts:
            st.markdown(f"**{analysis.title} — figures**")
            st.dataframe(_facts_frame(analysis), use_container_width=True, hide_index=True)
        if analysis.table:
            st.markdown(f"**{analysis.title} — table**")
            st.dataframe(_table_frame(analysis), use_container_width=True, hide_index=True)
        for note in analysis.notes:
            st.caption(f"Note: {note}")


def _render_controls(section) -> None:
    status = st.session_state.status[section.id]
    st.caption(f"Status: {status.upper()}")
    approve, flag, regenerate = st.columns(3)
    if approve.button("Approve", key=f"approve_{section.id}"):
        st.session_state.status[section.id] = APPROVED
        st.rerun()
    if flag.button("Flag", key=f"flag_{section.id}"):
        st.session_state.status[section.id] = FLAGGED
        st.rerun()
    if regenerate.button("Regenerate", key=f"regen_{section.id}", disabled=section.narrative is None):
        with st.spinner("Regenerating section"):
            try:
                _regenerate(section.id)
            except LLMError as error:
                st.error(f"LLM unavailable: {error}")
        st.rerun()


def _render_export(report: ReportResult) -> None:
    approved_ids = [sid for sid, status in st.session_state.status.items() if status == APPROVED]
    st.subheader(f"Export ({len(approved_ids)} of {len(report.sections)} sections approved)")
    if not approved_ids:
        st.info("Approve at least one section to export the report.")
        return
    approved = ReportResult(
        title=report.title,
        product=report.product,
        reporting_period=report.reporting_period,
        sections=[section for section in report.sections if section.id in approved_ids],
        manifest=report.manifest,
    )
    st.download_button(
        "Download approved report (Markdown)",
        data=render_markdown(approved),
        file_name="bisoprolol_pader_reviewed.md",
        mime="text/markdown",
    )


def main() -> None:
    st.set_page_config(page_title="Evidence-Grounded Report Review", layout="wide")
    st.title("Evidence-Grounded Regulatory Report — Review")
    st.caption(
        "Every figure is computed in Python; the model only frames pre-computed figures. "
        "Review each section, confirm its grounding status, then export the approved report."
    )

    _render_sidebar()
    report = st.session_state.get("report")
    if report is None:
        st.info("Set the config and dataset in the sidebar, then generate the report.")
        return

    st.header(f"{report.title} — {report.product}")
    st.markdown(f"**Reporting period:** {report.reporting_period}")

    for index, section in enumerate(report.sections, start=1):
        st.divider()
        st.subheader(f"{index}. {section.title}")
        _render_grounding(section)
        _render_narrative(section)
        with st.expander("Underlying evidence (computed in Python)"):
            _render_evidence(section)
        _render_controls(section)

    st.divider()
    _render_export(report)


if __name__ == "__main__":
    main()
