from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

from ss12000_common import as_list, extract_collection, first_value, load_json, ref_id, text


COLUMNS = ["observer_id", "student_id", "status"]


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create user_observers.csv from SS12000 Persons."
    )
    parser.add_argument("--persons", required=True)
    parser.add_argument("--output", default="output/user_observers.csv")
    return parser.parse_args()


def is_student(person: dict[str, Any]) -> bool:
    """A person is a student when any external identifier has studentguid context."""
    for identifier in as_list(person.get("externalIdentifiers")):
        if not isinstance(identifier, dict):
            continue
        if text(identifier.get("context")).casefold() == "studentguid":
            return True
    return False


def eppn_index(persons: list[dict[str, Any]]) -> dict[str, str]:
    """Map Person.id to the first non-empty eduPersonPrincipalNames value."""
    result: dict[str, str] = {}
    for person in persons:
        person_id = ref_id(person.get("id"))
        eppn = first_value(person.get("eduPersonPrincipalNames"))
        if person_id and eppn:
            result[person_id] = eppn
    return result


def observer_status(person: dict[str, Any]) -> str:
    return "active" if text(person.get("personStatus")).casefold() == "aktiv" else "inactive"


def rows(persons: list[dict[str, Any]]) -> list[dict[str, str]]:
    person_eppns = eppn_index(persons)
    generated: list[dict[str, str]] = []

    for student in persons:
        if not is_student(student):
            continue

        student_id = first_value(student.get("eduPersonPrincipalNames"))
        if not student_id:
            # The prompt explicitly says to omit rows with an empty student_id.
            continue

        status = observer_status(student)

        for responsible in as_list(student.get("responsibles")):
            if not isinstance(responsible, dict):
                continue
            if text(responsible.get("relationType")).casefold() != "vårdnadshavare":
                continue

            responsible_person_id = ref_id(responsible.get("person"))
            observer_id = person_eppns.get(responsible_person_id, "")

            # The prompt explicitly says to omit rows with an empty observer_id.
            if not observer_id:
                continue

            generated.append({
                "observer_id": observer_id,
                "student_id": student_id,
                "status": status,
            })

    return generated


def write_observers(path: Path, observer_rows: list[dict[str, str]]) -> int:
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
        writer.writerows(observer_rows)
    return len(observer_rows)


def main() -> int:
    args = arguments()
    try:
        persons = extract_collection(load_json(Path(args.persons)), ("persons",))
        count = write_observers(Path(args.output), rows(persons))
        print(f"Created {args.output} with {count} rows.")
        return 0
    except Exception as exc:
        print(f"Could not create user_observers CSV: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
