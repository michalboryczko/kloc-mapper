"""Calls.json to graph nodes and edges mapper.

Transforms calls.json data (values and calls arrays) into graph nodes and edges
for the unified graph format.
"""

from typing import Optional
import re

from src.models import (
    Node, Edge, Range, NodeKind, EdgeType,
    generate_value_node_id, generate_call_node_id, generate_node_id,
)


class CallsMapper:
    """Maps calls.json data to Value and Call nodes with edges."""

    def __init__(
        self,
        calls_data: dict,
        nodes: dict[str, Node],
        edges: list[Edge],
        symbol_to_node_id: dict[str, str],
        file_symbol_index: dict[str, list[tuple[int, int, str, NodeKind]]],
    ):
        """Initialize the mapper.

        Args:
            calls_data: Parsed calls.json data dict.
            nodes: Reference to the nodes dict (will be modified).
            edges: Reference to the edges list (will be modified).
            symbol_to_node_id: Mapping of SCIP symbols to node IDs.
            file_symbol_index: Spatial index for finding enclosing scopes.
        """
        self.calls_data = calls_data
        self.nodes = nodes
        self.edges = edges
        self.symbol_to_node_id = symbol_to_node_id
        self.file_symbol_index = file_symbol_index

        # Index for lookups
        self.value_id_to_node_id: dict[str, str] = {}  # calls.json id -> node_id
        self.call_id_to_node_id: dict[str, str] = {}   # calls.json id -> node_id

    def process(self):
        """Process calls.json data and create nodes/edges."""
        self._create_value_nodes()
        self._create_call_nodes()
        self._create_call_edges()
        self._create_value_edges()

    def _create_value_nodes(self):
        """Create Value nodes from calls.json values array."""
        values = self.calls_data.get("values", [])

        for value in values:
            value_id = value.get("id")
            if not value_id:
                continue

            node_id = generate_value_node_id(value_id)
            self.value_id_to_node_id[value_id] = node_id

            location = value.get("location", {})
            file_path = location.get("file")
            line = location.get("line", 0)
            col = location.get("col", 0)

            # Extract name from symbol or use kind-based default
            name = self._extract_value_name(value)
            value_kind = value.get("kind", "unknown")

            # Build FQN - use scope + name for parameters/locals, location for others
            symbol = value.get("symbol")
            fqn = self._build_value_fqn(value, name)

            # Create range (single position for values)
            range_obj = Range(
                start_line=line,
                start_col=col,
                end_line=line,
                end_col=col + len(name) if name else col,
            )

            node = Node(
                id=node_id,
                kind=NodeKind.VALUE,
                name=name,
                fqn=fqn,
                symbol=symbol or "",
                file=file_path,
                range=range_obj,
                value_kind=value_kind,
                type_symbol=value.get("type"),
            )

            self.nodes[node_id] = node

    def _create_call_nodes(self):
        """Create Call nodes from calls.json calls array."""
        calls = self.calls_data.get("calls", [])

        for call in calls:
            call_id = call.get("id")
            if not call_id:
                continue

            node_id = generate_call_node_id(call_id)
            self.call_id_to_node_id[call_id] = node_id

            location = call.get("location", {})
            file_path = location.get("file")
            line = location.get("line", 0)
            col = location.get("col", 0)

            # Extract name from callee symbol
            name = self._extract_call_name(call)
            call_kind = call.get("kind", "unknown")

            # Build FQN using caller + location
            fqn = self._build_call_fqn(call, line, col)

            # Create range (single position for call site)
            range_obj = Range(
                start_line=line,
                start_col=col,
                end_line=line,
                end_col=col + len(name) if name else col,
            )

            node = Node(
                id=node_id,
                kind=NodeKind.CALL,
                name=name,
                fqn=fqn,
                symbol="",  # Call nodes don't have SCIP symbols
                file=file_path,
                range=range_obj,
                call_kind=call_kind,
            )

            self.nodes[node_id] = node

    def _create_call_edges(self):
        """Create edges from Call nodes: calls, receiver, argument, produces, contains."""
        calls = self.calls_data.get("calls", [])

        for call in calls:
            call_id = call.get("id")
            call_node_id = self.call_id_to_node_id.get(call_id)
            if not call_node_id:
                continue

            # 1. Create 'calls' edge to target (method/function/property/class)
            callee = call.get("callee")
            if callee:
                target_node_id = self._resolve_symbol_to_node_id(callee)
                if target_node_id:
                    self.edges.append(Edge(
                        type=EdgeType.CALLS,
                        source=call_node_id,
                        target=target_node_id,
                    ))
                # For constructor calls, also create edge to the class
                elif call.get("kind") == "constructor":
                    return_type = call.get("return_type")
                    if return_type:
                        class_node_id = self._resolve_symbol_to_node_id(return_type)
                        if class_node_id:
                            self.edges.append(Edge(
                                type=EdgeType.CALLS,
                                source=call_node_id,
                                target=class_node_id,
                            ))

            # 2. Create 'receiver' edge to receiver value
            receiver_value_id = call.get("receiver_value_id")
            if receiver_value_id:
                receiver_node_id = self.value_id_to_node_id.get(receiver_value_id)
                if receiver_node_id:
                    self.edges.append(Edge(
                        type=EdgeType.RECEIVER,
                        source=call_node_id,
                        target=receiver_node_id,
                    ))

            # 3. Create 'argument' edges with position
            arguments = call.get("arguments", [])
            for arg in arguments:
                position = arg.get("position")
                value_id = arg.get("value_id")
                if value_id and position is not None:
                    arg_node_id = self.value_id_to_node_id.get(value_id)
                    if arg_node_id:
                        self.edges.append(Edge(
                            type=EdgeType.ARGUMENT,
                            source=call_node_id,
                            target=arg_node_id,
                            position=position,
                        ))

            # 4. Create 'produces' edge to result value
            # Result value has same ID as call
            result_value_node_id = self.value_id_to_node_id.get(call_id)
            if result_value_node_id:
                self.edges.append(Edge(
                    type=EdgeType.PRODUCES,
                    source=call_node_id,
                    target=result_value_node_id,
                ))

            # 5. Create 'contains' edge from enclosing method/function
            caller = call.get("caller")
            if caller:
                enclosing_node_id = self._resolve_symbol_to_node_id(caller)
                if enclosing_node_id:
                    self.edges.append(Edge(
                        type=EdgeType.CONTAINS,
                        source=enclosing_node_id,
                        target=call_node_id,
                    ))

    def _create_value_edges(self):
        """Create edges for Value nodes: assigned_from, type_of, contains."""
        values = self.calls_data.get("values", [])

        for value in values:
            value_id = value.get("id")
            value_node_id = self.value_id_to_node_id.get(value_id)
            if not value_node_id:
                continue

            # 1. Create 'assigned_from' edge for value-to-value assignments
            source_value_id = value.get("source_value_id")
            if source_value_id:
                source_node_id = self.value_id_to_node_id.get(source_value_id)
                if source_node_id:
                    self.edges.append(Edge(
                        type=EdgeType.ASSIGNED_FROM,
                        source=value_node_id,
                        target=source_node_id,
                    ))

            # 2. Create 'type_of' edge to type class/interface
            type_symbol = value.get("type")
            if type_symbol:
                type_node_id = self._resolve_symbol_to_node_id(type_symbol)
                if type_node_id:
                    self.edges.append(Edge(
                        type=EdgeType.TYPE_OF,
                        source=value_node_id,
                        target=type_node_id,
                    ))

            # 3. Create 'contains' edge from enclosing method/function
            # Extract scope from symbol
            symbol = value.get("symbol")
            if symbol:
                enclosing_symbol = self._get_enclosing_symbol_from_value(symbol)
                if enclosing_symbol:
                    enclosing_node_id = self._resolve_symbol_to_node_id(enclosing_symbol)
                    if enclosing_node_id:
                        self.edges.append(Edge(
                            type=EdgeType.CONTAINS,
                            source=enclosing_node_id,
                            target=value_node_id,
                        ))

    def _extract_value_name(self, value: dict) -> str:
        """Extract display name for a value."""
        symbol = value.get("symbol")
        kind = value.get("kind", "")

        if symbol:
            # Parameter: extract from ".($name)" pattern
            if ".($" in symbol:
                match = re.search(r'\.\(\$?([a-zA-Z_][a-zA-Z0-9_]*)\)', symbol)
                if match:
                    return "$" + match.group(1)

            # Local variable: extract from ".local$name@" pattern
            if ".local$" in symbol:
                match = re.search(r'\.local\$([a-zA-Z_][a-zA-Z0-9_]*)@', symbol)
                if match:
                    return "$" + match.group(1)

            # Property: extract from "#$name." pattern
            if "#$" in symbol:
                match = re.search(r'#\$([a-zA-Z_][a-zA-Z0-9_]*)\.?$', symbol)
                if match:
                    return "$" + match.group(1)

        # Fall back to kind-based names
        if kind == "result":
            return "(result)"
        if kind == "literal":
            return "(literal)"
        if kind == "constant":
            return "(constant)"

        return "$unknown"

    def _extract_call_name(self, call: dict) -> str:
        """Extract display name for a call."""
        callee = call.get("callee")
        kind = call.get("kind", "")

        if callee:
            # Method/Function: extract from "#name()." or "name()." pattern
            match = re.search(r'#?([a-zA-Z_][a-zA-Z0-9_]*)\(\)\.?$', callee)
            if match:
                name = match.group(1)
                if kind in ("method", "method_static", "function", "constructor"):
                    return f"{name}()"
                return name

            # Property: extract from "#$name." pattern
            match = re.search(r'#\$?([a-zA-Z_][a-zA-Z0-9_]*)\.?$', callee)
            if match:
                return match.group(1)

        # Constructor without callee - use return_type
        if kind == "constructor":
            return_type = call.get("return_type")
            if return_type:
                match = re.search(r'/([a-zA-Z_][a-zA-Z0-9_]*)#$', return_type)
                if match:
                    return f"new {match.group(1)}()"

        return "(call)"

    def _build_value_fqn(self, value: dict, name: str) -> str:
        """Build fully qualified name for a value."""
        symbol = value.get("symbol", "")
        location = value.get("location", {})
        file_path = location.get("file", "")
        line = location.get("line", 0)

        # For parameters/locals with symbol, use the symbol structure
        if symbol:
            # Extract scope from symbol (everything before the value part)
            scope_match = re.match(r'^(.+?)(?:\.local\$|\.\(\$)', symbol)
            if scope_match:
                scope = scope_match.group(1)
                # Convert SCIP symbol to FQN format
                fqn_scope = self._symbol_to_fqn(scope)
                return f"{fqn_scope}.{name}"

        # Fall back to file:line location
        return f"{file_path}:{line}:{name}"

    def _build_call_fqn(self, call: dict, line: int, col: int) -> str:
        """Build fully qualified name for a call."""
        caller = call.get("caller", "")
        caller_fqn = self._symbol_to_fqn(caller) if caller else ""

        if caller_fqn:
            return f"{caller_fqn}@{line}:{col}"

        location = call.get("location", {})
        file_path = location.get("file", "")
        return f"{file_path}:{line}:{col}"

    def _symbol_to_fqn(self, symbol: str) -> str:
        """Convert a SCIP symbol to FQN format."""
        # Remove SCIP prefix: "scip-php composer ... Namespace/Class#method()."
        if "scip-php" in symbol:
            parts = symbol.split()
            if len(parts) >= 4:
                # Take everything after the package version
                symbol_part = " ".join(parts[4:]) if len(parts) > 4 else parts[-1]
            else:
                symbol_part = parts[-1] if parts else symbol
        else:
            symbol_part = symbol

        # Convert to namespace format
        fqn = symbol_part.replace("/", "\\").rstrip(".")

        # Convert method suffix
        fqn = re.sub(r'#([a-zA-Z_][a-zA-Z0-9_]*)\(\)\.$', r'::\1()', fqn)
        fqn = re.sub(r'#([a-zA-Z_][a-zA-Z0-9_]*)\(\)$', r'::\1()', fqn)

        # Convert property suffix
        fqn = re.sub(r'#\$([a-zA-Z_][a-zA-Z0-9_]*)\.?$', r'::$\1', fqn)

        # Clean up
        fqn = fqn.rstrip("#").rstrip(".")

        return fqn

    def _resolve_symbol_to_node_id(self, symbol: str) -> Optional[str]:
        """Resolve a SCIP symbol to a node ID."""
        # Direct lookup
        if symbol in self.symbol_to_node_id:
            return self.symbol_to_node_id[symbol]

        # Try with trailing period removed/added
        symbol_clean = symbol.rstrip(".")
        if symbol_clean in self.symbol_to_node_id:
            return self.symbol_to_node_id[symbol_clean]

        symbol_with_dot = symbol + "."
        if symbol_with_dot in self.symbol_to_node_id:
            return self.symbol_to_node_id[symbol_with_dot]

        # For class symbols ending with #, try without
        symbol_no_hash = symbol.rstrip("#")
        if symbol_no_hash in self.symbol_to_node_id:
            return self.symbol_to_node_id[symbol_no_hash]

        # For builtin types, we may not have a node
        return None

    def _get_enclosing_symbol_from_value(self, symbol: str) -> Optional[str]:
        """Extract the enclosing method/function symbol from a value symbol."""
        # Parameter: "...#method().($param)" -> "...#method()."
        if ".($" in symbol:
            idx = symbol.rfind(".($")
            return symbol[:idx] + "."

        # Local: "...#method().local$var@line" -> "...#method()."
        if ".local$" in symbol:
            idx = symbol.rfind(".local$")
            return symbol[:idx] + "."

        return None
