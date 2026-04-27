"""Neo4j graph payload mapping for frontend consumers."""

from __future__ import annotations

from typing import Any

from tarkov.database.session import get_neo4j_driver


def _node_kind(labels: list[str]) -> str:
    if "Company" in labels:
        return "company"
    if "Person" in labels:
        return "person"
    return "event"


def _node_id(labels: list[str], properties: dict[str, Any]) -> str:
    if "Company" in labels:
        return f"company:{properties['company_id']}"
    if "Person" in labels:
        return f"person:{properties['person_id']}"
    return f"event:{properties['event_id']}"


def _node_label(labels: list[str], properties: dict[str, Any]) -> str:
    if "Company" in labels:
        return str(properties.get("full_name", properties["company_id"]))
    if "Person" in labels:
        return str(properties.get("name", properties["person_id"]))
    return str(properties.get("event_type", properties["event_id"]))


def load_graph_payload() -> dict[str, list[dict[str, Any]]]:
    driver = get_neo4j_driver()

    with driver.session() as session:
        node_rows = list(
            session.run(
                """
                MATCH (n)
                RETURN labels(n) AS labels, properties(n) AS properties
                ORDER BY id(n)
                """
            )
        )
        edge_rows = list(
            session.run(
                """
                MATCH (source)-[r]->(target)
                RETURN id(r) AS rel_id,
                       labels(source) AS source_labels,
                       properties(source) AS source_properties,
                       labels(target) AS target_labels,
                       properties(target) AS target_properties,
                       type(r) AS rel_type,
                       properties(r) AS rel_properties
                ORDER BY rel_id
                """
            )
        )

    nodes = [
        {
            "id": _node_id(row["labels"], row["properties"]),
            "kind": _node_kind(row["labels"]),
            "label": _node_label(row["labels"], row["properties"]),
            "properties": row["properties"],
        }
        for row in node_rows
    ]
    edges = [
        {
            "id": f"rel:{row['rel_id']}",
            "source": _node_id(row["source_labels"], row["source_properties"]),
            "target": _node_id(row["target_labels"], row["target_properties"]),
            "type": row["rel_type"],
            "properties": row["rel_properties"],
        }
        for row in edge_rows
    ]
    return {"nodes": nodes, "edges": edges}
