# All the exceptions of HOH.

class HOHError(Exception):
    """Base class for HOH errors."""
    pass

class DoesNotExistError(HOHError):
    """
    Raised when something in the field does not exist (e.g. a wrong day).
    """
    pass

class ParseError(HOHError):
    """
    Raised when field parsing fails.
    """
    pass

class SolarHoursNotSetError(HOHError):
    """
    Raised when trying to get a time from a solar hour without having defined them.
    """
    pass
