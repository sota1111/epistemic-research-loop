from __future__ import annotations

import csv
import hashlib
from copy import deepcopy
from pathlib import Path
from typing import Any


def anonymous_identifier(value: str, *, salt: str) -> str:
    digest = hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()[:12]
    return f"anonymous-{digest}"


def anonymize_competition_package(
    package: dict[str, Any],
    *,
    salt: str,
    hash_column_names: bool = False,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Remove competition identity and optionally replace every exposed column name."""

    result = deepcopy(package)
    identities = {
        str(result[key])
        for key in ("competition", "competition_name", "slug", "title")
        if key in result and str(result[key])
    }
    for key in ("competition", "competition_name", "slug", "title"):
        if key in result:
            result[key] = anonymous_identifier(str(result[key]), salt=salt)
    _replace_identity_strings(result, identities, salt)
    mapping: dict[str, str] = {}
    if hash_column_names:
        columns = result.get("columns", [])
        transformed: list[Any] = []
        for index, column in enumerate(columns):
            if isinstance(column, str):
                alias = _column_alias(column, index, salt)
                mapping[column] = alias
                transformed.append(alias)
            elif isinstance(column, dict) and "name" in column:
                original = str(column["name"])
                alias = _column_alias(original, index, salt)
                mapping[original] = alias
                transformed.append({**column, "name": alias})
            else:
                transformed.append(column)
        result["columns"] = transformed
        _replace_named_fields(result, mapping)
    return result, mapping


def anonymize_csv_columns(source: str | Path, destination: str | Path, *, salt: str) -> dict[str, str]:
    """Write a data-equivalent CSV variant with deterministic, meaning-neutral column names."""

    source_path = Path(source)
    destination_path = Path(destination)
    with source_path.open(newline="", encoding="utf-8") as input_file:
        reader = csv.reader(input_file)
        header = next(reader, None)
        if not header:
            raise ValueError("CSV input must contain a header")
        if len(header) != len(set(header)):
            raise ValueError("CSV input column names must be unique")
        mapping = {name: _column_alias(name, index, salt) for index, name in enumerate(header)}
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        with destination_path.open("w", newline="", encoding="utf-8") as output_file:
            writer = csv.writer(output_file)
            writer.writerow([mapping[name] for name in header])
            writer.writerows(reader)
    return mapping


def _column_alias(name: str, index: int, salt: str) -> str:
    digest = hashlib.sha256(f"{salt}:column:{name}".encode()).hexdigest()[:8]
    return f"feature_{index:04d}_{digest}"


def _replace_named_fields(value: Any, mapping: dict[str, str]) -> None:
    if isinstance(value, dict):
        for key, item in list(value.items()):
            if key != "columns" and isinstance(item, str) and item in mapping:
                value[key] = mapping[item]
            else:
                _replace_named_fields(item, mapping)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            if isinstance(item, str) and item in mapping:
                value[index] = mapping[item]
            else:
                _replace_named_fields(item, mapping)


def _replace_identity_strings(value: Any, identities: set[str], salt: str) -> None:
    if isinstance(value, dict):
        for key, item in list(value.items()):
            if isinstance(item, str):
                replaced = item
                for identity in identities:
                    replaced = replaced.replace(identity, anonymous_identifier(identity, salt=salt))
                value[key] = replaced
            else:
                _replace_identity_strings(item, identities, salt)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            if isinstance(item, str):
                replaced = item
                for identity in identities:
                    replaced = replaced.replace(identity, anonymous_identifier(identity, salt=salt))
                value[index] = replaced
            else:
                _replace_identity_strings(item, identities, salt)
