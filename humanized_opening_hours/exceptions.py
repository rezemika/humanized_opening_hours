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
