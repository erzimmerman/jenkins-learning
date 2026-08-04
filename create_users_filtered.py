from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

from ss12000_common import as_list, extract_collection, first_value, load_json, nested, text


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


def rows(persons: list[dict[str, Any]]) -> list[dict[str, str]]:
    generated: list[dict[str, str]] = []

    for person in persons:
        if excluded_student(person):
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
