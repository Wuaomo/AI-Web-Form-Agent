"""Sanity checks for benchmark form samples and their expected answers."""

import json
from pathlib import Path


BENCHMARK_DIR = Path(__file__).resolve().parents[1] / "benchmarks"
EXPECTED_DIR = BENCHMARK_DIR / "expected"
SUPPORTED_PROFILE_KEYS = {
    "first_name",
    "last_name",
    "full_name",
    "email",
    "university",
    "major",
    "phone",
    "linkedin",
    "github",
    "self_intro",
}


def test_benchmark_expected_files_are_complete() -> None:
    """Keep benchmark samples usable by the future metrics runner."""

    expected_files = sorted(EXPECTED_DIR.glob("*.json"))
    assert len(expected_files) == 10

    for expected_file in expected_files:
        data = json.loads(expected_file.read_text(encoding="utf-8"))
        expected = data["expected"]
        html_file = (expected_file.parent / data["html_file"]).resolve()
        html = html_file.read_text(encoding="utf-8")

        assert html_file.exists()
        assert data["case_id"]
        assert data["title"]
        assert isinstance(expected["login_required"], bool)
        assert expected["fields"]

        for field in expected["fields"]:
            selector = field["selector"]
            profile_key = field["profile_key"]

            assert selector.startswith("#")
            assert f'id="{selector[1:]}"' in html
            assert profile_key is None or profile_key in SUPPORTED_PROFILE_KEYS
            assert isinstance(field["required"], bool)

