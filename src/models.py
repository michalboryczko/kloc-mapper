"""Data models for Source-of-Truth JSON."""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional
import hashlib
import json


class NodeKind(str, Enum):
    """Types of nodes in the SoT graph."""
    # Structural nodes (from SCIP index)
    FILE = "File"
    CLASS = "Class"
    INTERFACE = "Interface"
    TRAIT = "Trait"
    ENUM = "Enum"
    METHOD = "Method"
    FUNCTION = "Function"
    PROPERTY = "Property"
    CONST = "Const"
    ARGUMENT = "Argument"
    ENUM_CASE = "EnumCase"

    # Runtime entities (from calls.json)
    VALUE = "Value"      # Runtime value: parameter, local, result, literal, constant
    CALL = "Call"        # Call site: method call, property access, constructor, etc.


class EdgeType(str, Enum):
    """Types of edges in the SoT graph."""
    # Structural edges (from SCIP index)
    CONTAINS = "contains"
    EXTENDS = "extends"
    IMPLEMENTS = "implements"
    USES_TRAIT = "uses_trait"
    OVERRIDES = "overrides"
    USES = "uses"

    # Type reference edges
    TYPE_HINT = "type_hint"        # Type annotation -> Class/Interface

    # Call relationship edges (from calls.json)
    CALLS = "calls"                # Call -> Method/Function/Property/Constructor
    RECEIVER = "receiver"          # Call -> Value (object being called on)
    ARGUMENT = "argument"          # Call -> Value (value passed as argument)

    # Value relationship edges (from calls.json)
    PRODUCES = "produces"          # Call -> Value (result of call)
    ASSIGNED_FROM = "assigned_from"  # Value -> Value (assignment source)
    TYPE_OF = "type_of"            # Value -> Class/Interface (runtime type)


@dataclass
class Range:
    """Source code range."""
    start_line: int
    start_col: int
    end_line: int
    end_col: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Location:
    """Source location (file + range)."""
    file: str
    line: int
    col: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Node:
    """A node in the SoT graph."""
    id: str
    kind: NodeKind
    name: str
    fqn: str
    symbol: str
    file: Optional[str]
    range: Optional[Range]
    enclosing_range: Optional[Range] = None
    documentation: list[str] = field(default_factory=list)

    # Value node fields (only set when kind == VALUE)
    value_kind: Optional[str] = None    # "parameter", "local", "result", "literal", "constant"
    type_symbol: Optional[str] = None   # SCIP symbol of the value's type

    # Call node fields (only set when kind == CALL)
    call_kind: Optional[str] = None     # "method", "method_static", "constructor", "access", "access_static", "function"

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "kind": self.kind.value,
            "name": self.name,
            "fqn": self.fqn,
            "symbol": self.symbol,
            "file": self.file,
            "range": self.range.to_dict() if self.range else None,
            "enclosing_range": self.enclosing_range.to_dict() if self.enclosing_range else None,
            "documentation": self.documentation,
        }
        # Add kind-specific fields only when set
        if self.value_kind is not None:
            d["value_kind"] = self.value_kind
        if self.type_symbol is not None:
            d["type_symbol"] = self.type_symbol
        if self.call_kind is not None:
            d["call_kind"] = self.call_kind
        return d


@dataclass
class Edge:
    """An edge in the SoT graph."""
    type: EdgeType
    source: str  # node id
    target: str  # node id
    location: Optional[Location] = None
    position: Optional[int] = None  # For argument edges: 0-based argument index

    def to_dict(self) -> dict:
        d = {
            "type": self.type.value,
            "source": self.source,
            "target": self.target,
        }
        if self.location:
            d["location"] = self.location.to_dict()
        if self.position is not None:
            d["position"] = self.position
        return d


@dataclass
class SoTGraph:
    """Complete Source-of-Truth graph."""
    version: str = "2.0"
    metadata: dict = field(default_factory=dict)
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "metadata": self.metadata,
            "nodes": sorted([n.to_dict() for n in self.nodes], key=lambda x: x["id"]),
            "edges": sorted(
                [e.to_dict() for e in self.edges],
                key=lambda x: (x["source"], x["type"], x["target"])
            ),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def generate_node_id(symbol: str) -> str:
    """Generate deterministic node ID from symbol string."""
    h = hashlib.sha256(symbol.encode("utf-8")).hexdigest()[:16]
    return f"node:{h}"


def generate_file_node_id(filepath: str) -> str:
    """Generate deterministic node ID for a file."""
    h = hashlib.sha256(f"file:{filepath}".encode("utf-8")).hexdigest()[:16]
    return f"node:{h}"


def generate_value_node_id(location_id: str) -> str:
    """Generate deterministic node ID for a Value node.

    Uses 'val:' prefix to distinguish from Call nodes at same location.

    Args:
        location_id: Location-based ID from calls.json (format: "file:line:col")

    Returns:
        Node ID with format "node:val:<hash>"
    """
    h = hashlib.sha256(f"val:{location_id}".encode("utf-8")).hexdigest()[:16]
    return f"node:val:{h}"


def generate_call_node_id(location_id: str) -> str:
    """Generate deterministic node ID for a Call node.

    Uses 'call:' prefix to distinguish from Value nodes at same location.

    Args:
        location_id: Location-based ID from calls.json (format: "file:line:col")

    Returns:
        Node ID with format "node:call:<hash>"
    """
    h = hashlib.sha256(f"call:{location_id}".encode("utf-8")).hexdigest()[:16]
    return f"node:call:{h}"
