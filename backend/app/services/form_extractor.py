"""Extract form controls and their metadata with Playwright."""

from dataclasses import dataclass

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from app.services.browser_session import run_with_persistent_page


@dataclass(frozen=True)
class ExtractedFormField:
    """A serializable form control discovered on a web page."""

    label: str | None
    selector: str
    field_type: str
    placeholder: str | None
    name: str | None
    html_id: str | None
    current_value: str | None
    required: bool


@dataclass(frozen=True)
class ExtractedFormAnalysis:
    """Form controls plus a signal that the current page is a login gate."""

    fields: list[ExtractedFormField]
    login_required: bool


async def extract_form_analysis(url: str, profile_id: int) -> ExtractedFormAnalysis:
    """Open a page and return form controls plus login-gate detection."""

    def extract(page: Page) -> ExtractedFormAnalysis:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)

        # Let client-rendered forms settle, but do not require pages with
        # background requests to ever become fully network-idle.
        try:
            page.wait_for_load_state("networkidle", timeout=5_000)
        except PlaywrightTimeoutError:
            pass

        raw_fields = page.locator(
            'input:not([type="hidden"]), textarea, select'
        ).evaluate_all(_EXTRACT_FIELDS_SCRIPT)
        login_required = page.evaluate(_LOGIN_DETECTION_SCRIPT)

        return ExtractedFormAnalysis(
            fields=[ExtractedFormField(**field) for field in raw_fields],
            login_required=login_required,
        )

    return await run_with_persistent_page(
        url,
        profile_id,
        extract,
    )


async def extract_form_fields(url: str, profile_id: int) -> list[ExtractedFormField]:
    """Open a page and return its visible, user-editable form controls."""

    analysis = await extract_form_analysis(url, profile_id)
    return analysis.fields


_EXTRACT_FIELDS_SCRIPT = """
(elements) => {
  function normalizeText(value) {
    if (!value) return null;
    const normalized = value.replace(/\\s+/g, " ").trim();
    return normalized || null;
  }

  function isVisible(element) {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.visibility !== "hidden" &&
      style.display !== "none" &&
      style.opacity !== "0" &&
      rect.width > 0 &&
      rect.height > 0;
  }

  function isInHiddenTree(element) {
    return Boolean(
      element.closest('[hidden], [aria-hidden="true"], [inert]')
    );
  }

  function isInsideTransientChoiceList(element) {
    const transientContainer = element.closest([
      '[role="listbox"]',
      '[role="menu"]',
      '[role="option"]',
      '[role="tree"]',
      '[role="grid"]',
      '[class*="dropdown" i]',
      '[class*="popover" i]',
      '[class*="menu" i]',
      '[class*="select-dropdown" i]',
      '[class*="cascader" i]',
    ].join(", "));
    if (!transientContainer) return false;

    const form = element.closest("form");
    return !form || !form.contains(transientContainer);
  }

  function isSupportedControl(element) {
    const tagName = element.tagName.toLowerCase();
    if (!["input", "textarea", "select"].includes(tagName)) return false;
    if (element.disabled) return false;
    if (!isVisible(element) || isInHiddenTree(element)) return false;
    if (isInsideTransientChoiceList(element)) return false;

    const type = (element.type || "text").toLowerCase();
    return ![
      "hidden",
      "button",
      "submit",
      "reset",
      "image",
      "file",
    ].includes(type);
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

    const title = normalizeText(element.getAttribute("title"));
    if (title) return title;

    const groupQuestion = questionFor(element);
    if (groupQuestion) return groupQuestion;

    const placeholder = normalizeText(element.getAttribute("placeholder"));
    if (placeholder) return placeholder;

    return null;
  }

  function formItemFor(element) {
    return element.closest([
      ".form-item",
      ".form-group",
      ".field",
      ".ant-form-item",
      ".el-form-item",
      "[class*='form-item' i]",
      "[class*='form_group' i]",
      "[class*='field' i]",
    ].join(", "));
  }

  function questionFor(element) {
    const fieldset = element.closest("fieldset");
    if (fieldset) {
      const legendText = normalizeText(
        fieldset.querySelector("legend")?.innerText ||
        fieldset.querySelector("legend")?.textContent
      );
      if (legendText) return legendText;
    }

    const formItem = formItemFor(element);
    if (formItem) {
      const labelNode = formItem.querySelector([
        ".label",
        ".title",
        ".question",
        ".ant-form-item-label",
        ".el-form-item__label",
        "label",
        "[class*='label' i]",
        "[class*='title' i]",
        "[class*='question' i]",
      ].join(", "));
      const labelText = normalizeText(
        labelNode?.innerText || labelNode?.textContent
      );
      if (labelText) return labelText;
    }

    const previousText = normalizeText(
      element.previousElementSibling?.innerText ||
      element.previousElementSibling?.textContent
    );
    if (previousText && previousText.length <= 120) {
      return previousText;
    }

    return null;
  }

  function displayLabelFor(element) {
    const ownLabel = labelFor(element);
    const type = (element.type || "").toLowerCase();
    if (!["radio", "checkbox"].includes(type)) return ownLabel;

    const question = questionFor(element);
    if (!question || !ownLabel || question === ownLabel) return ownLabel;
    return `${question} - ${ownLabel}`;
  }

  function hasUsefulIdentity(element, label) {
    return Boolean(
      label ||
      normalizeText(element.getAttribute("placeholder")) ||
      normalizeText(element.getAttribute("name")) ||
      normalizeText(element.id)
    );
  }

  function fieldKey(field) {
    if (field.name) return `${field.field_type}:name:${field.name}`;
    if (field.html_id) return `${field.field_type}:id:${field.html_id}`;
    if (field.label) return `${field.field_type}:label:${field.label}`;
    return `${field.field_type}:selector:${field.selector}`;
  }

  function currentValueFor(element, fieldType) {
    if (fieldType === "checkbox" || fieldType === "radio") {
      return element.checked ? "checked" : null;
    }
    if (element.tagName.toLowerCase() === "select") {
      return normalizeText(element.selectedOptions?.[0]?.textContent) ||
        normalizeText(element.value);
    }
    return normalizeText(element.value);
  }

  const fields = [];
  const seen = new Set();

  elements.forEach(element => {
    if (!isSupportedControl(element)) return;

    const tagName = element.tagName.toLowerCase();
    const fieldType = tagName === "input"
      ? (element.type || "text").toLowerCase()
      : tagName;
    const label = displayLabelFor(element);
    if (!hasUsefulIdentity(element, label)) return;

    const field = {
      label,
      selector: selectorFor(element),
      field_type: fieldType,
      placeholder: normalizeText(element.getAttribute("placeholder")),
      name: normalizeText(element.getAttribute("name")),
      html_id: normalizeText(element.id),
      current_value: currentValueFor(element, fieldType),
      required:
        Boolean(element.required) ||
        element.getAttribute("aria-required") === "true",
    };
    const key = fieldKey(field);
    if (seen.has(key)) return;

    seen.add(key);
    fields.push(field);
  });

  return fields;
}
"""

_LOGIN_DETECTION_SCRIPT = """
() => {
  const url = window.location.href.toLowerCase();
  const title = document.title.toLowerCase();
  const bodyText = (document.body?.innerText || "").toLowerCase();
  const passwordInputs = document.querySelectorAll('input[type="password"]').length;
  const visibleInputs = Array.from(
    document.querySelectorAll('input:not([type="hidden"]), textarea, select')
  ).filter(element => {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.visibility !== "hidden" &&
      style.display !== "none" &&
      rect.width > 0 &&
      rect.height > 0;
  });

  if (passwordInputs > 0) return true;
  if (/login|signin|passport|auth|account/.test(url)) return true;
  if (/登录|登陆|扫码登录|账号登录|密码登录|sign in|log in/.test(title)) return true;

  const loginWords = [
    "登录",
    "登陆",
    "扫码登录",
    "账号登录",
    "密码登录",
    "sign in",
    "log in",
  ];
  const hasLoginCopy = loginWords.some(word => bodyText.includes(word));
  return hasLoginCopy && visibleInputs.length <= 6;
}
"""
