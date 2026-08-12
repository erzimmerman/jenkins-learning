from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

from ss12000_common import as_list, extract_collection, first_value, load_json, nested, ref_id, text


COLUMNS = [
    "user_id",
    "login_id",
    "first_name",
    "last_name",
    "full_name",
    "short_name",
    "email",
    "status",
    "authentication_provider_id",
]


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create users_filtered.csv from SS12000 Persons."
    )
    parser.add_argument("--persons", required=True)
    parser.add_argument("--output", default="output/users_filtered.csv")
    return parser.parse_args()


def contains_school_type(value: Any, expected: str) -> bool:
    for item in as_list(value):
        if not isinstance(item, dict):
            continue
        if text(item.get("schoolType")).casefold() == expected.casefold():
            return True
    return False


def excluded_student(person: dict[str, Any]) -> bool:
    """Exclude preschool (FS) and higher vocational education (YH) students."""
    placements = nested(person, "_embedded.placements")
    if contains_school_type(placements, "FS"):
        return True

    # The documented response has enrolments directly on Person. Keep the
    # embedded fallback for installations that expand this relation there.
    enrolments = nested(person, "enrolments", "_embedded.enrolments")
    return contains_school_type(enrolments, "YH")


def user_status(person_status: Any) -> str:
    return "active" if text(person_status).casefold() == "aktiv" else "suspended"


def is_student(person: dict[str, Any]) -> bool:
    for identifier in as_list(person.get("externalIdentifiers")):
        if not isinstance(identifier, dict):
            continue
        if text(identifier.get("context")).casefold() == "studentguid":
            return True
    return False


def is_preschool_student(person: dict[str, Any]) -> bool:
    return contains_school_type(nested(person, "_embedded.placements"), "FS")


def guardian_ids_by_child_school_type(
    persons: list[dict[str, Any]],
) -> tuple[set[str], set[str]]:
    preschool_guardians: set[str] = set()
    other_guardians: set[str] = set()

    for student in persons:
        if not is_student(student):
            continue
        target = preschool_guardians if is_preschool_student(student) else other_guardians
        for responsible in as_list(student.get("responsibles")):
            if not isinstance(responsible, dict):
                continue
            if text(responsible.get("relationType")).casefold() != "vårdnadshavare":
                continue
            guardian_id = ref_id(responsible.get("person"))
            if guardian_id:
                target.add(guardian_id)

    return preschool_guardians, other_guardians


def has_duties(person: dict[str, Any]) -> bool:
    return bool(as_list(nested(person, "_embedded.duties", "duties")))


def included_person_ids(persons: list[dict[str, Any]]) -> set[str]:
    """Return Person.id values that will actually exist in users_filtered.csv."""
    preschool_guardians, other_guardians = guardian_ids_by_child_school_type(persons)
    preschool_only_guardians = preschool_guardians - other_guardians
    included: set[str] = set()

    for person in persons:
        if excluded_student(person):
            continue

        person_id = ref_id(person.get("id"))
        if person_id in preschool_only_guardians and not is_student(person) and not has_duties(person):
            continue
        if not person_id or not first_value(person.get("eduPersonPrincipalNames")):
            continue
        included.add(person_id)

    return included


def rows(persons: list[dict[str, Any]]) -> list[dict[str, str]]:
    generated: list[dict[str, str]] = []
    included = included_person_ids(persons)

    for person in persons:
        person_id = ref_id(person.get("id"))
        if person_id not in included:
            continue

        eppn = first_value(person.get("eduPersonPrincipalNames"))
        first_name = text(person.get("givenName"))
        last_name = text(person.get("familyName"))
        full_name = " ".join(
            value for value in (first_name, last_name) if value
        )

        generated.append(
            {
                "user_id": eppn,
                "login_id": eppn,
                "first_name": first_name,
                "last_name": last_name,
                "full_name": full_name,
                "short_name": full_name,
                "email": first_value(person.get("emails")),
                "status": user_status(person.get("personStatus")),
                "authentication_provider_id": "",
            }
        )

    return generated


def write_users(path: Path, user_rows: list[dict[str, str]]) -> int:
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
        writer.writerows(user_rows)
    return len(user_rows)


def main() -> int:
    args = arguments()
    try:
        persons = extract_collection(load_json(Path(args.persons)), ("persons",))
        count = write_users(Path(args.output), rows(persons))
        print(f"Created {args.output} with {count} rows.")
        return 0
    except Exception as exc:
        print(f"Could not create users CSV: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
