import os
from unittest.mock import patch

import pytest
from spielerplus_mcp.server import feeds


def test_configured_teams():
    with patch.dict(os.environ, {
        "SPIELERPLUS_CALENDARS":
        '{"Test":"https://www.spielerplus.de/events/ics?t=EXAMPLE&u=EXAMPLE"}'
    }):
        assert "Test" in feeds()


def test_invalid_config_rejected():
    with patch.dict(os.environ, {"SPIELERPLUS_CALENDARS": "[]"}):
        with pytest.raises(ValueError):
            feeds()
