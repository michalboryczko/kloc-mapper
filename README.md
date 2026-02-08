# kloc-mapper

A tool that converts unified JSON indexes (produced by scip-php) into a Source-of-Truth (SoT) JSON graph representation. Part of the **KLOC (Knowledge of Code)** project, which provides rich code context for AI coding agents.

## What it does

kloc-mapper transforms unified JSON data containing SCIP index and call graph information into a unified graph format that represents:

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
# Map unified JSON to SoT JSON
kloc-mapper map index.json --out sot.json

# With pretty-printed output
kloc-mapper map index.json --out sot.json --pretty
```

### CLI Options

| Option | Short | Description |
|--------|-------|-------------|
| `input` | | Path to unified JSON input file (.json, required, positional) |
| `--out` | `-o` | Output path for SoT JSON (required) |
| `--pretty` | `-p` | Pretty-print JSON output |

## Input Format

### Unified JSON (version 4.0)

A single `.json` file produced by scip-php containing both SCIP index data and call graph data in one unified format. This is the only supported input format.

The unified JSON includes:
- SCIP index data (documents, symbols, occurrences, relationships)
- Call graph data (values, calls, receivers, arguments)

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
| `contains` | Structural containment (File->Class, Class->Method, Method->Call) |
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
Input (unified JSON)
       |
       +-> Parse unified JSON (index + calls data)
       +-> Extract symbols and documentation
       +-> Create structural nodes (files, classes, methods, etc.)
       +-> Build spatial index for fast lookups
       +-> Build structural edges (contains, inheritance, uses, overrides)
       |
       +-> If calls data present:
           +-> Create Value nodes (parameters, locals, results)
           +-> Create Call nodes (method calls, property accesses)
           +-> Build call edges (calls, receiver, argument, produces)
           +-> Build type edges (type_of)
       |
       v
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
+-- cli.py           # Command-line interface
+-- models.py        # Data structures (Node, Edge, SoTGraph)
+-- parser.py        # SCIP symbol parsing utilities
+-- mapper.py        # Core JSON-to-SoT mapping logic
+-- json_parser.py   # Unified JSON parser (version 4.0)
+-- calls_mapper.py  # Calls data to Value/Call nodes
```

## Related Projects

- **kloc-cli**: Consumes SoT JSON to provide commands like `deps`, `usages`, `context`, and `inherit`
- **SCIP**: [Sourcegraph Code Intelligence Protocol](https://github.com/sourcegraph/scip)

## License

MIT
