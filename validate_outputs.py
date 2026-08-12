from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path


REQUIRED_COLUMNS = {
    "users_filtered.csv": ("user_id", "login_id", "first_name", "last_name", "full_name", "short_name", "email", "status", "authentication_provider_id"),
    "user_observers.csv": ("observer_id", "student_id", "status"),
    "sections.csv": ("section_id", "course_id", "name", "status", "start_date", "end_date"),
    "enrollments.csv": ("course_id", "start_date", "end_date", "user_id", "role", "section_id", "status"),
    "courses.csv": ("course_id", "short_name", "long_name", "account_id", "term_id", "status", "start_date", "end_date", "course_format"),
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

    # All user references use the first eduPersonPrincipalNames value.
    user_ids = {
        row["user_id"]
        for row in data.get("users_filtered.csv", [])
        if row.get("user_id")
    }
    course_ids = {row["course_id"] for row in data.get("courses.csv", [])}
    section_ids = {row["section_id"] for row in data.get("sections.csv", [])}
    for row in data.get("users_filtered.csv", []):
        if not row["user_id"] or row["user_id"] != row["login_id"]:
            errors.append(f"User has invalid EPPN identifiers: {row}")
        if row["status"] not in {"active", "suspended"}:
            errors.append(f"User has invalid status: {row}")
    for row in data.get("user_observers.csv", []):
        if row["observer_id"] not in user_ids or row["student_id"] not in user_ids:
            errors.append(f"Observer relationship references an unknown user: {row}")
        if row["status"] not in {"active", "inactive"}:
            errors.append(f"Observer relationship has invalid status: {row}")
    for row in data.get("sections.csv", []):
        if row["course_id"] not in course_ids:
            errors.append(f"Section references an unknown course: {row}")
        if not row["section_id"].startswith(f"{row['course_id']}_"):
            errors.append(f"Section has invalid composite section_id: {row}")
        if row["status"] != "active":
            errors.append(f"Section has invalid status: {row}")
    for row in data.get("enrollments.csv", []):
        if row["user_id"] not in user_ids:
            errors.append(f"Enrollment references an unknown user: {row}")
        if row["course_id"] not in course_ids:
            errors.append(f"Enrollment references an unknown course: {row}")
        if row["section_id"] not in section_ids:
            errors.append(f"Enrollment references an unknown section: {row}")
        if row["role"] not in {"teacher", "student"}:
            errors.append(f"Enrollment has invalid role: {row}")
        if row["status"] not in {"active", "completed"}:
            errors.append(f"Enrollment has invalid status: {row}")
    seen_courses: set[tuple[str, ...]] = set()
    course_columns = REQUIRED_COLUMNS["courses.csv"]
    for row in data.get("courses.csv", []):
        identity = tuple(row[column] for column in course_columns)
        if identity in seen_courses:
            errors.append(f"courses.csv contains an identical duplicate row: {row}")
        seen_courses.add(identity)
        if not re.fullmatch(r"\d{2}_\d{2}_\d+", row["term_id"]):
            errors.append(f"Course has invalid term_id: {row}")
        if row["status"] not in {"active", "completed"}:
            errors.append(f"Course has invalid status: {row}")
    if errors:
        for error in errors:
            print(f"Validation error: {error}", file=sys.stderr)
        return 1
    print("All generated CSV files passed structural validation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
