"""Small OAI-PMH client and mapper for the DSpace source-access spike.

The goal here is deliberately narrow: prove that DSpace exposes the metadata
fields A1 depends on, and capture the raw OAI payload in a RawThesis-compatible
shape. Later issues can turn this into the full resumable harvester.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from time import sleep
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

OAI_ENDPOINT = "https://dspace.cuni.cz/oai/request"
DEFAULT_METADATA_PREFIX = "xoai"
DEFAULT_SET_SPEC = "col_20.500.11956_1918"
DEFAULT_USER_AGENT = "graduation-arena-a1-source-spike/0.1 (contact: local-dev)"
IES_MARKERS = ("Institute of Economic Studies", "Institut ekonomických studií")
DS_NS = {"oai": "http://www.openarchives.org/OAI/2.0/"}


class OaiError(RuntimeError):
    """Raised when an OAI-PMH response cannot be fetched or parsed."""


@dataclass(frozen=True)
class OaiRecord:
    """A single OAI-PMH record mapped to the provisional raw thesis contract."""

    identifier: str
    datestamp: str | None
    set_specs: list[str]
    metadata: dict[str, Any]

    @property
    def handle_id(self) -> str:
        """Return the DSpace handle id fragment when the OAI id uses the expected form."""
        return self.identifier.rsplit(":", maxsplit=1)[-1]

    @property
    def source_url(self) -> str:
        return f"https://dspace.cuni.cz/handle/{self.handle_id}"

    def to_raw_thesis(self, fetched_at: datetime | None = None) -> dict[str, Any]:
        fetched = fetched_at or datetime.now(timezone.utc)
        return {
            "source_id": self.identifier,
            "source_url": self.source_url,
            "fetched_at": fetched.isoformat().replace("+00:00", "Z"),
            "raw_fields": {
                "datestamp": self.datestamp,
                "set_specs": self.set_specs,
                "metadata": self.metadata,
            },
        }


class OaiClient:
    """Polite, dependency-free OAI-PMH client for DSpace 6."""

    def __init__(
        self,
        *,
        endpoint: str = OAI_ENDPOINT,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout_seconds: float = 30,
        min_interval_seconds: float = 2,
    ) -> None:
        self.endpoint = endpoint
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.min_interval_seconds = min_interval_seconds
        self._last_request_at: datetime | None = None

    def get_record(self, identifier: str, metadata_prefix: str = DEFAULT_METADATA_PREFIX) -> OaiRecord:
        xml = self.request(
            {
                "verb": "GetRecord",
                "identifier": identifier,
                "metadataPrefix": metadata_prefix,
            }
        )
        root = parse_oai_xml(xml)
        record = root.find(".//oai:GetRecord/oai:record", DS_NS)
        if record is None:
            raise OaiError(f"OAI GetRecord response did not contain a record for {identifier!r}")
        return parse_record(record)

    def list_records(
        self,
        *,
        metadata_prefix: str = DEFAULT_METADATA_PREFIX,
        set_spec: str = DEFAULT_SET_SPEC,
        limit: int = 10,
        ies_only: bool = True,
    ) -> list[OaiRecord]:
        records: list[OaiRecord] = []
        token: str | None = None
        while len(records) < limit:
            params = {"verb": "ListRecords"}
            if token:
                params["resumptionToken"] = token
            else:
                params["metadataPrefix"] = metadata_prefix
                params["set"] = set_spec
            root = parse_oai_xml(self.request(params))
            for node in root.findall(".//oai:ListRecords/oai:record", DS_NS):
                record = parse_record(node)
                if ies_only and not is_ies_record(record):
                    continue
                records.append(record)
                if len(records) >= limit:
                    return records
            token_node = root.find(".//oai:ListRecords/oai:resumptionToken", DS_NS)
            token = text_or_none(token_node)
            if not token:
                return records
        return records

    def request(self, params: dict[str, str]) -> bytes:
        self._wait_if_needed()
        url = f"{self.endpoint}?{urlencode(params)}"
        request = Request(url, headers={"User-Agent": self.user_agent})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return response.read()
        except OSError as exc:
            raise OaiError(f"failed to fetch {url}: {exc}") from exc
        finally:
            self._last_request_at = datetime.now(timezone.utc)

    def _wait_if_needed(self) -> None:
        if self._last_request_at is None:
            return
        elapsed = (datetime.now(timezone.utc) - self._last_request_at).total_seconds()
        remaining = self.min_interval_seconds - elapsed
        if remaining > 0:
            sleep(remaining)


def parse_oai_xml(xml: bytes | str) -> ElementTree.Element:
    try:
        return ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise OaiError(f"invalid OAI XML: {exc}") from exc


def parse_record(record: ElementTree.Element) -> OaiRecord:
    header = record.find("oai:header", DS_NS)
    if header is None:
        raise OaiError("OAI record is missing header")
    identifier = text_or_none(header.find("oai:identifier", DS_NS))
    if not identifier:
        raise OaiError("OAI record is missing identifier")
    datestamp = text_or_none(header.find("oai:datestamp", DS_NS))
    set_specs = [
        text
        for node in header.findall("oai:setSpec", DS_NS)
        if (text := text_or_none(node)) is not None
    ]
    metadata_node = record.find("oai:metadata", DS_NS)
    return OaiRecord(
        identifier=identifier,
        datestamp=datestamp,
        set_specs=set_specs,
        metadata=element_to_dict(metadata_node) if metadata_node is not None else {},
    )


def element_to_dict(node: ElementTree.Element) -> dict[str, Any]:
    """Convert XML into a compact namespace-free dict suitable for raw_fields."""
    children = list(node)
    text = text_or_none(node)
    attrs = {strip_namespace(key): value for key, value in node.attrib.items()}
    result: dict[str, Any] = {}
    if attrs:
        result["@attrs"] = attrs
    if children:
        grouped: dict[str, list[Any]] = {}
        for child in children:
            grouped.setdefault(strip_namespace(child.tag), []).append(element_to_dict(child))
        for key, values in grouped.items():
            result[key] = values[0] if len(values) == 1 else values
    if text and not children:
        result["text"] = text
    return result


def is_ies_record(record: OaiRecord) -> bool:
    """Return True when raw metadata identifies the thesis as IES."""
    return any(marker in value for value in iter_text_values(record.metadata) for marker in IES_MARKERS)


def iter_text_values(value: Any) -> list[str]:
    """Collect text leaves from the compact XML dict."""
    if isinstance(value, dict):
        values: list[str] = []
        text = value.get("text")
        if isinstance(text, str):
            values.append(text)
        for key, child in value.items():
            if key in {"text", "@attrs"}:
                continue
            values.extend(iter_text_values(child))
        return values
    if isinstance(value, list):
        values = []
        for child in value:
            values.extend(iter_text_values(child))
        return values
    if isinstance(value, str):
        return [value]
    return []


def strip_namespace(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1]


def text_or_none(node: ElementTree.Element | None) -> str | None:
    if node is None or node.text is None:
        return None
    text = node.text.strip()
    return text or None
