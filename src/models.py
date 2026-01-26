"""Data models for Source-of-Truth JSON."""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional
import hashlib
import json


class NodeKind(str, Enum):
    """Types of nodes in the SoT graph."""
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


class EdgeType(str, Enum):
    """Types of edges in the SoT graph."""
    CONTAINS = "contains"
    EXTENDS = "extends"
    IMPLEMENTS = "implements"
    USES_TRAIT = "uses_trait"
    OVERRIDES = "overrides"
    USES = "uses"


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
    documentation: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "kind": self.kind.value,
            "name": self.name,
            "fqn": self.fqn,
            "symbol": self.symbol,
            "file": self.file,
            "range": self.range.to_dict() if self.range else None,
            "documentation": self.documentation,
        }
        return d


@dataclass
class Edge:
    """An edge in the SoT graph."""
    type: EdgeType
    source: str  # node id
    target: str  # node id
    location: Optional[Location] = None

    def to_dict(self) -> dict:
        d = {
            "type": self.type.value,
            "source": self.source,
            "target": self.target,
        }
        if self.location:
            d["location"] = self.location.to_dict()
        return d


@dataclass
class SoTGraph:
    """Complete Source-of-Truth graph."""
    version: str = "1.0"
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
