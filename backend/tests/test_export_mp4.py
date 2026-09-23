import pytest
from unittest.mock import MagicMock, patch
import numpy as np
from httpx import ASGITransport, AsyncClient

from backend.app.main import app
from backend.app.api.export_mp4 import _render_frame


def test_render_frame():
    field = np.ones((10, 10), dtype=np.float32)
    lons_1d = np.linspace(-180, 180, 10)
    lats_1d = np.linspace(80, -80, 10)
    fill_levels = [0.0, 0.5, 1.0]

    img = _render_frame(
        field=field,
        lons_1d=lons_1d,
        lats_1d=lats_1d,
        fill_levels=fill_levels,
        colormap_name="turbo",
        fhr=0,
        variable="totAOD550",
    )
    assert img.size == (1024, 1024)
    assert img.mode == "RGB"


@pytest.mark.anyio
async def test_export_mp4_endpoint():
    with patch("backend.app.api.export_mp4.get_field_selector") as mock_get_selector, \
         patch("backend.app.api.export_mp4.get_domain_config_safe") as mock_get_config:

        mock_selector = MagicMock()
        mock_get_selector.return_value = mock_selector
        mock_selector.get_forecast_hours.return_value = [{"fhr": 0}, {"fhr": 3}]

        mock_coords = MagicMock()
        mock_coords.lons = np.linspace(-180, 180, 10)
        mock_coords.lats = np.linspace(80, -80, 10)
        mock_selector.get_coordinates.return_value = mock_coords
        mock_selector.select.return_value = np.ones((10, 10), dtype=np.float32)

        mock_var_config = MagicMock()
        mock_var_config.rendering.fillLevels = [0.0, 0.5, 1.0]
        mock_var_config.rendering.colormap = "turbo"
        mock_domain_config = MagicMock()
        mock_domain_config.get_variable.return_value = mock_var_config
        mock_get_config.return_value = mock_domain_config

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/export-mp4?product=air&date=20250101&run=00&variable=totAOD550")
            assert response.status_code == 200
            assert response.headers["content-type"] == "video/mp4"
            assert 'attachment; filename="totAOD550_20250101_animation.mp4"' in response.headers["content-disposition"]
            assert len(response.content) > 0
