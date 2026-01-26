"""SCIP protobuf parsing utilities."""

from pathlib import Path
from typing import Optional
import re

from src import scip_pb2


def parse_scip_file(filepath: str | Path) -> scip_pb2.Index:
    """Parse a SCIP protobuf file and return the Index message."""
    with open(filepath, "rb") as f:
        data = f.read()

    index = scip_pb2.Index()
    index.ParseFromString(data)
    return index


def parse_symbol_string(symbol: str) -> dict:
    """Parse SCIP symbol string into components.

    SCIP symbol format: scheme manager package version descriptor
    Example: scip-php composer template/u-synxissetup 1.0.0.0 App/Entity/User#
    """
    parts = symbol.split(" ")
    if len(parts) >= 5:
        return {
            "scheme": parts[0],
            "manager": parts[1],
            "package": parts[2],
            "version": parts[3],
            "descriptor": " ".join(parts[4:]),
        }
    return {"raw": symbol}


def parse_range(range_list: list[int]) -> tuple[int, int, int, int]:
    """Parse SCIP range format to (start_line, start_col, end_line, end_col).

    SCIP range format:
    - 4 elements: [start_line, start_col, end_line, end_col]
    - 3 elements: [line, start_col, end_col] (same line)

    Lines are 0-based in SCIP.
    """
    if len(range_list) == 4:
        return (range_list[0], range_list[1], range_list[2], range_list[3])
    elif len(range_list) == 3:
        return (range_list[0], range_list[1], range_list[0], range_list[2])
    else:
        return (0, 0, 0, 0)


def extract_fqn_from_descriptor(descriptor: str) -> str:
    """Extract fully qualified name from SCIP descriptor.

    Examples:
    - 'App/Entity/User#' -> 'App\\Entity\\User'
    - 'App/Entity/User#getId().' -> 'App\\Entity\\User::getId()'
    - 'App/Entity/User#$name.' -> 'App\\Entity\\User::$name'
    - 'App/Entity/User#STATUS.' -> 'App\\Entity\\User::STATUS'
    - 'App/Entity/User#getId().($id)' -> 'App\\Entity\\User::getId()::$id'
    """
    # Remove trailing punctuation
    d = descriptor.rstrip(".")

    # Check for argument pattern: .($name) or .(name)
    arg_match = re.search(r'^(.+)\.\((\$?[a-zA-Z_][a-zA-Z0-9_]*)\)$', d)
    if arg_match:
        method_part = arg_match.group(1)
        arg_name = arg_match.group(2)
        method_fqn = extract_fqn_from_descriptor(method_part + ".")
        return f"{method_fqn}::{arg_name}"

    # Split by # to get class and member
    if "#" in d:
        parts = d.split("#", 1)
        class_part = parts[0].replace("/", "\\")

        if len(parts) > 1 and parts[1]:
            member = parts[1]
            # Check if it's a method (ends with ())
            if member.endswith("()"):
                return f"{class_part}::{member}"
            # Check if it's a property (starts with $)
            elif member.startswith("$"):
                return f"{class_part}::{member}"
            # Otherwise it's a const or enum case
            else:
                return f"{class_part}::{member}"
        return class_part

    # Standalone function or const
    return descriptor.replace("/", "\\").rstrip("#")


def extract_name_from_descriptor(descriptor: str) -> str:
    """Extract short name from SCIP descriptor.

    Examples:
    - 'App/Entity/User#' -> 'User'
    - 'App/Entity/User#getId().' -> 'getId'
    - 'App/Entity/User#$name.' -> '$name'
    - 'App/Entity/User#getId().($id)' -> '$id'
    """
    d = descriptor.rstrip(".")

    # Check for argument pattern: .($name) or .(name)
    arg_match = re.search(r'\.\((\$?[a-zA-Z_][a-zA-Z0-9_]*)\)$', d)
    if arg_match:
        return arg_match.group(1)

    if "#" in d:
        parts = d.split("#", 1)
        if len(parts) > 1 and parts[1]:
            member = parts[1].rstrip("()")
            return member
        # Class/interface/trait name
        return parts[0].split("/")[-1]

    # Standalone function or const
    return d.split("/")[-1].rstrip("#()")


def get_symbol_roles(roles_bitmask: int) -> list[str]:
    """Convert symbol roles bitmask to list of role names."""
    roles = []
    if roles_bitmask & 0x1:
        roles.append("Definition")
    if roles_bitmask & 0x2:
        roles.append("Import")
    if roles_bitmask & 0x4:
        roles.append("WriteAccess")
    if roles_bitmask & 0x8:
        roles.append("ReadAccess")
    if roles_bitmask & 0x10:
        roles.append("Generated")
    if roles_bitmask & 0x20:
        roles.append("Test")
    if roles_bitmask & 0x40:
        roles.append("ForwardDefinition")
    return roles if roles else ["Reference"]


def is_definition(roles_bitmask: int) -> bool:
    """Check if occurrence is a definition."""
    return bool(roles_bitmask & 0x1)


def infer_kind_from_documentation(docs: list[str]) -> Optional[str]:
    """Infer symbol kind from PHPDoc documentation.

    Returns: 'class', 'interface', 'trait', 'enum', or None
    """
    for doc in docs:
        doc_clean = doc.replace("```php", "").replace("```", "").strip().lower()
        doc_clean = " ".join(doc_clean.split())

        if doc_clean.startswith("interface "):
            return "interface"
        if doc_clean.startswith("trait "):
            return "trait"
        if doc_clean.startswith("enum "):
            return "enum"
        if doc_clean.startswith("class ") or doc_clean.startswith("abstract class ") or doc_clean.startswith("final class "):
            return "class"

    return None


def extract_extends_implements_from_docs(docs: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Extract extends, implements, and uses (traits) from PHPDoc.

    Returns: (extends_list, implements_list, uses_trait_list)
    """
    extends = []
    implements = []
    uses_traits = []

    for doc in docs:
        doc_clean = doc.replace("```php", "").replace("```", "").strip()
        doc_clean = " ".join(doc_clean.split())

        # Find extends
        extends_match = re.search(r'extends\s+\\?([A-Za-z0-9_\\]+)', doc_clean)
        if extends_match:
            extends.append(extends_match.group(1).replace("\\", "/"))

        # Find implements (can have multiple, comma-separated)
        implements_match = re.search(r'implements\s+(.+?)(?:\s*\{|$)', doc_clean, re.IGNORECASE)
        if implements_match:
            for iface in implements_match.group(1).split(","):
                iface = iface.strip().replace("\\", "/").lstrip("/")
                iface = re.sub(r'[`\s]+$', '', iface)
                if iface and not iface.startswith("{"):
                    implements.append(iface)

        # Find trait usage (use TraitName;)
        use_match = re.findall(r'use\s+\\?([A-Za-z0-9_\\]+)', doc_clean)
        for trait in use_match:
            uses_traits.append(trait.replace("\\", "/"))

    return extends, implements, uses_traits


def get_parent_symbol(symbol: str) -> Optional[str]:
    """Get the parent symbol for containment edge.

    Examples:
    - 'scip-php ... App/Entity/User#getId().' -> 'scip-php ... App/Entity/User#'
    - 'scip-php ... App/Entity/User#' -> None (contained by file, not symbol)
    - 'scip-php ... App/Entity/User#$name.' -> 'scip-php ... App/Entity/User#'
    - 'scip-php ... App/Entity/User#getId().($id)' -> 'scip-php ... App/Entity/User#getId().'
    """
    parts = symbol.split(" ")
    if len(parts) < 5:
        return None

    descriptor = parts[-1]

    # Argument inside a method/function: .($name) pattern
    arg_match = re.search(r'^(.+)\.\(\$?[a-zA-Z_][a-zA-Z0-9_]*\)$', descriptor)
    if arg_match:
        parent_descriptor = arg_match.group(1) + "."
        return " ".join(parts[:-1] + [parent_descriptor])

    # Method, property, const inside a class
    if "#" in descriptor:
        hash_idx = descriptor.index("#")
        suffix = descriptor[hash_idx + 1:]

        # If there's something after #, the parent is the class
        if suffix and suffix != "#":
            parent_descriptor = descriptor[:hash_idx + 1]
            return " ".join(parts[:-1] + [parent_descriptor])

    # Top-level symbols (classes, functions) are contained by file
    return None
