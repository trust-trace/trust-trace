"""Tests for the graph builder (Phase 1)."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from trust_web.config import TrustWebConfig
from trust_web.graph.builder import (
    _label_and_id_prop,
    _find_neighbor_firm_ids,
)


class TestLabelAndIdProp:
    def test_person_type(self):
        label, prop = _label_and_id_prop("person")
        assert label == "Person"
        assert prop == "person_id"

    def test_company_type(self):
        label, prop = _label_and_id_prop("company")
        assert label == "Company"
        assert prop == "company_id"

    def test_unknown_defaults_to_company(self):
        label, prop = _label_and_id_prop("organization")
        assert label == "Company"
        assert prop == "company_id"


class TestFindNeighborFirmIds:
    def test_extracts_neighbor_ids(self):
        event1 = MagicMock()
        event1.unique_id = "evt-1"

        ce1 = MagicMock()
        ce1.entity_1_type = "company"
        ce1.entity_1_id = "1"
        ce1.entity_2_type = "company"
        ce1.entity_2_id = "42"

        ce2 = MagicMock()
        ce2.entity_1_type = "company"
        ce2.entity_1_id = "1"
        ce2.entity_2_type = "person"
        ce2.entity_2_id = "p-99"

        session = MagicMock()
        session.scalars.return_value.all.return_value = [ce1, ce2]

        result = _find_neighbor_firm_ids([event1], 1, session)
        assert result == {42}

    def test_excludes_self(self):
        event1 = MagicMock()
        event1.unique_id = "evt-1"

        ce1 = MagicMock()
        ce1.entity_1_type = "company"
        ce1.entity_1_id = "1"
        ce1.entity_2_type = "company"
        ce1.entity_2_id = "1"

        session = MagicMock()
        session.scalars.return_value.all.return_value = [ce1]

        result = _find_neighbor_firm_ids([event1], 1, session)
        assert result == set()

    def test_handles_non_numeric_ids(self):
        event1 = MagicMock()
        event1.unique_id = "evt-1"

        ce1 = MagicMock()
        ce1.entity_1_type = "company"
        ce1.entity_1_id = "not-a-number"
        ce1.entity_2_type = "company"
        ce1.entity_2_id = "also-not"

        session = MagicMock()
        session.scalars.return_value.all.return_value = [ce1]

        result = _find_neighbor_firm_ids([event1], 1, session)
        assert result == set()
