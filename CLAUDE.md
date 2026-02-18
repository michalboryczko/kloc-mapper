# kloc-mapper Development Guide

## Overview

Maps unified JSON output from scip-php into Source-of-Truth (sot.json) graph format consumed by kloc-cli. Handles SCIP index parsing, symbol classification, node/edge construction, and call graph mapping.

## Development Setup

Python >=3.10. Uses `uv` as the package manager. Virtual environment at `.venv/`.

No runtime dependencies (stdlib only).

```bash
# Install dependencies (including dev)
uv pip install -e ".[dev]"

# Run the CLI during development
uv run kloc-mapper --help
uv run kloc-mapper map --help
```

## CLI Usage

```bash
# Map unified JSON to SoT JSON
uv run kloc-mapper map path/to/index.json -o output/sot.json

# With pretty printing
uv run kloc-mapper map path/to/index.json -o output/sot.json --pretty
```

Options for `map` command:
- `input` (positional, required) -- path to unified JSON input file (.json)
- `--out / -o` (required) -- output path for SoT JSON
- `--pretty / -p` -- pretty-print the JSON output

### Input format

Accepts unified JSON (version 4.0) produced by scip-php. Single `.json` file containing SCIP index data and call graph data. Legacy `.kloc` and `.scip` formats are not supported.

### Output format (sot.json v2.0)

- **13 Node kinds**: File, Class, Interface, Trait, Enum, Method, Function, Property, Constant, Argument, Value, Call
- **13 Edge types**: contains, uses, extends, implements, overrides, uses_trait, type_hint, calls, receiver, argument, produces, assigned_from, type_of

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run a specific test file
uv run pytest tests/test_parser.py -v
```

### Test files

| File | Type | What it tests |
|------|------|---------------|
| `test_models.py` | Unit | Data models: Node, Edge, Range, SoTGraph serialization, ID generation (714 lines) |
| `test_parser.py` | Unit | SCIP parsing: symbol strings, ranges, FQN extraction, role bitmasks |
| `test_classify_symbol.py` | Unit | Symbol classification logic |
| `test_mapper.py` | Integration | Full JSON-to-SoT mapping pipeline (requires `artifacts/index.json`, skipped if missing): node creation, edge building, containment, inheritance, overrides, deduplication |

## Architecture

### Source layout

```
src/
  cli.py           # CLI entry point (argparse)
  mapper.py        # Main mapping pipeline: SCIP documents -> SoT graph (538 lines)
  calls_mapper.py  # Call graph mapping: calls.json -> Call/Value nodes + edges (487 lines)
  parser.py        # SCIP protobuf parsing utilities (226 lines)
  json_parser.py   # Unified JSON input parser (122 lines)
  models.py        # SoT data models: Node, Edge, Range, SoTGraph (209 lines)
```

### Pipeline

1. `json_parser.py` reads unified JSON input
2. `parser.py` extracts SCIP symbol information (FQNs, ranges, roles)
3. `mapper.py` builds SoT graph nodes and edges from SCIP documents
4. `calls_mapper.py` adds Call and Value nodes with data-flow edges
5. `models.py` serializes the final SoT graph to JSON

## Building

Standalone binary via PyInstaller:

```bash
# Build for current platform (macOS native, Linux via Docker)
./build.sh

# Test the binary
./dist/kloc-mapper -h
```

### Force Linux build via Docker

```bash
docker build -t kloc-mapper-builder-linux -f - . <<'EOF'
FROM python:3.12-slim
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends binutils && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv
COPY pyproject.toml build_entry.py ./
COPY src/ ./src/
RUN uv pip install --system -e . && uv pip install --system pyinstaller
RUN pyinstaller --onefile --name kloc-mapper --collect-all src --clean build_entry.py
EOF

docker create --name kloc-mapper-build kloc-mapper-builder-linux
docker cp kloc-mapper-build:/build/dist/kloc-mapper ./dist/kloc-mapper
docker rm kloc-mapper-build
```
