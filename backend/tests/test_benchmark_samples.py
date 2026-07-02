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
    assert len(expected_files) == 15

    for expected_file in expected_files:
        data = json.loads(expected_file.read_text(encoding="utf-8"))
        assert "case_id" in data, f"{expected_file.name} missing required key: case_id"
        assert "title" in data, f"{expected_file.name} missing required key: title"
        assert "html_file" in data, f"{expected_file.name} missing required key: html_file"
        assert "expected" in data, f"{expected_file.name} missing required key: expected"

        expected = data["expected"]
        assert isinstance(expected, dict), f"{expected_file.name} expected must be an object"
        assert "login_required" in expected, (
            f'{expected_file.name} expected missing required key: "login_required"'
        )
        assert "fields" in expected, (
            f'{expected_file.name} expected missing required key: "fields"'
        )
        assert "not_extracted_selectors" in expected, (
            f'{expected_file.name} expected missing required key: "not_extracted_selectors"'
        )
        assert isinstance(expected["not_extracted_selectors"], list), (
            f'{expected_file.name} expected.not_extracted_selectors must be an array'
        )

        html_file = (expected_file.parent / data["html_file"]).resolve()
        html = html_file.read_text(encoding="utf-8")

        assert html_file.exists()
        assert isinstance(expected["login_required"], bool)
        assert expected["fields"]

        for field in expected["fields"]:
            assert isinstance(field, dict), (
                f"{expected_file.name} expected.fields items must be objects"
            )
            for required_key in ("selector", "profile_key", "required"):
                assert required_key in field, (
                    f"{expected_file.name} field missing required key: {required_key}"
                )

            selector = field["selector"]
            profile_key = field["profile_key"]

            assert isinstance(selector, str) and selector.startswith("#"), (
                f"{expected_file.name} field selector must start with '#': {selector!r}"
            )
            element_id = selector[1:]
            assert (
                f'<input id="{element_id}"' in html
                or f'<textarea id="{element_id}"' in html
                or f'<select id="{element_id}"' in html
            ), (
                f"{expected_file.name} selector must refer to input/textarea/select id: {selector}"
            )
            assert profile_key is None or profile_key in SUPPORTED_PROFILE_KEYS
            assert isinstance(field["required"], bool)

        for selector in expected["not_extracted_selectors"]:
            assert isinstance(selector, str) and selector.startswith("#"), (
                f"{expected_file.name} not_extracted_selectors values must start with '#': {selector!r}"
            )
            element_id = selector[1:]
            assert (
                f'<button id="{element_id}"' in html
                or f'<input id="{element_id}"' in html
            ), (
                f"{expected_file.name} not_extracted selector id not found in HTML: {selector}"
            )

