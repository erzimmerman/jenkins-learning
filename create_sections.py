from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ss12000_common import canvas_status, extract_collection, first_value, iso_date, load_json, ref_id, unique_rows, write_csv


COLUMNS = ["section_id", "course_id", "name", "status", "integration_id", "start_date", "end_date"]


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--activities", required=True)
    parser.add_argument("--output", default="output/sections.csv")
    return parser.parse_args()


def rows(activities: list[dict]) -> list[dict[str, str]]:
    generated = []
    for activity in activities:
        course_id = ref_id(activity.get("id"))
        embedded = activity.get("_embedded")
        groups = embedded.get("groups") if isinstance(embedded, dict) else None
        if not isinstance(groups, list):
            groups = activity.get("groups")
        for group in groups if isinstance(groups, list) else []:
            if not isinstance(group, dict):
                continue
            generated.append({
                "section_id": ref_id(group.get("id")),
                "course_id": course_id,
                "name": first_value(group.get("displayName") or group.get("name")) or ref_id(group.get("id")),
                "status": canvas_status(group.get("status") or activity.get("status") or activity.get("activityStatus")),
                "integration_id": "",
                "start_date": iso_date(group.get("startDate") or activity.get("startDate")),
                "end_date": iso_date(group.get("endDate") or activity.get("endDate")),
            })
    return list(unique_rows(generated, ("section_id", "course_id")))


def main() -> int:
    args = arguments()
    try:
        activities = extract_collection(load_json(Path(args.activities)), ("activities",))
        count = write_csv(Path(args.output), COLUMNS, rows(activities))
        print(f"Created {args.output} with {count} rows.")
        return 0
    except Exception as exc:
        print(f"Could not create sections CSV: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
