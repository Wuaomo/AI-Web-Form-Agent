"""Extract form controls and their metadata with Playwright."""

from dataclasses import dataclass

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from app.asyncio_compat import run_playwright_compatible


@dataclass(frozen=True)
class ExtractedFormField:
    """A serializable form control discovered on a web page."""

    label: str | None
    selector: str
    field_type: str
    placeholder: str | None
    name: str | None
    html_id: str | None
    required: bool


async def extract_form_fields(url: str) -> list[ExtractedFormField]:
    """Open a page and return its visible, user-editable form controls."""

    return await run_playwright_compatible(lambda: _extract_form_fields(url))


async def _extract_form_fields(url: str) -> list[ExtractedFormField]:
    """Open a page and return its visible, user-editable form controls."""

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page(viewport={"width": 1440, "height": 900})
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)

            # Let client-rendered forms settle, but do not require pages with
            # background requests to ever become fully network-idle.
            try:
                await page.wait_for_load_state("networkidle", timeout=5_000)
            except PlaywrightTimeoutError:
                pass

            raw_fields = await page.locator(
                'input:not([type="hidden"]), textarea, select, button'
            ).evaluate_all(_EXTRACT_FIELDS_SCRIPT)
        finally:
            await browser.close()

    return [ExtractedFormField(**field) for field in raw_fields]


_EXTRACT_FIELDS_SCRIPT = """
(elements) => {
  function normalizeText(value) {
    if (!value) return null;
    const normalized = value.replace(/\\s+/g, " ").trim();
    return normalized || null;
  }

  function isUnique(selector) {
    try {
      return document.querySelectorAll(selector).length === 1;
    } catch {
      return false;
    }
  }

  function selectorFor(element) {
    if (element.id) {
      const idSelector = `#${CSS.escape(element.id)}`;
      if (isUnique(idSelector)) return idSelector;
    }

    if (element.name) {
      const nameSelector =
        `${element.tagName.toLowerCase()}[name="${CSS.escape(element.name)}"]`;
      if (isUnique(nameSelector)) return nameSelector;

      if (element.type) {
        const typedNameSelector =
          `${element.tagName.toLowerCase()}[type="${CSS.escape(element.type)}"]` +
          `[name="${CSS.escape(element.name)}"]`;
        if (isUnique(typedNameSelector)) return typedNameSelector;
      }
    }

    const path = [];
    let current = element;
    while (current && current.nodeType === Node.ELEMENT_NODE) {
      if (current.id) {
        path.unshift(`#${CSS.escape(current.id)}`);
        const candidate = path.join(" > ");
        if (isUnique(candidate)) return candidate;
      }

      const tagName = current.tagName.toLowerCase();
      const siblings = current.parentElement
        ? Array.from(current.parentElement.children).filter(
            sibling => sibling.tagName === current.tagName
          )
        : [];
      const position = Math.max(siblings.indexOf(current) + 1, 1);
      path.unshift(`${tagName}:nth-of-type(${position})`);

      const candidate = path.join(" > ");
      if (isUnique(candidate)) return candidate;
      current = current.parentElement;
    }

    return path.join(" > ");
  }

  function labelFor(element) {
    const labels = element.labels
      ? Array.from(element.labels)
          .map(label => normalizeText(label.innerText || label.textContent))
          .filter(Boolean)
      : [];
    if (labels.length) return labels.join(" ");

    const ariaLabel = normalizeText(element.getAttribute("aria-label"));
    if (ariaLabel) return ariaLabel;

    const labelledBy = element.getAttribute("aria-labelledby");
    if (labelledBy) {
      const text = labelledBy
        .split(/\\s+/)
        .map(id => document.getElementById(id))
        .filter(Boolean)
        .map(node => normalizeText(node.innerText || node.textContent))
        .filter(Boolean)
        .join(" ");
      if (text) return text;
    }

    if (element.tagName.toLowerCase() === "button") {
      return normalizeText(element.innerText || element.textContent);
    }

    if (["button", "submit", "reset"].includes(element.type)) {
      return normalizeText(element.value);
    }

    return null;
  }

  return elements.map(element => {
    const tagName = element.tagName.toLowerCase();
    const fieldType = tagName === "input"
      ? (element.type || "text").toLowerCase()
      : tagName;

    return {
      label: labelFor(element),
      selector: selectorFor(element),
      field_type: fieldType,
      placeholder: normalizeText(element.getAttribute("placeholder")),
      name: normalizeText(element.getAttribute("name")),
      html_id: normalizeText(element.id),
      required:
        Boolean(element.required) ||
        element.getAttribute("aria-required") === "true",
    };
  });
}
"""
