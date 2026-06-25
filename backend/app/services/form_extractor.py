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
  const NON_FILLABLE_INPUT_TYPES = new Set([
    "hidden",
    "button",
    "submit",
    "reset",
    "image",
    "file",
  ]);
  const GENERIC_PROMPTS = new Set([
    "input",
    "enter",
    "please enter",
    "please input",
    "select",
    "please select",
    "请输入",
    "请填写",
    "请选择",
  ]);
  const STABLE_ATTRIBUTES = [
    "data-testid",
    "data-test",
    "data-cy",
    "aria-label",
    "autocomplete",
    "placeholder",
  ];

  function normalizeText(value) {
    if (!value) return null;
    const normalized = value.replace(/\\s+/g, " ").trim();
    return normalized || null;
  }

  function normalizedLowerText(value) {
    return (normalizeText(value) || "").toLowerCase();
  }

  function isUnique(selector) {
    try {
      return document.querySelectorAll(selector).length === 1;
    } catch {
      return false;
    }
  }

  function attrSelector(element, attribute) {
    const value = normalizeText(element.getAttribute(attribute));
    if (!value) return null;
    return `${element.tagName.toLowerCase()}[${attribute}="${CSS.escape(value)}"]`;
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

    for (const attribute of STABLE_ATTRIBUTES) {
      const selector = attrSelector(element, attribute);
      if (selector && isUnique(selector)) return selector;
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

  function elementIsVisible(element) {
    if (element.hidden || element.getAttribute("aria-hidden") === "true") {
      return false;
    }

    const style = window.getComputedStyle(element);
    if (
      style.display === "none" ||
      style.visibility === "hidden" ||
      Number(style.opacity) === 0
    ) {
      return false;
    }

    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function isSkippableControl(element) {
    const tagName = element.tagName.toLowerCase();
    const fieldType = tagName === "input"
      ? (element.type || "text").toLowerCase()
      : tagName;

    if (!elementIsVisible(element)) return true;
    if (element.disabled || element.readOnly) return true;
    if (tagName === "input" && NON_FILLABLE_INPUT_TYPES.has(fieldType)) {
      return true;
    }
    return false;
  }

  function isTextNodeVisible(node) {
    const parent = node.parentElement;
    return parent && elementIsVisible(parent);
  }

  function isInsideControl(node, rootControl) {
    const parent = node.parentElement;
    return Boolean(
      parent?.closest("input, textarea, select, button, option, script, style") &&
      !parent.closest("label")?.contains(rootControl)
    );
  }

  function textOutsideControls(container, rootControl) {
    const walker = document.createTreeWalker(
      container,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode(node) {
          if (!isTextNodeVisible(node)) return NodeFilter.FILTER_REJECT;
          if (isInsideControl(node, rootControl)) return NodeFilter.FILTER_REJECT;
          return NodeFilter.FILTER_ACCEPT;
        },
      }
    );

    const parts = [];
    let node = walker.nextNode();
    while (node) {
      const text = normalizeText(node.textContent);
      if (text) parts.push(text);
      node = walker.nextNode();
    }
    return normalizeText(parts.join(" "));
  }

  function fieldsetLegendText(element) {
    const fieldset = element.closest("fieldset");
    const legend = fieldset?.querySelector("legend");
    return normalizeText(legend?.innerText || legend?.textContent);
  }

  function previousSiblingText(element) {
    const parts = [];
    let sibling = element.previousElementSibling;
    while (sibling && parts.join(" ").length < 140) {
      if (!sibling.matches("input, textarea, select, button")) {
        const text = textOutsideControls(sibling, element);
        if (text) parts.unshift(text);
      }
      sibling = sibling.previousElementSibling;
    }
    return normalizeText(parts.join(" "));
  }

  function ancestorContextText(element) {
    const selector = [
      ".ant-form-item",
      ".el-form-item",
      ".semi-form-field",
      ".form-item",
      ".form-group",
      ".field",
      ".field-row",
      ".control-group",
      "[role='group']",
      "li",
      "label",
    ].join(",");
    let current = element.parentElement;
    let fallback = null;

    while (current && current !== document.body) {
      if (current.matches(selector)) {
        const text = textOutsideControls(current, element);
        if (text && text.length <= 180) return text;
        if (text && text.length <= 280 && !fallback) fallback = text;
      }
      current = current.parentElement;
    }

    return fallback;
  }

  function uniqueTextParts(parts) {
    const seen = new Set();
    return parts.filter(part => {
      const normalized = normalizedLowerText(part);
      if (!normalized || seen.has(normalized)) return false;
      seen.add(normalized);
      return true;
    });
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

    const legend = fieldsetLegendText(element);
    const previous = previousSiblingText(element);
    const ancestor = ancestorContextText(element);
    const context = normalizeText(
      uniqueTextParts([legend, previous, ancestor].filter(Boolean)).join(" ")
    );
    if (context) return context;

    return null;
  }

  function hasMeaningfulMetadata(field) {
    const metadata = [
      field.label,
      field.name,
      field.html_id,
      field.placeholder,
    ].filter(Boolean).join(" ");
    if (!metadata) return false;

    const placeholder = normalizedLowerText(field.placeholder);
    const hasOnlyGenericPrompt =
      !field.label &&
      !field.name &&
      !field.html_id &&
      GENERIC_PROMPTS.has(placeholder);
    return !hasOnlyGenericPrompt;
  }

  return elements.map(element => {
    if (isSkippableControl(element)) return null;

    const tagName = element.tagName.toLowerCase();
    const fieldType = tagName === "input"
      ? (element.type || "text").toLowerCase()
      : tagName;

    const field = {
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

    return hasMeaningfulMetadata(field) ? field : null;
  }).filter(Boolean);
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
