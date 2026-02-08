"""Unit tests for _classify_symbol — ISSUE-02 FUNCTION classification bug fix."""

import pytest
from unittest.mock import patch

from src.mapper import SCIPMapper
from src.models import NodeKind


@pytest.fixture
def mapper():
    """Create a SCIPMapper with mocked init (no SCIP file needed)."""
    with patch.object(SCIPMapper, '__init__', lambda self, *a, **kw: None):
        m = SCIPMapper.__new__(SCIPMapper)
        m.symbol_metadata = {}
        yield m


class TestFunctionVsMethod:
    """Verify standalone functions are classified as FUNCTION, not METHOD."""

    def test_standalone_function_classified_as_function(self, mapper):
        """Standalone PHP function (no # in descriptor) should be FUNCTION."""
        symbol = "scip-php composer pkg 1.0.0 App/Helper/formatPrice()."
        descriptor = "App/Helper/formatPrice()."
        kind = mapper._classify_symbol(symbol, descriptor, [])
        assert kind == NodeKind.FUNCTION

    def test_class_method_classified_as_method(self, mapper):
        """Class method (has # in descriptor) should be METHOD."""
        symbol = "scip-php composer pkg 1.0.0 App/Entity/Order#getId()."
        descriptor = "App/Entity/Order#getId()."
        kind = mapper._classify_symbol(symbol, descriptor, [])
        assert kind == NodeKind.METHOD

    def test_constructor_classified_as_method(self, mapper):
        """Constructor __construct (has # in descriptor) should be METHOD."""
        symbol = "scip-php composer pkg 1.0.0 App/Entity/Order#__construct()."
        descriptor = "App/Entity/Order#__construct()."
        kind = mapper._classify_symbol(symbol, descriptor, [])
        assert kind == NodeKind.METHOD

    def test_namespaced_function_classified_as_function(self, mapper):
        """Namespaced standalone function (no #) should be FUNCTION."""
        symbol = "scip-php composer pkg 1.0.0 App/Helpers/array_get()."
        descriptor = "App/Helpers/array_get()."
        kind = mapper._classify_symbol(symbol, descriptor, [])
        assert kind == NodeKind.FUNCTION

    def test_interface_method_classified_as_method(self, mapper):
        """Interface method (has # in descriptor) should be METHOD."""
        symbol = "scip-php composer pkg 1.0.0 App/Repository/OrderRepositoryInterface#findById()."
        descriptor = "App/Repository/OrderRepositoryInterface#findById()."
        kind = mapper._classify_symbol(symbol, descriptor, [])
        assert kind == NodeKind.METHOD
