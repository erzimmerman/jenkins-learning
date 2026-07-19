from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ss12000_common import activity_name, canvas_status, course_id_for, extract_collection, iso_date, load_json, ref_id, unique_rows, write_csv


COLUMNS = ["section_id", "course_id", "name", "status", "integration_id", "start_date", "end_date"]


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--activities", required=True)
    parser.add_argument("--output", default="output/sections.csv")
    return parser.parse_args()


def rows(activities: list[dict]) -> list[dict[str, str]]:
    generated = []
    for activity in activities:
        generated.append({
            "section_id": ref_id(activity.get("id")),
            "course_id": course_id_for(activity),
            "name": activity_name(activity),
            "status": canvas_status(activity.get("status") or activity.get("activityStatus")),
            "integration_id": "",
            "start_date": iso_date(activity.get("startDate")),
            "end_date": iso_date(activity.get("endDate")),
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

