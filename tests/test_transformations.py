import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(script: str, *args: str) -> None:
    subprocess.run([sys.executable, str(ROOT / script), *args], check=True, cwd=ROOT)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class TransformationTests(unittest.TestCase):
    def test_all_transformations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.run_transformations(Path(directory))

    def run_transformations(self, tmp_path: Path) -> None:
        persons = {
            "persons": [
                {"id": "student-1", "givenName": "Anna", "familyName": "Elev", "eduPersonPrincipalNames": ["anna@example.se"], "emails": [{"value": "anna@example.se"}], "responsiblePersons": [{"id": "observer-1"}]},
                {"id": "observer-1", "givenName": "Olle", "familyName": "Vårdnadshavare", "eduPersonPrincipalNames": ["olle@example.se"]},
                {"id": "teacher-1", "givenName": "Tina", "familyName": "Lärare", "eduPersonPrincipalNames": ["tina@example.se"], "duties": [{"id": "duty-1"}]},
            ]
        }
        activities = {
            "activities": [
                {"id": "section-1", "displayName": "Svenska 7A", "parentActivity": {"id": "course-1", "displayName": "Svenska 7"}, "organisation": {"id": "school-1"}, "students": [{"person": {"id": "student-1"}}], "teachers": [{"duty": {"id": "duty-1"}}]},
            ]
        }
        persons_path, activities_path = tmp_path / "persons.json", tmp_path / "activities.json"
        persons_path.write_text(json.dumps(persons), encoding="utf-8")
        activities_path.write_text(json.dumps(activities), encoding="utf-8")

        outputs = {
            "users_filtered.csv": ("create_users_filtered.py", "--persons", str(persons_path)),
            "user_observers.csv": ("create_user_observers.py", "--persons", str(persons_path)),
            "sections.csv": ("create_sections.py", "--activities", str(activities_path)),
            "courses.csv": ("create_courses.py", "--activities", str(activities_path)),
            "enrollments.csv": ("create_enrollments.py", "--persons", str(persons_path), "--activities", str(activities_path)),
        }
        for filename, invocation in outputs.items():
            run(invocation[0], *invocation[1:], "--output", str(tmp_path / filename))

        self.assertEqual(len(read_csv(tmp_path / "users_filtered.csv")), 3)
        self.assertEqual(read_csv(tmp_path / "user_observers.csv"), [{"observer_id": "observer-1", "student_id": "student-1", "status": "active"}])
        self.assertEqual(read_csv(tmp_path / "sections.csv")[0]["course_id"], "course-1")
        self.assertEqual(read_csv(tmp_path / "courses.csv")[0]["course_id"], "course-1")
        enrollments = read_csv(tmp_path / "enrollments.csv")
        self.assertEqual({(row["user_id"], row["role"]) for row in enrollments}, {("student-1", "student"), ("teacher-1", "teacher")})

        run("validate_outputs.py", "--output-dir", str(tmp_path))


if __name__ == "__main__":
    unittest.main()
