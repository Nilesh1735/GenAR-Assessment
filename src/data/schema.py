from __future__ import annotations

import pandas as pd


class DatasetError(ValueError):
    pass


CASE_ID = "safetyreportid"
CASE_VERSION = "safetyreportversion"
SERIOUS = "serious"
EXPEDITE = "fulfillexpeditecriteria"
RECEIVE_DATE = "receivedate"
REACTION_PT = "patient_reaction_reactionmeddrapt"
REACTION_OUTCOME = "patient_reaction_reactionoutcome"
AGE = "patient_patientonsetage"
AGE_UNIT = "patient_patientonsetageunit"
SEX = "patient_patientsex"
COUNTRY = "occurcountry"

SERIOUSNESS_FLAGS = {
    "death": "seriousnessdeath",
    "life_threatening": "seriousnesslifethreatening",
    "hospitalization": "seriousnesshospitalization",
    "disabling": "seriousnessdisabling",
    "congenital_anomaly": "seriousnesscongenitalanomali",
    "other": "seriousnessother",
}

SERIOUSNESS_LABELS = {
    "death": "Death",
    "life_threatening": "Life-threatening",
    "hospitalization": "Hospitalization",
    "disabling": "Disabling / incapacitating",
    "congenital_anomaly": "Congenital anomaly",
    "other": "Other medically important condition",
}

REQUIRED_COLUMNS = frozenset(
    {
        CASE_ID,
        CASE_VERSION,
        SERIOUS,
        EXPEDITE,
        RECEIVE_DATE,
        REACTION_PT,
        REACTION_OUTCOME,
        AGE,
        AGE_UNIT,
        SEX,
        COUNTRY,
        *SERIOUSNESS_FLAGS.values(),
    }
)


def validate_dataset(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise DatasetError(f"dataset missing required columns: {sorted(missing)}")
    if df.empty:
        raise DatasetError("dataset contains no rows")
    if df[CASE_ID].isna().all():
        raise DatasetError(f"column {CASE_ID!r} is entirely empty")
