import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


CSV_COLUMNS = [
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


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create users_filtered.csv from an SS12000 Persons response."
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Path to the Persons JSON file.",
    )

    parser.add_argument(
        "--output",
        default="users_filtered.csv",
        help="Path to the output CSV file.",
    )

    return parser.parse_args()


def load_json(input_path: Path) -> Any:
    if not input_path.exists():
        raise FileNotFoundError(
            f"Input file does not exist: {input_path}"
        )

    with input_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def extract_persons(response_data: Any) -> list[dict[str, Any]]:
    """
    Supports several common SS12000 response formats:

    1. A plain JSON list:
       [
           {...},
           {...}
       ]

    2. An object containing a data list:
       {
           "data": [
               {...},
               {...}
           ]
       }

    3. HAL-style embedded responses:
       {
           "_embedded": {
               "persons": [
                   {...},
                   {...}
               ]
           }
       }
    """

    if isinstance(response_data, list):
        return [
            person
            for person in response_data
            if isinstance(person, dict)
        ]

    if not isinstance(response_data, dict):
        raise ValueError(
            "Unexpected JSON format. Expected a list or object."
        )

    possible_list_fields = [
        "data",
        "persons",
        "items",
        "content",
        "results",
    ]

    for field in possible_list_fields:
        value = response_data.get(field)

        if isinstance(value, list):
            return [
                person
                for person in value
                if isinstance(person, dict)
            ]

    embedded = response_data.get("_embedded")

    if isinstance(embedded, dict):
        for field in possible_list_fields:
            value = embedded.get(field)

            if isinstance(value, list):
                return [
                    person
                    for person in value
                    if isinstance(person, dict)
                ]

        # Some APIs use a different name for the list inside _embedded.
        for value in embedded.values():
            if isinstance(value, list):
                return [
                    person
                    for person in value
                    if isinstance(person, dict)
                ]

    raise ValueError(
        "Could not find a list of persons in the JSON response. "
        f"Top-level fields: {list(response_data.keys())}"
    )


def first_non_empty_string(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                return item.strip()

            if isinstance(item, dict):
                nested_value = item.get("value")

                if isinstance(nested_value, str) and nested_value.strip():
                    return nested_value.strip()

    return ""


def get_login_id(person: dict[str, Any]) -> str:
    eppn = person.get("eduPersonPrincipalNames")

    return first_non_empty_string(eppn)


def get_email(person: dict[str, Any]) -> str:
    emails = person.get("emails")

    if not isinstance(emails, list):
        return ""

    # Behåller tidigare regel: använd första e-postadressen.
    for email in emails:
        if isinstance(email, str) and email.strip():
            return email.strip()

        if isinstance(email, dict):
            value = email.get("value")

            if isinstance(value, str) and value.strip():
                return value.strip()

    return ""


def create_row(person: dict[str, Any]) -> dict[str, str]:
    first_name = first_non_empty_string(
        person.get("givenName")
    )

    last_name = first_non_empty_string(
        person.get("familyName")
    )

    full_name = " ".join(
        part
        for part in [first_name, last_name]
        if part
    )

    return {
        "user_id": first_non_empty_string(
            person.get("id")
        ),
        "login_id": get_login_id(person),
        "first_name": first_name,
        "last_name": last_name,
        "full_name": full_name,
        "short_name": full_name,
        "email": get_email(person),
        "status": first_non_empty_string(
            person.get("personStatus")
        ),
        "authentication_provider_id": "",
    }


def write_csv(
    persons: list[dict[str, Any]],
    output_path: Path,
) -> int:
    rows_written = 0

    with output_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=CSV_COLUMNS,
            delimiter=",",
            quoting=csv.QUOTE_MINIMAL,
        )

        writer.writeheader()

        for person in persons:
            writer.writerow(create_row(person))
            rows_written += 1

    return rows_written


def main() -> int:
    try:
        args = parse_arguments()

        input_path = Path(args.input)
        output_path = Path(args.output)

        response_data = load_json(input_path)
        persons = extract_persons(response_data)

        print(f"Found {len(persons)} persons in {input_path}.")

        rows_written = write_csv(
            persons=persons,
            output_path=output_path,
        )

        print(
            f"Created {output_path} with "
            f"{rows_written} data rows."
        )

        return 0

    except Exception as exc:
        print(
            f"Could not create users CSV: {exc}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    sys.exit(main())
