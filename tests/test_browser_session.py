import pytest
from playwright.async_api import Error

from sime_mcp.browser.session import open_diary, open_login
from sime_mcp.errors import AuthenticationRequiredError


class FakeLocator:
    async def count(self):
        return 1


class FakePage:
    url = "about:blank"

    def __init__(self, abort=False):
        self.abort = abort
        self.visited = None

    async def goto(self, url, **kwargs):
        self.visited = url
        if self.abort:
            raise Error("Page.goto: net::ERR_ABORTED")
        self.url = url

    async def wait_for_url(self, pattern, **kwargs):
        self.url = "https://agenda.sime.md/ords/r/agenda/main/public"

    def locator(self, selector):
        return FakeLocator()


class FakeContext:
    def __init__(self, page):
        self.pages = [page]


@pytest.mark.asyncio
async def test_login_opens_real_form_instead_of_diary_redirect():
    page = FakePage()
    await open_login(FakeContext(page))
    assert page.visited == "https://agenda.sime.md"
    assert page.url.endswith("/public")
    assert page.url != "about:blank"


@pytest.mark.asyncio
async def test_aborted_diary_navigation_requires_login():
    page = FakePage(abort=True)
    with pytest.raises(AuthenticationRequiredError):
        await open_diary(FakeContext(page))
