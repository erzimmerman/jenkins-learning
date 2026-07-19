from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


REQUIRED_COLUMNS = {
    "users_filtered.csv": ("user_id", "login_id", "first_name", "last_name", "full_name", "short_name", "email", "status", "authentication_provider_id"),
    "user_observers.csv": ("observer_id", "student_id", "status"),
    "sections.csv": ("section_id", "course_id", "name", "status", "integration_id", "start_date", "end_date"),
    "enrollments.csv": ("course_id", "start_date", "end_date", "user_id", "role", "section_id", "status"),
    "courses.csv": ("course_id", "short_name", "long_name", "account_id", "term_id", "status", "start_date", "end_date"),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="output")
    output_dir = Path(parser.parse_args().output_dir)
    errors: list[str] = []
    data: dict[str, list[dict[str, str]]] = {}
    for filename, expected in REQUIRED_COLUMNS.items():
        path = output_dir / filename
        if not path.is_file():
            errors.append(f"Missing {path}")
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != expected:
                errors.append(f"Wrong header in {path}: {reader.fieldnames}")
                continue
            rows = list(reader)
            data[filename] = rows
        print(f"Validated {filename}: {len(rows)} data rows")
        if filename in {"users_filtered.csv", "sections.csv", "courses.csv"} and not rows:
            errors.append(f"{path} contains no data rows")

    # enrollments.csv deliberately uses EPPN as user_id according to the
    # integration mapping. In users_filtered.csv that value is login_id, while
    # Person.id is stored in user_id, so accept both identifiers here.
    user_ids = {
        value
        for row in data.get("users_filtered.csv", [])
        for value in (row.get("user_id", ""), row.get("login_id", ""))
        if value
    }
    course_ids = {row["course_id"] for row in data.get("courses.csv", [])}
    section_ids = {row["section_id"] for row in data.get("sections.csv", [])}
    for row in data.get("user_observers.csv", []):
        if row["observer_id"] not in user_ids or row["student_id"] not in user_ids:
            errors.append(f"Observer relationship references an unknown user: {row}")
    for row in data.get("sections.csv", []):
        if row["course_id"] not in course_ids:
            errors.append(f"Section references an unknown course: {row}")
    for row in data.get("enrollments.csv", []):
        if row["user_id"] not in user_ids:
            errors.append(f"Enrollment references an unknown user: {row}")
        if row["course_id"] not in course_ids:
            errors.append(f"Enrollment references an unknown course: {row}")
        if row["section_id"] not in section_ids:
            errors.append(f"Enrollment references an unknown section: {row}")
    if errors:
        for error in errors:
            print(f"Validation error: {error}", file=sys.stderr)
        return 1
    print("All generated CSV files passed structural validation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
