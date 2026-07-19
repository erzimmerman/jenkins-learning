from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ss12000_common import canvas_status, extract_collection, first_value, load_json, ref_id, text, unique_rows, write_csv


COLUMNS = [
    "user_id", "login_id", "first_name", "last_name", "full_name",
    "short_name", "email", "status", "authentication_provider_id",
]


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--persons", required=True)
    parser.add_argument("--output", default="output/users_filtered.csv")
    return parser.parse_args()


def rows(persons: list[dict]) -> list[dict[str, str]]:
    result = []
    for person in persons:
        first = text(person.get("givenName"))
        last = text(person.get("familyName"))
        full = " ".join(part for part in (first, last) if part)
        result.append({
            "user_id": ref_id(person.get("id")),
            "login_id": first_value(person.get("eduPersonPrincipalNames")),
            "first_name": first,
            "last_name": last,
            "full_name": full,
            "short_name": full,
            "email": first_value(person.get("emails")),
            "status": canvas_status(person.get("personStatus")),
            "authentication_provider_id": "",
        })
    return list(unique_rows(result, ("user_id", "login_id")))


def main() -> int:
    args = arguments()
    try:
        persons = extract_collection(load_json(Path(args.persons)), ("persons",))
        count = write_csv(Path(args.output), COLUMNS, rows(persons))
        print(f"Created {args.output} with {count} rows.")
        return 0
    except Exception as exc:
        print(f"Could not create users CSV: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
