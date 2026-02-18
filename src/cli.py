"""CLI entry point for kloc-mapper."""

import argparse
import json as json_module
import sys
from pathlib import Path

from src.mapper import SCIPMapper
from src.json_parser import parse_unified_json


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="kloc-mapper",
        description="Map unified JSON index to Source-of-Truth JSON"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # map command
    map_parser = subparsers.add_parser("map", help="Map unified JSON to SoT JSON")
    map_parser.add_argument(
        "input",
        help="Path to unified JSON input file (.json)"
    )
    map_parser.add_argument(
        "--out", "-o",
        required=True,
        help="Output path for SoT JSON"
    )
    map_parser.add_argument(
        "--pretty", "-p",
        action="store_true",
        help="Pretty-print JSON output"
    )

    args = parser.parse_args()

    if args.command == "map":
        cmd_map(args)
    else:
        parser.print_help()
        sys.exit(1)


KNOWN_VERSIONS = {"3.0", "4.0"}


def validate_input_version(data: dict) -> None:
    """Validate the version field of input data.

    Logs warnings for missing or unknown versions but never errors out.
    """
    version = data.get("version", "")
    if not version:
        print("Warning: input data has no version field (deprecated format)", file=sys.stderr)
    elif version not in KNOWN_VERSIONS:
        print(f"Warning: unknown input version '{version}', proceeding anyway", file=sys.stderr)


def cmd_map(args):
    """Execute the map command."""
    input_path = Path(args.input)
    out_path = Path(args.out)

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    if input_path.suffix.lower() != ".json":
        print(f"Error: Unsupported input format '{input_path.suffix}'. Only .json (unified JSON) is supported.", file=sys.stderr)
        sys.exit(1)

    print(f"Loading unified JSON {input_path}...", file=sys.stderr)

    try:
        with open(input_path, "r") as f:
            raw_data = json_module.load(f)
        validate_input_version(raw_data)
    except json_module.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {input_path}: {e}", file=sys.stderr)
        sys.exit(1)

    index, calls_data = parse_unified_json(input_path)

    print(f"Mapping to SoT JSON...", file=sys.stderr)

    mapper = SCIPMapper(input_path, calls_data=calls_data, index=index)
    graph = mapper.map()

    indent = 2 if args.pretty else None
    json_output = graph.to_json(indent=indent)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        f.write(json_output)

    # Count node types
    value_count = sum(1 for n in graph.nodes if n.kind.value == "Value")
    call_count = sum(1 for n in graph.nodes if n.kind.value == "Call")

    print(f"Written to {out_path}", file=sys.stderr)
    print(f"  Version: {graph.version}", file=sys.stderr)
    print(f"  Nodes: {len(graph.nodes)} (including {value_count} Value, {call_count} Call)", file=sys.stderr)
    print(f"  Edges: {len(graph.edges)}", file=sys.stderr)


if __name__ == "__main__":
    main()
