from contextlib import asynccontextmanager

import pytest

from sime_mcp import cli
from sime_mcp.config import Settings


class Frame:
    def locator(self, selector):
        return self

    async def count(self):
        return 1


class Page:
    url = "https://agenda.sime.md/ords/r/agenda/main/main-page?session=synthetic"
    frames = [Frame()]

    def is_closed(self):
        return False


class Context:
    pages = [Page()]


@pytest.mark.asyncio
async def test_login_saves_visible_diary_without_reopening_it(monkeypatch, tmp_path, capsys):
    @asynccontextmanager
    async def fake_browser(settings, headless):
        yield Context()

    async def fake_open_login(context):
        return context.pages[0]

    async def fail_if_reopened(*args, **kwargs):
        raise AssertionError("login must not navigate away from the visible diary")

    saved = []

    async def fake_save(context, page, settings):
        saved.append(page.url)

    monkeypatch.setattr(cli, "browser_context", fake_browser)
    monkeypatch.setattr(cli, "open_login", fake_open_login)
    monkeypatch.setattr(cli, "open_diary", fail_if_reopened)
    monkeypatch.setattr(cli, "save_authenticated_session", fake_save)
    monkeypatch.setattr("builtins.input", lambda: "")
    await cli._login(Settings(data_dir=tmp_path))
    assert saved == [Context.pages[0].url]
    assert "session=synthetic" not in capsys.readouterr().out
