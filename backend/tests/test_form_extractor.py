"""Tests for browser-side form field extraction heuristics."""

from pathlib import Path

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from app.services.form_extractor import _EXTRACT_FIELDS_SCRIPT


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

