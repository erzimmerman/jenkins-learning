"""Shared, dependency-free helpers for SS12000-to-Canvas transformations."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence


JsonObject = dict[str, Any]


def load_json(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"Input file does not exist: {path}")
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def extract_collection(payload: Any, names: Sequence[str]) -> list[JsonObject]:
    """Extract records from a list or common API wrapper shapes."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON array or object")

    candidates = list(names) + ["data", "items", "content", "results"]
    for name in candidates:
        value = payload.get(name)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    embedded = payload.get("_embedded")
    if isinstance(embedded, dict):
        for name in candidates:
            value = embedded.get(name)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        list_values = [value for value in embedded.values() if isinstance(value, list)]
        if len(list_values) == 1:
            return [item for item in list_values[0] if isinstance(item, dict)]

    raise ValueError(
        f"Could not find {', '.join(names)} collection; top-level fields: "
        f"{', '.join(payload.keys())}"
    )


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, dict):
        for key in ("value", "displayName", "name", "code", "id"):
            result = text(value.get(key))
            if result:
                return result
    return ""


def first_value(value: Any) -> str:
    for item in as_list(value):
        result = text(item)
        if result:
            return result
    return ""


def ref_id(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("id", "personId", "activityId", "groupId", "dutyId", "value"):
            result = text(value.get(key))
            if result:
                return result
        for key in ("person", "activity", "group", "duty", "reference"):
            result = ref_id(value.get(key))
            if result:
                return result
    return text(value)


def nested(obj: JsonObject, *paths: str) -> Any:
    for path in paths:
        current: Any = obj
        found = True
        for part in path.split("."):
            if not isinstance(current, dict) or part not in current:
                found = False
                break
            current = current[part]
        if found and current is not None:
            return current
    return None


def canvas_status(value: Any, *, default: str = "active") -> str:
    raw = text(value).casefold()
    if raw in {"deleted", "inactive", "cancelled", "canceled", "avslutad", "inaktiv", "false"}:
        return "deleted"
    return default


def iso_date(value: Any) -> str:
    raw = text(value)
    if not raw:
        return ""
    if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
        return f"{raw}T00:00:00Z"
    return raw


def course_id_for(activity: JsonObject) -> str:
    for path in (
        "parentActivity",
        "course",
        "syllabus",
        "subject",
        "parent",
    ):
        result = ref_id(nested(activity, path))
        if result:
            return result
    return ref_id(activity.get("id"))


def course_name_for(activity: JsonObject) -> str:
    for path in ("parentActivity", "course", "syllabus", "subject", "parent"):
        value = nested(activity, path)
        if isinstance(value, dict):
            result = first_value(
                nested(value, "displayName", "name", "title", "courseCode", "code")
            )
            if result:
                return result
    return first_value(
        nested(activity, "displayName", "name", "title", "activityCode", "code")
    )


def activity_name(activity: JsonObject) -> str:
    return first_value(
        nested(activity, "displayName", "name", "title", "activityCode", "code")
    )


def write_csv(path: Path, columns: Sequence[str], rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})
            count += 1
    return count


def unique_rows(rows: Iterable[dict[str, Any]], keys: Sequence[str]) -> Iterator[dict[str, Any]]:
    seen: set[tuple[str, ...]] = set()
    for row in rows:
        identity = tuple(text(row.get(key)) for key in keys)
        if not all(identity) or identity in seen:
            continue
        seen.add(identity)
        yield row


def person_ids_from(value: Any) -> Iterator[str]:
    for item in as_list(value):
        identifier = ref_id(item)
        if identifier:
            yield identifier


def duty_to_person_index(persons: Sequence[JsonObject]) -> dict[str, str]:
    index: dict[str, str] = {}
    for person in persons:
        person_id = ref_id(person.get("id"))
        if not person_id:
            continue
        for field in ("duties", "dutyAssignments", "assignments"):
            for duty in as_list(person.get(field)):
                duty_id = ref_id(duty)
                if duty_id:
                    index[duty_id] = person_id
    return index

