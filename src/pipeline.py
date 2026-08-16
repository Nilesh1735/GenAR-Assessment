from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from src.analysis.analyses import period_string
from src.analysis.base import AnalysisResult, run_analyses
from src.data.loader import file_sha256, load_dataset
from src.data.normalize import CaseData, normalize
from src.evidence.packet import build_packet
from src.eval.grounding import check_grounding
from src.llm.client import NarrativeGenerator
from src.llm.prompting import prompts_hash, section_prompt, system_prompt
from src.log import emit
from src.report.model import ReportResult, SectionOutput

NARRATIVE_MODES = ("narrative", "both")


def load_report_config(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _required_analysis_keys(config: dict) -> list[str]:
    keys: list[str] = []
    for section in config["sections"]:
        for key in section["required_analyses"]:
            if key not in keys:
                keys.append(key)
    return keys


def prepare_analyses(config: dict, data_path: str | Path) -> tuple[CaseData, dict[str, AnalysisResult]]:
    data = normalize(load_dataset(data_path))
    results = run_analyses(_required_analysis_keys(config), data)
    return data, results


def build_section(
    section: dict,
    results: dict[str, AnalysisResult],
    product: str,
    period: str,
    generator: NarrativeGenerator,
    base_prompt: str,
) -> SectionOutput:
    analyses = [results[key] for key in section["required_analyses"]]
    narrative = None
    grounding = None
    if section["mode"] in NARRATIVE_MODES:
        packet = build_packet(section, results, product, period)
        emit("section_generate", section=section["id"])
        narrative = generator.generate(base_prompt, section_prompt(packet))
        grounding = check_grounding(narrative, packet)
        emit(
            "section_grounding",
            section=section["id"],
            status=grounding.status,
            numbers_checked=grounding.numbers_checked,
            ungrounded=len(grounding.ungrounded_numbers),
        )
    return SectionOutput(
        id=section["id"],
        title=section["title"],
        mode=section["mode"],
        analyses=analyses,
        narrative=narrative,
        grounding=grounding,
    )


def build_manifest(
    config: dict,
    data_path: str | Path,
    data: CaseData,
    generator: NarrativeGenerator,
    now: datetime | None = None,
) -> dict:
    return {
        "report_type": config.get("report_type"),
        "config_version": config.get("version"),
        "dataset": Path(data_path).name,
        "dataset_sha256": file_sha256(data_path),
        "model": generator.config.model,
        "prompts_hash": prompts_hash(),
        "n_cases": data.n_cases,
        "generated_at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
    }


def generate_report(
    config_path: str | Path,
    data_path: str | Path,
    generator: NarrativeGenerator | None = None,
    now: datetime | None = None,
) -> ReportResult:
    config = load_report_config(config_path)
    data, results = prepare_analyses(config, data_path)
    product = config["product"]
    period = period_string(data)

    if generator is None:
        generator = NarrativeGenerator()
    base_prompt = system_prompt(product)

    sections = [
        build_section(section, results, product, period, generator, base_prompt)
        for section in config["sections"]
    ]
    manifest = build_manifest(config, data_path, data, generator, now)
    return ReportResult(
        title=config["title"],
        product=product,
        reporting_period=period,
        sections=sections,
        manifest=manifest,
    )
