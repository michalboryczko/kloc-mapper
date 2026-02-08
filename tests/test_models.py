"""Tests for models module."""

import pytest
from src.models import (
    Node, Edge, Range, Location, SoTGraph,
    NodeKind, EdgeType,
    generate_node_id, generate_file_node_id,
    generate_value_node_id, generate_call_node_id,
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

        assert parsed["version"] == "2.0"  # Default version is now 2.0
        assert len(parsed["nodes"]) == 1


class TestValueNodeId:
    def test_deterministic(self):
        """Same location should produce same ID."""
        id1 = generate_value_node_id("src/Service.php:10:8")
        id2 = generate_value_node_id("src/Service.php:10:8")
        assert id1 == id2

    def test_format(self):
        """ID should have expected format with val prefix."""
        id_ = generate_value_node_id("src/Service.php:10:8")
        assert id_.startswith("node:val:")
        # "node:val:" (9 chars) + 16 hex chars = 25 total
        assert len(id_) == 9 + 16

    def test_different_from_call_id(self):
        """Value ID should differ from Call ID for same location."""
        value_id = generate_value_node_id("src/Service.php:10:8")
        call_id = generate_call_node_id("src/Service.php:10:8")
        assert value_id != call_id


class TestCallNodeId:
    def test_deterministic(self):
        """Same location should produce same ID."""
        id1 = generate_call_node_id("src/Service.php:10:20")
        id2 = generate_call_node_id("src/Service.php:10:20")
        assert id1 == id2

    def test_format(self):
        """ID should have expected format with call prefix."""
        id_ = generate_call_node_id("src/Service.php:10:20")
        assert id_.startswith("node:call:")
        # "node:call:" (10 chars) + 16 hex chars = 26 total
        assert len(id_) == 10 + 16


class TestNodeKindValues:
    def test_value_kind_exists(self):
        """VALUE node kind should exist."""
        assert NodeKind.VALUE.value == "Value"

    def test_call_kind_exists(self):
        """CALL node kind should exist."""
        assert NodeKind.CALL.value == "Call"


class TestEdgeTypeValues:
    def test_type_hint_exists(self):
        """TYPE_HINT edge type should exist."""
        assert EdgeType.TYPE_HINT.value == "type_hint"

    def test_calls_exists(self):
        """CALLS edge type should exist."""
        assert EdgeType.CALLS.value == "calls"

    def test_receiver_exists(self):
        """RECEIVER edge type should exist."""
        assert EdgeType.RECEIVER.value == "receiver"

    def test_argument_exists(self):
        """ARGUMENT edge type should exist."""
        assert EdgeType.ARGUMENT.value == "argument"

    def test_produces_exists(self):
        """PRODUCES edge type should exist."""
        assert EdgeType.PRODUCES.value == "produces"

    def test_assigned_from_exists(self):
        """ASSIGNED_FROM edge type should exist."""
        assert EdgeType.ASSIGNED_FROM.value == "assigned_from"

    def test_type_of_exists(self):
        """TYPE_OF edge type should exist."""
        assert EdgeType.TYPE_OF.value == "type_of"


class TestValueNode:
    def test_to_dict_with_value_kind(self):
        """Value node should include value_kind in dict."""
        node = Node(
            id="node:val:abc123",
            kind=NodeKind.VALUE,
            name="$order",
            fqn="App\\Service\\OrderService::createOrder().$order",
            symbol="scip-php ... #createOrder().($order)",
            file="src/Service.php",
            range=Range(40, 8, 40, 14),
            value_kind="local",
            type_symbol="scip-php ... Order#",
        )
        d = node.to_dict()

        assert d["kind"] == "Value"
        assert d["value_kind"] == "local"
        assert d["type_symbol"] == "scip-php ... Order#"
        assert "call_kind" not in d  # Should not include call_kind


class TestCallNode:
    def test_to_dict_with_call_kind(self):
        """Call node should include call_kind in dict."""
        node = Node(
            id="node:call:abc123",
            kind=NodeKind.CALL,
            name="save()",
            fqn="App\\Service\\OrderService::createOrder()@40:26",
            symbol="",
            file="src/Service.php",
            range=Range(40, 26, 40, 30),
            call_kind="method",
        )
        d = node.to_dict()

        assert d["kind"] == "Call"
        assert d["call_kind"] == "method"
        assert "value_kind" not in d  # Should not include value_kind


class TestEdgeWithPosition:
    def test_to_dict_with_position(self):
        """Argument edge should include position in dict."""
        edge = Edge(
            type=EdgeType.ARGUMENT,
            source="node:call:abc",
            target="node:val:def",
            position=0,
        )
        d = edge.to_dict()

        assert d["type"] == "argument"
        assert d["position"] == 0

    def test_to_dict_without_position(self):
        """Non-argument edge should not include position."""
        edge = Edge(
            type=EdgeType.CALLS,
            source="node:call:abc",
            target="node:method:def",
        )
        d = edge.to_dict()

        assert d["type"] == "calls"
        assert "position" not in d
