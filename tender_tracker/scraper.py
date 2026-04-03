from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from tender_tracker.config import AppConfig


DATE_FORMATS = (
    "%d-%b-%Y %I:%M %p",
    "%d-%b-%Y %H:%M",
    "%d %b %Y %I:%M %p",
    "%d %b %Y %H:%M",
)
ROW_NUMBER_PREFIX_PATTERN = re.compile(r"^\d+\.\s+")


class ScraperError(RuntimeError):
    """Raised when tender data cannot be fetched or parsed."""


def clean_text(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split())


def parse_portal_datetime(value: str | None) -> str | None:
    cleaned = clean_text(value)
    if not cleaned:
        return None

    for date_format in DATE_FORMATS:
        try:
            parsed = datetime.strptime(cleaned, date_format)
            return parsed.isoformat()
        except ValueError:
            continue
    return None


class TenderTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._table_depth = 0
        self._inside_row = False
        self._inside_cell = False
        self._current_cell_text: list[str] = []
        self._current_cell_links: list[str] = []
        self._current_row: list[dict[str, Any]] = []
        self.rows: list[list[dict[str, Any]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table":
            self._table_depth += 1
            return

        if self._table_depth == 0:
            return

        if tag == "tr":
            self._inside_row = True
            self._current_row = []
            return

        if self._inside_row and tag in {"td", "th"}:
            self._inside_cell = True
            self._current_cell_text = []
            self._current_cell_links = []
            return

        if self._inside_cell and tag == "a":
            href = attributes.get("href")
            if href:
                self._current_cell_links.append(href)

    def handle_data(self, data: str) -> None:
        if self._inside_cell:
            self._current_cell_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self._table_depth > 0:
            self._table_depth -= 1
            return

        if tag in {"td", "th"} and self._inside_cell:
            self._current_row.append(
                {
                    "text": clean_text("".join(self._current_cell_text)),
                    "links": list(self._current_cell_links),
                }
            )
            self._inside_cell = False
            self._current_cell_text = []
            self._current_cell_links = []
            return

        if tag == "tr" and self._inside_row:
            self.rows.append(list(self._current_row))
            self._inside_row = False
            self._current_row = []


def build_fingerprint(tender: dict[str, Any]) -> str:
    fingerprint_source = "|".join(
        [
            clean_text(tender.get("source", "")),
            clean_text(tender.get("source_tender_id", "")),
            normalize_tender_title(tender.get("title", "")),
            clean_text(tender.get("closing_date", "")),
        ]
    )
    return hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()


def _strip_tags(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value, flags=re.S)
    return clean_text(html.unescape(without_tags))


def normalize_tender_title(value: str | None) -> str:
    cleaned = clean_text(value)
    if not cleaned:
        return ""
    return ROW_NUMBER_PREFIX_PATTERN.sub("", cleaned)


def extract_detail_fields(detail_html: str) -> dict[str, str]:
    pattern = re.compile(
        r"<td[^>]*class=[\"']td_caption[\"'][^>]*>\s*<b>(.*?)</b>\s*</td>"
        r"\s*<td[^>]*class=[\"']td_field[\"'][^>]*>(.*?)</td>",
        re.I | re.S,
    )
    fields: dict[str, str] = {}
    for raw_label, raw_value in pattern.findall(detail_html):
        label = _strip_tags(raw_label).rstrip(":")
        value = _strip_tags(raw_value)
        if label and value and label not in fields:
            fields[label] = value
    return fields


def _find_detail_value(detail_fields: dict[str, str], *labels: str) -> str:
    for label in labels:
        value = clean_text(detail_fields.get(label, ""))
        if value:
            return value
    return ""


def extract_emd_amount(
    detail_fields: dict[str, str],
    detail_html: str | None = None,
) -> str:
    searchable_parts = [*detail_fields.keys(), *detail_fields.values()]
    if detail_html:
        searchable_parts.append(_strip_tags(detail_html))
    searchable_text = clean_text(" ".join(part for part in searchable_parts if part))
    match = re.search(
        r"EMD Amount in (?:₹|Rs\.?)?\s*([0-9][0-9,]*(?:\.\d+)?)",
        searchable_text,
        re.I,
    )
    if match:
        return clean_text(match.group(1))
    return ""


def enrich_tender_from_detail_page(
    session: requests.Session,
    tender: dict[str, Any],
    *,
    timeout_seconds: int,
) -> dict[str, Any]:
    source_url = tender.get("source_url", "")
    if not source_url:
        return tender

    response = session.get(source_url, timeout=timeout_seconds)
    response.raise_for_status()
    detail_fields = extract_detail_fields(response.text)

    organisation_chain = detail_fields.get("Organisation Chain", "")
    tender_inviting_authority = detail_fields.get("Name", "")
    tender["department"] = organisation_chain
    if not tender.get("location"):
        tender["location"] = _find_detail_value(detail_fields, "Location")
    if not tender.get("emd"):
        tender["emd"] = extract_emd_amount(detail_fields, response.text)
    if not tender.get("estimated_value"):
        tender["estimated_value"] = _find_detail_value(
            detail_fields,
            "Tender Value in ₹",
            "Tender Value",
        )
    if not tender.get("description"):
        tender["description"] = _find_detail_value(
            detail_fields,
            "Name of Work / Subwork / Packages",
            "Work Description",
            "Title",
        )
    tender["raw_payload"]["detail_fields"] = detail_fields
    if tender_inviting_authority:
        tender["raw_payload"]["tender_inviting_authority"] = tender_inviting_authority
    return tender


def _session_with_retries() -> requests.Session:
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.trust_env = False
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        }
    )
    return session


def _parse_latest_tender_rows(
    rows: list[list[dict[str, Any]]],
    *,
    base_url: str,
    source_name: str,
    limit: int,
) -> list[dict[str, Any]]:
    tenders: list[dict[str, Any]] = []
    latest_section_started = False

    for row in rows:
        cell_texts = [clean_text(cell["text"]) for cell in row if clean_text(cell["text"])]
        if not cell_texts:
            continue

        row_signature = " | ".join(cell_texts).lower()
        if (
            "tender title" in row_signature
            and "reference no" in row_signature
            and "closing date" in row_signature
        ):
            latest_section_started = True
            continue

        if not latest_section_started:
            continue

        if "latest tenders updates every" in row_signature:
            break

        if any(
            marker in row_signature
            for marker in ("more...", "search | active tenders", "results of tenders")
        ):
            break

        normalized = list(cell_texts)
        if normalized[0].isdigit() and len(normalized) >= 5:
            normalized = normalized[1:]

        if len(normalized) < 4:
            continue

        title, reference_no, closing_date, bid_opening_date = normalized[:4]
        title = normalize_tender_title(title)
        source_url = base_url
        for cell in row:
            if cell["links"]:
                source_url = urljoin(base_url, cell["links"][0])
                break

        tender = {
            "source": source_name,
            "source_tender_id": reference_no or source_url,
            "title": title,
            "description": "",
            "reference_no": reference_no,
            "department": "",
            "location": "",
            "emd": "",
            "estimated_value": "",
            "closing_date": closing_date,
            "closing_date_iso": parse_portal_datetime(closing_date),
            "bid_opening_date": bid_opening_date,
            "bid_opening_date_iso": parse_portal_datetime(bid_opening_date),
            "source_url": source_url,
            "raw_payload": {
                "cells": normalized,
                "row_signature": row_signature,
            },
        }
        tender["fingerprint"] = build_fingerprint(tender)
        tenders.append(tender)

        if len(tenders) >= limit:
            break

    return tenders


def fetch_latest_tenders(config: AppConfig) -> list[dict[str, Any]]:
    session = _session_with_retries()
    response = session.get(
        config.source_url,
        timeout=config.request_timeout_seconds,
    )
    response.raise_for_status()
    html = response.text

    parser = TenderTableParser()
    parser.feed(html)
    tenders = _parse_latest_tender_rows(
        parser.rows,
        base_url=config.source_url,
        source_name=config.source_name,
        limit=config.max_scraped_tenders,
    )

    if tenders:
        enriched_tenders = []
        for tender in tenders:
            try:
                enriched_tenders.append(
                    enrich_tender_from_detail_page(
                        session,
                        tender,
                        timeout_seconds=config.request_timeout_seconds,
                    )
                )
            except requests.RequestException:
                enriched_tenders.append(tender)
        return enriched_tenders

    title_matches = re.findall(
        r"Tender Title.*?(\d+\.\s*.+?)Latest Tenders updates every",
        clean_text(html),
    )
    if title_matches:
        raise ScraperError(
            "The source page structure changed and table parsing needs an update."
        )

    raise ScraperError("No latest tender rows could be parsed from the source page.")
