"""SCIP to Source-of-Truth JSON mapper."""

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
    infer_kind_from_documentation, extract_extends_implements_from_docs,
    get_parent_symbol
)


class SCIPMapper:
    """Maps SCIP index to Source-of-Truth graph."""

    def __init__(self, scip_path: str | Path):
        self.scip_path = Path(scip_path)
        self.index = parse_scip_file(self.scip_path)

        # Internal mappings
        self.nodes: dict[str, Node] = {}  # node_id -> Node
        self.edges: list[Edge] = []
        self.symbol_to_node_id: dict[str, str] = {}  # symbol -> node_id
        self.file_to_node_id: dict[str, str] = {}  # filepath -> node_id

        # Symbol metadata from doc.symbols
        self.symbol_metadata: dict[str, dict] = {}  # symbol -> {docs, relationships}

        # Track occurrences for uses edges
        self.occurrences: list[dict] = []  # [{symbol, file, range, roles, enclosing_symbol}]

        # Spatial index: file -> sorted list of (start_line, end_line, symbol, node_kind)
        self.file_symbol_index: dict[str, list[tuple[int, int, str, NodeKind]]] = {}

    def map(self) -> SoTGraph:
        """Perform the full mapping pipeline."""
        self._collect_symbol_metadata()
        self._create_file_nodes()
        self._create_symbol_nodes()
        self._estimate_symbol_ranges()  # NEW: Fill missing end_lines
        self._build_file_symbol_index()  # NEW: Build spatial index
        self._build_contains_edges()
        self._build_inheritance_edges()
        self._build_uses_edges()
        self._build_override_edges()

        return SoTGraph(
            version="1.0",
            metadata={
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source_scip": str(self.scip_path.name),
                "project_root": self.index.metadata.project_root if self.index.metadata else "",
            },
            nodes=list(self.nodes.values()),
            edges=self.edges,
        )

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
        definition_locations: dict[str, tuple[str, list[int]]] = {}  # symbol -> (file, range)

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

                # Record definition location
                if is_definition(occ.symbol_roles):
                    definition_locations[symbol] = (filepath, range_list)

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
                filepath, range_list = loc
                start_line, start_col, end_line, end_col = parse_range(range_list)
                range_obj = Range(start_line, start_col, end_line, end_col)
            else:
                filepath = meta.get("file")
                range_obj = None

            node_id = generate_node_id(symbol)
            node = Node(
                id=node_id,
                kind=kind,
                name=extract_name_from_descriptor(descriptor),
                fqn=extract_fqn_from_descriptor(descriptor),
                symbol=symbol,
                file=filepath,
                range=range_obj,
                documentation=docs,
            )

            self.nodes[node_id] = node
            self.symbol_to_node_id[symbol] = node_id

    def _estimate_symbol_ranges(self):
        """Estimate end_line for symbols with incomplete range data.

        SCIP often provides ranges that only cover the definition line (signature),
        not the entire body. We estimate end_line based on:
        1. The next sibling symbol's start_line - 1
        2. A large default if no sibling exists
        """
        from collections import defaultdict

        # Group symbols by file and parent
        # Key: (filepath, parent_symbol), Value: list of (start_line, symbol)
        symbols_by_context: dict[tuple[str, Optional[str]], list[tuple[int, str]]] = defaultdict(list)

        for symbol, node_id in self.symbol_to_node_id.items():
            node = self.nodes[node_id]
            if not node.file or not node.range:
                continue

            parent_symbol = get_parent_symbol(symbol)
            key = (node.file, parent_symbol)
            symbols_by_context[key].append((node.range.start_line, symbol))

        # For each context, sort by start_line and estimate end_lines
        for key, symbols in symbols_by_context.items():
            symbols.sort(key=lambda x: x[0])

            for i, (start_line, symbol) in enumerate(symbols):
                node = self.nodes[self.symbol_to_node_id[symbol]]
                if not node.range:
                    continue

                # If end_line equals start_line (common in SCIP), estimate it
                if node.range.end_line <= node.range.start_line:
                    if i + 1 < len(symbols):
                        # Next sibling starts at next_start, so this ends at next_start - 1
                        next_start = symbols[i + 1][0]
                        node.range.end_line = max(next_start - 1, node.range.start_line)
                    else:
                        # Last symbol in context - estimate based on kind
                        if node.kind in (NodeKind.METHOD, NodeKind.FUNCTION):
                            # Methods typically 20-50 lines
                            node.range.end_line = node.range.start_line + 50
                        elif node.kind in (NodeKind.CLASS, NodeKind.INTERFACE, NodeKind.TRAIT, NodeKind.ENUM):
                            # Classes can be much larger
                            node.range.end_line = node.range.start_line + 500
                        else:
                            # Properties, consts - small
                            node.range.end_line = node.range.start_line + 5

    def _build_file_symbol_index(self):
        """Build spatial index for fast enclosing symbol lookup."""
        from collections import defaultdict

        file_symbols: dict[str, list[tuple[int, int, str, NodeKind]]] = defaultdict(list)

        for symbol, node_id in self.symbol_to_node_id.items():
            node = self.nodes[node_id]

            # Only index container types that can have uses inside them
            if node.kind not in (
                NodeKind.METHOD, NodeKind.FUNCTION,
                NodeKind.CLASS, NodeKind.INTERFACE, NodeKind.TRAIT, NodeKind.ENUM,
                NodeKind.PROPERTY
            ):
                continue

            if not node.file or not node.range:
                continue

            file_symbols[node.file].append((
                node.range.start_line,
                node.range.end_line,
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
        """Build extends, implements, and uses_trait edges."""
        for symbol, meta in self.symbol_metadata.items():
            source_id = self.symbol_to_node_id.get(symbol)
            if not source_id:
                continue

            docs = meta.get("documentation", [])
            scip_rels = meta.get("relationships", [])

            # Parse extends/implements from documentation
            extends_list, implements_list, uses_traits = extract_extends_implements_from_docs(docs)

            # Build lookup of relationship symbols by short name
            rel_by_short_name: dict[str, str] = {}
            for rel in scip_rels:
                rel_sym = rel["symbol"]
                parsed = parse_symbol_string(rel_sym)
                if "descriptor" in parsed:
                    short = parsed["descriptor"].rstrip("#").split("/")[-1]
                    rel_by_short_name[short] = rel_sym

            # Process extends
            for ext in extends_list:
                short_name = ext.split("/")[-1]
                target_symbol = rel_by_short_name.get(short_name, ext)
                target_id = self._resolve_relationship_target(target_symbol)
                if target_id:
                    self.edges.append(Edge(
                        type=EdgeType.EXTENDS,
                        source=source_id,
                        target=target_id,
                    ))

            # Process implements
            for impl in implements_list:
                short_name = impl.split("/")[-1]
                target_symbol = rel_by_short_name.get(short_name, impl)
                target_id = self._resolve_relationship_target(target_symbol)
                if target_id:
                    self.edges.append(Edge(
                        type=EdgeType.IMPLEMENTS,
                        source=source_id,
                        target=target_id,
                    ))

            # Process trait usage
            for trait in uses_traits:
                short_name = trait.split("/")[-1]
                target_symbol = rel_by_short_name.get(short_name, trait)
                target_id = self._resolve_relationship_target(target_symbol)
                if target_id:
                    self.edges.append(Edge(
                        type=EdgeType.USES_TRAIT,
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

        candidates: list[tuple[int, int, str, NodeKind]] = []

        for start_line, end_line, symbol, kind in entries:
            if start_line <= line <= end_line:
                span = end_line - start_line
                # Priority: smaller span is better, methods/functions preferred over classes
                kind_priority = 0 if kind in (NodeKind.METHOD, NodeKind.FUNCTION, NodeKind.PROPERTY) else 1
                candidates.append((span, kind_priority, symbol, kind))

        if not candidates:
            return None

        # Sort by span (smaller is better), then by kind priority (methods first)
        candidates.sort(key=lambda x: (x[0], x[1]))
        return candidates[0][2]

    def _build_uses_edges(self):
        """Build uses edges from occurrences."""
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

            start_line, start_col, _, _ = parse_range(range_list)
            location = Location(file=filepath, line=start_line, col=start_col)

            self.edges.append(Edge(
                type=EdgeType.USES,
                source=source_id,
                target=target_id,
                location=location,
            ))

    def _build_override_edges(self):
        """Build overrides edges for methods that override parent methods."""
        # Collect all methods grouped by class
        methods_by_class: dict[str, dict[str, str]] = {}  # class_symbol -> {method_name -> method_symbol}

        for symbol, node_id in self.symbol_to_node_id.items():
            node = self.nodes[node_id]
            if node.kind != NodeKind.METHOD:
                continue

            parent_symbol = get_parent_symbol(symbol)
            if parent_symbol:
                if parent_symbol not in methods_by_class:
                    methods_by_class[parent_symbol] = {}
                methods_by_class[parent_symbol][node.name] = symbol

        # Build extends chain for each class
        class_parents: dict[str, str] = {}  # class_symbol -> parent_class_symbol
        for source_id, edge_type, target_id in [(e.source, e.type, e.target) for e in self.edges]:
            if edge_type == EdgeType.EXTENDS:
                # Find symbols from node IDs
                source_symbol = None
                target_symbol = None
                for sym, nid in self.symbol_to_node_id.items():
                    if nid == source_id:
                        source_symbol = sym
                    if nid == target_id:
                        target_symbol = sym
                if source_symbol and target_symbol:
                    class_parents[source_symbol] = target_symbol

        # For each method, check if parent class has same method
        for class_symbol, methods in methods_by_class.items():
            parent_class = class_parents.get(class_symbol)
            if not parent_class:
                continue

            parent_methods = methods_by_class.get(parent_class, {})

            for method_name, method_symbol in methods.items():
                if method_name in parent_methods:
                    parent_method_symbol = parent_methods[method_name]

                    source_id = self.symbol_to_node_id.get(method_symbol)
                    target_id = self.symbol_to_node_id.get(parent_method_symbol)

                    if source_id and target_id:
                        self.edges.append(Edge(
                            type=EdgeType.OVERRIDES,
                            source=source_id,
                            target=target_id,
                        ))
