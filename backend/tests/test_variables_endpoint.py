"""Tests verifying /api/variables returns grouped, labeled variables from domain config.

Validates that:
1. The config loader can parse air.yaml and return all expected variables
2. Variables are grouped by their configured categories
3. Rendering info (colormap, contourInterval, fillLevels) is present
4. The API endpoint integrates domain config metadata into responses
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.config.loader import (
    DomainConfig,
    VariableConfig,
    get_domain_config,
    get_domain_config_safe,
)
from backend.app.main import app

# --------------------------------------------------------------------------
# Unit tests for config loader
# --------------------------------------------------------------------------


class TestConfigLoader:
    """Tests for the domain configuration loader."""

    def setup_method(self):
        """Clear the lru_cache before each test to ensure fresh loads."""
        get_domain_config.cache_clear()

    def test_load_air_config_succeeds(self):
        """Config loader can load air.yaml without errors."""
        config = get_domain_config("air")
        assert config is not None
        assert isinstance(config, DomainConfig)

    def test_air_product_metadata(self):
        """Air config has correct product name and ID."""
        config = get_domain_config("air")
        assert config.product.name == "GEFS-Aerosol"
        assert config.product.id == "air"

    def test_air_config_has_expected_categories(self):
        """Air config defines the 5 expected categories in order."""
        config = get_domain_config("air")
        expected_categories = [
            "Optical Depth",
            "Scattering Optical Depth",
            "Single Scattering Albedo",
            "Asymmetry",
            "Column Mass Density",
        ]
        assert config.categories == expected_categories

    def test_air_config_has_variables(self):
        """Air config defines 25+ variables."""
        config = get_domain_config("air")
        assert len(config.variables) >= 25

    def test_variable_has_required_fields(self):
        """Each variable has shortName, fullName, units, category."""
        config = get_domain_config("air")
        for name, var in config.variables.items():
            assert isinstance(var, VariableConfig), f"Variable {name} not a VariableConfig"
            assert var.shortName, f"Variable {name} missing shortName"
            assert var.fullName, f"Variable {name} missing fullName"
            assert var.category, f"Variable {name} missing category"
            # units can be empty string, but must be present
            assert var.units is not None, f"Variable {name} missing units"

    def test_variable_rendering_config(self):
        """Each variable has rendering config with colormap, contourInterval, fillLevels."""
        config = get_domain_config("air")
        for name, var in config.variables.items():
            assert var.rendering is not None, f"Variable {name} missing rendering"
            assert var.rendering.colormap, f"Variable {name} missing colormap"
            assert var.rendering.contourInterval > 0, f"Variable {name} has invalid contourInterval"
            assert isinstance(
                var.rendering.fillLevels, list
            ), f"Variable {name} fillLevels is not a list"
            assert len(var.rendering.fillLevels) > 0, f"Variable {name} has empty fillLevels"

    def test_variables_grouped_by_category(self):
        """get_variables_by_category returns vars grouped under correct categories."""
        config = get_domain_config("air")
        grouped = config.get_variables_by_category()

        # All 5 categories should be present
        for cat in config.categories:
            assert cat in grouped, f"Category '{cat}' missing from grouped output"
            assert len(grouped[cat]) > 0, f"Category '{cat}' has no variables"

        # Check category ordering matches config
        category_keys = list(grouped.keys())
        for i, cat in enumerate(config.categories):
            assert (
                category_keys[i] == cat
            ), f"Category order mismatch at index {i}: expected '{cat}', got '{category_keys[i]}'"

    def test_specific_variable_lookup(self):
        """get_variable returns correct metadata for totAOD550."""
        config = get_domain_config("air")
        var = config.get_variable("totAOD550")
        assert var is not None
        assert var.shortName == "totAOD550"
        assert var.fullName == "Total Aerosol Optical Depth at 550nm"
        assert var.units == "Numeric"
        assert var.category == "Optical Depth"
        assert var.rendering.colormap == "afmhot_r"
        assert var.rendering.contourInterval == 0.1
        assert var.rendering.fillLevels == [
            0.05,
            0.1,
            0.2,
            0.3,
            0.5,
            0.6,
            0.7,
            0.8,
            0.9,
            1.0,
            1.25,
            1.5,
            2.0,
        ]

    def test_nonexistent_product_raises(self):
        """Loading a nonexistent product raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            get_domain_config("nonexistent_product_xyz")

    def test_safe_loader_returns_none_for_missing(self):
        """get_domain_config_safe returns None for missing products."""
        get_domain_config_safe.cache_clear() if hasattr(
            get_domain_config_safe, "cache_clear"
        ) else None
        result = get_domain_config_safe("nonexistent_product_xyz")
        assert result is None


# --------------------------------------------------------------------------
# Integration tests for /api/variables endpoint
# --------------------------------------------------------------------------


def _make_mock_variables(product: str = "air") -> list[dict[str, Any]]:
    """Build a mock variable list matching what FieldSelector.get_variables returns.

    Uses the real domain config to produce realistic test data.
    """
    config = get_domain_config(product)
    variables: list[dict[str, Any]] = []

    for name, var_config in config.variables.items():
        variables.append(
            {
                "name": name,
                "shortName": var_config.shortName,
                "fullName": var_config.fullName,
                "units": var_config.units,
                "category": var_config.category,
                "rendering": {
                    "colormap": var_config.rendering.colormap,
                    "contourInterval": var_config.rendering.contourInterval,
                    "fillLevels": var_config.rendering.fillLevels,
                },
            }
        )

    # Sort by category order, then shortName (mimicking FieldSelector behavior)
    if config.categories:
        cat_order = {cat: idx for idx, cat in enumerate(config.categories)}
        default_order = len(cat_order)
        variables.sort(
            key=lambda v: (
                cat_order.get(v["category"], default_order),
                v["shortName"],
            )
        )

    return variables


@pytest.mark.anyio
class TestVariablesEndpoint:
    """Integration tests for the GET /api/variables endpoint."""

    async def test_variables_endpoint_returns_grouped_variables(self):
        """The endpoint returns variables with category grouping from config."""
        mock_variables = _make_mock_variables("air")

        mock_selector = MagicMock()
        mock_selector.get_variables.return_value = mock_variables

        with patch(
            "backend.app.data.product_registry.get_field_selector",
            return_value=mock_selector,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/variables",
                    params={"product": "air", "date": "20240101", "run": "00"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["product"] == "air"
        assert data["date"] == "20240101"
        assert data["run"] == "00"
        assert len(data["variables"]) >= 25

    async def test_variables_have_rendering_info(self):
        """Each variable in the response includes rendering configuration."""
        mock_variables = _make_mock_variables("air")

        mock_selector = MagicMock()
        mock_selector.get_variables.return_value = mock_variables

        with patch(
            "backend.app.data.product_registry.get_field_selector",
            return_value=mock_selector,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/variables",
                    params={"product": "air", "date": "20240101", "run": "00"},
                )

        data = response.json()
        for var in data["variables"]:
            assert "rendering" in var, f"Variable {var['name']} missing rendering"
            rendering = var["rendering"]
            assert "colormap" in rendering
            assert "contourInterval" in rendering
            assert "fillLevels" in rendering
            assert isinstance(rendering["fillLevels"], list)
            assert len(rendering["fillLevels"]) > 0

    async def test_variables_sorted_by_category_order(self):
        """Variables are returned ordered by the config's category list."""
        mock_variables = _make_mock_variables("air")

        mock_selector = MagicMock()
        mock_selector.get_variables.return_value = mock_variables

        with patch(
            "backend.app.data.product_registry.get_field_selector",
            return_value=mock_selector,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/variables",
                    params={"product": "air", "date": "20240101", "run": "00"},
                )

        data = response.json()
        variables = data["variables"]

        expected_category_order = [
            "Optical Depth",
            "Scattering Optical Depth",
            "Single Scattering Albedo",
            "Asymmetry",
            "Column Mass Density",
        ]

        # Extract unique categories in order of appearance
        seen_categories: list[str] = []
        for var in variables:
            cat = var["category"]
            if cat not in seen_categories:
                seen_categories.append(cat)

        assert seen_categories == expected_category_order

    async def test_variables_have_required_metadata_fields(self):
        """Each variable has name, shortName, fullName, units, category."""
        mock_variables = _make_mock_variables("air")

        mock_selector = MagicMock()
        mock_selector.get_variables.return_value = mock_variables

        with patch(
            "backend.app.data.product_registry.get_field_selector",
            return_value=mock_selector,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/variables",
                    params={"product": "air", "date": "20240101", "run": "00"},
                )

        data = response.json()
        for var in data["variables"]:
            assert "name" in var
            assert "shortName" in var
            assert "fullName" in var
            assert "units" in var
            assert "category" in var
            # All fields should be non-empty strings
            assert var["name"]
            assert var["shortName"]
            assert var["fullName"]
            assert var["category"]

    async def test_invalid_product_returns_404(self):
        """Requesting variables for an unknown product returns 404."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/variables",
                params={"product": "bogus", "date": "20240101", "run": "00"},
            )
        assert response.status_code == 404

    async def test_invalid_date_format_returns_422(self):
        """Requesting variables with invalid date format returns 422."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/variables",
                params={"product": "air", "date": "not-a-date", "run": "00"},
            )
        assert response.status_code == 422
