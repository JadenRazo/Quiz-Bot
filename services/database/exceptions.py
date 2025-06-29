"""Custom database exceptions for the Quiz Bot."""

from typing import Any, Optional


class DatabaseError(Exception):
    """Base exception for all database-related errors."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error


class EntityNotFoundError(DatabaseError):
    """Raised when a specific entity is not found."""
    
    def __init__(self, entity: str, entity_id: Any, field: str = "id"):
        self.entity = entity
        self.entity_id = entity_id
        self.field = field
        super().__init__(f"{entity} with {field} '{entity_id}' not found")


class DuplicateEntityError(DatabaseError):
    """Raised on unique constraint violations."""
    
    def __init__(self, entity: str, conflicting_field: str, conflicting_value: Any):
        self.entity = entity
        self.conflicting_field = conflicting_field
        self.conflicting_value = conflicting_value
        super().__init__(
            f"A {entity} with {conflicting_field} '{conflicting_value}' already exists"
        )


class ValidationError(DatabaseError):
    """Raised when data validation fails."""
    
    def __init__(self, field: str, value: Any, reason: str):
        self.field = field
        self.value = value
        self.reason = reason
        super().__init__(f"Validation failed for {field}='{value}': {reason}")


class TransactionError(DatabaseError):
    """Raised when a database transaction fails."""
    
    def __init__(self, message: str, operation: str, original_error: Optional[Exception] = None):
        self.operation = operation
        super().__init__(f"Transaction failed during {operation}: {message}", original_error)


class ConnectionError(DatabaseError):
    """Raised when database connection issues occur."""
    pass