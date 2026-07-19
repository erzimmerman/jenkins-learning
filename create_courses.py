from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ss12000_common import activity_name, canvas_status, extract_collection, iso_date, load_json, nested, ref_id, unique_rows, write_csv


COLUMNS = ["course_id", "short_name", "long_name", "account_id", "term_id", "status", "start_date", "end_date"]


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--activities", required=True)
    parser.add_argument("--output", default="output/courses.csv")
    return parser.parse_args()


def rows(activities: list[dict]) -> list[dict[str, str]]:
    generated = []
    for activity in activities:
        course_id = ref_id(activity.get("id"))
        name = activity_name(activity) or course_id
        generated.append({
            "course_id": course_id,
            "short_name": name,
            "long_name": name,
            "account_id": ref_id(nested(activity, "organisation", "organization")),
            "term_id": ref_id(nested(activity, "term", "schoolYear", "academicSession")),
            "status": canvas_status(activity.get("status") or activity.get("activityStatus")),
            "start_date": iso_date(activity.get("startDate")),
            "end_date": iso_date(activity.get("endDate")),
        })
    return list(unique_rows(generated, ("course_id",)))


def main() -> int:
    args = arguments()
    try:
        activities = extract_collection(load_json(Path(args.activities)), ("activities",))
        count = write_csv(Path(args.output), COLUMNS, rows(activities))
        print(f"Created {args.output} with {count} rows.")
        return 0
    except Exception as exc:
        print(f"Could not create courses CSV: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
