class SimeError(Exception):
    """Base class for safe, user-facing errors."""


class AuthenticationRequiredError(SimeError):
    pass


class BrowserUnavailableError(SimeError):
    pass


class CalendarNotFoundError(SimeError):
    pass


class CalendarResponseError(SimeError):
    pass


class InvalidCalendarDataError(SimeError):
    pass


class UnsupportedDateRangeError(SimeError):
    pass
