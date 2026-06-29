"""Extract form controls and their metadata with Playwright."""

from dataclasses import dataclass

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from app.services.browser_session import run_with_persistent_page


@dataclass(frozen=True)
class ExtractedFormField:
    """A serializable form control discovered on a web page."""

    element_ref: str
    form_title: str | None
    section_title: str | None
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

  function cleanLabelText(value) {
    const text = normalizeText(value);
    if (!text) return null;
    const withoutRequiredMarker = text
      .replace(/^[*＊\\s]+/, "")
      .replace(/[*＊\\s]+$/, "")
      .replace(/^(必填|必选|required)\\s*[:：]?\\s*/i, "")
      .replace(/\\s*(必填|必选|required)$/i, "")
      .replace(/[\\s\\u00a0]+\\+[\\s\\u00a0]*\\d[\\d\\s\\u00a0-]*.*$/, "")
      .replace(/[\\s\\u00a0]+(请输入|请填写|请选择|please enter|please input|please select)$/i, "")
      .replace(/[\\s\\u00a0]*[-–—~至到]+$/, "")
      .trim();
    return withoutRequiredMarker || text;
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

  function visibleTextFrom(node) {
    if (!node || !elementIsVisible(node)) return null;
    return normalizeText(node.innerText || node.textContent);
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
    if (!elementIsVisible(element) || isInHiddenTree(element)) return false;
    if (isInsideTransientChoiceList(element)) return false;

    const type = (element.type || "text").toLowerCase();
    return !(tagName === "input" && NON_FILLABLE_INPUT_TYPES.has(type));
  }

  function shortTextFrom(node) {
    const text = normalizeText(node?.innerText || node?.textContent);
    if (!text || text.length > 160) return null;
    return text;
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

  function uniqueTextParts(parts) {
    const seen = new Set();
    return parts.filter(part => {
      const normalized = normalizedLowerText(part);
      if (!normalized || seen.has(normalized)) return false;
      seen.add(normalized);
      return true;
    });
  }

  function formItemFor(element) {
    let current = element.parentElement;
    while (current && current !== document.body) {
      const className =
        typeof current.className === "string" ? current.className : "";
      const normalizedClass = className.toLowerCase();
      const isFormItemPart =
        /(^|[-_\\s])(control|content|core|label|help|extra|feedback|message)([-_\\s]|$)/.test(
          normalizedClass
        ) || normalizedClass.includes("date-uxform-field-cascade");
      const isDirectFormItem = current.matches([
        ".form-item",
        ".form-group",
        ".next-form-item",
        ".kuma-uxform-field",
        ".ant-form-item",
        ".el-form-item",
        ".arco-form-item",
        ".semi-form-field",
        ".semi-form-field-wrapper",
        "[role='group']",
      ].join(", "));
      const isNamedFormItem =
        /form[-_]?item|form[-_]?field|formgroup|form_group|uxform[-_]?field/.test(
          normalizedClass
        );

      if ((isDirectFormItem || isNamedFormItem) && !isFormItemPart) {
        return current;
      }

      current = current.parentElement;
    }

    return element.closest(".field, .field-row, .control-group, li, label");
  }

  function fieldsetLegendText(element) {
    const fieldset = element.closest("fieldset");
    const legend = fieldset?.querySelector("legend");
    return cleanLabelText(legend?.innerText || legend?.textContent);
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
    const formItem = formItemFor(element);
    if (formItem) {
      const labelNode = formItem.querySelector([
        ".kuma-label .label-content",
        ".kuma-label",
        ".next-form-item-label",
        ".label",
        ".title",
        ".question",
        ".ant-form-item-label",
        ".ant-form-item-required",
        ".el-form-item__label",
        ".arco-form-label-item",
        ".semi-form-field-label",
        "label",
        "[class*='item-label' i]",
        "[class*='form-label' i]",
        "[class*='label' i]",
        "[class*='title' i]",
        "[class*='question' i]",
      ].join(", "));
      const labelText = cleanLabelText(
        labelNode?.innerText || labelNode?.textContent
      );
      if (labelText) return labelText;

      const text = textOutsideControls(formItem, element);
      if (text && text.length <= 180) return text;
    }

    return null;
  }

  function labelFor(element) {
    const labels = element.labels
      ? Array.from(element.labels)
          .map(label => cleanLabelText(label.innerText || label.textContent))
          .filter(Boolean)
      : [];
    if (labels.length) return labels.join(" ");

    const ariaLabel = cleanLabelText(element.getAttribute("aria-label"));
    if (ariaLabel) return ariaLabel;

    const labelledBy = element.getAttribute("aria-labelledby");
    if (labelledBy) {
      const text = labelledBy
        .split(/\\s+/)
        .map(id => document.getElementById(id))
        .filter(Boolean)
        .map(node => cleanLabelText(node.innerText || node.textContent))
        .filter(Boolean)
        .join(" ");
      if (text) return text;
    }

    const legend = fieldsetLegendText(element);
    const ancestor = ancestorContextText(element);
    const previous = previousSiblingText(element);
    const context = normalizeText(
      uniqueTextParts([legend, ancestor, previous].filter(Boolean)).join(" ")
    );
    if (context) return cleanLabelText(context);

    const title = cleanLabelText(element.getAttribute("title"));
    if (title) return title;

    return placeholderFor(element);
  }

  function requiredFor(element, label) {
    if (Boolean(element.required) || element.getAttribute("aria-required") === "true") {
      return true;
    }

    const formItem = formItemFor(element);
    const requiredContainer = element.closest('[aria-required="true"], [required]');
    if (requiredContainer) return true;

    if (formItem) {
      const requiredNode = formItem.querySelector([
        ".required",
        ".ant-form-item-required",
        ".el-form-item.is-required",
        ".next-form-item-required",
        ".semi-form-field-label-required",
        ".arco-form-label-item-required",
        "[class*='required' i]",
        "[class*='asterisk' i]",
      ].join(", "));
      if (requiredNode && elementIsVisible(requiredNode)) return true;

      const labelText = visibleTextFrom(formItem.querySelector([
        ".kuma-label",
        ".next-form-item-label",
        ".ant-form-item-label",
        ".el-form-item__label",
        ".arco-form-label-item",
        ".semi-form-field-label",
        "label",
        "[class*='item-label' i]",
        "[class*='form-label' i]",
        "[class*='label' i]",
      ].join(", ")));
      if (/^[\\s*＊]+/.test(labelText || "") || /[*＊]/.test(labelText || "")) {
        return true;
      }

      const validationText = visibleTextFrom(formItem);
      if (/不能为空|不可为空|必填|必选|required|must not be empty|please enter/i.test(validationText || "")) {
        return true;
      }
    }

    return /^[\\s*＊]+/.test(label || "");
  }

  function textByIds(value) {
    if (!value) return null;
    const text = value
      .split(/\\s+/)
      .map(id => document.getElementById(id))
      .filter(Boolean)
      .map(shortTextFrom)
      .filter(Boolean)
      .join(" ");
    return normalizeText(text);
  }

  function headingBefore(element) {
    const headings = Array.from(
      document.querySelectorAll("h1, h2, h3, h4, legend, [role='heading']")
    ).filter(heading => {
      if (!elementIsVisible(heading)) return false;
      const position = heading.compareDocumentPosition(element);
      return Boolean(position & Node.DOCUMENT_POSITION_FOLLOWING);
    });
    return shortTextFrom(headings.at(-1));
  }

  function headingBeforeWithin(container, element) {
    if (!container) return null;
    const headings = Array.from(
      container.querySelectorAll("h2, h3, h4, h5, legend, [role='heading']")
    ).filter(heading => {
      if (!elementIsVisible(heading)) return false;
      const position = heading.compareDocumentPosition(element);
      return Boolean(position & Node.DOCUMENT_POSITION_FOLLOWING);
    });
    return shortTextFrom(headings.at(-1));
  }

  function formTitleFor(element) {
    const container = element.closest(
      "form, section, article, [role='form'], .uxcore-card, .form-card, [class*='form-card' i]"
    );
    if (container) {
      const labelledText = textByIds(container.getAttribute("aria-labelledby"));
      if (labelledText) return labelledText;

      const ariaLabel = normalizeText(container.getAttribute("aria-label"));
      if (ariaLabel) return ariaLabel;

      const heading = Array.from(
        container.querySelectorAll([
          "h1",
          "h2",
          "h3",
          "h4",
          "legend",
          "[role='heading']",
          ".uxcore-card-title",
          ".next-card-title",
          ".card-title",
          "[class*='card-title' i]",
          "[class*='section-title' i]",
        ].join(", "))
      )
        .map(shortTextFrom)
        .find(Boolean);
      if (heading) return heading;
    }

    return headingBefore(element);
  }

  function sectionTitleFor(element, fieldLabel) {
    const fieldset = element.closest("fieldset");
    if (fieldset) {
      const legendText = shortTextFrom(fieldset.querySelector("legend"));
      if (legendText && legendText !== fieldLabel) return legendText;
    }

    const container = element.closest([
      "[class*='section' i]",
      "[class*='card' i]",
      "[class*='panel' i]",
      "[class*='collapse' i]",
      "[class*='experience' i]",
      "[class*='education' i]",
      "section",
      "article",
      "li",
    ].join(", "));
    const heading = headingBeforeWithin(container, element);
    if (heading && heading !== fieldLabel) return heading;

    return null;
  }

  function displayLabelFor(element) {
    const ownLabel = labelFor(element);
    const type = (element.type || "").toLowerCase();
    if (!["radio", "checkbox"].includes(type)) return ownLabel;

    const question = ancestorContextText(element) || fieldsetLegendText(element);
    if (!question || !ownLabel || question === ownLabel) return ownLabel;
    const normalizedQuestion = normalizedLowerText(cleanLabelText(question));
    const normalizedOwnLabel = normalizedLowerText(cleanLabelText(ownLabel));
    if (
      normalizedQuestion === normalizedOwnLabel ||
      normalizedQuestion.includes(normalizedOwnLabel) ||
      normalizedOwnLabel.includes(normalizedQuestion)
    ) {
      return cleanLabelText(ownLabel);
    }
    return `${question} - ${ownLabel}`;
  }

  function placeholderFor(element) {
    const nativePlaceholder = normalizeText(element.getAttribute("placeholder"));
    if (nativePlaceholder) return nativePlaceholder;

    const formItem = formItemFor(element);
    if (formItem) {
      const componentPlaceholder = [
        ".kuma-select2-selection__placeholder",
        ".next-select-placeholder",
        ".ant-select-selection-placeholder",
        ".el-input__inner[placeholder]",
        "[class*='placeholder' i]",
      ]
        .map(selector => formItem.querySelector(selector))
        .filter(Boolean)
        .map(node => normalizeText(
          node.getAttribute("placeholder") ||
          node.innerText ||
          node.textContent
        ))
        .find(Boolean);
      if (componentPlaceholder) return componentPlaceholder;
    }

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

  function fieldKey(field) {
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
    const field = {
      element_ref: "",
      form_title: formTitleFor(element),
      section_title: sectionTitleFor(element, label),
      label,
      selector: selectorFor(element),
      field_type: fieldType,
      placeholder: placeholderFor(element),
      name: normalizeText(element.getAttribute("name")),
      html_id: normalizeText(element.id),
      current_value: currentValueFor(element, fieldType),
      required: requiredFor(element, label),
    };
    if (!hasMeaningfulMetadata(field)) return;

    const key = fieldKey(field);
    if (seen.has(key)) return;

    seen.add(key);
    field.element_ref = `field_${fields.length + 1}`;
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
