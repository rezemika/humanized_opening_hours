class HOHError(Exception):
    """Base class for HOH errors."""
    pass


class ParseError(HOHError):
    """
    Raised when field parsing fails.
    """
    pass


class SolarHoursError(HOHError):
    """
    Raised when trying to get a time from a solar hour
    without having defined them.
    """
    pass


class CommentOnlyField(ParseError):
    """
    Raised when a field contains only a comment.
    The comment is accessible via the 'comment' attribute.
    """
    def __init__(self, message, comment):
        super().__init__(message)
        self.comment = comment
