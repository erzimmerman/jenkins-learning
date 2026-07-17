import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export persons from an SS12000 API."
    )

    parser.add_argument(
        "--base-url",
        required=True,
        help="Base URL, for example https://example.se/ss12000/v2",
    )

    parser.add_argument(
        "--org-id",
        required=True,
        type=int,
        help="Organization ID used when requesting the API token.",
    )

    return parser.parse_args()


def get_secret() -> str:
    secret = os.environ.get("SS12000_SECRET")

    if not secret:
        raise RuntimeError(
            "Environment variable SS12000_SECRET is missing."
        )

    return secret


def request_token(
    base_url: str,
    secret: str,
    org_id: int,
) -> str:
    token_url = f"{base_url.rstrip('/')}/token"

    request_body = {
        "secret": secret,
        "orgId": org_id,
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    print(f"Requesting token from: {token_url}")

    response = requests.post(
        token_url,
        json=request_body,
        headers=headers,
        timeout=30,
    )

    response.raise_for_status()

    try:
        response_data: Any = response.json()
    except requests.JSONDecodeError as exc:
        raise RuntimeError(
            "The token endpoint did not return valid JSON."
        ) from exc

    token = extract_token(response_data)

    print("Token received successfully.")

    return token


def extract_token(response_data: Any) -> str:
    if isinstance(response_data, str):
        return response_data

    if not isinstance(response_data, dict):
        raise RuntimeError(
            "Unexpected response format from token endpoint."
        )

    possible_fields = [
        "access_token",
        "accessToken",
        "token",
        "apiToken",
    ]

    for field in possible_fields:
        value = response_data.get(field)

        if isinstance(value, str) and value:
            return value

    raise RuntimeError(
        "Could not find a token in the token endpoint response. "
        f"Available fields: {list(response_data.keys())}"
    )


def request_persons(
    base_url: str,
    token: str,
) -> Any:
    persons_url = f"{base_url.rstrip('/')}/persons"

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }

    print(f"Requesting persons from: {persons_url}")

    response = requests.get(
        persons_url,
        headers=headers,
        timeout=120,
    )

    response.raise_for_status()

    try:
        return response.json()
    except requests.JSONDecodeError as exc:
        raise RuntimeError(
            "The Persons endpoint did not return valid JSON."
        ) from exc


def save_response(response_data: Any) -> Path:
    timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    output_path = Path(f"response_persons_{timestamp}.json")

    output_path.write_text(
        json.dumps(
            response_data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Created output file: {output_path}")

    return output_path


def main() -> int:
    try:
        args = parse_arguments()
        secret = get_secret()

        token = request_token(
            base_url=args.base_url,
            secret=secret,
            org_id=args.org_id,
        )

        persons = request_persons(
            base_url=args.base_url,
            token=token,
        )

        save_response(persons)

        print("SS12000 export completed successfully.")

        return 0

    except requests.HTTPError as exc:
        status_code = exc.response.status_code
        response_text = exc.response.text[:1000]

        print(
            f"HTTP request failed with status {status_code}.",
            file=sys.stderr,
        )
        print(
            f"Response: {response_text}",
            file=sys.stderr,
        )

        return 1

    except requests.RequestException as exc:
        print(
            f"Network request failed: {exc}",
            file=sys.stderr,
        )

        return 1

    except Exception as exc:
        print(
            f"Export failed: {exc}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    sys.exit(main())
