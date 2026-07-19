from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests

from ss12000_common import extract_collection


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Persons and Activities from SS12000")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--org-id", required=True, type=int)
    parser.add_argument("--output-dir", default="output")
    return parser.parse_args()


def extract_token(response: requests.Response) -> str:
    body = response.text.strip()
    if not body:
        raise RuntimeError("The token endpoint returned an empty response")
    try:
        payload: Any = response.json()
    except requests.JSONDecodeError:
        return body
    if isinstance(payload, str) and payload.strip():
        return payload.strip()
    if isinstance(payload, dict):
        for field in ("access_token", "accessToken", "token", "apiToken"):
            value = payload.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()
    raise RuntimeError("Could not find a token in the token endpoint response")


def request_token(session: requests.Session, base_url: str, secret: str, org_id: int) -> str:
    url = f"{base_url.rstrip('/')}/token"
    print(f"Requesting token from: {url}")
    response = session.post(
        url,
        json={"secret": secret, "orgId": org_id},
        headers={"Accept": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    token = extract_token(response)
    print("Token received successfully.")
    return token


def next_url(payload: Any, current_url: str) -> str:
    if not isinstance(payload, dict):
        return ""
    candidates = [payload.get("next"), payload.get("nextPage")]
    for container_name in ("_links", "links", "pagination", "meta"):
        container = payload.get(container_name)
        if isinstance(container, dict):
            candidates.extend([container.get("next"), container.get("nextPage")])
    for candidate in candidates:
        if isinstance(candidate, dict):
            candidate = candidate.get("href") or candidate.get("url")
        if isinstance(candidate, str) and candidate.strip():
            return urljoin(current_url, candidate.strip())
    return ""


def request_collection(
    session: requests.Session,
    base_url: str,
    resource: str,
    token: str,
) -> list[dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/{resource}"
    records: list[dict[str, Any]] = []
    visited: set[str] = set()
    page = 0
    while url:
        if url in visited or page >= 1000:
            raise RuntimeError(f"Pagination loop detected while requesting /{resource}")
        visited.add(url)
        page += 1
        print(f"Requesting {resource}, page {page}: {url}")
        response = session.get(
            url,
            headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
            timeout=120,
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except requests.JSONDecodeError as exc:
            raise RuntimeError(f"The /{resource} endpoint did not return valid JSON") from exc
        records.extend(extract_collection(payload, (resource,)))
        url = next_url(payload, url)
    print(f"Received {len(records)} {resource} records.")
    return records


def save(path: Path, resource: str, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({resource: records}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Created: {path}")


def main() -> int:
    args = arguments()
    secret = os.environ.get("SS12000_SECRET", "").strip()
    if not secret:
        print("SS12000_SECRET is missing", file=sys.stderr)
        return 2
    try:
        with requests.Session() as session:
            token = request_token(session, args.base_url, secret, args.org_id)
            persons = request_collection(session, args.base_url, "persons", token)
            activities = request_collection(session, args.base_url, "activities", token)
        output_dir = Path(args.output_dir)
        save(output_dir / "persons.json", "persons", persons)
        save(output_dir / "activities.json", "activities", activities)
        return 0
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        print(f"SS12000 HTTP request failed with status {status}", file=sys.stderr)
    except requests.RequestException as exc:
        print(f"SS12000 network request failed: {exc}", file=sys.stderr)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"SS12000 export failed: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

