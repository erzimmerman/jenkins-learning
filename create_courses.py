from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path
from typing import Any

from ss12000_common import extract_collection, load_json, nested, ref_id, text


COLUMNS = [
    "course_id",
    "short_name",
    "long_name",
    "account_id",
    "term_id",
    "status",
    "start_date",
    "end_date",
    "course_format",
]


ACCOUNT_IDS = {
    "Förskola": "41",
    "Grundskola": "42",
    "Gymnasium": "40",
    "Lärande": "0",
    "Yrkeshögskola": "43",
    "Consensum Yrkeshögskola": "8",
    "Lärande Förskola Omvärlden": "1",
    "Lärande Förskola Skogstorp": "2",
    "Lärande Förskola Skutan": "3",
    "Lärande Grundskola Fresta": "10",
    "Lärande Grundskola Magneten": "11",
    "Lärande Grundskola Oden": "12",
    "Lärande Grundskola Skapa": "13",
    "Lärande Grundskola Södra": "14",
    "Lärande Grundskola Vira": "15",
    "Lärande Grundskola Östra": "16",
    "Realgymnasiet Borlänge": "17",
    "Realgymnasiet Borås": "18",
    "Realgymnasiet Eskilstuna": "19",
    "Realgymnasiet Gävle": "20",
    "Realgymnasiet Göteborg": "21",
    "Realgymnasiet Halmstad": "22",
    "Realgymnasiet Helsingborg": "23",
    "Realgymnasiet Karlstad": "24",
    "Realgymnasiet Linköping": "25",
    "Realgymnasiet Luleå": "26",
    "Realgymnasiet Lund": "27",
    "Realgymnasiet Lund 2": "28",
    "Realgymnasiet Malmö": "29",
    "Realgymnasiet Norrköping": "30",
    "Realgymnasiet Nyköping": "31",
    "Realgymnasiet Skövde": "33",
    "Realgymnasiet Stockholm": "32",
    "Realgymnasiet Sundbyberg": "44",
    "Realgymnasiet Sundsvall": "34",
    "Realgymnasiet Trollhättan": "35",
    "Realgymnasiet Uppsala": "36",
    "Realgymnasiet Västerås": "38",
    "Realgymnasiet Växjö": "37",
    "Realgymnasiet Örebro": "39",
    "Snickarbarnen Charlottendal": "5",
    "Snickarbarnen Häggvik": "7",
    "Snickarbarnen Mölnvik": "4",
    "Snickarbarnen Sjöberg": "6",
    "Testskola": "45",
    "Yrkeshögskolan SKY": "9",
}


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create courses.csv from SS12000 Activities."
    )
    parser.add_argument("--activities", required=True)
    parser.add_argument("--output", default="output/courses.csv")
    return parser.parse_args()


def embedded_groups(activity: dict[str, Any]) -> list[dict[str, Any]]:
    embedded = activity.get("_embedded")
    if isinstance(embedded, dict):
        groups = embedded.get("groups")
        if isinstance(groups, list):
            return [group for group in groups if isinstance(group, dict)]

    # Tolerate implementations that return expanded groups directly.
    groups = activity.get("groups")
    if isinstance(groups, list):
        return [group for group in groups if isinstance(group, dict)]
    return []


def account_id_for(activity: dict[str, Any]) -> str:
    display_name = text(
        nested(
            activity,
            "organisation.displayName",
            "organization.displayName",
        )
    )
    account_id = ACCOUNT_IDS.get(display_name)
    if account_id is None:
        raise ValueError(
            f"Unknown organisation.displayName {display_name!r} for Activity "
            f"{ref_id(activity.get('id'))!r}"
        )
    return account_id


def names_for(
    activity: dict[str, Any],
    groups: list[dict[str, Any]],
) -> tuple[str, str]:
    school_type = text(
        nested(
            activity,
            "_embedded.syllabus.schoolType",
            "syllabus.schoolType",
        )
    ).upper()

    if school_type == "GR":
        short_name = text(
            nested(
                activity,
                "_embedded.syllabus.subjectName",
                "_embedded.syllabus.subjectname",
                "syllabus.subjectName",
                "syllabus.subjectname",
            )
        )
        long_name = short_name
    elif school_type == "GY":
        group_names = [text(group.get("displayName")) for group in groups]
        group_names = [name for name in group_names if name]
        syllabus_name = text(nested(activity, "syllabus.displayName"))
        short_name = ",".join([*group_names, syllabus_name] if syllabus_name else group_names)
        long_name = text(
            nested(
                activity,
                "_embedded.syllabus.courseName",
                "_embedded.syllabus.coursename",
                "syllabus.syllabus.courseName",
                "syllabus.syllabus.coursename",
                "syllabus.courseName",
                "syllabus.coursename",
            )
        ) or short_name
    else:
        raise ValueError(
            f"Unsupported syllabus.schoolType {school_type!r} for Activity "
            f"{ref_id(activity.get('id'))!r}; expected 'GR' or 'GY'"
        )

    if not short_name:
        raise ValueError(
            f"Could not create short_name for Activity {ref_id(activity.get('id'))!r}"
        )
    return short_name, long_name or short_name


def term_id_for(group: dict[str, Any], account_id: str, course_id: str) -> str:
    raw_start_date = text(group.get("startDate"))
    try:
        group_start = date.fromisoformat(raw_start_date[:10])
    except ValueError as exc:
        raise ValueError(
            f"Invalid or missing group.startDate {raw_start_date!r} for "
            f"Activity {course_id!r}"
        ) from exc

    if (group_start.month, group_start.day) <= (6, 30):
        first_year = group_start.year - 1
        second_year = group_start.year
    else:
        first_year = group_start.year
        second_year = group_start.year + 1

    return f"{first_year % 100:02d}_{second_year % 100:02d}_{account_id}"


def course_status(end_date: Any) -> str:
    raw_end_date = text(end_date)
    if not raw_end_date:
        return "active"
    try:
        parsed_end_date = date.fromisoformat(raw_end_date[:10])
    except ValueError as exc:
        raise ValueError(f"Invalid Activity.endDate: {raw_end_date!r}") from exc
    return "completed" if parsed_end_date < date.today() else "active"


def rows(activities: list[dict[str, Any]]) -> list[dict[str, str]]:
    generated: list[dict[str, str]] = []

    for activity in activities:
        course_id = ref_id(activity.get("id"))
        if not course_id:
            raise ValueError("An Activity is missing id")

        groups = embedded_groups(activity)
        if not groups:
            continue

        account_id = account_id_for(activity)
        short_name, long_name = names_for(activity, groups)
        start_date = text(activity.get("startDate"))
        end_date = text(activity.get("endDate"))

        for group in groups:
            generated.append(
                {
                    "course_id": course_id,
                    "short_name": short_name,
                    "long_name": long_name,
                    "account_id": account_id,
                    "term_id": term_id_for(group, account_id, course_id),
                    "status": course_status(end_date),
                    "start_date": start_date,
                    "end_date": end_date,
                    "course_format": "",
                }
            )

    # Remove only completely identical rows, including rows whose course_format is empty.
    unique: list[dict[str, str]] = []
    seen: set[tuple[str, ...]] = set()
    for row in generated:
        identity = tuple(row[column] for column in COLUMNS)
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(row)
    return unique


def write_courses(path: Path, course_rows: list[dict[str, str]]) -> int:
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
        writer.writerows(course_rows)
    return len(course_rows)


def main() -> int:
    args = arguments()
    try:
        activities = extract_collection(
            load_json(Path(args.activities)), ("activities",)
        )
        course_rows = rows(activities)
        if activities and not course_rows:
            raise ValueError(
                "Activities contains records, but none has an expanded group that "
                "can be converted to a course"
            )
        count = write_courses(Path(args.output), course_rows)
        print(f"Created {args.output} with {count} rows.")
        return 0
    except Exception as exc:
        print(f"Could not create courses CSV: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
