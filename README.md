# SIME MCP

Local, read-only access to an **authorized** [SIME electronic diary](https://agenda.sime.md/) through a Python CLI and STDIO MCP server. The browser performs normal SIME navigation; the application observes calendar responses and extracts lessons, homework, and grades shown on calendar cards. It does not manage passwords or call an external AI API.

## Status and limits

The parser, services, cache, CLI, and MCP tools are implemented and covered by synthetic tests. Calendar and homework retrieval through the CLI and local MCP client have also been verified with an authorized SIME session. Calendar grades were inspected in an authorized session. The site's Oracle APEX markup and AJAX behavior are undocumented and may change. A separate grades page and attendance are not supported. The subject list reflects only the current month unless a different month is supplied in the CLI.

Homework belongs to the **lesson date**. SIME's calendar event does not establish a due date, so `due_date` is `null`. Missing homework is also `null`, not a claim that no work was assigned.

Grades are copied as text from the calendar card's `.lesson-grade` elements. The date is the associated lesson date; the integration does not infer when a mark was awarded or reinterpret unusual values. Lessons without a displayed grade have an empty `grades` list.

SIME can return duplicate cards for one lesson with different details. The parser merges their displayed grades, homework, teacher, and room instead of discarding the later card.

## Architecture

```text
SIME website in isolated Playwright Chromium
  -> observe the site's calendar response
  -> BeautifulSoup / Pydantic normalization
  -> calendar, homework, grade, subject services
  -> CLI or local STDIO MCP tools
  -> optional private SQLite snapshots
```

The code never reconstructs authenticated AJAX requests. The response listener checks HTTPS origin, endpoint shape, POST method, `x01=GET`, requested date coverage, and event-array structure. SIME's month view can request days from adjacent months; the service filters normalized lessons to the requested month. Original event JavaScript URLs and raw HTML are discarded during parsing. After a successful manual login, a private resume file inside the isolated browser profile stores the current diary page URL and SIME cookies so the next local process can reopen it; neither is logged or returned by MCP.

## Install on macOS Apple Silicon

Install Python 3.12 or newer and `uv` (for example with Homebrew):

```sh
brew install python@3.12 uv
cd /path/to/SIME
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e '.[dev]'
.venv/bin/playwright install chromium
```

`pip` also works: `python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev]'`. The Chromium download is required once. The browser profile and optional cache default to `~/.local/share/sime-mcp`, outside the repository. They are made private to the local user where POSIX permissions apply.

Copy `.env.example` to `.env` only if you need to change defaults. Key settings:

| Setting | Default | Meaning |
| --- | --- | --- |
| `SIME_DATA_DIR` | `~/.local/share/sime-mcp` | Private data directory |
| `SIME_PROFILE_DIR` | `SIME_DATA_DIR/browser-profile` | Isolated Chromium profile |
| `SIME_CACHE_ENABLED` | `false` | Store normalized lessons and change history in SQLite |
| `SIME_CACHE_TTL_SECONDS` | `900` | Fresh cache lifetime |
| `SIME_BROWSER_HEADLESS` | `true` | Headless fetches after manual login |
| `SIME_BROWSER_TIMEOUT_MS` | `30000` | UI/response timeout |

## First login and calendar fetch

```sh
.venv/bin/sime login
```

An isolated Chromium window opens at SIME's public page. Choose your account role there and use the site's login dialog. When the diary is visible, return to the terminal and press Enter. The app never asks for your password. Then run:

```sh
.venv/bin/sime check-auth
.venv/bin/sime fetch-calendar --year 2026 --month 10
.venv/bin/sime homework --from 2026-10-10 --to 2026-10-17
.venv/bin/sime grades --from 2026-10-01 --to 2026-10-31
.venv/bin/sime subjects
```

`check-auth` reports only whether a calendar is visible; this is a heuristic, not a proof of authorization. If the website changes layout or the calendar cannot be found, run `.venv/bin/sime discover`. It prints only calendar CSS classes and toolbar button attributes, without page text or account data. If discovery indicates a different layout, update the selectors in `browser/calendar_capture.py` before fetching again.

If a session expires, repeat `sime login`. Only one process should use the isolated profile at a time. The profile does **not** overlap your everyday Chrome profile.

## MCP server and local test client

Run `.venv/bin/sime mcp` as a local STDIO MCP server. It waits silently for an MCP client; starting it in a terminal does not open a window or print a menu. Press Ctrl-C to stop a manually started server.

To use it in the ChatGPT/Codex desktop app on this Mac, register the executable once (replace the path if you move the repository):

```sh
codex mcp add sime -- /absolute/path/to/SIME/.venv/bin/sime mcp
codex mcp get sime
```

Restart the desktop app, type `/mcp` in the composer to check that `sime` is connected, then ask for a specific diary task such as "Use SIME to show my schedule for 2026-10-12" or "Use SIME to list homework from 2026-10-12 to 2026-10-18." The app starts the server when needed; a separate terminal process is unnecessary. Manual SIME login must already be valid (`.venv/bin/sime check-auth`). This local STDIO server is available to the desktop app on the same Mac, not to ChatGPT web.

The read-only tools are:

- `get_schedule(start_date, end_date)`
- `get_homework(start_date, end_date)`
- `get_grades(start_date, end_date)`
- `get_subjects()`
- `get_today_schedule()`
- `get_week_schedule(week_start)`

Dates are ISO `YYYY-MM-DD`; ranges are inclusive and limited to 12 calendar months. Today uses `Europe/Chisinau`. Tool output contains structured lesson, homework, or grade objects without cookies, session URLs, event HTML, or student IDs.

For a quick local protocol check after installation:

```sh
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
```

The MCP tests invoke the registered tools with a mocked calendar service; they need no school account. A live fetch is deliberately separate and user initiated.

## Cache and privacy

Caching is opt in. When enabled, SQLite stores normalized lessons (including displayed grades), retrieval times, and changes between month snapshots. It stores no cookies or raw network responses. Slot matching uses lesson date plus lesson number, falling back to start time. A room, teacher, subject, time, homework, or grade edit on the same slot is an update. A renumbered or moved lesson may appear as a removal and addition. A missing event from one snapshot may reflect transient site data, so review changes before treating them as authoritative.

```sh
.venv/bin/sime changes
.venv/bin/sime clear-cache
.venv/bin/sime logout
```

`clear-cache` deletes SQLite educational data after confirmation. `logout` deletes the isolated browser profile, including its private resume file, after confirmation. To delete both noninteractively, pass `--yes` to each command. Do not run these while another `sime` process is using the profile. The profile contains sensitive authentication state; do not back it up or upload it. No telemetry, analytics, tunnel, or external LLM request is configured.

## Troubleshooting

- **Browser unavailable:** run `.venv/bin/playwright install chromium`, close any other SIME Chromium instance, then retry.
- **Login required or calendar missing:** run `sime login`, navigate to the diary calendar in the browser, and retry. `sime discover` provides sanitized selector clues.
- **No matching calendar response:** the calendar may use a changed date range or controls. Inspect it manually in browser developer tools and adjust only the browser capture layer. Never copy session identifiers into source code or bug reports.
- **SIME unavailable:** retry later. A fresh opt-in cache can serve requests within its configured TTL; expired data triggers a live fetch.

## Planned work and ChatGPT integration

The calendar tool includes only grades displayed on lesson cards. A separate grades page and attendance require authorized inspection of their UI and browser behavior before implementation.

The current server uses local STDIO. A remote ChatGPT connection would require a separate authenticated HTTPS Streamable HTTP endpoint, authorization controls, a safe way to keep a browser session on the host, and verification of current ChatGPT MCP support. A local interactive browser is a poor fit for an unattended remote server. No remote listener or public tunnel is provided. Before scheduled or unattended access, verify SIME's terms and permitted automation methods. If unattended access is not allowed, keep this as a manual, user initiated workflow.
