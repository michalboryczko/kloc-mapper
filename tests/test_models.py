"""Tests for models module."""

import pytest
from src.models import (
    Node, Edge, Range, Location, SoTGraph,
    NodeKind, EdgeType,
    generate_node_id, generate_file_node_id,
)


class TestNodeId:
    def test_deterministic(self):
        """Same input should produce same ID."""
        id1 = generate_node_id("test-symbol")
        id2 = generate_node_id("test-symbol")
        assert id1 == id2

    def test_different_inputs_different_ids(self):
        """Different inputs should produce different IDs."""
        id1 = generate_node_id("symbol-a")
        id2 = generate_node_id("symbol-b")
        assert id1 != id2

    def test_format(self):
        """ID should have expected format."""
        id_ = generate_node_id("test")
        assert id_.startswith("node:")
        assert len(id_) == 5 + 16  # "node:" + 16 hex chars


class TestFileNodeId:
    def test_deterministic(self):
        """Same file should produce same ID."""
        id1 = generate_file_node_id("src/foo.php")
        id2 = generate_file_node_id("src/foo.php")
        assert id1 == id2

    def test_different_from_symbol_id(self):
        """File ID should differ from symbol ID for same string."""
        file_id = generate_file_node_id("test")
        symbol_id = generate_node_id("test")
        assert file_id != symbol_id


class TestNode:
    def test_to_dict(self):
        node = Node(
            id="node:abc123",
            kind=NodeKind.CLASS,
            name="Foo",
            fqn="App\\Entity\\Foo",
            symbol="scip-php ... Foo#",
            file="src/Entity/Foo.php",
            range=Range(10, 0, 50, 0),
            documentation=["Class Foo"],
        )
        d = node.to_dict()

        assert d["id"] == "node:abc123"
        assert d["kind"] == "Class"
        assert d["name"] == "Foo"
        assert d["fqn"] == "App\\Entity\\Foo"
        assert d["range"]["start_line"] == 10


class TestEdge:
    def test_to_dict_minimal(self):
        edge = Edge(
            type=EdgeType.CONTAINS,
            source="node:a",
            target="node:b",
        )
        d = edge.to_dict()

        assert d["type"] == "contains"
        assert d["source"] == "node:a"
        assert d["target"] == "node:b"
        assert "location" not in d

    def test_to_dict_with_location(self):
        edge = Edge(
            type=EdgeType.USES,
            source="node:a",
            target="node:b",
            location=Location("src/foo.php", 42, 8),
        )
        d = edge.to_dict()

        assert d["location"]["file"] == "src/foo.php"
        assert d["location"]["line"] == 42


class TestSoTGraph:
    def test_to_dict_sorted(self):
        """Nodes and edges should be sorted for determinism."""
        graph = SoTGraph(
            nodes=[
                Node("node:zzz", NodeKind.CLASS, "Z", "Z", "z#", "z.php", None),
                Node("node:aaa", NodeKind.CLASS, "A", "A", "a#", "a.php", None),
            ],
            edges=[
                Edge(EdgeType.USES, "node:b", "node:a"),
                Edge(EdgeType.CONTAINS, "node:a", "node:b"),
            ],
        )
        d = graph.to_dict()

        # Nodes sorted by ID
        assert d["nodes"][0]["id"] == "node:aaa"
        assert d["nodes"][1]["id"] == "node:zzz"

        # Edges sorted by (source, type, target)
        assert d["edges"][0]["source"] == "node:a"
        assert d["edges"][1]["source"] == "node:b"

    def test_to_json(self):
        """JSON output should be valid."""
        import json
        graph = SoTGraph(
            nodes=[Node("node:a", NodeKind.CLASS, "A", "A", "a#", "a.php", None)],
            edges=[],
        )
        json_str = graph.to_json()
        parsed = json.loads(json_str)

        assert parsed["version"] == "1.0"
        assert len(parsed["nodes"]) == 1
