import sys
import types
import unittest

# request_collection itself only needs the response/session interface exercised
# below. Stub the package so this unit test also runs before requirements are
# installed; Jenkins installs the real requests package before executing export.
requests_stub = types.ModuleType("requests")
requests_stub.Session = object
requests_stub.JSONDecodeError = ValueError
requests_stub.HTTPError = RuntimeError
requests_stub.RequestException = RuntimeError
sys.modules.setdefault("requests", requests_stub)

from ss12000_export import request_collection


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self):
        return {"activities": [{"id": "activity-1"}]}


class FakeSession:
    def __init__(self) -> None:
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse()


class ExportTests(unittest.TestCase):
    def test_activities_query_contains_repeated_expand_parameters(self) -> None:
        session = FakeSession()
        params = [
            ("expandReferenceNames", "true"),
            ("expandplacement", "true"),
            ("expand", "groups"),
            ("expand", "teachers"),
        ]

        records = request_collection(
            session,
            "https://example.se/ss12000/v2",
            "activities",
            "secret-token",
            query_params=params,
        )

        self.assertEqual(records, [{"id": "activity-1"}])
        self.assertEqual(session.calls[0][1]["params"], params)
        self.assertEqual(
            [value for key, value in session.calls[0][1]["params"] if key == "expand"],
            ["groups", "teachers"],
        )


if __name__ == "__main__":
    unittest.main()
