"""Persistent cache helpers for extracted form analysis results."""

import json
from dataclasses import asdict
from hashlib import sha256
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FormAnalysisCache, utc_now
from app.services.form_extractor import ExtractedFormAnalysis, ExtractedFormField


def normalize_analysis_url(url: str) -> str:
    """Return a stable URL key source for public form-analysis caching."""

    parsed = urlparse(url)
    scheme = (parsed.scheme or "https").lower()
    hostname = (parsed.hostname or "").lower()
    netloc = hostname
    if parsed.port:
        netloc = f"{hostname}:{parsed.port}"

    path = parsed.path or "/"
    if len(path) > 1:
        path = path.rstrip("/")

    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
    ]
    query = urlencode(sorted(query_items), doseq=True)
    return urlunparse((scheme, netloc, path, "", query, ""))


def _url_cache_key(normalized_url: str) -> str:
    """Hash a normalized URL for compact indexed storage."""

    return sha256(normalized_url.encode("utf-8")).hexdigest()


def read_form_analysis_cache(
    db: Session,
    url: str,
) -> ExtractedFormAnalysis | None:
    """Return cached non-login form analysis for a URL when available."""

    normalized_url = normalize_analysis_url(url)
    entry = db.scalar(
        select(FormAnalysisCache).where(
            FormAnalysisCache.url_cache_key == _url_cache_key(normalized_url)
        )
    )
    if entry is None:
        return None

    raw_fields = json.loads(entry.fields_json)
    entry.hit_count += 1
    entry.last_used_at = utc_now()
    return ExtractedFormAnalysis(
        fields=[ExtractedFormField(**field) for field in raw_fields],
        login_required=False,
    )


def write_form_analysis_cache(
    db: Session,
    url: str,
    analysis: ExtractedFormAnalysis,
) -> None:
    """Store non-login form analysis results for future same-URL tasks."""

    if analysis.login_required:
        return

    normalized_url = normalize_analysis_url(url)
    cache_key = _url_cache_key(normalized_url)
    fields_json = json.dumps(
        [asdict(field) for field in analysis.fields],
        ensure_ascii=False,
    )
    entry = db.scalar(
        select(FormAnalysisCache).where(
            FormAnalysisCache.url_cache_key == cache_key
        )
    )
    if entry is None:
        db.add(
            FormAnalysisCache(
                url_cache_key=cache_key,
                normalized_url=normalized_url,
                source_url=url,
                fields_json=fields_json,
            )
        )
        return

    entry.source_url = url
    entry.fields_json = fields_json
