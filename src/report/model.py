from __future__ import annotations

from dataclasses import dataclass, field

from src.analysis.base import AnalysisResult
from src.eval.grounding import GroundingReport
from src.llm.sections import SectionNarrative


@dataclass
class SectionOutput:
    id: str
    title: str
    mode: str
    analyses: list[AnalysisResult]
    narrative: SectionNarrative | None = None
    grounding: GroundingReport | None = None


@dataclass
class ReportResult:
    title: str
    product: str
    reporting_period: str
    sections: list[SectionOutput]
    manifest: dict = field(default_factory=dict)
