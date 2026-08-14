from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

from ss12000_common import extract_collection, load_json, ref_id, text


COLUMNS = [
    "section_id",
    "course_id",
    "name",
    "status",
    "start_date",
    "end_date",
]


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create sections.csv from SS12000 Activities."
    )
    parser.add_argument("--activities", required=True)
    parser.add_argument("--output", default="output/sections.csv")
    return parser.parse_args()


def expanded_groups(activity: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every group below Activity._embedded.groups.

    sections.csv is defined by the expanded group collection itself. The
    activity's top-level ``groups`` references must not limit which expanded
    groups are traversed.
    """
    embedded = activity.get("_embedded")
    if not isinstance(embedded, dict):
        return []
    groups = embedded.get("groups")
    if isinstance(groups, list):
        return [group for group in groups if isinstance(group, dict)]
    # Compatibility with APIs wrapping the expanded collection once more.
    if isinstance(groups, dict):
        for key in ("groups", "data", "items", "content", "results"):
            values = groups.get(key)
            if isinstance(values, list):
                return [group for group in values if isinstance(group, dict)]
        if ref_id(groups.get("id")):
            return [groups]
    return []


def rows(activities: list[dict[str, Any]]) -> list[dict[str, str]]:
    generated: list[dict[str, str]] = []

    for activity in activities:
        course_id = ref_id(activity.get("id"))
        if not course_id:
            raise ValueError("An Activity is missing id")

        start_date = text(activity.get("startDate"))
        end_date = text(activity.get("endDate"))

        for group in expanded_groups(activity):
            group_id = ref_id(group.get("id"))
            if not group_id:
                raise ValueError(
                    f"Activity {course_id!r} has an expanded group without id"
                )
            name = text(group.get("displayName"))
            if not name:
                raise ValueError(
                    f"Expanded group {group_id!r} has no displayName"
                )
            generated.append(
                {
                    "section_id": f"{course_id}_{group_id}",
                    "course_id": course_id,
                    "name": name,
                    "status": "active",
                    "start_date": start_date,
                    "end_date": end_date,
                }
            )

    return generated


def write_sections(path: Path, section_rows: list[dict[str, str]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=COLUMNS,
            extrasaction="ignore",
            delimiter=",",
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        writer.writerows(section_rows)
    return len(section_rows)


def main() -> int:
    args = arguments()
    try:
        activities = extract_collection(
            load_json(Path(args.activities)), ("activities",)
        )
        section_rows = rows(activities)
        if activities and not section_rows:
            raise ValueError(
                "Activities contains records, but no groups could be converted "
                "to sections"
            )
        count = write_sections(Path(args.output), section_rows)
        print(
            f"Created {args.output} with {count} rows from "
            f"{len(activities)} activities."
        )
        return 0
    except Exception as exc:
        print(f"Could not create sections CSV: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
