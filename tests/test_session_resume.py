import json
import stat

import pytest

from sime_mcp.browser.session import resume_diary_url, save_authenticated_session
from sime_mcp.config import Settings


class FakePage:
    url = "https://agenda.sime.md/ords/r/agenda/main/main-page?session=private-value"


class FakeContext:
    async def storage_state(self):
        return {
            "cookies": [
                {"name": "sime", "value": "secret", "domain": "agenda.sime.md"},
                {"name": "other", "value": "discard", "domain": "example.net"},
            ],
            "origins": [],
        }


@pytest.mark.asyncio
async def test_resume_state_stays_private_and_site_scoped(tmp_path):
    settings = Settings(data_dir=tmp_path)
    settings.browser_profile.mkdir()
    await save_authenticated_session(FakeContext(), FakePage(), settings)
    path = settings.browser_profile / ".sime-resume.json"
    state = json.loads(path.read_text())
    assert len(state["cookies"]) == 1
    assert state["cookies"][0]["name"] == "sime"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert resume_diary_url(settings) == FakePage.url
