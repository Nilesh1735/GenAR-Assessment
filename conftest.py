from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.data import schema
from src.data.loader import load_dataset
from src.data.normalize import normalize

ROOT = Path(__file__).parent
DATASET = ROOT / "Bisoprolol_icsr_sample_1068rows.xlsx"


def _row(case_id, version, serious, pt, outcome, age, unit, sex="female", country="france"):
    row = {
        schema.CASE_ID: case_id,
        schema.CASE_VERSION: version,
        schema.SERIOUS: serious,
        schema.EXPEDITE: "yes" if serious == "serious" else "no",
        schema.RECEIVE_DATE: 20250115,
        schema.REACTION_PT: pt,
        schema.REACTION_OUTCOME: outcome,
        schema.AGE: age,
        schema.AGE_UNIT: unit,
        schema.SEX: sex,
        schema.COUNTRY: country,
    }
    for column in schema.SERIOUSNESS_FLAGS.values():
        row[column] = "no"
    return row


@pytest.fixture
def synthetic_df() -> pd.DataFrame:
    rows = [
        _row("A", 1, "serious", "Headache", "recovered/resolved", 50, "year"),
        _row("A", 3, "serious", "Headache,Nausea", "recovered/resolved,fatal", 50, "year"),
        _row("A", 2, "serious", "Headache", "recovered/resolved", 50, "year"),
        _row("B", 1, "not serious", "Rash,Fever,Chills", "unknown", 8, "year"),
        _row("C", 1, "serious", "Dizziness", "unknown", 800, 800),
        _row("D", 1, "serious", "Vomiting", "recovering/resolving", 6, "month"),
        _row("E", 1, "serious", "Fall", "not recovered/not resolved/ongoing", 90, "year", sex=None, country="eu"),
    ]
    return pd.DataFrame(rows)


@pytest.fixture(scope="session")
def real_cases():
    if not DATASET.exists():
        pytest.skip("golden dataset not present")
    return normalize(load_dataset(DATASET))


@pytest.fixture(scope="session")
def dataset_path():
    if not DATASET.exists():
        pytest.skip("golden dataset not present")
    return DATASET
