# kloc-mapper

Transforms unified JSON indexes (produced by scip-php) into Source-of-Truth (SoT) JSON graph files consumed by kloc-cli.

## Pipeline Position

```
PHP code -> scip-php -> index.json -> kloc-mapper -> sot.json -> kloc-cli -> output
```

kloc-mapper sits between scip-php (which produces `index.json`) and kloc-cli (which queries `sot.json`).

## Installation

```bash
cd kloc-mapper
uv venv && source .venv/bin/activate
uv pip install -e .
```

Requires Python 3.10+. No external dependencies.

## Usage

```bash
# Map unified JSON to SoT JSON
kloc-mapper map index.json --out sot.json

# With pretty-printed output
kloc-mapper map index.json --out sot.json --pretty
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `input` | | Path to unified JSON input file (positional, required) |
| `--out` | `-o` | Output path for SoT JSON (required) |
| `--pretty` | `-p` | Pretty-print JSON output |

## Input: Unified JSON (v4.0)

A single `.json` file produced by scip-php containing:
- SCIP index data (documents, symbols, occurrences, relationships)
- Call graph data (values, calls, receivers, arguments)

Only `.json` files are accepted. Legacy `.kloc` and `.scip` formats are not supported.

## Output: SoT JSON (v2.0)

The graph contains nodes and edges representing the complete code structure.

```json
{
  "version": "2.0",
  "metadata": { "generated_at": "...", "project_root": "..." },
  "nodes": [...],
  "edges": [...]
}
```

### Node Kinds

**Structural**: File, Class, Interface, Trait, Enum, Method, Function, Property, Const, Argument, EnumCase

**Runtime**: Value (parameters, locals, results), Call (method calls, property accesses, constructors)

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
| `receiver` | Call to receiver value |
| `argument` | Call to argument value (with position) |
| `produces` | Call to result value |
| `assigned_from` | Value assignment source |
| `type_of` | Value to its runtime type |

## Project Structure

```
src/
├── cli.py           # Command-line interface
├── models.py        # Data structures (Node, Edge, SoTGraph)
├── parser.py        # SCIP symbol parsing utilities
├── mapper.py        # Core JSON-to-SoT mapping logic
├── json_parser.py   # Unified JSON parser (v4.0)
└── calls_mapper.py  # Calls data to Value/Call nodes
```

## How It Works

```
Unified JSON (index.json)
       |
       +-> Parse unified JSON (SCIP index + calls data)
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
SoT JSON v2.0 (sot.json)
```

## Development

```bash
uv pip install -e ".[dev]"
uv run pytest tests/ -v
```

## Building Standalone Binary

```bash
./build.sh
```

Builds platform-appropriate binary: Linux via Docker, macOS natively.

## License

MIT
