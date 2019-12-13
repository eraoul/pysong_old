"""Custom exception type definitions."""


class ArgumentError(Exception):
    """Used to indicate incorrect use of function arguments. Simple type checking is done
    via assert statements, but when more complex logic is required we raise this exception to
    indicate bad function arguments."""
    pass
