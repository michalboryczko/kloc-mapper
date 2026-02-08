# kloc-mapper Development Guide

## Development Setup

This project uses `uv` as the package manager. The virtual environment is at `.venv/`.

```bash
# Install dependencies (including dev)
uv pip install -e ".[dev]"

# Run the CLI during development
uv run kloc-mapper --help
uv run kloc-mapper map --help

# Or run directly via python module
.venv/bin/python -m src.cli --help
```

### CLI Usage

```bash
# Map a .kloc archive to SoT JSON (includes calls.json data)
uv run kloc-mapper map path/to/index.kloc -o output/sot.json

# Map a plain .scip file to SoT JSON (without call graph data)
uv run kloc-mapper map path/to/index.scip -o output/sot.json

# With pretty printing
uv run kloc-mapper map path/to/index.kloc -o output/sot.json --pretty
```

Options for `map` command:
- `input` (positional, required) — path to input file (.kloc archive or .scip file)
- `--out / -o` (required) — output path for SoT JSON
- `--pretty / -p` — pretty-print the JSON output

### Input Formats

The mapper accepts two input formats:

1. **.kloc archive** (ZIP file containing):
   - `index.scip` — SCIP protobuf index (required)
   - `calls.json` — call graph data from scip-php (optional)

2. **.scip file** — plain SCIP protobuf index (no call graph data)

When using .kloc archives, the output sot.json includes Value and Call nodes for detailed call tracking. With plain .scip files, only definition/reference nodes are created.

### Output Format (sot.json v2.0)

The unified graph format includes:
- **Node kinds**: File, Class, Interface, Trait, Enum, Method, Function, Property, Constant, Argument, Value, Call
- **Edge types**: contains, uses, extends, implements, overrides, uses_trait, type_hint, calls, receiver, argument, produces, assigned_from, type_of

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run a specific test file
uv run pytest tests/test_parser.py -v
uv run pytest tests/test_models.py -v
uv run pytest tests/test_mapper.py -v
```

### Test structure

- `tests/test_models.py` — **Unit tests** for data models (Node, Edge, Range, SoTGraph serialization, ID generation)
- `tests/test_parser.py` — **Unit tests** for SCIP parsing utilities (symbol strings, ranges, FQN extraction, role bitmasks)
- `tests/test_mapper.py` — **Integration tests** for the full SCIP-to-SoT mapping pipeline. Requires `artifacts/index_fixed.scip` (skipped if missing). Tests node creation, edge building, containment, inheritance, overrides, and deduplication.

## Building

The project builds a standalone binary using PyInstaller via `build.sh`.

```bash
# Build for current platform (macOS builds natively, Linux uses Docker)
./build.sh

# Test the binary
./dist/kloc-mapper -h
```

### Force Linux build via Docker

On macOS, you can force a Linux binary build by running the Docker build directly:

```bash
docker build -t kloc-mapper-builder-linux -f - . <<'EOF'
FROM python:3.12-slim
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends binutils && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv
COPY pyproject.toml build_entry.py ./
COPY src/ ./src/
RUN uv pip install --system -e . && uv pip install --system pyinstaller
RUN pyinstaller --onefile --name kloc-mapper --collect-all src --collect-all protobuf --clean build_entry.py
EOF

docker create --name kloc-mapper-build kloc-mapper-builder-linux
docker cp kloc-mapper-build:/build/dist/kloc-mapper ./dist/kloc-mapper
docker rm kloc-mapper-build
```

The output binary is at `./dist/kloc-mapper`.
