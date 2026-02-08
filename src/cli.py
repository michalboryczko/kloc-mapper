"""CLI entry point for kloc-mapper."""

import argparse
import sys
from pathlib import Path

from src.mapper import SCIPMapper
from src.archive import KlocArchive, ArchiveError


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="kloc-mapper",
        description="Map SCIP index to Source-of-Truth JSON"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # map command
    map_parser = subparsers.add_parser("map", help="Map SCIP/kloc to SoT JSON")
    map_parser.add_argument(
        "input",
        help="Path to input file (.kloc archive, .scip file, or unified .json)"
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
    # Keep --scip as hidden alias for backward compatibility
    map_parser.add_argument(
        "--scip", "-s",
        dest="input_legacy",
        help=argparse.SUPPRESS
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
    # Handle backward compat: --scip overrides positional if provided
    input_path = Path(args.input_legacy if args.input_legacy else args.input)
    out_path = Path(args.out)

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Determine input type by extension
    suffix = input_path.suffix.lower()

    if suffix == ".json":
        cmd_map_json(input_path, out_path, args.pretty)
    elif suffix == ".kloc":
        cmd_map_kloc(input_path, out_path, args.pretty)
    elif suffix == ".scip":
        cmd_map_scip(input_path, out_path, args.pretty)
    else:
        # Try to detect by probing the file
        import zipfile
        if zipfile.is_zipfile(input_path):
            cmd_map_kloc(input_path, out_path, args.pretty)
        else:
            # Assume SCIP protobuf
            cmd_map_scip(input_path, out_path, args.pretty)


def cmd_map_scip(scip_path: Path, out_path: Path, pretty: bool):
    """Map a plain .scip file (backward compatibility)."""
    print(f"Mapping {scip_path} to SoT JSON...", file=sys.stderr)

    mapper = SCIPMapper(scip_path)
    graph = mapper.map()

    indent = 2 if pretty else None
    json_output = graph.to_json(indent=indent)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        f.write(json_output)

    print(f"Written to {out_path}", file=sys.stderr)
    print(f"  Version: {graph.version}", file=sys.stderr)
    print(f"  Nodes: {len(graph.nodes)}", file=sys.stderr)
    print(f"  Edges: {len(graph.edges)}", file=sys.stderr)


def cmd_map_json(json_path: Path, out_path: Path, pretty: bool):
    """Map a unified JSON file to SoT JSON."""
    import json as json_module
    from src.json_parser import parse_unified_json

    print(f"Loading unified JSON {json_path}...", file=sys.stderr)

    try:
        # Validate version before parsing
        with open(json_path, "r") as f:
            raw_data = json_module.load(f)
        validate_input_version(raw_data)
    except json_module.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {json_path}: {e}", file=sys.stderr)
        sys.exit(1)

    index, calls_data = parse_unified_json(json_path)

    print(f"Mapping to SoT JSON...", file=sys.stderr)

    mapper = SCIPMapper(json_path, calls_data=calls_data, index=index)
    graph = mapper.map()

    indent = 2 if pretty else None
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


def cmd_map_kloc(kloc_path: Path, out_path: Path, pretty: bool):
    """Map a .kloc archive to SoT JSON."""
    print(f"Loading archive {kloc_path}...", file=sys.stderr)

    try:
        with KlocArchive.load(kloc_path) as archive:
            print(f"  Has calls data: {archive.has_calls_data}", file=sys.stderr)

            print(f"Mapping to SoT JSON...", file=sys.stderr)

            mapper = SCIPMapper(archive.scip_path, calls_data=archive.calls_data)
            graph = mapper.map()

            indent = 2 if pretty else None
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

    except ArchiveError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
