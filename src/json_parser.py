"""Unified JSON parser for kloc-mapper.

Parses the unified JSON output from scip-php (version 4.0) into objects
compatible with the protobuf-based SCIPMapper interface. This eliminates
the need for scip_pb2.py protobuf parsing and archive.py ZIP extraction.
"""

import json
from pathlib import Path


class _Obj:
    """Lightweight attribute-access wrapper over a dict."""

    def __init__(self, data: dict, defaults: dict | None = None):
        self._data = data
        self._defaults = defaults or {}

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._data:
            return self._data[name]
        if name in self._defaults:
            return self._defaults[name]
        raise AttributeError(f"No attribute '{name}' in JSON object")


class _ToolInfo(_Obj):
    def __init__(self, data: dict):
        super().__init__(data, defaults={"arguments": []})


class _Metadata(_Obj):
    """SCIP metadata with project_root attribute."""

    def __init__(self, data: dict):
        super().__init__(data, defaults={"project_root": ""})
        self.tool_info = _ToolInfo(data.get("tool_info", {}))


class _Relationship(_Obj):
    """SCIP relationship with boolean flags."""

    def __init__(self, data: dict):
        super().__init__(data, defaults={
            "is_implementation": False,
            "is_reference": False,
            "is_type_definition": False,
            "is_definition": False,
        })


class _SymbolInformation(_Obj):
    """SCIP symbol information with documentation and relationships."""

    def __init__(self, data: dict):
        super().__init__(data, defaults={"symbol": "", "documentation": []})
        self.documentation = data.get("documentation", [])
        self.relationships = [
            _Relationship(r) for r in data.get("relationships", [])
        ]


class _Occurrence(_Obj):
    """SCIP occurrence with range, symbol_roles, and enclosing_range."""

    def __init__(self, data: dict):
        super().__init__(data, defaults={
            "symbol": "",
            "symbol_roles": 0,
        })
        self.range = data.get("range", [])
        self.enclosing_range = data.get("enclosing_range", [])


class _Document(_Obj):
    """SCIP document with relative_path, symbols, and occurrences."""

    def __init__(self, data: dict):
        super().__init__(data, defaults={"relative_path": "", "language": ""})
        self.symbols = [
            _SymbolInformation(s) for s in data.get("symbols", [])
        ]
        self.occurrences = [
            _Occurrence(o) for o in data.get("occurrences", [])
        ]


class _Index:
    """Top-level SCIP index with metadata and documents."""

    def __init__(self, scip_data: dict):
        self.metadata = _Metadata(scip_data.get("metadata", {}))
        self.documents = [
            _Document(d) for d in scip_data.get("documents", [])
        ]


def parse_unified_json(filepath: str | Path) -> tuple[_Index, dict]:
    """Parse a unified JSON file from scip-php.

    Returns:
        (index, calls_data) tuple where:
        - index: object with .metadata and .documents attributes,
          duck-typing the protobuf scip_pb2.Index interface
        - calls_data: dict with "calls" and "values" arrays
    """
    filepath = Path(filepath)

    with open(filepath, "r") as f:
        data = json.load(f)

    scip_data = data.get("scip", {})
    index = _Index(scip_data)

    calls_data = {
        "calls": data.get("calls", []),
        "values": data.get("values", []),
    }

    return index, calls_data
