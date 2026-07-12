"""Extract structured page data using Playwright."""

from dataclasses import dataclass, field
from typing import Any

from playwright.sync_api import Page

from app.services.browser_session import run_with_persistent_page


MAX_TEXT_BLOCK_LENGTH = 2000
MAX_HEADING_LENGTH = 500
MAX_LINK_TEXT_LENGTH = 500
MAX_URL_LENGTH = 2000
MAX_TABLE_CELL_LENGTH = 500


@dataclass(frozen=True)
class ExtractedHeading:
    """A heading element extracted from a page."""

    level: int
    text: str


@dataclass(frozen=True)
class ExtractedLink:
    """A hyperlink extracted from a page."""

    text: str
    href: str


@dataclass(frozen=True)
class ExtractedTable:
    """A table extracted from a page."""

    headers: list[str]
    rows: list[list[str]]


@dataclass(frozen=True)
class ExtractedForm:
    """A form extracted from a page."""

    action: str | None
    method: str
    field_count: int


@dataclass(frozen=True)
class PageExtractionResult:
    """Structured data extracted from a web page."""

    title: str
    headings: list[ExtractedHeading]
    main_text_blocks: list[str]
    links: list[ExtractedLink]
    tables: list[ExtractedTable]
    forms: list[ExtractedForm]


def _truncate(text: str, max_length: int) -> str:
    """Truncate text to max_length with ellipsis if needed."""

    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def _build_result(raw: dict[str, Any]) -> PageExtractionResult:
    """Build extraction result from raw page evaluation output."""

    return PageExtractionResult(
        title=_truncate(raw.get("title", ""), MAX_HEADING_LENGTH),
        headings=[
            ExtractedHeading(
                level=heading.get("level", 1),
                text=_truncate(heading.get("text", ""), MAX_HEADING_LENGTH),
            )
            for heading in raw.get("headings", [])
        ],
        main_text_blocks=[
            _truncate(block, MAX_TEXT_BLOCK_LENGTH)
            for block in raw.get("main_text_blocks", [])
        ],
        links=[
            ExtractedLink(
                text=_truncate(link.get("text", ""), MAX_LINK_TEXT_LENGTH),
                href=_truncate(link.get("href", ""), MAX_URL_LENGTH),
            )
            for link in raw.get("links", [])
        ],
        tables=[
            ExtractedTable(
                headers=[_truncate(h, MAX_TABLE_CELL_LENGTH) for h in table.get("headers", [])],
                rows=[
                    [_truncate(cell, MAX_TABLE_CELL_LENGTH) for cell in row]
                    for row in table.get("rows", [])
                ],
            )
            for table in raw.get("tables", [])
        ],
        forms=[
            ExtractedForm(
                action=form.get("action"),
                method=form.get("method", "GET"),
                field_count=form.get("field_count", 0),
            )
            for form in raw.get("forms", [])
        ],
    )


def extract_page_sync(page: Page, url: str) -> PageExtractionResult:
    """Extract structured data from a page using a provided Playwright page instance."""

    page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    raw = page.evaluate(_EXTRACT_PAGE_SCRIPT)
    return _build_result(raw)


async def extract_page(url: str, profile_id: int) -> PageExtractionResult:
    """Open a page and extract structured data including title, headings, text, links, tables, and forms."""

    def _extract(page: Page) -> PageExtractionResult:
        return extract_page_sync(page, url)

    return await run_with_persistent_page(url, profile_id, _extract)


_EXTRACT_PAGE_SCRIPT = """
() => {
    function normalizeText(value) {
        if (!value) return '';
        return value.replace(/\\s+/g, ' ').trim();
    }

    function elementIsVisible(element) {
        if (element.hidden || element.getAttribute('aria-hidden') === 'true') {
            return false;
        }
        const style = window.getComputedStyle(element);
        if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0) {
            return false;
        }
        const rect = element.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
    }

    const title = normalizeText(document.title);

    const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6'))
        .filter(elementIsVisible)
        .map(heading => ({
            level: parseInt(heading.tagName[1]),
            text: normalizeText(heading.innerText || heading.textContent),
        }))
        .filter(h => h.text);

    const mainTextBlocks = Array.from(document.querySelectorAll('p, article > *, section > *'))
        .filter(element => elementIsVisible(element) && !element.matches('h1, h2, h3, h4, h5, h6, script, style, nav, footer, header'))
        .map(element => normalizeText(element.innerText || element.textContent))
        .filter(text => text && text.length > 20);

    const links = Array.from(document.querySelectorAll('a[href]'))
        .filter(elementIsVisible)
        .map(link => ({
            text: normalizeText(link.innerText || link.textContent),
            href: link.href,
        }))
        .filter(link => link.href && link.href !== '#');

    const tables = Array.from(document.querySelectorAll('table'))
        .filter(table => {
            const rect = table.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0;
        })
        .map(table => {
            const headers = Array.from(table.querySelectorAll('th'))
                .map(th => normalizeText(th.innerText || th.textContent));
            
            const rows = Array.from(table.querySelectorAll('tr'))
                .filter(tr => tr.querySelectorAll('td, th').length > 0)
                .slice(headers.length > 0 ? 1 : 0)
                .map(tr => Array.from(tr.querySelectorAll('td'))
                    .map(td => normalizeText(td.innerText || td.textContent))
                );

            return { headers, rows };
        })
        .filter(t => t.headers.length > 0 || t.rows.length > 0);

    const forms = Array.from(document.querySelectorAll('form'))
        .map(form => ({
            action: form.action || null,
            method: (form.method || 'GET').toUpperCase(),
            field_count: form.querySelectorAll('input, textarea, select, button').length,
        }));

    return {
        title,
        headings,
        main_text_blocks: mainTextBlocks,
        links,
        tables,
        forms,
    };
}
"""