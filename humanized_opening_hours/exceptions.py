class HOHError(Exception):
    """Base class for HOH errors."""
    pass


class ParseError(HOHError):
    """
    Raised when field parsing fails.
    """
    pass


class InconsistentField(ParseError):
    """
    Raised when a field contains an error which can't be
    corrected automatically.
    """
    pass


class UnsupportedPattern(ParseError, NotImplementedError):
    """
    Raised when the field is parsable, but a pattern in it is not supported.
    """
    pass
