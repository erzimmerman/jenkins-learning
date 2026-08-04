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
                {
                    "id": "student-1",
                    "givenName": "Anna",
                    "familyName": "Elev",
                    "eduPersonPrincipalNames": ["anna@example.se"],
                    "emails": [{"value": "anna@example.se"}],
                    "personStatus": "Aktiv",
                    "externalIdentifiers": [
                        {"context": "studentguid", "value": "external-student-1"}
                    ],
                    "responsibles": [
                        {"relationType": "Vårdnadshavare", "person": {"id": "observer-1"}},
                        {"relationType": "Vårdnadshavare", "person": {"id": "observer-2"}},
                        {"relationType": "Kontaktperson", "person": {"id": "teacher-1"}},
                    ],
                },
                {"id": "student-2", "givenName": "Bo", "familyName": "Elev", "eduPersonPrincipalNames": ["bo@example.se"]},
                {"id": "student-3", "givenName": "Cecilia", "familyName": "Elev", "eduPersonPrincipalNames": ["cecilia@example.se"]},
                {"id": "student-4", "givenName": "David", "familyName": "Elev", "eduPersonPrincipalNames": ["david@example.se"]},
                {"id": "student-5", "givenName": "Eva", "familyName": "Elev", "eduPersonPrincipalNames": ["eva@example.se"]},
                {"id": "observer-1", "givenName": "Olle", "familyName": "Vårdnadshavare", "eduPersonPrincipalNames": ["olle@example.se"]},
                {"id": "observer-2", "givenName": "Vera", "familyName": "Vårdnadshavare", "eduPersonPrincipalNames": ["vera@example.se"]},
                {"id": "teacher-1", "givenName": "Tina", "familyName": "Lärare", "eduPersonPrincipalNames": ["tina@example.se"], "duties": [{"id": "duty-1"}]},
                {
                    "id": "preschool-student",
                    "givenName": "Filip",
                    "familyName": "Förskola",
                    "eduPersonPrincipalNames": ["filip@example.se"],
                    "_embedded": {
                        "placements": [{"schoolType": "FS"}]
                    },
                },
                {
                    "id": "yh-student",
                    "givenName": "Ylva",
                    "familyName": "Yrkeshögskola",
                    "eduPersonPrincipalNames": ["ylva@example.se"],
                    "enrolments": [{"schoolType": "YH"}],
                },
            ]
        }
        activities = {
            "activities": [
                {
                    "id": "course-1",
                    "displayName": "Svenska 7",
                    "startDate": "2099-01-10",
                    "endDate": "2099-06-30",
                    "organisation": {
                        "id": "school-1",
                        "displayName": "Lärande Grundskola Fresta",
                    },
                    "syllabus": {
                        "displayName": "Svenska 7",
                    },
                    "groups": [{"id": "section-1"}],
                    "teachers": [{"duty": {"id": "duty-1"}}],
                    "_embedded": {
                        "syllabus": {
                            "schoolType": "GR",
                            "subjectName": "Svenska",
                        },
                        "groups": [
                            {
                                "id": "section-1",
                                "displayName": "Svenska 7A",
                                "startDate": "2098-08-10",
                                "endDate": "2099-05-30",
                                "groupMemberships": [
                                    {"person": {"id": "student-1"}},
                                    {"person": {"id": "student-2"}},
                                    {"person": {"id": "student-3"}},
                                    {"person": {"id": "student-4"}},
                                    {"person": {"id": "student-5"}},
                                ],
                            }
                        ],
                        "teachers": [
                            {
                                "id": "duty-1",
                                "person": {"id": "teacher-1"},
                                "dutyRole": "Lärare",
                            }
                        ],
                    },
                },
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

        users = read_csv(tmp_path / "users_filtered.csv")
        self.assertEqual(len(users), 8)
        self.assertEqual(
            users[0],
            {
                "user_id": "anna@example.se",
                "login_id": "anna@example.se",
                "first_name": "Anna",
                "last_name": "Elev",
                "full_name": "Anna Elev",
                "short_name": "Anna Elev",
                "email": "anna@example.se",
                "status": "active",
                "authentication_provider_id": "",
            },
        )
        self.assertEqual(
            next(row for row in users if row["user_id"] == "bo@example.se")["status"],
            "suspended",
        )
        self.assertNotIn("filip@example.se", {row["user_id"] for row in users})
        self.assertNotIn("ylva@example.se", {row["user_id"] for row in users})
        for line in (tmp_path / "users_filtered.csv").read_text(
            encoding="utf-8-sig"
        ).splitlines():
            self.assertTrue(line.startswith('"'))
            self.assertTrue(line.endswith('"'))
        self.assertEqual(
            read_csv(tmp_path / "user_observers.csv"),
            [
                {"observer_id": "olle@example.se", "student_id": "anna@example.se", "status": "active"},
                {"observer_id": "vera@example.se", "student_id": "anna@example.se", "status": "active"},
            ],
        )
        first_observer_line = (tmp_path / "user_observers.csv").read_text(encoding="utf-8-sig").splitlines()[1]
        self.assertTrue(first_observer_line.startswith('"'))
        self.assertIn('","', first_observer_line)
        self.assertEqual(
            read_csv(tmp_path / "sections.csv"),
            [
                {
                    "section_id": "section-1",
                    "course_id": "course-1",
                    "name": "Svenska 7A",
                    "status": "active",
                    "start_date": "2099-01-10",
                    "end_date": "2099-06-30",
                }
            ],
        )
        for line in (tmp_path / "sections.csv").read_text(
            encoding="utf-8-sig"
        ).splitlines():
            self.assertTrue(line.startswith('"'))
            self.assertTrue(line.endswith('"'))
        self.assertEqual(
            read_csv(tmp_path / "courses.csv"),
            [
                {
                    "course_id": "course-1",
                    "short_name": "Svenska",
                    "long_name": "Svenska",
                    "account_id": "10",
                    "term_id": "98*99*10",
                    "status": "active",
                    "start_date": "2099-01-10",
                    "end_date": "2099-06-30",
                    "course_format": "",
                }
            ],
        )
        first_course_line = (tmp_path / "courses.csv").read_text(
            encoding="utf-8-sig"
        ).splitlines()[1]
        self.assertTrue(first_course_line.startswith('"'))
        self.assertIn('","', first_course_line)
        enrollments = read_csv(tmp_path / "enrollments.csv")
        self.assertEqual(
            {(row["user_id"], row["role"]) for row in enrollments},
            {
                ("anna@example.se", "student"),
                ("bo@example.se", "student"),
                ("cecilia@example.se", "student"),
                ("david@example.se", "student"),
                ("eva@example.se", "student"),
                ("tina@example.se", "teacher"),
            },
        )
        self.assertEqual(len(enrollments), 6)
        self.assertEqual({row["section_id"] for row in enrollments}, {"section-1"})
        self.assertEqual({row["status"] for row in enrollments}, {"active"})
        first_enrollment_line = (tmp_path / "enrollments.csv").read_text(encoding="utf-8-sig").splitlines()[1]
        self.assertTrue(first_enrollment_line.startswith('"'))
        self.assertIn('","', first_enrollment_line)

        run("validate_outputs.py", "--output-dir", str(tmp_path))

    def test_courses_uses_latest_group_based_mapping(self) -> None:
        activities = {
            "activities": [
                {
                    "id": "gr-course",
                    "startDate": "2025-08-15",
                    "endDate": "2026-06-30",
                    "organisation": {
                        "displayName": "Lärande Grundskola Fresta"
                    },
                    "syllabus": {
                        "displayName": "Matematik",
                    },
                    "_embedded": {
                        "syllabus": {
                            "schoolType": "GR",
                            "subjectName": "Matematik",
                        },
                        "groups": [
                            {"id": "gr-a", "displayName": "7A", "startDate": "2026-05-08"},
                            {"id": "gr-b", "displayName": "7B", "startDate": "2026-05-08"},
                        ]
                    },
                },
                {
                    "id": "gy-course",
                    "startDate": "2026-08-17",
                    "endDate": "2099-06-30",
                    "organisation": {"displayName": "Realgymnasiet Borlänge"},
                    "syllabus": {
                        "displayName": "PRRPRR01",
                    },
                    "_embedded": {
                        "syllabus": {
                            "schoolType": "GY",
                            "courseName": "Programmering 1",
                        },
                        "groups": [
                            {"id": "gy-a", "displayName": "TE4A", "startDate": "2026-08-17"},
                            {"id": "gy-b", "displayName": "TE4B", "startDate": "2027-08-17"},
                        ]
                    },
                },
                {
                    "id": "gy-fallback",
                    "startDate": "2026-08-17",
                    "endDate": "2099-06-30",
                    "organisation": {"displayName": "Realgymnasiet Borås"},
                    "syllabus": {
                        "displayName": "GYARB",
                    },
                    "_embedded": {
                        "syllabus": {"schoolType": "GY", "courseName": ""},
                        "groups": [
                            {"id": "gy-c", "displayName": "BA24", "startDate": "2026-08-17"}
                        ]
                    },
                },
            ]
        }

        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            activities_path = tmp_path / "activities.json"
            output_path = tmp_path / "courses.csv"
            activities_path.write_text(json.dumps(activities), encoding="utf-8")

            run(
                "create_courses.py",
                "--activities",
                str(activities_path),
                "--output",
                str(output_path),
            )

            courses = read_csv(output_path)
            self.assertEqual(len(courses), 4)

            gr_course = next(row for row in courses if row["course_id"] == "gr-course")
            self.assertEqual(gr_course["short_name"], "Matematik")
            self.assertEqual(gr_course["long_name"], "Matematik")
            self.assertEqual(gr_course["account_id"], "10")
            self.assertEqual(gr_course["term_id"], "25*26*10")
            self.assertEqual(gr_course["status"], "completed")
            self.assertEqual(gr_course["course_format"], "")

            gy_courses = [row for row in courses if row["course_id"] == "gy-course"]
            self.assertEqual(
                {row["term_id"] for row in gy_courses},
                {"26*27*17", "27*28*17"},
            )
            self.assertEqual(
                {row["short_name"] for row in gy_courses},
                {"TE4A/TE4B/PRRPRR01"},
            )
            self.assertEqual(
                {row["long_name"] for row in gy_courses},
                {"Programmering 1"},
            )

            fallback = next(
                row for row in courses if row["course_id"] == "gy-fallback"
            )
            self.assertEqual(fallback["short_name"], "BA24/GYARB")
            self.assertEqual(fallback["long_name"], fallback["short_name"])

            for line in output_path.read_text(encoding="utf-8-sig").splitlines():
                self.assertTrue(line.startswith('"'))
                self.assertTrue(line.endswith('"'))

    def test_enrollments_uses_latest_person_lookup_mapping(self) -> None:
        persons = {
            "persons": [
                {
                    "id": "teacher-person",
                    "eduPersonPrincipalNames": ["teacher@example.se"],
                },
                {
                    "id": "student-person",
                    "eduPersonPrincipalNames": ["student@example.se"],
                },
            ]
        }
        activities = {
            "activities": [
                {
                    "id": "activity-1",
                    "startDate": "2025-08-18",
                    "endDate": "2026-01-10",
                    # The top-level reference has no person.id in the actual API.
                    "teachers": [{"duty": {"id": "teacher-duty"}}],
                    "_embedded": {
                        "teachers": [
                            {
                                "id": "teacher-duty",
                                "person": {"id": "teacher-person"},
                            }
                        ],
                        "groups": [
                            {
                                "id": "section-1",
                                "groupMemberships": [
                                    {"person": {"id": "student-person"}}
                                ],
                            }
                        ],
                    },
                }
            ]
        }

        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            persons_path = tmp_path / "persons.json"
            activities_path = tmp_path / "activities.json"
            output_path = tmp_path / "enrollments.csv"
            persons_path.write_text(json.dumps(persons), encoding="utf-8")
            activities_path.write_text(json.dumps(activities), encoding="utf-8")

            run(
                "create_enrollments.py",
                "--persons",
                str(persons_path),
                "--activities",
                str(activities_path),
                "--output",
                str(output_path),
            )

            self.assertEqual(
                read_csv(output_path),
                [
                    {
                        "course_id": "activity-1",
                        "start_date": "2025-08-18",
                        "end_date": "2026-01-10",
                        "user_id": "teacher@example.se",
                        "role": "teacher",
                        "section_id": "section-1",
                        "status": "completed",
                    },
                    {
                        "course_id": "activity-1",
                        "start_date": "2025-08-18",
                        "end_date": "2026-01-10",
                        "user_id": "student@example.se",
                        "role": "student",
                        "section_id": "section-1",
                        "status": "completed",
                    },
                ],
            )
            for line in output_path.read_text(encoding="utf-8-sig").splitlines():
                self.assertTrue(line.startswith('"'))
                self.assertTrue(line.endswith('"'))

    def test_user_observers_uses_latest_relationship_mapping(self) -> None:
        persons = {
            "persons": [
                {
                    "id": "inactive-student",
                    "eduPersonPrincipalNames": ["student@example.se"],
                    "personStatus": "Inaktiv",
                    "externalIdentifiers": [{"context": "studentguid"}],
                    "responsibles": [
                        {
                            "relationType": "Vårdnadshavare",
                            "person": {"id": "valid-observer"},
                        },
                        {
                            "relationType": "Vårdnadshavare",
                            "person": {"id": "observer-without-eppn"},
                        },
                        {
                            "relationType": "Kontaktperson",
                            "person": {"id": "valid-observer"},
                        },
                    ],
                },
                {
                    "id": "student-without-eppn",
                    "personStatus": "Aktiv",
                    "externalIdentifiers": [{"context": "studentguid"}],
                    "responsibles": [
                        {
                            "relationType": "Vårdnadshavare",
                            "person": {"id": "valid-observer"},
                        }
                    ],
                },
                {
                    "id": "not-a-student",
                    "eduPersonPrincipalNames": ["staff@example.se"],
                    "personStatus": "Aktiv",
                    "responsibles": [
                        {
                            "relationType": "Vårdnadshavare",
                            "person": {"id": "valid-observer"},
                        }
                    ],
                },
                {
                    "id": "valid-observer",
                    "eduPersonPrincipalNames": ["observer@example.se"],
                },
                {"id": "observer-without-eppn"},
            ]
        }

        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            persons_path = tmp_path / "persons.json"
            output_path = tmp_path / "user_observers.csv"
            persons_path.write_text(json.dumps(persons), encoding="utf-8")

            run(
                "create_user_observers.py",
                "--persons",
                str(persons_path),
                "--output",
                str(output_path),
            )

            self.assertEqual(
                read_csv(output_path),
                [
                    {
                        "observer_id": "observer@example.se",
                        "student_id": "student@example.se",
                        "status": "inactive",
                    }
                ],
            )
            for line in output_path.read_text(encoding="utf-8-sig").splitlines():
                self.assertTrue(line.startswith('"'))
                self.assertTrue(line.endswith('"'))


if __name__ == "__main__":
    unittest.main()
