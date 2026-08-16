from __future__ import annotations

from datetime import date

import pandas as pd

from src.analysis.base import AnalysisResult, register
from src.data import schema
from src.data.normalize import CaseData

TOP_N_REACTIONS = 15
ALERT_WINDOW_DAYS = 15
SOC_NOTE = (
    "MedDRA System Organ Class (SOC) grouping is not available in the source data; "
    "reactions are reported at Preferred Term (PT) level only."
)
EXPECTEDNESS_NOTE = (
    "Expectedness (labelled vs. unlisted) is not assessed: no product label or Company Core Data "
    "Sheet (CCDS) is available in the source data, so cases cannot be classified as labelled or unlabelled."
)


def _ids(frame: pd.DataFrame) -> list[str]:
    return [str(value) for value in frame[schema.CASE_ID].tolist()]


def period_bounds(data: CaseData) -> tuple[date, date]:
    dates = [value for value in data.cases["receive_date"] if value is not None]
    return min(dates), max(dates)


def period_string(data: CaseData) -> str:
    start, end = period_bounds(data)
    return f"{start.isoformat()} to {end.isoformat()}"


def _pt_case_counts(reactions: pd.DataFrame) -> pd.DataFrame:
    distinct = reactions.drop_duplicates([schema.CASE_ID, "reaction_pt"])
    grouped = distinct.groupby("reaction_pt")[schema.CASE_ID].agg(list)
    frame = pd.DataFrame({"ids": grouped})
    frame["cases"] = frame["ids"].map(len)
    return frame.sort_values("cases", ascending=False)


@register("reporting_period")
def reporting_period(data: CaseData) -> AnalysisResult:
    start, end = period_bounds(data)
    return AnalysisResult(
        key="reporting_period",
        title="Reporting Period",
        kind="scalar",
        facts={"total_cases": data.n_cases},
        columns=["metric", "value"],
        table=[
            {"metric": "Reporting interval start", "value": start.isoformat()},
            {"metric": "Reporting interval end", "value": end.isoformat()},
            {"metric": "Total cases received", "value": data.n_cases},
        ],
        evidence={},
        notes=[],
    )


@register("case_counts")
def case_counts(data: CaseData) -> AnalysisResult:
    cases = data.cases
    serious = cases[cases["is_serious"]]
    non_serious = cases[~cases["is_serious"]]
    total = data.n_cases
    serious_n = len(serious)
    non_serious_n = len(non_serious)
    facts = {
        "total_cases": total,
        "serious_cases": serious_n,
        "non_serious_cases": non_serious_n,
        "serious_pct": round(serious_n / total * 100, 1),
        "non_serious_pct": round(non_serious_n / total * 100, 1),
        "expedited_cases": int(cases["is_expedited"].sum()),
    }
    table = [
        {"category": "Serious", "cases": serious_n, "percent": facts["serious_pct"]},
        {"category": "Non-serious", "cases": non_serious_n, "percent": facts["non_serious_pct"]},
        {"category": "Total", "cases": total, "percent": 100.0},
    ]
    evidence = {"Serious": _ids(serious), "Non-serious": _ids(non_serious)}
    return AnalysisResult(
        key="case_counts",
        title="Case Seriousness Counts",
        kind="table",
        facts=facts,
        columns=["category", "cases", "percent"],
        table=table,
        evidence=evidence,
        notes=[],
    )


@register("demographics")
def demographics(data: CaseData) -> AnalysisResult:
    cases = data.cases
    ages = cases["age_years"].dropna()
    facts = {
        "age_mean": round(float(ages.mean()), 1),
        "age_median": float(ages.median()),
        "age_min": float(ages.min()),
        "age_max": float(ages.max()),
        "age_reported": int(ages.shape[0]),
        "age_missing": int(cases.shape[0] - ages.shape[0]),
    }
    rows: list[dict[str, object]] = []
    evidence: dict[str, list[str]] = {}
    dimensions = [("Age group", "age_group"), ("Sex", "sex"), ("Country", "country")]
    for dimension, column in dimensions:
        for group, count in cases[column].value_counts().items():
            subset = cases[cases[column] == group]
            rows.append(
                {
                    "dimension": dimension,
                    "group": str(group),
                    "cases": int(count),
                    "percent": round(int(count) / data.n_cases * 100, 1),
                }
            )
            evidence[f"{dimension}: {group}"] = _ids(subset)
    notes = [
        f"{facts['age_missing']} of {cases.shape[0]} cases have no usable age "
        "(non-year age units and missing values excluded); age groups are derived buckets."
    ]
    if (cases["country"] == "eu").any():
        notes.append("'eu' is recorded as a region rather than a specific country.")
    return AnalysisResult(
        key="demographics",
        title="Demographic Breakdown",
        kind="table",
        facts=facts,
        columns=["dimension", "group", "cases", "percent"],
        table=rows,
        evidence=evidence,
        notes=notes,
    )


@register("reactions")
def reactions(data: CaseData) -> AnalysisResult:
    overall = _pt_case_counts(data.reactions)
    serious = _pt_case_counts(data.reactions[data.reactions["is_serious"]])
    facts = {
        "distinct_reactions_all": int(overall.shape[0]),
        "distinct_reactions_serious": int(serious.shape[0]),
    }
    rows: list[dict[str, object]] = []
    evidence: dict[str, list[str]] = {}
    for scope, frame in [("All cases", overall), ("Serious cases", serious)]:
        for pt, record in frame.head(TOP_N_REACTIONS).iterrows():
            rows.append({"scope": scope, "reaction": pt, "cases": int(record["cases"])})
            evidence[f"{scope}: {pt}"] = [str(value) for value in record["ids"]]
    return AnalysisResult(
        key="reactions",
        title="Most Frequent Reactions (MedDRA PT, case-level)",
        kind="table",
        facts=facts,
        columns=["scope", "reaction", "cases"],
        table=rows,
        evidence=evidence,
        notes=[SOC_NOTE],
    )


@register("outcomes")
def outcomes(data: CaseData) -> AnalysisResult:
    frame = data.reactions[data.reactions["outcome"].notna()]
    total = int(frame.shape[0])
    counts = frame["outcome"].value_counts()
    rows: list[dict[str, object]] = []
    evidence: dict[str, list[str]] = {}
    for outcome, count in counts.items():
        rows.append(
            {
                "outcome": outcome,
                "reaction_records": int(count),
                "percent": round(int(count) / total * 100, 1),
            }
        )
        ids = frame.loc[frame["outcome"] == outcome, schema.CASE_ID].astype(str)
        evidence[outcome] = sorted(set(ids))
    notes = [
        "Outcomes are counted at the reaction level (one reaction may be one of several in a case); "
        "the reaction outcome 'fatal' is distinct from the case-level death seriousness criterion."
    ]
    return AnalysisResult(
        key="outcomes",
        title="Reaction Outcomes",
        kind="table",
        facts={"total_outcome_records": total},
        columns=["outcome", "reaction_records", "percent"],
        table=rows,
        evidence=evidence,
        notes=notes,
    )


@register("seriousness_breakdown")
def seriousness_breakdown(data: CaseData) -> AnalysisResult:
    cases = data.cases
    total = data.n_cases
    facts: dict[str, float] = {}
    rows: list[dict[str, object]] = []
    evidence: dict[str, list[str]] = {}
    for name, column in schema.SERIOUSNESS_FLAGS.items():
        label = schema.SERIOUSNESS_LABELS[name]
        flagged = cases[cases[f"flag_{name}"]]
        count = len(flagged)
        facts[name] = count
        rows.append(
            {
                "criterion": label,
                "cases": count,
                "percent": round(count / total * 100, 1),
            }
        )
        evidence[label] = _ids(flagged)
    notes = ["Seriousness criteria are not mutually exclusive; a case may satisfy several."]
    return AnalysisResult(
        key="seriousness_breakdown",
        title="Seriousness Criteria",
        kind="table",
        facts=facts,
        columns=["criterion", "cases", "percent"],
        table=rows,
        evidence=evidence,
        notes=notes,
    )


@register("alert_cases")
def alert_cases(data: CaseData) -> AnalysisResult:
    cases = data.cases
    expedited = cases[cases["is_expedited"]]
    serious = cases[cases["is_serious"]]
    facts = {
        "alert_window_days": ALERT_WINDOW_DAYS,
        "expedited_cases": len(expedited),
        "serious_cases": len(serious),
    }
    table = [
        {"metric": f"Cases meeting {ALERT_WINDOW_DAYS}-day expedited criteria", "cases": len(expedited)},
        {"metric": "Serious cases", "cases": len(serious)},
    ]
    evidence = {"Expedited": _ids(expedited), "Serious": _ids(serious)}
    notes = [
        f"A {ALERT_WINDOW_DAYS}-day alert corresponds to a case flagged as meeting expedited "
        "reporting criteria in the source data (fulfillexpeditecriteria).",
        EXPECTEDNESS_NOTE,
    ]
    return AnalysisResult(
        key="alert_cases",
        title="15-Day Alert / Expedited Cases",
        kind="table",
        facts=facts,
        columns=["metric", "cases"],
        table=table,
        evidence=evidence,
        notes=notes,
    )


@register("trends")
def trends(data: CaseData) -> AnalysisResult:
    cases = data.cases
    months = pd.Series(
        [value.strftime("%Y-%m") if value is not None else None for value in cases["receive_date"]],
        index=cases.index,
    )
    counts = months.value_counts().sort_index()
    rows: list[dict[str, object]] = []
    evidence: dict[str, list[str]] = {}
    for month, count in counts.items():
        rows.append({"month": month, "cases": int(count)})
        evidence[month] = _ids(cases[months == month])
    peak_month = counts.idxmax()
    facts = {
        "months_covered": int(counts.shape[0]),
        "peak_month_cases": int(counts.max()),
        "mean_cases_per_month": round(float(counts.mean()), 1),
    }
    notes = [
        "Monthly counts reflect case receipt volume and reporting practices; an increase is an "
        "observation for human review, not in itself a safety signal.",
        f"Highest-volume month: {peak_month}.",
    ]
    return AnalysisResult(
        key="trends",
        title="Monthly Case Volume",
        kind="series",
        facts=facts,
        columns=["month", "cases"],
        table=rows,
        evidence=evidence,
        notes=notes,
    )


@register("history_of_actions")
def history_of_actions(data: CaseData) -> AnalysisResult:
    return AnalysisResult(
        key="history_of_actions",
        title="History of Actions",
        kind="scalar",
        facts={},
        columns=[],
        table=[],
        evidence={},
        notes=[
            "No history of actions (regulatory actions, labelling changes, or company-initiated "
            "actions) is recorded in the source data for this reporting period."
        ],
    )


@register("case_index")
def case_index(data: CaseData) -> AnalysisResult:
    cases = data.cases
    pt_by_case = (
        data.reactions.drop_duplicates([schema.CASE_ID, "reaction_pt"])
        .groupby(schema.CASE_ID)["reaction_pt"]
        .agg(lambda values: "; ".join(values))
    )
    rows: list[dict[str, object]] = []
    evidence: dict[str, list[str]] = {}
    for _, case in cases.iterrows():
        case_id = str(case[schema.CASE_ID])
        received = case["receive_date"]
        age = case["age_years"]
        rows.append(
            {
                "case_id": case_id,
                "received": received.isoformat() if received is not None else "",
                "country": case["country"],
                "sex": case["sex"],
                "age": "" if pd.isna(age) else int(age),
                "serious": "yes" if case["is_serious"] else "no",
                "reactions": pt_by_case.get(case[schema.CASE_ID], ""),
            }
        )
        evidence[case_id] = [case_id]
    return AnalysisResult(
        key="case_index",
        title="Case Index / Listing",
        kind="table",
        facts={"n_cases": data.n_cases},
        columns=["case_id", "received", "country", "sex", "age", "serious", "reactions"],
        table=rows,
        evidence=evidence,
        notes=[],
    )
