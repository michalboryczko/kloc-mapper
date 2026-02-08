"""Integration tests for the SCIP mapper using fixed SCIP index."""

import json
import pytest
from pathlib import Path

from src.mapper import SCIPMapper
from src.models import NodeKind, EdgeType


SCIP_PATH = Path(__file__).parent.parent.parent / "artifacts" / "index_fixed.scip"

pytestmark = pytest.mark.skipif(
    not SCIP_PATH.exists(),
    reason="artifacts/index_fixed.scip not found",
)


@pytest.fixture(scope="module")
def graph():
    """Map the fixed SCIP file to a SoT graph."""
    mapper = SCIPMapper(SCIP_PATH)
    return mapper.map()


@pytest.fixture(scope="module")
def graph_dict(graph):
    """Get graph as dict for easier assertions."""
    return graph.to_dict()


@pytest.fixture(scope="module")
def nodes_by_fqn(graph):
    """Index nodes by FQN for lookup."""
    idx = {}
    for n in graph.nodes:
        idx[n.fqn] = n
    return idx


@pytest.fixture(scope="module")
def edges_by_type(graph):
    """Group edges by type."""
    result = {}
    for e in graph.edges:
        result.setdefault(e.type, []).append(e)
    return result


@pytest.fixture(scope="module")
def node_id_to_node(graph):
    """Map node ID to node."""
    return {n.id: n for n in graph.nodes}


# --- Basic structure tests ---

class TestBasicStructure:
    def test_has_nodes(self, graph):
        assert len(graph.nodes) > 0

    def test_has_edges(self, graph):
        assert len(graph.edges) > 0

    def test_has_file_nodes(self, graph):
        file_nodes = [n for n in graph.nodes if n.kind == NodeKind.FILE]
        assert len(file_nodes) > 0

    def test_has_class_nodes(self, graph):
        class_nodes = [n for n in graph.nodes if n.kind == NodeKind.CLASS]
        assert len(class_nodes) > 0

    def test_has_method_nodes(self, graph):
        method_nodes = [n for n in graph.nodes if n.kind == NodeKind.METHOD]
        assert len(method_nodes) > 0

    def test_has_argument_nodes(self, graph):
        arg_nodes = [n for n in graph.nodes if n.kind == NodeKind.ARGUMENT]
        assert len(arg_nodes) > 0

    def test_has_interface_nodes(self, graph):
        iface_nodes = [n for n in graph.nodes if n.kind == NodeKind.INTERFACE]
        assert len(iface_nodes) > 0

    def test_has_enum_nodes(self, graph):
        enum_nodes = [n for n in graph.nodes if n.kind == NodeKind.ENUM]
        assert len(enum_nodes) > 0


# --- Issue #1: Correct ranges (no estimation needed) ---

class TestCorrectRanges:
    def test_methods_have_multiline_ranges(self, graph):
        """Methods should have ranges that span multiple lines (full body)."""
        methods = [n for n in graph.nodes if n.kind == NodeKind.METHOD and n.range]
        multiline = [m for m in methods if m.range.end_line > m.range.start_line]
        # With fixed SCIP, most methods should have multi-line ranges
        assert len(multiline) > 0, "No methods with multi-line ranges found"
        ratio = len(multiline) / len(methods) if methods else 0
        assert ratio > 0.3, f"Only {ratio:.0%} methods have multi-line ranges"

    def test_classes_have_multiline_ranges(self, graph):
        """Classes should have ranges spanning their full body."""
        classes = [n for n in graph.nodes
                   if n.kind in (NodeKind.CLASS, NodeKind.INTERFACE, NodeKind.TRAIT)
                   and n.range]
        multiline = [c for c in classes if c.range.end_line > c.range.start_line]
        assert len(multiline) > 0

    def test_synxis_config_service_method_ranges(self, nodes_by_fqn):
        """Specific check: SynxisConfigurationService methods have proper ranges."""
        fqn = "App\\Service\\Synxis\\SynxisConfigurationService::getCodesByItemIds()"
        node = nodes_by_fqn.get(fqn)
        if node and node.range:
            # Method should span more than just the signature line
            assert node.range.end_line > node.range.start_line, (
                f"getCodesByItemIds() range is single-line: {node.range.start_line}-{node.range.end_line}"
            )


# --- Issue #2: Parameter references create edges ---

class TestParameterReferences:
    def test_no_parameter_self_reference_edges(self, graph, node_id_to_node):
        """Methods should NOT have USES edges to their own parameters."""
        for edge in graph.edges:
            if edge.type != EdgeType.USES:
                continue
            source = node_id_to_node.get(edge.source)
            target = node_id_to_node.get(edge.target)
            if not source or not target:
                continue
            if target.kind == NodeKind.ARGUMENT:
                # Target is a parameter - check it doesn't belong to source method
                assert not target.symbol.startswith(source.symbol), (
                    f"Self-reference: {source.fqn} USES own param {target.fqn}"
                )


# --- USES edge deduplication ---

class TestUsesDeduplication:
    def test_no_duplicate_uses_edges(self, graph):
        """Each (source, target) pair should appear at most once for USES edges."""
        seen = set()
        for edge in graph.edges:
            if edge.type != EdgeType.USES:
                continue
            key = (edge.source, edge.target)
            assert key not in seen, (
                f"Duplicate USES edge: {edge.source} -> {edge.target}"
            )
            seen.add(key)


# --- Inheritance from SCIP relationships ---

class TestInheritanceEdges:
    def test_has_extends_edges(self, edges_by_type):
        extends = edges_by_type.get(EdgeType.EXTENDS, [])
        assert len(extends) > 0, "No extends edges found"

    def test_has_implements_edges(self, edges_by_type):
        implements = edges_by_type.get(EdgeType.IMPLEMENTS, [])
        assert len(implements) > 0, "No implements edges found"

    def test_extends_source_is_class_like(self, edges_by_type, node_id_to_node):
        """Extends edges should have class-like sources."""
        for edge in edges_by_type.get(EdgeType.EXTENDS, []):
            source = node_id_to_node.get(edge.source)
            if source:
                assert source.kind in (
                    NodeKind.CLASS, NodeKind.INTERFACE, NodeKind.TRAIT, NodeKind.ENUM
                ), f"Extends source {source.fqn} is {source.kind}"

    def test_implements_source_is_class(self, edges_by_type, node_id_to_node):
        """Implements edges should have class sources."""
        for edge in edges_by_type.get(EdgeType.IMPLEMENTS, []):
            source = node_id_to_node.get(edge.source)
            if source:
                assert source.kind in (
                    NodeKind.CLASS, NodeKind.ENUM
                ), f"Implements source {source.fqn} is {source.kind}"

    def test_implements_target_is_interface(self, edges_by_type, node_id_to_node):
        """Implements edges should target interfaces."""
        for edge in edges_by_type.get(EdgeType.IMPLEMENTS, []):
            target = node_id_to_node.get(edge.target)
            if target:
                assert target.kind == NodeKind.INTERFACE, (
                    f"Implements target {target.fqn} is {target.kind}"
                )


# --- Override edges from SCIP relationships ---

class TestOverrideEdges:
    def test_has_override_edges(self, edges_by_type):
        overrides = edges_by_type.get(EdgeType.OVERRIDES, [])
        assert len(overrides) > 0, "No override edges found"

    def test_override_source_is_method(self, edges_by_type, node_id_to_node):
        """Override edges should have method sources."""
        for edge in edges_by_type.get(EdgeType.OVERRIDES, []):
            source = node_id_to_node.get(edge.source)
            if source:
                assert source.kind == NodeKind.METHOD, (
                    f"Override source {source.fqn} is {source.kind}"
                )

    def test_override_target_is_method(self, edges_by_type, node_id_to_node):
        """Override edges should have method targets."""
        for edge in edges_by_type.get(EdgeType.OVERRIDES, []):
            target = node_id_to_node.get(edge.target)
            if target:
                assert target.kind == NodeKind.METHOD, (
                    f"Override target {target.fqn} is {target.kind}"
                )


# --- Contains edges ---

class TestContainsEdges:
    def test_has_contains_edges(self, edges_by_type):
        contains = edges_by_type.get(EdgeType.CONTAINS, [])
        assert len(contains) > 0

    def test_methods_contained_by_classes(self, graph, node_id_to_node):
        """Methods should be contained by class-like nodes."""
        for edge in graph.edges:
            if edge.type != EdgeType.CONTAINS:
                continue
            target = node_id_to_node.get(edge.target)
            source = node_id_to_node.get(edge.source)
            if target and target.kind == NodeKind.METHOD and source:
                assert source.kind in (
                    NodeKind.CLASS, NodeKind.INTERFACE, NodeKind.TRAIT, NodeKind.ENUM
                ), f"Method {target.fqn} contained by {source.kind} {source.fqn}"

    def test_arguments_contained_by_methods(self, graph, node_id_to_node):
        """Arguments should be contained by methods."""
        for edge in graph.edges:
            if edge.type != EdgeType.CONTAINS:
                continue
            target = node_id_to_node.get(edge.target)
            source = node_id_to_node.get(edge.source)
            if target and target.kind == NodeKind.ARGUMENT and source:
                assert source.kind in (NodeKind.METHOD, NodeKind.FUNCTION), (
                    f"Argument {target.fqn} contained by {source.kind} {source.fqn}"
                )


# --- USES edges ---

class TestUsesEdges:
    def test_has_uses_edges(self, edges_by_type):
        uses = edges_by_type.get(EdgeType.USES, [])
        assert len(uses) > 0

    def test_uses_edges_have_locations(self, edges_by_type):
        """USES edges should have source locations."""
        uses = edges_by_type.get(EdgeType.USES, [])
        with_loc = [e for e in uses if e.location is not None]
        assert len(with_loc) > 0

    def test_no_self_referencing_uses(self, edges_by_type):
        """No USES edge should reference itself."""
        for edge in edges_by_type.get(EdgeType.USES, []):
            assert edge.source != edge.target


# --- JSON output ---

class TestJsonOutput:
    def test_valid_json(self, graph):
        """Graph should serialize to valid JSON."""
        json_str = graph.to_json()
        parsed = json.loads(json_str)
        assert "nodes" in parsed
        assert "edges" in parsed
        assert "version" in parsed

    def test_nodes_sorted(self, graph_dict):
        """Nodes should be sorted by ID."""
        ids = [n["id"] for n in graph_dict["nodes"]]
        assert ids == sorted(ids)

    def test_edges_sorted(self, graph_dict):
        """Edges should be sorted by (source, type, target)."""
        keys = [(e["source"], e["type"], e["target"]) for e in graph_dict["edges"]]
        assert keys == sorted(keys)
