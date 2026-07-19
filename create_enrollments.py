from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path
from typing import Any

from ss12000_common import as_list, extract_collection, first_value, load_json, ref_id, text


COLUMNS = [
    "course_id",
    "start_date",
    "end_date",
    "user_id",
    "role",
    "section_id",
    "status",
]


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create enrollments.csv from SS12000 Activities and Persons."
    )
    parser.add_argument("--persons", required=True)
    parser.add_argument("--activities", required=True)
    parser.add_argument("--output", default="output/enrollments.csv")
    return parser.parse_args()


def person_user_ids(persons: list[dict[str, Any]]) -> dict[str, str]:
    """Map SS12000 Person.id to the first eduPersonPrincipalNames value."""
    result: dict[str, str] = {}
    for person in persons:
        person_id = ref_id(person.get("id"))
        user_id = first_value(person.get("eduPersonPrincipalNames"))
        if person_id and user_id:
            result[person_id] = user_id
    return result


def embedded_groups(activity: dict[str, Any]) -> list[dict[str, Any]]:
    embedded = activity.get("_embedded")
    if isinstance(embedded, dict):
        groups = embedded.get("groups")
        if isinstance(groups, list):
            return [group for group in groups if isinstance(group, dict)]

    # Kept as a fallback for SS12000 implementations returning expanded groups
    # directly on the activity instead of below _embedded.
    groups = activity.get("groups")
    if isinstance(groups, list):
        return [group for group in groups if isinstance(group, dict)]
    return []


def enrollment_status(end_date: Any) -> str:
    value = text(end_date)
    if not value:
        return "active"
    try:
        parsed = date.fromisoformat(value[:10])
    except ValueError as exc:
        raise ValueError(f"Invalid Activity.endDate: {value!r}") from exc
    return "completed" if parsed < date.today() else "active"


def lookup_user_id(index: dict[str, str], person_id: str, context: str) -> str:
    if not person_id:
        raise ValueError(f"Missing person.id for {context}")
    user_id = index.get(person_id)
    if not user_id:
        raise ValueError(
            f"Person {person_id!r}, referenced by {context}, was not found in "
            "Persons or has no eduPersonPrincipalNames value"
        )
    return user_id


def base_row(activity: dict[str, Any]) -> dict[str, str]:
    course_id = ref_id(activity.get("id"))
    if not course_id:
        raise ValueError("An activity is missing id")
    start_date = text(activity.get("startDate"))
    end_date = text(activity.get("endDate"))
    return {
        "course_id": course_id,
        "start_date": start_date,
        "end_date": end_date,
        "status": enrollment_status(end_date),
    }


def rows(
    persons: list[dict[str, Any]],
    activities: list[dict[str, Any]],
) -> list[dict[str, str]]:
    user_ids = person_user_ids(persons)
    generated: list[dict[str, str]] = []

    for activity in activities:
        base = base_row(activity)
        groups = embedded_groups(activity)
        group_ids = [ref_id(group.get("id")) for group in groups]
        group_ids = [group_id for group_id in group_ids if group_id]

        teachers = [teacher for teacher in as_list(activity.get("teachers")) if isinstance(teacher, dict)]
        if teachers and not group_ids:
            raise ValueError(
                f"Activity {base['course_id']!r} has teachers but no expanded group id "
                "to use as section_id"
            )
        if len(group_ids) > 1 and teachers:
            print(
                f"Activity {base['course_id']} has multiple groups; teacher enrollments "
                f"use the first group, {group_ids[0]}.",
                file=sys.stderr,
            )

        # Exactly one row for every teacher on the activity.
        for teacher in teachers:
            person_id = ref_id(teacher.get("person"))
            generated.append({
                **base,
                "user_id": lookup_user_id(
                    user_ids, person_id, f"Activity {base['course_id']} teachers"
                ),
                "role": "teacher",
                "section_id": group_ids[0],
            })

        # Exactly one row for every student group membership. The group that
        # contains the membership supplies section_id.
        for group in groups:
            section_id = ref_id(group.get("id"))
            if not section_id:
                raise ValueError(
                    f"An expanded group in Activity {base['course_id']!r} is missing id"
                )
            memberships = group.get("groupMemberships")
            if memberships is None:
                memberships = group.get("groupmemberships")
            for membership in as_list(memberships):
                if not isinstance(membership, dict):
                    continue
                person_id = ref_id(membership.get("person"))
                generated.append({
                    **base,
                    "user_id": lookup_user_id(
                        user_ids,
                        person_id,
                        f"Activity {base['course_id']} group {section_id} groupMemberships",
                    ),
                    "role": "student",
                    "section_id": section_id,
                })

    return generated


def write_enrollments(path: Path, enrollment_rows: list[dict[str, str]]) -> int:
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
        writer.writerows(enrollment_rows)
    return len(enrollment_rows)


def main() -> int:
    args = arguments()
    try:
        persons = extract_collection(load_json(Path(args.persons)), ("persons",))
        activities = extract_collection(load_json(Path(args.activities)), ("activities",))
        enrollment_rows = rows(persons, activities)
        if activities and not enrollment_rows:
            raise ValueError(
                "Activities contains records, but no teachers or "
                "_embedded.groups.groupMemberships could be converted"
            )
        count = write_enrollments(Path(args.output), enrollment_rows)
        print(f"Created {args.output} with {count} rows.")
        return 0
    except Exception as exc:
        print(f"Could not create enrollments CSV: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
