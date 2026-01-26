# kloc-mapper

A tool that converts SCIP (Sourcegraph Code Intelligence Protocol) indexes into a Source-of-Truth (SoT) JSON graph representation. Part of the **KLOC (Knowledge of Code)** project, which provides rich code context for AI coding agents.

## What it does

kloc-mapper transforms low-level SCIP protobuf data into a higher-level graph format that clearly represents:

- **Nodes**: Files, classes, interfaces, traits, enums, methods, functions, properties, constants, and arguments
- **Edges**: Structural relationships (`contains`), inheritance (`extends`, `implements`, `uses_trait`), method overrides (`overrides`), and usage dependencies (`uses`)

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
# Basic usage
kloc-mapper map --scip <path-to-scip.index> --out <output.json>

# With pretty-printed output
kloc-mapper map -s artifacts/scip.index -o artifacts/sot.json --pretty
```

### CLI Options

| Option | Short | Description |
|--------|-------|-------------|
| `--scip` | `-s` | Path to SCIP index file (required) |
| `--out` | `-o` | Output path for SoT JSON (required) |
| `--pretty` | `-p` | Pretty-print JSON output |

## Output Format

The SoT JSON contains two main arrays:

### Nodes

```json
{
  "id": "abc123",
  "kind": "METHOD",
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

### Edges

```json
{
  "type": "uses",
  "source": "abc123",
  "target": "def456",
  "location": {
    "file": "src/Service/User.php",
    "line": 45,
    "col": 12
  }
}
```

### Node Kinds

`FILE`, `CLASS`, `INTERFACE`, `TRAIT`, `ENUM`, `METHOD`, `FUNCTION`, `PROPERTY`, `CONST`, `ARGUMENT`, `ENUM_CASE`

### Edge Types

| Type | Description |
|------|-------------|
| `contains` | Structural containment (File→Class, Class→Method) |
| `extends` | Class/interface inheritance |
| `implements` | Interface implementation |
| `uses_trait` | Trait usage |
| `overrides` | Method override |
| `uses` | Direct reference (calls, type hints, instantiation) |

## How it works

```
SCIP Index (.scip)
       │
       ├─→ Parse protobuf
       ├─→ Extract symbols and documentation
       ├─→ Create nodes (files, classes, methods, etc.)
       ├─→ Estimate missing range data
       ├─→ Build spatial index for fast lookups
       ├─→ Build edges (contains, inheritance, uses, overrides)
       │
       ▼
SoT JSON (nodes + edges)
```

The mapper uses a multi-phase pipeline to:
1. Collect symbol metadata and documentation
2. Create nodes for all symbols
3. Estimate missing end-line data using sibling positions
4. Build a spatial index for efficient enclosing symbol lookup
5. Build structural, inheritance, and usage edges

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
├── cli.py        # Command-line interface
├── models.py     # Data structures (Node, Edge, SoTGraph)
├── parser.py     # SCIP protobuf parsing utilities
├── mapper.py     # Core SCIP-to-SoT mapping logic
└── scip_pb2.py   # Pre-generated protobuf bindings for SCIP format
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
