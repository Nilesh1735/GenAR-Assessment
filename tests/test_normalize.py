from __future__ import annotations

from datetime import date

import pandas as pd

from src.data.normalize import _age_group, normalize


def test_dedup_keeps_latest_version(synthetic_df):
    data = normalize(synthetic_df)
    assert data.n_cases == 5
    case_a = data.cases.set_index("safetyreportid").loc["A"]
    assert case_a["safetyreportversion"] == 3


def test_reaction_explosion_positional(synthetic_df):
    data = normalize(synthetic_df)
    a = data.reactions[data.reactions["safetyreportid"] == "A"].reset_index(drop=True)
    assert list(a["reaction_pt"]) == ["Headache", "Nausea"]
    assert list(a["outcome"]) == ["recovered/resolved", "fatal"]


def test_reaction_explosion_pads_missing_outcome(synthetic_df):
    data = normalize(synthetic_df)
    b = data.reactions[data.reactions["safetyreportid"] == "B"].reset_index(drop=True)
    assert list(b["reaction_pt"]) == ["Rash", "Fever", "Chills"]
    assert list(b["outcome"]) == ["unknown", None, None]


def test_bad_and_nonyear_age_units_excluded(synthetic_df):
    data = normalize(synthetic_df)
    idx = data.cases.set_index("safetyreportid")
    assert pd.isna(idx.loc["C", "age_years"])
    assert idx.loc["C", "age_group"] == "Unknown"
    assert pd.isna(idx.loc["D", "age_years"])
    assert idx.loc["D", "age_group"] == "Unknown"


def test_age_group_edges():
    assert _age_group(17) == "0-17"
    assert _age_group(18) == "18-64"
    assert _age_group(64) == "18-64"
    assert _age_group(65) == "65-74"
    assert _age_group(74) == "65-74"
    assert _age_group(75) == "75-84"
    assert _age_group(84) == "75-84"
    assert _age_group(85) == "85+"
    assert _age_group(None) == "Unknown"


def test_sex_and_country_normalization(synthetic_df):
    data = normalize(synthetic_df)
    idx = data.cases.set_index("safetyreportid")
    assert idx.loc["E", "sex"] == "unknown"
    assert idx.loc["E", "country"] == "eu"


def test_golden_case_counts(real_cases):
    assert real_cases.n_cases == 1024
    assert int(real_cases.cases["is_serious"].sum()) == 1023
    assert int(real_cases.cases["is_expedited"].sum()) == 1023
    assert len(real_cases.reactions) == 3429


def test_golden_reporting_period(real_cases):
    dates = [d for d in real_cases.cases["receive_date"] if d is not None]
    assert min(dates) == date(2024, 12, 27)
    assert max(dates) == date(2025, 12, 26)
