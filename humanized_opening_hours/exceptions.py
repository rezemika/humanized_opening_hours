class HOHError(Exception):
    """Base class for HOH errors."""
    pass


class ParseError(HOHError):
    """
    Raised when field parsing fails.
    """
    pass


class SolarHoursNotSetError(HOHError):
    """
    Raised when trying to get a time from a solar hour
    without having defined them.
    """
    pass


class SpanOverMidnight(HOHError):
    """
    Raised when a field has a period which spans over midnight
    (for example: "Mo-Fr 20:00-02:00"), which is not yet supported.
    """
    pass


class NextChangeError(HOHError):
    """
    Raised when something goes wrong in the 'next_change()' method,
    for example if the facility is always open.
    """
    pass
