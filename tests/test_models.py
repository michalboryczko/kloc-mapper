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


class TestEdgeWithExpression:
    def test_to_dict_with_expression(self):
        """Argument edge should include expression when set."""
        edge = Edge(
            type=EdgeType.ARGUMENT,
            source="node:call:abc",
            target="node:val:def",
            position=0,
            expression="$input->productId",
        )
        d = edge.to_dict()

        assert d["type"] == "argument"
        assert d["position"] == 0
        assert d["expression"] == "$input->productId"

    def test_to_dict_without_expression(self):
        """Argument edge without expression should not include it."""
        edge = Edge(
            type=EdgeType.ARGUMENT,
            source="node:call:abc",
            target="node:val:def",
            position=0,
        )
        d = edge.to_dict()

        assert d["type"] == "argument"
        assert d["position"] == 0
        assert "expression" not in d

    def test_to_dict_with_complex_expression(self):
        """Edge should preserve complex expression text."""
        edge = Edge(
            type=EdgeType.ARGUMENT,
            source="node:call:abc",
            target="node:val:def",
            position=1,
            expression="new DateTimeImmutable()",
        )
        d = edge.to_dict()

        assert d["expression"] == "new DateTimeImmutable()"

    def test_non_argument_edge_no_expression(self):
        """Non-argument edge should not include expression."""
        edge = Edge(
            type=EdgeType.CALLS,
            source="node:call:abc",
            target="node:method:def",
        )
        d = edge.to_dict()

        assert "expression" not in d
        assert "position" not in d


class TestPromotedPropertyAssignedFrom:
    """Tests for mapper creating assigned_from edges from promoted_property_symbol."""

    def test_mapper_creates_assigned_from_for_promoted_property(self):
        """Mapper should create assigned_from edge from Property to Value(parameter)
        when promoted_property_symbol is present on the value."""
        from src.calls_mapper import CallsMapper

        # Set up a Property node in the symbol index
        prop_symbol = "scip-php composer . App/Entity/Order#$id."
        prop_node_id = generate_node_id(prop_symbol)
        prop_node = Node(
            id=prop_node_id,
            kind=NodeKind.PROPERTY,
            name="$id",
            fqn="App\\Entity\\Order::$id",
            symbol=prop_symbol,
            file="src/Entity/Order.php",
            range=Range(12, 8, 12, 22),
        )

        nodes = {prop_node_id: prop_node}
        edges = []
        symbol_to_node_id = {prop_symbol: prop_node_id}

        calls_data = {
            "values": [
                {
                    "id": "src/Entity/Order.php:12:16",
                    "kind": "parameter",
                    "symbol": "scip-php composer . App/Entity/Order#__construct().($id)",
                    "type": None,
                    "location": {"file": "src/Entity/Order.php", "line": 12, "col": 16},
                    "promoted_property_symbol": prop_symbol,
                },
            ],
            "calls": [],
        }

        mapper = CallsMapper(
            calls_data=calls_data,
            nodes=nodes,
            edges=edges,
            symbol_to_node_id=symbol_to_node_id,
            file_symbol_index={},
        )
        mapper.process()

        # Find the assigned_from edge
        assigned_from_edges = [
            e for e in edges
            if e.type == EdgeType.ASSIGNED_FROM and e.source == prop_node_id
        ]

        assert len(assigned_from_edges) == 1, (
            f"Expected 1 assigned_from edge from Property, found {len(assigned_from_edges)}"
        )

        # Verify the edge direction: source=Property, target=Value(parameter)
        af_edge = assigned_from_edges[0]
        assert af_edge.source == prop_node_id
        # Target should be the Value node ID for the parameter
        value_node_id = mapper.value_id_to_node_id.get("src/Entity/Order.php:12:16")
        assert value_node_id is not None, "Value node should have been created"
        assert af_edge.target == value_node_id

    def test_mapper_no_assigned_from_without_promoted_property(self):
        """Non-promoted parameters should NOT get assigned_from edges from properties."""
        from src.calls_mapper import CallsMapper

        nodes = {}
        edges = []
        symbol_to_node_id = {}

        calls_data = {
            "values": [
                {
                    "id": "src/Component/EmailSender.php:12:8",
                    "kind": "parameter",
                    "symbol": "scip-php composer . App/Component/EmailSender#send().($to)",
                    "type": None,
                    "location": {"file": "src/Component/EmailSender.php", "line": 12, "col": 8},
                    # No promoted_property_symbol — regular parameter
                },
            ],
            "calls": [],
        }

        mapper = CallsMapper(
            calls_data=calls_data,
            nodes=nodes,
            edges=edges,
            symbol_to_node_id=symbol_to_node_id,
            file_symbol_index={},
        )
        mapper.process()

        # Should have no assigned_from edges at all
        assigned_from_edges = [e for e in edges if e.type == EdgeType.ASSIGNED_FROM]
        assert len(assigned_from_edges) == 0, (
            f"Non-promoted param should have no assigned_from edges, found {len(assigned_from_edges)}"
        )


class TestBuildValueFqn:
    """Tests for _build_value_fqn local variable identity preservation."""

    def test_local_variable_fqn_preserves_identity(self):
        """Local variable symbol should produce FQN with local$name@line format."""
        from src.calls_mapper import CallsMapper

        nodes = {}
        edges = []
        calls_data = {"values": [], "calls": []}

        mapper = CallsMapper(
            calls_data=calls_data,
            nodes=nodes,
            edges=edges,
            symbol_to_node_id={},
            file_symbol_index={},
        )

        value = {
            "symbol": "scip-php composer . App/Service/OrderService#createOrder().local$savedOrder@45",
            "location": {"file": "src/Service/OrderService.php", "line": 45, "col": 8},
        }

        fqn = mapper._build_value_fqn(value, "$savedOrder")
        assert fqn == "App\\Service\\OrderService::createOrder().local$savedOrder@45"

    def test_parameter_fqn_unchanged(self):
        """Parameter symbol should produce FQN with .$name format (unchanged behavior)."""
        from src.calls_mapper import CallsMapper

        nodes = {}
        edges = []
        calls_data = {"values": [], "calls": []}

        mapper = CallsMapper(
            calls_data=calls_data,
            nodes=nodes,
            edges=edges,
            symbol_to_node_id={},
            file_symbol_index={},
        )

        value = {
            "symbol": "scip-php composer . App/Service/OrderService#createOrder().($order)",
            "location": {"file": "src/Service/OrderService.php", "line": 30, "col": 4},
        }

        fqn = mapper._build_value_fqn(value, "$order")
        assert fqn == "App\\Service\\OrderService::createOrder().$order"

    def test_local_variable_different_lines_different_fqns(self):
        """Two local variables with same name on different lines should have different FQNs."""
        from src.calls_mapper import CallsMapper

        nodes = {}
        edges = []
        calls_data = {"values": [], "calls": []}

        mapper = CallsMapper(
            calls_data=calls_data,
            nodes=nodes,
            edges=edges,
            symbol_to_node_id={},
            file_symbol_index={},
        )

        value1 = {
            "symbol": "scip-php composer . App/Service/OrderService#process().local$result@10",
            "location": {"file": "src/Service/OrderService.php", "line": 10, "col": 8},
        }
        value2 = {
            "symbol": "scip-php composer . App/Service/OrderService#process().local$result@25",
            "location": {"file": "src/Service/OrderService.php", "line": 25, "col": 8},
        }

        fqn1 = mapper._build_value_fqn(value1, "$result")
        fqn2 = mapper._build_value_fqn(value2, "$result")

        assert fqn1 != fqn2
        assert "local$result@10" in fqn1
        assert "local$result@25" in fqn2
