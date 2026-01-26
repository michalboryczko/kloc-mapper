"""Tests for parser module."""

import pytest
from src.parser import (
    parse_symbol_string,
    parse_range,
    extract_fqn_from_descriptor,
    extract_name_from_descriptor,
    get_symbol_roles,
    is_definition,
    infer_kind_from_documentation,
    get_parent_symbol,
)


class TestParseSymbolString:
    def test_full_symbol(self):
        symbol = "scip-php composer template/pkg 1.0.0 App/Entity/User#"
        result = parse_symbol_string(symbol)
        assert result["scheme"] == "scip-php"
        assert result["manager"] == "composer"
        assert result["package"] == "template/pkg"
        assert result["version"] == "1.0.0"
        assert result["descriptor"] == "App/Entity/User#"

    def test_short_symbol(self):
        symbol = "short"
        result = parse_symbol_string(symbol)
        assert result == {"raw": "short"}


class TestParseRange:
    def test_four_elements(self):
        result = parse_range([10, 5, 12, 20])
        assert result == (10, 5, 12, 20)

    def test_three_elements(self):
        result = parse_range([10, 5, 20])
        assert result == (10, 5, 10, 20)

    def test_empty(self):
        result = parse_range([])
        assert result == (0, 0, 0, 0)


class TestExtractFqnFromDescriptor:
    def test_class(self):
        result = extract_fqn_from_descriptor("App/Entity/User#")
        assert result == "App\\Entity\\User"

    def test_method(self):
        result = extract_fqn_from_descriptor("App/Entity/User#getId().")
        assert result == "App\\Entity\\User::getId()"

    def test_property(self):
        result = extract_fqn_from_descriptor("App/Entity/User#$name.")
        assert result == "App\\Entity\\User::$name"

    def test_const(self):
        result = extract_fqn_from_descriptor("App/Entity/User#STATUS.")
        assert result == "App\\Entity\\User::STATUS"

    def test_argument(self):
        result = extract_fqn_from_descriptor("App/Entity/User#getId().($id)")
        assert result == "App\\Entity\\User::getId()::$id"


class TestExtractNameFromDescriptor:
    def test_class(self):
        result = extract_name_from_descriptor("App/Entity/User#")
        assert result == "User"

    def test_method(self):
        result = extract_name_from_descriptor("App/Entity/User#getId().")
        assert result == "getId"

    def test_property(self):
        result = extract_name_from_descriptor("App/Entity/User#$name.")
        assert result == "$name"

    def test_argument(self):
        result = extract_name_from_descriptor("App/Entity/User#getId().($id)")
        assert result == "$id"


class TestGetSymbolRoles:
    def test_definition(self):
        result = get_symbol_roles(0x1)
        assert "Definition" in result

    def test_reference(self):
        result = get_symbol_roles(0x0)
        assert result == ["Reference"]

    def test_multiple_roles(self):
        result = get_symbol_roles(0x5)  # Definition + WriteAccess
        assert "Definition" in result
        assert "WriteAccess" in result


class TestIsDefinition:
    def test_is_definition(self):
        assert is_definition(0x1) is True
        assert is_definition(0x5) is True

    def test_not_definition(self):
        assert is_definition(0x0) is False
        assert is_definition(0x8) is False


class TestInferKindFromDocumentation:
    def test_class(self):
        docs = ["```php\nclass Foo\n```"]
        assert infer_kind_from_documentation(docs) == "class"

    def test_interface(self):
        docs = ["```php\ninterface IFoo\n```"]
        assert infer_kind_from_documentation(docs) == "interface"

    def test_trait(self):
        docs = ["```php\ntrait MyTrait\n```"]
        assert infer_kind_from_documentation(docs) == "trait"

    def test_enum(self):
        docs = ["```php\nenum Status\n```"]
        assert infer_kind_from_documentation(docs) == "enum"

    def test_unknown(self):
        docs = ["```php\nfunction foo()\n```"]
        assert infer_kind_from_documentation(docs) is None


class TestGetParentSymbol:
    def test_method_parent_is_class(self):
        symbol = "scip-php composer pkg 1.0.0 App/Entity/User#getId()."
        result = get_parent_symbol(symbol)
        assert result == "scip-php composer pkg 1.0.0 App/Entity/User#"

    def test_property_parent_is_class(self):
        symbol = "scip-php composer pkg 1.0.0 App/Entity/User#$name."
        result = get_parent_symbol(symbol)
        assert result == "scip-php composer pkg 1.0.0 App/Entity/User#"

    def test_argument_parent_is_method(self):
        symbol = "scip-php composer pkg 1.0.0 App/Entity/User#getId().($id)"
        result = get_parent_symbol(symbol)
        assert result == "scip-php composer pkg 1.0.0 App/Entity/User#getId()."

    def test_class_no_parent(self):
        symbol = "scip-php composer pkg 1.0.0 App/Entity/User#"
        result = get_parent_symbol(symbol)
        assert result is None
