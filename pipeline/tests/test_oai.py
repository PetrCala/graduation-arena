"""Tests for the narrow A1 OAI-PMH access layer."""

from __future__ import annotations

from datetime import datetime, timezone

from ga_pipeline.oai import is_ies_record, parse_oai_xml, parse_record


GET_RECORD_XML = """<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <GetRecord>
    <record>
      <header>
        <identifier>oai:dspace.cuni.cz:20.500.11956/176640</identifier>
        <datestamp>2024-01-17T10:00:00Z</datestamp>
        <setSpec>com_20.500.11956_1905</setSpec>
        <setSpec>col_20.500.11956_1918</setSpec>
      </header>
      <metadata>
        <dim:dim xmlns:dim="http://www.dspace.org/xmlns/dspace/dim">
          <dim:field mdschema="dc" element="contributor" qualifier="advisor">
            Example Supervisor
          </dim:field>
          <dim:field mdschema="dc" element="contributor" qualifier="opponent">
            Example Opponent
          </dim:field>
          <dim:field mdschema="uk" element="degree-discipline" qualifier="en">
            Economics and Finance
          </dim:field>
          <dim:field mdschema="dc" element="description" qualifier="department">
            Institute of Economic Studies
          </dim:field>
        </dim:dim>
      </metadata>
    </record>
  </GetRecord>
</OAI-PMH>
"""


def test_parse_record_maps_header_and_metadata() -> None:
    root = parse_oai_xml(GET_RECORD_XML)
    record_node = root.find(".//{http://www.openarchives.org/OAI/2.0/}record")
    assert record_node is not None

    record = parse_record(record_node)

    assert record.identifier == "oai:dspace.cuni.cz:20.500.11956/176640"
    assert record.source_url == "https://dspace.cuni.cz/handle/20.500.11956/176640"
    assert record.set_specs == ["com_20.500.11956_1905", "col_20.500.11956_1918"]
    fields = record.metadata["dim"]["field"]
    assert fields[0]["@attrs"]["qualifier"] == "advisor"
    assert fields[0]["text"] == "Example Supervisor"


def test_raw_thesis_payload_is_schema_shaped() -> None:
    root = parse_oai_xml(GET_RECORD_XML)
    record_node = root.find(".//{http://www.openarchives.org/OAI/2.0/}record")
    assert record_node is not None

    payload = parse_record(record_node).to_raw_thesis(
        fetched_at=datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)
    )

    assert payload["source_id"] == "oai:dspace.cuni.cz:20.500.11956/176640"
    assert payload["fetched_at"] == "2026-06-27T12:00:00Z"
    assert payload["raw_fields"]["datestamp"] == "2024-01-17T10:00:00Z"


def test_ies_record_detection_uses_metadata_text() -> None:
    root = parse_oai_xml(GET_RECORD_XML)
    record_node = root.find(".//{http://www.openarchives.org/OAI/2.0/}record")
    assert record_node is not None

    assert is_ies_record(parse_record(record_node))
