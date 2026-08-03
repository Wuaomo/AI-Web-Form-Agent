"""Tests for browser-side form field extraction heuristics."""

from pathlib import Path

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from app.services.form_extractor import _EXTRACT_FIELDS_SCRIPT, _LOGIN_DETECTION_SCRIPT


def extract_fields_from_html(tmp_path: Path, html: str) -> list[dict[str, object]]:
    """Render a small page and run the production extractor script."""

    html_path = tmp_path / "page.html"
    html_path.write_text(html, encoding="utf-8")

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except PlaywrightError as exc:
            pytest.skip(f"Chromium is not installed for Playwright: {exc}")

        page = browser.new_page()
        page.goto(html_path.as_uri())
        fields = page.locator(
            'input:not([type="hidden"]), textarea, select'
        ).evaluate_all(_EXTRACT_FIELDS_SCRIPT)
        browser.close()

    return fields


def detect_login_from_html(tmp_path: Path, html: str) -> bool:
    """Render a small page and run the production login detector script."""

    html_path = tmp_path / "page.html"
    html_path.write_text(html, encoding="utf-8")

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except PlaywrightError as exc:
            pytest.skip(f"Chromium is not installed for Playwright: {exc}")

        page = browser.new_page()
        page.goto(html_path.as_uri())
        login_required = page.evaluate(_LOGIN_DETECTION_SCRIPT)
        browser.close()

    return bool(login_required)


def test_extractor_skips_actions_uploads_and_generic_internal_inputs(
    tmp_path: Path,
) -> None:
    fields = extract_fields_from_html(
        tmp_path,
        """
        <main>
          <button type="button">切换至校招</button>
          <label>Resume <input name="resume" type="file"></label>

          <div class="form-item">
            <span>姓名</span>
            <input placeholder="请输入">
          </div>
          <div class="form-item">
            <span>邮箱</span>
            <input name="email" type="email" placeholder="请输入邮箱">
          </div>

          <div class="dropdown-panel">
            <ul>
              <li><input placeholder="请输入"></li>
            </ul>
          </div>
          <button type="submit">保存</button>
        </main>
        """,
    )

    assert [field["field_type"] for field in fields] == ["text", "email"]
    assert [field["label"] for field in fields] == ["姓名", "邮箱"]
    assert [field["placeholder"] for field in fields] == ["请输入", "请输入邮箱"]


def test_extractor_returns_options_for_select_and_radio_fields(
    tmp_path: Path,
) -> None:
    fields = extract_fields_from_html(
        tmp_path,
        """
        <main>
          <label>
            Work authorization
            <select id="authorization" name="authorization">
              <option value="">Choose one</option>
              <option value="yes">Yes</option>
              <option value="no">No</option>
            </select>
          </label>

          <fieldset>
            <legend>Preferred location</legend>
            <label><input id="remote" type="radio" name="location" value="remote"> Remote</label>
            <label><input id="office" type="radio" name="location" value="office"> Office</label>
          </fieldset>
        </main>
        """,
    )

    select_field = next(field for field in fields if field["field_type"] == "select")
    radio_field = next(field for field in fields if field["html_id"] == "remote")

    assert select_field["options"] == [
        {"label": "Choose one", "value": "", "selector": None},
        {"label": "Yes", "value": "yes", "selector": None},
        {"label": "No", "value": "no", "selector": None},
    ]
    assert radio_field["options"] == [
        {"label": "Remote", "value": "remote", "selector": "#remote"},
        {"label": "Office", "value": "office", "selector": "#office"},
    ]


def test_login_detector_does_not_block_questionnaire_password_fields(
    tmp_path: Path,
) -> None:
    assert not detect_login_from_html(
        tmp_path,
        """
        <main>
          <h1>Vendor Security Questionnaire</h1>
          <form>
            <label>Security contact email <input name="email" type="email"></label>
            <label>Do you enforce multi-factor authentication?<textarea name="mfa"></textarea></label>
            <label>Do you encrypt data at rest?<select name="encryption"><option>Yes</option></select></label>
            <label>Data retention period <input name="retention" type="text"></label>
            <label>Administrator password <input name="admin_password" type="password"></label>
            <label><input name="attestation" type="checkbox"> I confirm these answers were reviewed.</label>
          </form>
        </main>
        """,
    )

