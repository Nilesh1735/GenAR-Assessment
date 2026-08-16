from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from src.llm.sections import SectionNarrative
from src.pipeline import generate_report
from src.report.assemble import render_markdown

CONFIG = "config/pader.yaml"
FIXED_NOW = datetime(2025, 6, 1, tzinfo=timezone.utc)

EXPECTED_SECTION_IDS = [
    "reporting_period",
    "narrative_summary",
    "summary_analysis_cases",
    "reaction_analysis",
    "serious_cases_15day",
    "trends",
    "history_of_actions",
    "case_index",
]


class StubGenerator:
    def __init__(self):
        self.config = SimpleNamespace(model="stub-model")
        self.calls = 0

    def generate(self, system_prompt, user_prompt):
        self.calls += 1
        return SectionNarrative(summary="Section narrative placeholder for testing.", claims=[])


def test_pipeline_sections_and_manifest(dataset_path):
    generator = StubGenerator()
    report = generate_report(CONFIG, dataset_path, generator=generator, now=FIXED_NOW)

    assert [section.id for section in report.sections] == EXPECTED_SECTION_IDS
    assert report.manifest["n_cases"] == 1024
    assert report.manifest["model"] == "stub-model"
    assert report.manifest["report_type"] == "PADER"
    assert report.manifest["generated_at"] == "2025-06-01T00:00:00+00:00"
    assert len(report.manifest["dataset_sha256"]) == 64


def test_pipeline_narrative_only_on_narrative_modes(dataset_path):
    report = generate_report(CONFIG, dataset_path, generator=StubGenerator(), now=FIXED_NOW)
    by_id = {section.id: section for section in report.sections}

    assert by_id["narrative_summary"].narrative is not None
    assert by_id["reporting_period"].narrative is None
    assert by_id["case_index"].narrative is None


def test_pipeline_grounding_passes_for_numberless_narrative(dataset_path):
    report = generate_report(CONFIG, dataset_path, generator=StubGenerator(), now=FIXED_NOW)
    checked = [section for section in report.sections if section.grounding is not None]

    assert checked
    assert all(section.grounding.status == "pass" for section in checked)


def test_render_markdown_contains_golden_figures(dataset_path):
    report = generate_report(CONFIG, dataset_path, generator=StubGenerator(), now=FIXED_NOW)
    markdown = render_markdown(report)

    assert "Periodic Adverse Drug Experience Report" in markdown
    assert "2024-12-27 to 2025-12-26" in markdown
    assert "Acute kidney injury" in markdown
    assert "1024" in markdown
    assert "Run manifest" in markdown
