"""OAI-PMH harvesting utilities for the DSpace metadata scrape."""

from __future__ import annotations

import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ga_schemas.models import RawThesis

OAI_ENDPOINT = "https://dspace.cuni.cz/oai/request"
DEFAULT_SET_SPEC = "col_20.500.11956_1918"
DEFAULT_METADATA_PREFIX = "xoai"
DEFAULT_USER_AGENT = (
    "graduation-arena/0.0.0 "
    "(metadata research harvester; contact: set GA_PIPELINE_CONTACT_EMAIL)"
)
OAI_NS = {"oai": "http://www.openarchives.org/OAI/2.0/"}


class OAIError(RuntimeError):
    """Raised when the OAI endpoint returns malformed or failed data."""


@dataclass(frozen=True)
class HarvestConfig:
    """Configuration for a polite OAI-PMH ListRecords harvest."""

    endpoint: str = OAI_ENDPOINT
    set_spec: str = DEFAULT_SET_SPEC
    metadata_prefix: str = DEFAULT_METADATA_PREFIX
    from_date: str | None = None
    until_date: str | None = None
    user_agent: str = DEFAULT_USER_AGENT
    delay_seconds: float = 2.0


class OAIClient:
    """Small OAI-PMH client that follows ListRecords resumption tokens."""

    def __init__(self, config: HarvestConfig) -> None:
        self.config = config

    def list_records(self) -> Iterator[RawThesis]:
        """Yield validated ``RawThesis`` records from the configured OAI harvest."""
        token: str | None = None
        first_request = True

        while first_request or token:
            if not first_request and self.config.delay_seconds > 0:
                time.sleep(self.config.delay_seconds)
            first_request = False

            root = self._request(token)
            for error in root.findall("oai:error", OAI_NS):
                code = error.attrib.get("code", "unknown")
                raise OAIError(f"OAI-PMH error {code}: {error.text or ''}".strip())

            list_records = root.find("oai:ListRecords", OAI_NS)
            if list_records is None:
                raise OAIError("OAI-PMH response did not contain ListRecords")

            fetched_at = datetime.now(UTC)
            for record in list_records.findall("oai:record", OAI_NS):
                if _is_deleted(record):
                    continue
                yield raw_thesis_from_record(
                    record,
                    fetched_at=fetched_at,
                    metadata_prefix=self.config.metadata_prefix,
                )

            token_el = list_records.find("oai:resumptionToken", OAI_NS)
            token = token_el.text.strip() if token_el is not None and token_el.text else None

    def _request(self, token: str | None) -> ET.Element:
        params = {"verb": "ListRecords"}
        if token:
            params["resumptionToken"] = token
        else:
            params["metadataPrefix"] = self.config.metadata_prefix
            params["set"] = self.config.set_spec
            if self.config.from_date:
                params["from"] = self.config.from_date
            if self.config.until_date:
                params["until"] = self.config.until_date

        url = f"{self.config.endpoint}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, headers={"User-Agent": self.config.user_agent})
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()
        try:
            return ET.fromstring(body)
        except ET.ParseError as exc:
            raise OAIError(f"OAI-PMH response was not valid XML: {exc}") from exc


def raw_thesis_from_record(
    record: ET.Element,
    fetched_at: datetime,
    metadata_prefix: str = DEFAULT_METADATA_PREFIX,
) -> RawThesis:
    """Map one OAI ``record`` element into the loose raw thesis contract."""
    header = record.find("oai:header", OAI_NS)
    if header is None:
        raise OAIError("OAI record is missing a header")

    identifier = _required_text(header, "oai:identifier")
    handle = identifier.rsplit(":", 1)[-1]
    metadata = record.find("oai:metadata", OAI_NS)
    raw_metadata = _element_to_data(metadata[0]) if metadata is not None and len(metadata) else {}

    return RawThesis(
        source_id=identifier,
        source_url=f"https://dspace.cuni.cz/handle/{handle}",
        fetched_at=fetched_at,
        raw_fields={
            "oai": {
                "identifier": identifier,
                "datestamp": _required_text(header, "oai:datestamp"),
                "sets": [el.text for el in header.findall("oai:setSpec", OAI_NS) if el.text],
            },
            "metadata_prefix": metadata_prefix,
            "metadata": raw_metadata,
        },
    )


def _is_deleted(record: ET.Element) -> bool:
    header = record.find("oai:header", OAI_NS)
    return header is not None and header.attrib.get("status") == "deleted"


def _required_text(element: ET.Element, path: str) -> str:
    found = element.find(path, OAI_NS)
    if found is None or found.text is None or not found.text.strip():
        raise OAIError(f"OAI record is missing required field {path}")
    return found.text.strip()


def _element_to_data(element: ET.Element) -> dict[str, Any]:
    """Convert XML to JSON-friendly data while preserving attrs, text, and children."""
    data: dict[str, Any] = {"tag": _local_name(element.tag)}
    if element.attrib:
        data["attrs"] = dict(element.attrib)
    text = (element.text or "").strip()
    if text:
        data["text"] = text
    children = [_element_to_data(child) for child in element]
    if children:
        data["children"] = children
    return data


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag
