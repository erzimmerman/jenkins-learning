from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path
from typing import Any

from ss12000_common import as_list, extract_collection, first_value, load_json, nested, ref_id, text


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


def person_index(persons: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        person_id: person
        for person in persons
        if (person_id := ref_id(person.get("id")))
    }


def membership_role(person: dict[str, Any]) -> str:
    duties = nested(person, "_embedded.duties")
    return "teacher" if as_list(duties) else "student"


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


def activity_teachers(activity: dict[str, Any]) -> list[dict[str, Any]]:
    """Return expanded duties, where the actual teacher is available as person.id."""
    embedded = activity.get("_embedded")
    if isinstance(embedded, dict):
        teachers = embedded.get("teachers")
        if isinstance(teachers, list):
            return [teacher for teacher in teachers if isinstance(teacher, dict)]

    # Fallback for implementations that put expanded teachers directly on the
    # activity. Duty-only references without person.id are not usable here.
    teachers = activity.get("teachers")
    if isinstance(teachers, list):
        return [
            teacher
            for teacher in teachers
            if isinstance(teacher, dict) and ref_id(teacher.get("person"))
        ]
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


def lookup_person(
    index: dict[str, dict[str, Any]],
    person_id: str,
    context: str,
) -> dict[str, Any]:
    if not person_id:
        raise ValueError(f"Missing person.id for {context}")
    person = index.get(person_id)
    if person is None:
        raise ValueError(
            f"Person {person_id!r}, referenced by {context}, was not found in Persons"
        )
    return person


def section_id_for(course_id: str, group_id: str) -> str:
    if not group_id:
        raise ValueError(f"Activity {course_id!r} has a group without id")
    return f"{course_id}_{group_id}"


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
    persons_by_id = person_index(persons)
    generated: list[dict[str, str]] = []

    for activity in activities:
        base = base_row(activity)
        groups = embedded_groups(activity)
        group_ids = [ref_id(group.get("id")) for group in groups]
        group_ids = [group_id for group_id in group_ids if group_id]

        # Every group membership becomes a row. Persons._embedded.duties
        # determines whether that membership is a teacher or a student.
        for group in groups:
            group_id = ref_id(group.get("id"))
            section_id = section_id_for(base["course_id"], group_id)
            memberships = group.get("groupMemberships")
            if memberships is None:
                memberships = group.get("groupmemberships")
            for membership in as_list(memberships):
                if not isinstance(membership, dict):
                    continue
                person_id = ref_id(membership.get("person"))
                context = (
                    f"Activity {base['course_id']} group {group_id} "
                    "groupMemberships"
                )
                person = lookup_person(persons_by_id, person_id, context)
                generated.append({
                    **base,
                    "user_id": lookup_user_id(user_ids, person_id, context),
                    "role": membership_role(person),
                    "section_id": section_id,
                })

        # The expanded teachers list may contain teachers that are absent from
        # groupMemberships. It has no group reference, so the activity's first
        # group supplies section_id, matching the established integration rule.
        teachers = activity_teachers(activity)
        if teachers and not group_ids:
            raise ValueError(
                f"Activity {base['course_id']!r} has teachers but no expanded group id "
                "to use as section_id"
            )
        if len(group_ids) > 1 and teachers:
            print(
                f"Activity {base['course_id']} has multiple groups; teachers from "
                f"_embedded.teachers use the first group, {group_ids[0]}.",
                file=sys.stderr,
            )
        for teacher in teachers:
            person_id = ref_id(teacher.get("person"))
            generated.append({
                **base,
                "user_id": lookup_user_id(
                    user_ids,
                    person_id,
                    f"Activity {base['course_id']} _embedded.teachers",
                ),
                "role": "teacher",
                "section_id": section_id_for(base["course_id"], group_ids[0]),
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
