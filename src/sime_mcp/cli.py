"""User initiated local command line interface."""

import argparse
import asyncio
import json
import shutil
import sys
from datetime import date
from urllib.parse import urlparse

from sime_mcp.browser.calendar_capture import CALENDAR_SELECTOR, safe_calendar_structure
from sime_mcp.browser.session import (
    browser_context,
    open_diary,
    open_login,
    save_authenticated_session,
)
from sime_mcp.config import Settings
from sime_mcp.errors import AuthenticationRequiredError, SimeError
from sime_mcp.logging_utils import configure_logging
from sime_mcp.mcp_server import main as run_mcp
from sime_mcp.services.calendar import CalendarService
from sime_mcp.services.grades import GradeService
from sime_mcp.services.homework import HomeworkService
from sime_mcp.services.subjects import SubjectService
from sime_mcp.storage.database import CalendarStore


def _json(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


async def _has_calendar(page) -> bool:
    for frame in page.frames:
        if await frame.locator(CALENDAR_SELECTOR).count():
            return True
    return False


async def _login(settings: Settings) -> None:
    async with browser_context(settings, headless=False) as context:
        await open_login(context)
        print(
            "In Chromium, choose your account role and complete SIME login. "
            "When the diary is visible, press Enter here."
        )
        await asyncio.to_thread(input)
        diary = None
        for _ in range(5):
            for page in reversed(context.pages):
                if page.is_closed():
                    continue
                if await _has_calendar(page):
                    diary = page
                    break
            if diary:
                break
            await asyncio.sleep(1)
        if diary is None:
            for page in reversed(context.pages):
                parsed = urlparse(page.url)
                if (
                    parsed.hostname == "agenda.sime.md"
                    and parsed.path
                    not in {"/ords/r/agenda/main/public", "/ords/r/agenda/main/login_desktop"}
                    and not await page.locator("input[type='password']").count()
                ):
                    diary = page
                    break
        if diary is None:
            print("Diary page was not detected. The browser session was not marked as verified.")
            return
        await save_authenticated_session(context, diary, settings)
        print("SIME diary session saved locally.")
        if not await _has_calendar(diary):
            print("Calendar controls were not detected; run `sime discover` for safe diagnostics.")


async def _check_auth(settings: Settings) -> None:
    async with browser_context(settings) as context:
        try:
            page = await open_diary(context, settings)
            visible = await _has_calendar(page)
        except AuthenticationRequiredError:
            visible = False
        _json(
            {
                "calendar_visible": visible,
                "authentication": "likely_valid" if visible else "unverified",
            }
        )


async def _discover(settings: Settings) -> None:
    async with browser_context(settings) as context:
        page = await open_diary(context, settings)
        _json(await safe_calendar_structure(page))


async def _run(args: argparse.Namespace, settings: Settings) -> None:
    calendar = CalendarService(settings)
    if args.command == "login":
        await _login(settings)
    elif args.command == "check-auth":
        await _check_auth(settings)
    elif args.command == "discover":
        await _discover(settings)
    elif args.command == "fetch-calendar":
        result = await calendar.get_calendar_month(args.year, args.month, refresh=args.refresh)
        _json(result.model_dump(mode="json"))
    elif args.command == "homework":
        result = await HomeworkService(calendar).get_homework(
            date.fromisoformat(args.start), date.fromisoformat(args.end)
        )
        _json([item.model_dump(mode="json") for item in result])
    elif args.command == "grades":
        result = await GradeService(calendar).get_grades(
            date.fromisoformat(args.start), date.fromisoformat(args.end)
        )
        _json([item.model_dump(mode="json") for item in result])
    elif args.command == "subjects":
        result = await SubjectService(calendar).get_subjects(args.year, args.month)
        _json([item.model_dump(mode="json") for item in result])
    elif args.command == "changes":
        if not settings.cache_enabled:
            print("Caching is disabled. Set SIME_CACHE_ENABLED=true to record changes.")
        else:
            _json(CalendarStore(settings.database_path).changes())


def _confirm(message: str, yes: bool) -> bool:
    return yes or input(f"{message} Type DELETE to continue: ").strip() == "DELETE"


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(prog="sime", description="Read-only SIME diary tools")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("login", help="Open isolated Chromium for manual login")
    sub.add_parser("check-auth")
    sub.add_parser("discover", help="Print sanitized calendar control structure")
    fetch = sub.add_parser("fetch-calendar")
    fetch.add_argument("--year", type=int, required=True)
    fetch.add_argument("--month", type=int, required=True)
    fetch.add_argument("--refresh", action="store_true")
    homework = sub.add_parser("homework")
    homework.add_argument("--from", dest="start", required=True)
    homework.add_argument("--to", dest="end", required=True)
    grades = sub.add_parser("grades")
    grades.add_argument("--from", dest="start", required=True)
    grades.add_argument("--to", dest="end", required=True)
    subjects = sub.add_parser("subjects")
    subjects.add_argument("--year", type=int)
    subjects.add_argument("--month", type=int)
    sub.add_parser("changes")
    sub.add_parser("mcp")
    clear = sub.add_parser("clear-cache")
    clear.add_argument("--yes", action="store_true")
    logout = sub.add_parser("logout")
    logout.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    settings = Settings.from_env()
    try:
        if args.command == "mcp":
            run_mcp()
        elif args.command == "clear-cache":
            if _confirm("Delete all cached school data?", args.yes):
                if settings.database_path.exists():
                    settings.database_path.unlink()
                print("Cached data deleted.")
        elif args.command == "logout":
            if _confirm("Delete the isolated SIME browser session?", args.yes):
                if settings.browser_profile.exists():
                    if not (settings.browser_profile / ".sime-mcp-profile").is_file():
                        raise SimeError(
                            "Profile was not created by SIME MCP; refusing to delete it."
                        )
                    shutil.rmtree(settings.browser_profile)
                print("Browser session deleted.")
        else:
            asyncio.run(_run(args, settings))
    except (SimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
