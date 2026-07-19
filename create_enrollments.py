from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Iterator

from ss12000_common import as_list, canvas_status, course_id_for, duty_to_person_index, extract_collection, load_json, nested, ref_id, text, unique_rows, write_csv


COLUMNS = ["course_id", "user_id", "role", "section_id", "status", "associated_user_id"]


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--persons", required=True)
    parser.add_argument("--activities", required=True)
    parser.add_argument("--output", default="output/enrollments.csv")
    return parser.parse_args()


def role_name(value: Any, default: str) -> str:
    raw = text(value).casefold()
    if any(word in raw for word in ("teacher", "lärare", "educator", "staff")):
        return "teacher"
    if any(word in raw for word in ("student", "elev", "learner", "member")):
        return "student"
    if any(word in raw for word in ("observer", "guardian", "parent", "vårdnad")):
        return "observer"
    if raw in {"ta", "assistant", "assistent"}:
        return "ta"
    return default


def direct_members(activity: dict[str, Any], duty_index: dict[str, str]) -> Iterator[tuple[str, str, str]]:
    fields = {
        "students": "student",
        "studentAssignments": "student",
        "members": "student",
        "participants": "student",
        "persons": "student",
        "teachers": "teacher",
        "teacherAssignments": "teacher",
        "staff": "teacher",
    }
    for field, default_role in fields.items():
        for member in as_list(activity.get(field)):
            if not isinstance(member, dict):
                member = {"person": member}
            direct_person = member.get("person") or member.get("student") or member.get("teacher")
            if direct_person is not None:
                person_id = ref_id(direct_person)
            elif default_role == "teacher" and member.get("duty") is not None:
                person_id = duty_index.get(ref_id(member.get("duty")), "")
            else:
                person_id = ref_id(member)
            if person_id:
                yield person_id, role_name(member.get("role") or member.get("type"), default_role), canvas_status(member.get("status"))

    # Some implementations embed group memberships below Activity.groups.
    for group in as_list(activity.get("groups")):
        if not isinstance(group, dict):
            continue
        for member in as_list(group.get("groupMemberships")) + as_list(group.get("members")):
            if isinstance(member, dict):
                person_id = ref_id(member.get("person") or member)
                if person_id:
                    yield person_id, role_name(member.get("role"), "student"), canvas_status(member.get("status"))


def person_activity_memberships(persons: list[dict[str, Any]]) -> Iterator[tuple[str, str, str, str]]:
    for person in persons:
        person_id = ref_id(person.get("id"))
        if not person_id:
            continue
        for field in ("activities", "activityMemberships", "memberships", "activityAssignments"):
            for membership in as_list(person.get(field)):
                if not isinstance(membership, dict):
                    continue
                activity_id = ref_id(membership.get("activity") or membership)
                if activity_id:
                    yield activity_id, person_id, role_name(membership.get("role") or membership.get("type"), "student"), canvas_status(membership.get("status"))


def rows(persons: list[dict[str, Any]], activities: list[dict[str, Any]]) -> list[dict[str, str]]:
    person_ids = {ref_id(person.get("id")) for person in persons}
    activities_by_id = {ref_id(activity.get("id")): activity for activity in activities}
    duty_index = duty_to_person_index(persons)
    generated: list[dict[str, str]] = []

    for activity_id, activity in activities_by_id.items():
        for person_id, role, status in direct_members(activity, duty_index):
            if person_id in person_ids:
                generated.append({
                    "course_id": course_id_for(activity), "user_id": person_id,
                    "role": role, "section_id": activity_id, "status": status,
                    "associated_user_id": "",
                })

    for activity_id, person_id, role, status in person_activity_memberships(persons):
        activity = activities_by_id.get(activity_id)
        if activity:
            generated.append({
                "course_id": course_id_for(activity), "user_id": person_id,
                "role": role, "section_id": activity_id, "status": status,
                "associated_user_id": "",
            })

    return list(unique_rows(generated, ("section_id", "user_id", "role")))


def main() -> int:
    args = arguments()
    try:
        persons = extract_collection(load_json(Path(args.persons)), ("persons",))
        activities = extract_collection(load_json(Path(args.activities)), ("activities",))
        count = write_csv(Path(args.output), COLUMNS, rows(persons, activities))
        print(f"Created {args.output} with {count} rows.")
        return 0
    except Exception as exc:
        print(f"Could not create enrollments CSV: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
