# kloc-mapper

A tool that converts SCIP (Sourcegraph Code Intelligence Protocol) indexes into a Source-of-Truth (SoT) JSON graph representation. Part of the **KLOC (Knowledge of Code)** project, which provides rich code context for AI coding agents.

## What it does

kloc-mapper transforms SCIP protobuf data and call graph information into a unified graph format that represents:

- **Structural nodes**: Files, classes, interfaces, traits, enums, methods, functions, properties, constants, arguments
- **Runtime nodes**: Values (parameters, locals, results) and Calls (method calls, property accesses, constructors)
- **Edges**: Structural relationships, inheritance, usage dependencies, call relationships, and type information

## Installation

Requires Python 3.10+

```bash
# Using uv (recommended)
cd kloc-mapper
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .

# Or using pip
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

## Usage

```bash
# From .kloc archive (includes call graph data)
kloc-mapper map project.kloc --out sot.json

# From plain .scip file (structural data only)
kloc-mapper map index.scip --out sot.json

# With pretty-printed output
kloc-mapper map project.kloc --out sot.json --pretty
```

### CLI Options

| Option | Short | Description |
|--------|-------|-------------|
| `input` | | Path to input file: .kloc archive or .scip file (required, positional) |
| `--out` | `-o` | Output path for SoT JSON (required) |
| `--pretty` | `-p` | Pretty-print JSON output |

## Input Formats

### .kloc Archive (Recommended)

A ZIP file containing both structural and call graph data:

```
project.kloc
├── index.scip       # SCIP protobuf index (required)
└── calls.json       # Call graph data (optional)
```

When processing a .kloc archive with calls.json, the output includes Value and Call nodes for detailed call tracking.

### .scip File

Plain SCIP protobuf index. Produces a graph with structural nodes only (no Value/Call nodes).

## Output Format (sot.json v2.0)

The SoT JSON contains nodes and edges representing the complete code graph:

```json
{
  "version": "2.0",
  "metadata": {
    "generated_at": "2026-02-05T12:00:00Z",
    "project_root": "/path/to/project"
  },
  "nodes": [...],
  "edges": [...]
}
```

### Node Example

```json
{
  "id": "abc123",
  "kind": "Method",
  "name": "getUserId",
  "fqn": "App\\Service\\User::getUserId()",
  "symbol": "scip-php composer ... App/Service/User#getUserId().",
  "file": "src/Service/User.php",
  "range": {
    "start_line": 42,
    "start_col": 4,
    "end_line": 50,
    "end_col": 5
  },
  "documentation": ["Returns the user ID"]
}
```

### Edge Example

```json
{
  "type": "calls",
  "source": "node:call:123",
  "target": "node:method:456"
}
```

### Node Kinds

**Structural nodes**: `File`, `Class`, `Interface`, `Trait`, `Enum`, `Method`, `Function`, `Property`, `Const`, `Argument`, `EnumCase`

**Runtime nodes**: `Value`, `Call`

### Edge Types

| Type | Description |
|------|-------------|
| `contains` | Structural containment (File→Class, Class→Method, Method→Call) |
| `extends` | Class/interface inheritance |
| `implements` | Interface implementation |
| `uses_trait` | Trait usage |
| `overrides` | Method override |
| `uses` | Direct reference (calls, type hints, instantiation) |
| `type_hint` | Type annotation reference |
| `calls` | Call site to target method/property/constructor |
| `receiver` | Call to receiver value (object being called on) |
| `argument` | Call to argument value (with position) |
| `produces` | Call to result value |
| `assigned_from` | Value assignment source |
| `type_of` | Value to its runtime type |

## How it works

```
Input (.kloc or .scip)
       │
       ├─→ Load archive/file
       ├─→ Parse SCIP protobuf
       ├─→ Extract symbols and documentation
       ├─→ Create structural nodes (files, classes, methods, etc.)
       ├─→ Estimate missing range data
       ├─→ Build spatial index for fast lookups
       ├─→ Build structural edges (contains, inheritance, uses, overrides)
       │
       └─→ If calls.json present:
           ├─→ Create Value nodes (parameters, locals, results)
           ├─→ Create Call nodes (method calls, property accesses)
           ├─→ Build call edges (calls, receiver, argument, produces)
           └─→ Build type edges (type_of)
       │
       ▼
SoT JSON v2.0 (unified graph)
```

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"
# or: pip install -e ".[dev]"

# Run tests
pytest tests/
```

## Building Standalone Binary

```bash
./build.sh
```

Detects platform and builds appropriate binary:
- **Linux**: uses Docker (requires Docker)
- **macOS**: builds natively (requires Python 3.10+, Docker cannot produce macOS binaries)

## Project Structure

```
src/
├── cli.py           # Command-line interface
├── models.py        # Data structures (Node, Edge, SoTGraph)
├── parser.py        # SCIP protobuf parsing utilities
├── mapper.py        # Core SCIP-to-SoT mapping logic
├── archive.py       # .kloc archive loader
├── calls_mapper.py  # Calls.json to Value/Call nodes
└── scip_pb2.py      # Pre-generated protobuf bindings for SCIP format
```

### Regenerating scip_pb2.py

The `scip_pb2.py` file is pre-generated from the [SCIP protocol definition](https://github.com/sourcegraph/scip). To regenerate it (e.g., after a SCIP schema update):

```bash
# Download the latest scip.proto
curl -o scip.proto https://raw.githubusercontent.com/sourcegraph/scip/main/scip.proto

# Generate Python bindings
protoc --python_out=src scip.proto

# Clean up
rm scip.proto
```

## Related Projects

- **kloc-cli**: Consumes SoT JSON to provide commands like `deps`, `usages`, `context`, and `inherit`
- **SCIP**: [Sourcegraph Code Intelligence Protocol](https://github.com/sourcegraph/scip)

## License

MIT
