from __future__ import annotations

from src.analysis.base import AnalysisResult, EvidencePacket
from src.eval.grounding import check_grounding
from src.llm.sections import Claim, SectionNarrative


def _packet() -> EvidencePacket:
    analysis = AnalysisResult(
        key="case_counts",
        title="Case Seriousness Counts",
        kind="table",
        facts={"total_cases": 1024, "serious_cases": 1023, "serious_pct": 99.9},
        columns=["category", "cases"],
        table=[{"category": "Serious", "cases": 1023}],
        evidence={},
        notes=[],
    )
    return EvidencePacket(
        section_id="narrative_summary",
        section_title="Narrative Summary",
        product="Bisoprolol",
        reporting_period="2024-12-27 to 2025-12-26",
        instructions="",
        analyses=[analysis],
        notes=[],
    )


def test_grounded_narrative_passes():
    packet = _packet()
    narrative = SectionNarrative(
        summary="A total of 1024 cases were received, of which 1023 (99.9%) were serious.",
        claims=[
            Claim(
                statement="1023 of 1024 cases were serious (99.9%).",
                figures=["1023", "1024", "99.9%"],
                analysis_key="case_counts",
            )
        ],
    )
    report = check_grounding(narrative, packet)
    assert report.status == "pass"
    assert report.ungrounded_numbers == []


def test_fabricated_number_is_flagged():
    packet = _packet()
    narrative = SectionNarrative(
        summary="A total of 1024 cases were received; 4321 were fatal.",
        claims=[Claim(statement="4321 cases were fatal.", figures=["4321"], analysis_key="case_counts")],
    )
    report = check_grounding(narrative, packet)
    assert report.status == "fail"
    assert "4321" in report.ungrounded_numbers


def test_unknown_analysis_key_is_flagged():
    packet = _packet()
    narrative = SectionNarrative(
        summary="A total of 1024 cases were received.",
        claims=[Claim(statement="1024 cases were received.", figures=["1024"], analysis_key="does_not_exist")],
    )
    report = check_grounding(narrative, packet)
    assert report.status == "fail"
    assert "does_not_exist" in report.unknown_analysis_keys


def test_reporting_period_dates_ground():
    packet = _packet()
    narrative = SectionNarrative(
        summary="The reporting period spanned 2024 to 2025.",
        claims=[Claim(statement="The period covered 2024 to 2025.", figures=["2024", "2025"], analysis_key="case_counts")],
    )
    report = check_grounding(narrative, packet)
    assert report.status == "pass"


def _labelled_packet() -> EvidencePacket:
    analysis = AnalysisResult(
        key="demographics",
        title="Demographics",
        kind="table",
        facts={"age_n": 931},
        columns=["dimension", "group", "cases"],
        table=[
            {"dimension": "Age group", "group": "65-74", "cases": 300},
            {"dimension": "Age group", "group": "0-17", "cases": 12},
        ],
        evidence={},
        notes=[],
    )
    return EvidencePacket(
        section_id="summary_analysis_cases",
        section_title="Summary Analysis of Cases",
        product="Bisoprolol",
        reporting_period="2024-12-27 to 2025-12-26",
        instructions="",
        analyses=[analysis],
        notes=[],
    )


def test_category_label_boundaries_ground():
    packet = _labelled_packet()
    narrative = SectionNarrative(
        summary="Most cases fell in the 65-74 age group; the 0-17 group was smallest.",
        claims=[
            Claim(statement="The 65-74 group was largest.", figures=["65-74"], analysis_key="demographics")
        ],
    )
    report = check_grounding(narrative, packet)
    assert report.status == "pass"
    assert report.ungrounded_numbers == []


def test_fabricated_number_still_flagged_with_labels():
    packet = _labelled_packet()
    narrative = SectionNarrative(
        summary="The 65-74 group contained 4321 cases.",
        claims=[Claim(statement="The 65-74 group had 4321 cases.", figures=["4321"], analysis_key="demographics")],
    )
    report = check_grounding(narrative, packet)
    assert report.status == "fail"
    assert "4321" in report.ungrounded_numbers
