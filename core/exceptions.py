class CodeAttendException(Exception):
    """
    Base exception for all CodeAttend application errors.
    """
    pass


class AuthenticationError(CodeAttendException):
    """
    Raised when authentication fails.
    """
    pass


class AccountNotActiveError(AuthenticationError):
    """
    Raised when a user tries to access the system
    before their account has been approved/activated.
    """
    pass


class PermissionDeniedError(CodeAttendException):
    """
    Raised when a user tries to perform an action
    they are not allowed to perform.
    """
    pass

class InvalidApprovalError(Exception):
    """Raised when an invalid approval action is attempted."""

class AttendanceError(Exception):
    """Raised when attendance recording fails."""