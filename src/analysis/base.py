from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Literal

import pandas as pd

from src.data.normalize import CaseData

Kind = Literal["scalar", "table", "series"]
RENDER_ROW_CAP = 60
_DIGITS = re.compile(r"\d+")


def num_token(value: object) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if pd.isna(value):
            return None
        if value.is_integer():
            return str(int(value))
        return f"{value:g}"
    return None


@dataclass(frozen=True)
class AnalysisResult:
    key: str
    title: str
    kind: Kind
    facts: dict[str, float]
    columns: list[str]
    table: list[dict[str, object]]
    evidence: dict[str, list[str]]
    notes: list[str]

    def numbers(self) -> set[str]:
        tokens: set[str] = set()
        for value in self.facts.values():
            token = num_token(value)
            if token is not None:
                tokens.add(token)
        for row in self.table:
            for cell in row.values():
                token = num_token(cell)
                if token is not None:
                    tokens.add(token)
        return tokens

    def label_numbers(self) -> set[str]:
        tokens: set[str] = set()
        for column in self.columns:
            tokens |= set(_DIGITS.findall(str(column)))
        for row in self.table:
            for cell in row.values():
                if num_token(cell) is None:
                    tokens |= set(_DIGITS.findall(str(cell)))
        return tokens


@dataclass(frozen=True)
class EvidencePacket:
    section_id: str
    section_title: str
    product: str
    reporting_period: str
    instructions: str
    analyses: list[AnalysisResult]
    notes: list[str]

    def allowed_numbers(self) -> set[str]:
        tokens: set[str] = set(_DIGITS.findall(self.reporting_period))
        for analysis in self.analyses:
            tokens |= analysis.numbers()
            tokens |= analysis.label_numbers()
        return tokens

    def render(self) -> str:
        blocks: list[str] = []
        for analysis in self.analyses:
            lines = [f"[{analysis.key}] {analysis.title}"]
            for name, value in analysis.facts.items():
                token = num_token(value)
                lines.append(f"  {name}: {token if token is not None else value}")
            if analysis.table:
                lines.append("  " + " | ".join(analysis.columns))
                for row in analysis.table[:RENDER_ROW_CAP]:
                    lines.append("  " + " | ".join(str(row.get(column, "")) for column in analysis.columns))
                if len(analysis.table) > RENDER_ROW_CAP:
                    lines.append(f"  ... ({len(analysis.table)} rows total)")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)


AnalysisFn = Callable[[CaseData], AnalysisResult]
_REGISTRY: dict[str, AnalysisFn] = {}


def register(key: str) -> Callable[[AnalysisFn], AnalysisFn]:
    def decorator(fn: AnalysisFn) -> AnalysisFn:
        _REGISTRY[key] = fn
        return fn

    return decorator


def available_analyses() -> set[str]:
    return set(_REGISTRY)


def run_analyses(keys: list[str], data: CaseData) -> dict[str, AnalysisResult]:
    unknown = [key for key in keys if key not in _REGISTRY]
    if unknown:
        raise KeyError(f"unknown analyses requested: {unknown}")
    return {key: _REGISTRY[key](data) for key in keys}
