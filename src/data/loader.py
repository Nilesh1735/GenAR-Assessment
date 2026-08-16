from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from src.data.schema import DatasetError, validate_dataset


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    raise DatasetError(f"unsupported dataset format {suffix!r} (expected .xlsx, .xls or .csv)")


def load_dataset(path: str | Path) -> pd.DataFrame:
    resolved = Path(path)
    if not resolved.exists():
        raise DatasetError(f"dataset not found: {resolved}")
    df = _read(resolved)
    validate_dataset(df)
    return df
