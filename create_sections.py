from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

from ss12000_common import as_list, extract_collection, load_json, ref_id, text


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
    embedded = activity.get("_embedded")
    if not isinstance(embedded, dict):
        return []
    groups = embedded.get("groups")
    if not isinstance(groups, list):
        return []
    return [group for group in groups if isinstance(group, dict)]


def group_pairs(
    activity: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    """Pair each top-level groups.id with its expanded group details."""
    expanded = expanded_groups(activity)
    expanded_by_id = {
        ref_id(group.get("id")): group
        for group in expanded
        if ref_id(group.get("id"))
    }

    references = [
        reference
        for reference in as_list(activity.get("groups"))
        if isinstance(reference, dict)
    ]

    # The real API normally has references at Activity.groups and details at
    # Activity._embedded.groups. Keep an embedded-only fallback for exports
    # where the reference list has been omitted.
    if not references:
        return [
            (ref_id(group.get("id")), group)
            for group in expanded
            if ref_id(group.get("id"))
        ]

    pairs: list[tuple[str, dict[str, Any]]] = []
    for reference in references:
        section_id = ref_id(reference.get("id"))
        if not section_id:
            raise ValueError("An Activity.groups reference is missing id")
        group = expanded_by_id.get(section_id)
        if group is None:
            raise ValueError(
                f"Group {section_id!r} is referenced by Activity.groups but is "
                "missing from Activity._embedded.groups"
            )
        pairs.append((section_id, group))
    return pairs


def rows(activities: list[dict[str, Any]]) -> list[dict[str, str]]:
    generated: list[dict[str, str]] = []

    for activity in activities:
        course_id = ref_id(activity.get("id"))
        if not course_id:
            raise ValueError("An Activity is missing id")

        start_date = text(activity.get("startDate"))
        end_date = text(activity.get("endDate"))

        for section_id, group in group_pairs(activity):
            name = text(group.get("displayName"))
            if not name:
                raise ValueError(
                    f"Expanded group {section_id!r} has no displayName"
                )
            generated.append(
                {
                    "section_id": f"{course_id}_{section_id}",
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
        print(f"Created {args.output} with {count} rows.")
        return 0
    except Exception as exc:
        print(f"Could not create sections CSV: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
