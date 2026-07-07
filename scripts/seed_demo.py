"""Seed a small demo profile through the running API."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_PROFILE = {
    "profile_name": "Demo Applicant",
    "full_name": "Alex Demo",
    "email": "alex.demo@example.com",
    "phone": "+1 555 010 2026",
    "university": "Demo State University",
    "major": "Computer Science",
    "linkedin": "https://www.linkedin.com/in/alex-demo",
    "github": "https://github.com/alex-demo",
    "self_intro": "Demo profile for AI Web Form Agent reviews.",
    "custom_values": {
        "portfolio_url": "https://alex-demo.dev",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a reusable demo profile in the running API.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Backend API base URL. Default: %(default)s",
    )
    return parser.parse_args()


def _request_json(method: str, url: str, payload: dict[str, object] | None = None) -> object:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def profile_exists(base_url: str, profile_name: str) -> bool:
    profiles = _request_json("GET", f"{base_url}/profiles")
    return any(
        isinstance(profile, dict) and profile.get("profile_name") == profile_name
        for profile in profiles
    )


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")

    try:
        _request_json("GET", f"{base_url}/health")
    except urllib.error.URLError as exc:
        print(f"Backend is not reachable at {base_url}: {exc}", file=sys.stderr)
        return 1

    try:
        if profile_exists(base_url, DEFAULT_PROFILE["profile_name"]):
            print("Demo profile already exists. No changes made.")
            return 0

        created = _request_json("POST", f"{base_url}/profiles", DEFAULT_PROFILE)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(
            f"Demo seed failed with HTTP {exc.code}: {body}",
            file=sys.stderr,
        )
        return 1
    except urllib.error.URLError as exc:
        print(f"Demo seed failed: {exc}", file=sys.stderr)
        return 1

    if not isinstance(created, dict):
        print("Demo seed failed: unexpected response payload", file=sys.stderr)
        return 1

    print(f"Created demo profile #{created.get('id')}: {created.get('profile_name')}")
    print("Next step: open http://localhost:5173 and start a workflow run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
