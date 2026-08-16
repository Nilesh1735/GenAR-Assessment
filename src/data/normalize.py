from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from src.data import schema

AGE_GROUPS = ("0-17", "18-64", "65-74", "75-84", "85+", "Unknown")
REGION_CODES = {"eu", "eea", "row"}


@dataclass(frozen=True)
class CaseData:
    cases: pd.DataFrame
    reactions: pd.DataFrame

    @property
    def n_cases(self) -> int:
        return len(self.cases)


def _norm_text(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().str.lower()


def _flag(series: pd.Series, token: str) -> pd.Series:
    return _norm_text(series).eq(token).fillna(False)


def _latest_version(df: pd.DataFrame) -> pd.DataFrame:
    latest = df.groupby(schema.CASE_ID)[schema.CASE_VERSION].idxmax()
    return df.loc[latest].reset_index(drop=True)


def _to_date(value: object) -> date | None:
    text = str(value).strip()
    if len(text) != 8 or not text.isdigit():
        return None
    try:
        return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    except ValueError:
        return None


def _age_years(age: object, unit: object) -> float | None:
    if str(unit).strip().lower() != "year":
        return None
    try:
        value = float(age)
    except (TypeError, ValueError):
        return None
    if value < 0 or value > 150:
        return None
    return value


def _age_group(age: float | None) -> str:
    if age is None or pd.isna(age):
        return "Unknown"
    if age < 18:
        return "0-17"
    if age < 65:
        return "18-64"
    if age < 75:
        return "65-74"
    if age < 85:
        return "75-84"
    return "85+"


def _sex(value: object) -> str:
    text = str(value).strip().lower()
    if text in {"female", "f"}:
        return "female"
    if text in {"male", "m"}:
        return "male"
    return "unknown"


def _explode_reactions(cases: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for case_id, is_serious, pts, outcomes in zip(
        cases[schema.CASE_ID],
        cases["is_serious"],
        cases[schema.REACTION_PT],
        cases[schema.REACTION_OUTCOME],
    ):
        if pd.isna(pts):
            continue
        pt_list = [p.strip() for p in str(pts).split(",") if p.strip()]
        outcome_list = [o.strip() for o in str(outcomes).split(",")] if pd.notna(outcomes) else []
        for position, pt in enumerate(pt_list):
            outcome = outcome_list[position] if position < len(outcome_list) and outcome_list[position] else None
            records.append(
                {
                    schema.CASE_ID: case_id,
                    "reaction_pt": pt,
                    "outcome": outcome,
                    "is_serious": bool(is_serious),
                }
            )
    return pd.DataFrame.from_records(
        records, columns=[schema.CASE_ID, "reaction_pt", "outcome", "is_serious"]
    )


def normalize(df: pd.DataFrame) -> CaseData:
    cases = _latest_version(df)
    cases["is_serious"] = _flag(cases[schema.SERIOUS], "serious")
    cases["is_expedited"] = _flag(cases[schema.EXPEDITE], "yes")
    cases["sex"] = cases[schema.SEX].map(_sex)
    cases["country"] = _norm_text(cases[schema.COUNTRY]).fillna("unknown")
    cases["receive_date"] = cases[schema.RECEIVE_DATE].map(_to_date)
    age_values = [
        _age_years(age, unit)
        for age, unit in zip(cases[schema.AGE], cases[schema.AGE_UNIT])
    ]
    cases["age_years"] = age_values
    cases["age_group"] = [_age_group(value) for value in age_values]
    for name, column in schema.SERIOUSNESS_FLAGS.items():
        cases[f"flag_{name}"] = _flag(cases[column], "yes")
    reactions = _explode_reactions(cases)
    return CaseData(cases=cases, reactions=reactions)
