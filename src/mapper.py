"""SCIP to Source-of-Truth JSON mapper."""

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import re

from src.models import (
    Node, Edge, Range, Location, SoTGraph,
    NodeKind, EdgeType,
    generate_node_id, generate_file_node_id
)
from src.parser import (
    parse_scip_file, parse_symbol_string, parse_range,
    extract_fqn_from_descriptor, extract_name_from_descriptor,
    get_symbol_roles, is_definition,
    infer_kind_from_documentation,
    get_parent_symbol
)


class SCIPMapper:
    """Maps SCIP index to Source-of-Truth graph."""

    def __init__(self, scip_path: str | Path, calls_data: Optional[dict] = None):
        """Initialize the mapper.

        Args:
            scip_path: Path to the SCIP index file.
            calls_data: Optional calls.json data dict for Value/Call node generation.
        """
        self.scip_path = Path(scip_path)
        self.index = parse_scip_file(self.scip_path)
        self.calls_data = calls_data

        # Internal mappings
        self.nodes: dict[str, Node] = {}  # node_id -> Node
        self.edges: list[Edge] = []
        self.symbol_to_node_id: dict[str, str] = {}  # symbol -> node_id
        self.file_to_node_id: dict[str, str] = {}  # filepath -> node_id

        # Symbol metadata from doc.symbols
        self.symbol_metadata: dict[str, dict] = {}  # symbol -> {docs, relationships}

        # Track occurrences for uses edges
        self.occurrences: list[dict] = []  # [{symbol, file, range, roles, is_definition}]

        # Spatial index: file -> sorted list of (start_line, end_line, symbol, node_kind)
        self.file_symbol_index: dict[str, list[tuple[int, int, str, NodeKind]]] = {}

    def map(self) -> SoTGraph:
        """Perform the full mapping pipeline."""
        self._collect_symbol_metadata()
        self._create_file_nodes()
        self._create_symbol_nodes()
        self._build_file_symbol_index()
        self._build_contains_edges()
        self._build_inheritance_edges()
        self._build_type_hint_edges()
        self._build_uses_edges()
        self._build_override_edges()

        # Process calls.json data if available
        if self.calls_data:
            self._process_calls_data()

        return SoTGraph(
            version="2.0",
            metadata={
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source_scip": str(self.scip_path.name),
                "project_root": self.index.metadata.project_root if self.index.metadata else "",
            },
            nodes=list(self.nodes.values()),
            edges=self.edges,
        )

    def _process_calls_data(self):
        """Process calls.json data to create Value and Call nodes.

        Delegates to the calls_mapper module.
        """
        from src.calls_mapper import CallsMapper
        calls_mapper = CallsMapper(
            calls_data=self.calls_data,
            nodes=self.nodes,
            edges=self.edges,
            symbol_to_node_id=self.symbol_to_node_id,
            file_symbol_index=self.file_symbol_index,
        )
        calls_mapper.process()

    def _collect_symbol_metadata(self):
        """Collect documentation and relationships from doc.symbols."""
        for doc in self.index.documents:
            for sym in doc.symbols:
                symbol = sym.symbol
                docs = list(sym.documentation) if sym.documentation else []
                relationships = []

                for rel in sym.relationships:
                    relationships.append({
                        "symbol": rel.symbol,
                        "is_implementation": rel.is_implementation,
                        "is_reference": rel.is_reference,
                        "is_type_definition": rel.is_type_definition,
                        "is_definition": rel.is_definition,
                    })

                self.symbol_metadata[symbol] = {
                    "documentation": docs,
                    "relationships": relationships,
                    "file": doc.relative_path,
                }

    def _create_file_nodes(self):
        """Create File nodes for each document."""
        for doc in self.index.documents:
            filepath = doc.relative_path
            node_id = generate_file_node_id(filepath)

            if node_id not in self.nodes:
                node = Node(
                    id=node_id,
                    kind=NodeKind.FILE,
                    name=Path(filepath).name,
                    fqn=filepath,
                    symbol=f"file:{filepath}",
                    file=filepath,
                    range=None,
                    documentation=[],
                )
                self.nodes[node_id] = node
                self.file_to_node_id[filepath] = node_id

    def _classify_symbol(self, symbol: str, descriptor: str, docs: list[str]) -> Optional[NodeKind]:
        """Classify a symbol into a NodeKind based on descriptor pattern and docs."""
        # Argument: contains parameter pattern like .($name) or .(name)
        # Must check before METHOD since arguments are inside methods
        if re.search(r'\.\(\$?[a-zA-Z_][a-zA-Z0-9_]*\)', descriptor):
            return NodeKind.ARGUMENT

        # Method: ends with ().)
        if descriptor.endswith("()."):
            return NodeKind.METHOD

        # Property: contains #$
        if "#$" in descriptor:
            return NodeKind.PROPERTY

        # Class/Interface/Trait/Enum: ends with #
        if descriptor.endswith("#"):
            kind_str = infer_kind_from_documentation(docs)
            if kind_str == "interface":
                return NodeKind.INTERFACE
            elif kind_str == "trait":
                return NodeKind.TRAIT
            elif kind_str == "enum":
                return NodeKind.ENUM
            else:
                return NodeKind.CLASS

        # Const or EnumCase: has # but doesn't end with () or $
        if "#" in descriptor:
            member = descriptor.split("#", 1)[1].rstrip(".")
            if member and not member.startswith("$") and not member.endswith("()"):
                # Check if parent is enum
                parent_symbol = get_parent_symbol(symbol)
                if parent_symbol:
                    parent_meta = self.symbol_metadata.get(parent_symbol, {})
                    parent_docs = parent_meta.get("documentation", [])
                    parent_kind = infer_kind_from_documentation(parent_docs)
                    if parent_kind == "enum":
                        return NodeKind.ENUM_CASE
                return NodeKind.CONST

        # Standalone function: ends with ().
        if descriptor.endswith("().") and "#" not in descriptor:
            return NodeKind.FUNCTION

        return None

    def _create_symbol_nodes(self):
        """Create nodes for all symbols in the SCIP index."""
        # First pass: collect all definitions from occurrences
        # symbol -> (file, range, enclosing_range)
        definition_locations: dict[str, tuple[str, list[int], list[int]]] = {}

        for doc in self.index.documents:
            filepath = doc.relative_path

            for occ in doc.occurrences:
                symbol = occ.symbol
                roles = get_symbol_roles(occ.symbol_roles)
                range_list = list(occ.range)

                # Track occurrence for uses edges
                self.occurrences.append({
                    "symbol": symbol,
                    "file": filepath,
                    "range": range_list,
                    "roles": roles,
                    "is_definition": is_definition(occ.symbol_roles),
                })

                # Record definition location with enclosing_range
                if is_definition(occ.symbol_roles):
                    enclosing = list(occ.enclosing_range) if occ.enclosing_range else []
                    definition_locations[symbol] = (filepath, range_list, enclosing)

        # Second pass: create nodes
        all_symbols = set(definition_locations.keys()) | set(self.symbol_metadata.keys())

        for symbol in all_symbols:
            parsed = parse_symbol_string(symbol)
            if "descriptor" not in parsed:
                continue

            descriptor = parsed["descriptor"]
            meta = self.symbol_metadata.get(symbol, {})
            docs = meta.get("documentation", [])

            kind = self._classify_symbol(symbol, descriptor, docs)
            if kind is None:
                continue

            # Get location
            loc = definition_locations.get(symbol)
            if loc:
                filepath, range_list, enclosing_list = loc
                start_line, start_col, end_line, end_col = parse_range(range_list)
                range_obj = Range(start_line, start_col, end_line, end_col)
                if enclosing_list:
                    es, esc, ee, eec = parse_range(enclosing_list)
                    enclosing_obj = Range(es, esc, ee, eec)
                else:
                    enclosing_obj = None
            else:
                filepath = meta.get("file")
                range_obj = None
                enclosing_obj = None

            node_id = generate_node_id(symbol)
            node = Node(
                id=node_id,
                kind=kind,
                name=extract_name_from_descriptor(descriptor),
                fqn=extract_fqn_from_descriptor(descriptor),
                symbol=symbol,
                file=filepath,
                range=range_obj,
                enclosing_range=enclosing_obj,
                documentation=docs,
            )

            self.nodes[node_id] = node
            self.symbol_to_node_id[symbol] = node_id

    def _build_file_symbol_index(self):
        """Build spatial index for fast enclosing symbol lookup.

        Uses enclosing_range (full AST extent) when available for accurate
        containment. Falls back to range (identifier position) otherwise.
        """
        file_symbols: dict[str, list[tuple[int, int, str, NodeKind]]] = defaultdict(list)

        for symbol, node_id in self.symbol_to_node_id.items():
            node = self.nodes[node_id]

            # Only index container types that can enclose references
            if node.kind not in (
                NodeKind.METHOD, NodeKind.FUNCTION,
                NodeKind.CLASS, NodeKind.INTERFACE, NodeKind.TRAIT, NodeKind.ENUM,
            ):
                continue

            if not node.file or not node.range:
                continue

            # Prefer enclosing_range for containment (covers full AST body),
            # fall back to range (identifier position only)
            r = node.enclosing_range or node.range
            file_symbols[node.file].append((
                r.start_line,
                r.end_line,
                symbol,
                node.kind
            ))

        # Sort by start_line, then by smaller span (more specific first)
        for filepath in file_symbols:
            file_symbols[filepath].sort(key=lambda x: (x[0], x[1] - x[0]))

        self.file_symbol_index = file_symbols

    def _build_contains_edges(self):
        """Build contains edges (structural containment)."""
        for symbol, node_id in self.symbol_to_node_id.items():
            node = self.nodes[node_id]

            # Skip files - they don't have a parent symbol
            if node.kind == NodeKind.FILE:
                continue

            parent_symbol = get_parent_symbol(symbol)

            if parent_symbol:
                # Parent is another symbol (class/interface/trait/method)
                parent_id = self.symbol_to_node_id.get(parent_symbol)
                if parent_id:
                    self.edges.append(Edge(
                        type=EdgeType.CONTAINS,
                        source=parent_id,
                        target=node_id,
                    ))
            else:
                # Top-level symbol, contained by file
                if node.file:
                    file_id = self.file_to_node_id.get(node.file)
                    if file_id:
                        self.edges.append(Edge(
                            type=EdgeType.CONTAINS,
                            source=file_id,
                            target=node_id,
                        ))

    def _resolve_relationship_target(self, rel_symbol: str) -> Optional[str]:
        """Resolve a relationship target symbol to a node ID."""
        # Direct lookup
        if rel_symbol in self.symbol_to_node_id:
            return self.symbol_to_node_id[rel_symbol]

        # Try to match by descriptor suffix
        rel_clean = rel_symbol.lstrip("/").rstrip("#")

        for symbol, node_id in self.symbol_to_node_id.items():
            parsed = parse_symbol_string(symbol)
            if "descriptor" not in parsed:
                continue

            desc = parsed["descriptor"].rstrip("#")
            if desc == rel_clean or desc.endswith("/" + rel_clean):
                return node_id

        return None

    def _build_inheritance_edges(self):
        """Build extends, implements, and uses_trait edges from SCIP relationships.

        Uses structured relationship data from SCIP symbol metadata instead of
        parsing PHPDoc documentation strings.
        """
        for symbol, meta in self.symbol_metadata.items():
            source_id = self.symbol_to_node_id.get(symbol)
            if not source_id:
                continue

            node = self.nodes.get(source_id)
            if not node:
                continue

            # Only process class-like symbols for inheritance
            if node.kind not in (NodeKind.CLASS, NodeKind.INTERFACE, NodeKind.TRAIT, NodeKind.ENUM):
                continue

            for rel in meta.get("relationships", []):
                # Skip type_definition relationships (parameter/property types)
                if rel.get("is_type_definition"):
                    continue

                target_symbol = rel["symbol"]
                target_id = self._resolve_relationship_target(target_symbol)
                if not target_id:
                    continue

                if rel.get("is_implementation") and not rel.get("is_reference"):
                    # implements interface
                    edge_type = EdgeType.IMPLEMENTS
                elif rel.get("is_reference") and rel.get("is_implementation"):
                    # uses trait
                    edge_type = EdgeType.USES_TRAIT
                elif rel.get("is_reference") and not rel.get("is_implementation"):
                    # extends class/interface
                    edge_type = EdgeType.EXTENDS
                else:
                    continue

                self.edges.append(Edge(type=edge_type, source=source_id, target=target_id))

    def _build_type_hint_edges(self):
        """Build type_hint edges from SCIP relationships.

        Type hints connect elements (parameters, properties, methods) to their type annotations.
        These come from SCIP relationships with is_type_definition=True.
        """
        for symbol, meta in self.symbol_metadata.items():
            source_id = self.symbol_to_node_id.get(symbol)
            if not source_id:
                continue

            node = self.nodes.get(source_id)
            if not node:
                continue

            # Type hints apply to: Argument (parameters), Property, Method (return type)
            if node.kind not in (NodeKind.ARGUMENT, NodeKind.PROPERTY, NodeKind.METHOD):
                continue

            for rel in meta.get("relationships", []):
                # Only process type_definition relationships
                if not rel.get("is_type_definition"):
                    continue

                target_symbol = rel["symbol"]
                target_id = self._resolve_relationship_target(target_symbol)
                if not target_id:
                    continue

                self.edges.append(Edge(
                    type=EdgeType.TYPE_HINT,
                    source=source_id,
                    target=target_id,
                ))

    def _find_enclosing_symbol(self, filepath: str, line: int) -> Optional[str]:
        """Find the enclosing symbol (method/function/class) for a given location.

        Uses the pre-built spatial index for fast lookup.
        Prefers more specific (narrower) matches - methods over classes.
        """
        entries = self.file_symbol_index.get(filepath, [])
        if not entries:
            return None

        best = None
        best_span = float("inf")
        best_priority = float("inf")

        for start_line, end_line, symbol, kind in entries:
            if start_line <= line <= end_line:
                span = end_line - start_line
                priority = 0 if kind in (NodeKind.METHOD, NodeKind.FUNCTION) else 1
                if (span, priority) < (best_span, best_priority):
                    best = symbol
                    best_span = span
                    best_priority = priority

        return best

    def _build_uses_edges(self):
        """Build uses edges from occurrences.

        Deduplicates by (source_id, target_id) pair - multiple references from
        the same source to the same target produce only one USES edge.
        Filters out parameter self-references (method USES its own parameter).
        """
        seen_edges: set[tuple[str, str]] = set()

        for occ in self.occurrences:
            # Skip definitions - they don't create uses edges
            if occ["is_definition"]:
                continue

            target_symbol = occ["symbol"]
            target_id = self.symbol_to_node_id.get(target_symbol)
            if not target_id:
                continue

            # Find the enclosing symbol for this reference
            filepath = occ["file"]
            range_list = occ["range"]
            line = range_list[0] if range_list else 0

            enclosing_symbol = self._find_enclosing_symbol(filepath, line)
            if not enclosing_symbol:
                # Fall back to file
                source_id = self.file_to_node_id.get(filepath)
            else:
                source_id = self.symbol_to_node_id.get(enclosing_symbol)

            if not source_id:
                continue

            # Don't create self-references
            if source_id == target_id:
                continue

            # Filter parameter self-references: skip if target is a parameter
            # of the enclosing method (e.g. method USES its own $param)
            if enclosing_symbol and target_symbol.startswith(enclosing_symbol):
                continue

            # Deduplicate by (source, target) pair
            edge_key = (source_id, target_id)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)

            start_line, start_col, _, _ = parse_range(range_list)
            location = Location(file=filepath, line=start_line, col=start_col)

            self.edges.append(Edge(
                type=EdgeType.USES,
                source=source_id,
                target=target_id,
                location=location,
            ))

    def _build_override_edges(self):
        """Build overrides edges from SCIP relationship data.

        Method symbols with relationships where is_implementation=true and
        is_reference=true indicate the method overrides/implements a parent method.
        """
        for symbol, meta in self.symbol_metadata.items():
            source_id = self.symbol_to_node_id.get(symbol)
            if not source_id:
                continue

            # Only process method symbols
            node = self.nodes.get(source_id)
            if not node or node.kind != NodeKind.METHOD:
                continue

            for rel in meta.get("relationships", []):
                if rel.get("is_implementation") and rel.get("is_reference"):
                    target_symbol = rel["symbol"]
                    target_id = self._resolve_relationship_target(target_symbol)
                    if target_id:
                        self.edges.append(Edge(
                            type=EdgeType.OVERRIDES,
                            source=source_id,
                            target=target_id,
                        ))
