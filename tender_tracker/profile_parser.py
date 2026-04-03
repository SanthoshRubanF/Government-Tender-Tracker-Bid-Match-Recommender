from __future__ import annotations

import io
from pathlib import Path

import pandas as pd


PREFERRED_COLUMNS = (
    "services",
    "service",
    "capabilities",
    "capability",
    "keywords",
    "keyword",
    "expertise",
    "description",
)


class ProfileValidationError(ValueError):
    """Raised when the uploaded profile cannot be parsed safely."""


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ProfileValidationError("The uploaded file could not be decoded as text.")


def _collect_text_values(dataframe: pd.DataFrame) -> tuple[str, list[str]]:
    if dataframe.empty:
        raise ProfileValidationError("The uploaded CSV file is empty.")

    available_columns = [column for column in dataframe.columns if str(column).strip()]
    preferred = [
        column
        for column in available_columns
        if str(column).strip().lower() in PREFERRED_COLUMNS
    ]

    candidate_columns = preferred or [
        column
        for column in available_columns
        if pd.api.types.is_string_dtype(dataframe[column])
        or dataframe[column].dtype == object
    ]

    if not candidate_columns:
        raise ProfileValidationError(
            "No usable text columns were found in the uploaded CSV file."
        )

    text_values: list[str] = []
    for column in candidate_columns:
        for value in dataframe[column].dropna().astype(str):
            cleaned = " ".join(value.split())
            if cleaned:
                text_values.append(cleaned)

    unique_values = list(dict.fromkeys(text_values))
    if not unique_values:
        raise ProfileValidationError("The uploaded profile does not contain any text values.")

    return " ".join(unique_values), [str(column) for column in candidate_columns]


def load_profile_text(uploaded_file) -> tuple[str, dict]:
    file_name = getattr(uploaded_file, "name", "uploaded_profile")
    suffix = Path(file_name).suffix.lower()
    data = uploaded_file.getvalue()
    if not data:
        raise ProfileValidationError("The uploaded file is empty.")

    if suffix == ".csv":
        dataframe = pd.read_csv(io.BytesIO(data))
        profile_text, columns_used = _collect_text_values(dataframe)
        return profile_text, {
            "file_name": file_name,
            "rows": int(len(dataframe)),
            "columns_used": columns_used,
        }

    if suffix in {".txt", ".md"}:
        text = _decode_text(data)
        cleaned = " ".join(text.split())
        if not cleaned:
            raise ProfileValidationError("The uploaded text file is empty.")
        return cleaned, {
            "file_name": file_name,
            "rows": 1,
            "columns_used": ["plain_text"],
        }

    raise ProfileValidationError(
        "Unsupported profile format. Upload a CSV, TXT, or MD file."
    )
