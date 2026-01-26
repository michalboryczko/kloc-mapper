"""CLI entry point for kloc-mapper."""

import argparse
import sys
from pathlib import Path

from src.mapper import SCIPMapper


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="kloc-mapper",
        description="Map SCIP index to Source-of-Truth JSON"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # map command
    map_parser = subparsers.add_parser("map", help="Map SCIP to SoT JSON")
    map_parser.add_argument(
        "--scip", "-s",
        required=True,
        help="Path to SCIP index file"
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


def cmd_map(args):
    """Execute the map command."""
    scip_path = Path(args.scip)
    out_path = Path(args.out)

    if not scip_path.exists():
        print(f"Error: SCIP file not found: {scip_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Mapping {scip_path} to SoT JSON...", file=sys.stderr)

    mapper = SCIPMapper(scip_path)
    graph = mapper.map()

    indent = 2 if args.pretty else None
    json_output = graph.to_json(indent=indent)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        f.write(json_output)

    print(f"Written to {out_path}", file=sys.stderr)
    print(f"  Nodes: {len(graph.nodes)}", file=sys.stderr)
    print(f"  Edges: {len(graph.edges)}", file=sys.stderr)


if __name__ == "__main__":
    main()
