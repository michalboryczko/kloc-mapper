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
# Map unified JSON to SoT JSON
uv run kloc-mapper map path/to/index.json -o output/sot.json

# With pretty printing
uv run kloc-mapper map path/to/index.json -o output/sot.json --pretty
```

Options for `map` command:
- `input` (positional, required) -- path to unified JSON input file (.json)
- `--out / -o` (required) -- output path for SoT JSON
- `--pretty / -p` -- pretty-print the JSON output

### Input Format

The mapper accepts **unified JSON** input (version 4.0) produced by scip-php. This is a single `.json` file containing SCIP index data and call graph data in one unified format.

Only `.json` files are accepted. Legacy `.kloc` and `.scip` formats are no longer supported.

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

- `tests/test_models.py` -- **Unit tests** for data models (Node, Edge, Range, SoTGraph serialization, ID generation)
- `tests/test_parser.py` -- **Unit tests** for SCIP parsing utilities (symbol strings, ranges, FQN extraction, role bitmasks)
- `tests/test_mapper.py` -- **Integration tests** for the full JSON-to-SoT mapping pipeline. Requires `artifacts/index.json` (skipped if missing). Tests node creation, edge building, containment, inheritance, overrides, and deduplication.

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
RUN pyinstaller --onefile --name kloc-mapper --collect-all src --clean build_entry.py
EOF

docker create --name kloc-mapper-build kloc-mapper-builder-linux
docker cp kloc-mapper-build:/build/dist/kloc-mapper ./dist/kloc-mapper
docker rm kloc-mapper-build
```

The output binary is at `./dist/kloc-mapper`.
