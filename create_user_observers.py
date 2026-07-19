from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Iterator

from ss12000_common import as_list, canvas_status, extract_collection, load_json, ref_id, text, unique_rows, write_csv


COLUMNS = ["observer_id", "student_id", "status"]


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--persons", required=True)
    parser.add_argument("--output", default="output/user_observers.csv")
    return parser.parse_args()


def relationship_refs(person: dict[str, Any], person_id: str) -> Iterator[dict[str, str]]:
    # Student-centric fields: each reference identifies an observing adult.
    for field in ("responsiblePersons", "guardians", "parents", "contacts"):
        for relation in as_list(person.get(field)):
            observer_id = ref_id(relation)
            if observer_id and observer_id != person_id:
                yield {"observer_id": observer_id, "student_id": person_id, "status": canvas_status(relation.get("status") if isinstance(relation, dict) else None)}

    # Observer-centric field: each reference identifies an observed student.
    for field in ("responsibleFor", "students", "children"):
        for relation in as_list(person.get(field)):
            student_id = ref_id(relation)
            if student_id and student_id != person_id:
                yield {"observer_id": person_id, "student_id": student_id, "status": canvas_status(relation.get("status") if isinstance(relation, dict) else None)}

    # Generic relationship representations.
    for relation in as_list(person.get("relationships")) + as_list(person.get("relations")):
        if not isinstance(relation, dict):
            continue
        kind = text(relation.get("type") or relation.get("relationType") or relation.get("role")).casefold()
        other_id = ref_id(relation.get("person") or relation.get("relatedPerson") or relation.get("target"))
        if not other_id:
            continue
        if any(word in kind for word in ("guardian", "parent", "responsible", "vårdnad")):
            direction = text(relation.get("direction")).casefold()
            if direction in {"child", "student", "responsiblefor"}:
                observer_id, student_id = person_id, other_id
            else:
                observer_id, student_id = other_id, person_id
            yield {"observer_id": observer_id, "student_id": student_id, "status": canvas_status(relation.get("status"))}


def rows(persons: list[dict[str, Any]]) -> list[dict[str, str]]:
    person_ids = {ref_id(person.get("id")) for person in persons}
    generated = []
    for person in persons:
        person_id = ref_id(person.get("id"))
        if person_id:
            generated.extend(relationship_refs(person, person_id))
    # Keep only relationships whose two users exist in users_filtered.csv.
    generated = [row for row in generated if row["observer_id"] in person_ids and row["student_id"] in person_ids]
    return list(unique_rows(generated, ("observer_id", "student_id")))


def main() -> int:
    args = arguments()
    try:
        persons = extract_collection(load_json(Path(args.persons)), ("persons",))
        count = write_csv(Path(args.output), COLUMNS, rows(persons))
        print(f"Created {args.output} with {count} rows.")
        return 0
    except Exception as exc:
        print(f"Could not create user_observers CSV: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

