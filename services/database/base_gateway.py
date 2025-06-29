"""Base database gateway providing common database operation patterns."""

import asyncio
import logging
from abc import ABC
from typing import Any, Dict, List, Optional, TypeVar, Union

import asyncpg

from .exceptions import ConnectionError, DatabaseError, TransactionError

logger = logging.getLogger("bot.database.gateway")

# Type variable for concrete data models
T = TypeVar('T')


class BaseGateway(ABC):
    """
    Base class for database gateways using the Table Data Gateway pattern.
    
    Provides common database operation utilities while allowing concrete
    implementations to define their specific table operations.
    """
    
    def __init__(self, connection: Union[asyncpg.Connection, asyncpg.Pool]):
        """
        Initialize the gateway with a database connection or pool.
        
        Args:
            connection: Either a single connection (for transactions) or pool (for simple operations)
        """
        self._connection = connection
        self._logger = logging.getLogger(f"bot.database.{self.__class__.__name__.lower()}")
    
    async def _fetchrow(self, query: str, *params: Any) -> Optional[asyncpg.Record]:
        """
        Execute a query and return a single row.
        
        Args:
            query: SQL query with parameter placeholders ($1, $2, etc.)
            *params: Query parameters
            
        Returns:
            Single database record or None if no results
            
        Raises:
            DatabaseError: If query execution fails
        """
        try:
            self._logger.debug(f"Executing fetchrow: {query[:100]}...")
            
            if isinstance(self._connection, asyncpg.Pool):
                async with self._connection.acquire() as conn:
                    result = await conn.fetchrow(query, *params)
            else:
                result = await self._connection.fetchrow(query, *params)
                
            self._logger.debug(f"fetchrow returned: {'record' if result else 'None'}")
            return result
            
        except asyncpg.PostgresError as e:
            self._logger.error(f"PostgreSQL error in fetchrow: {e}", exc_info=True)
            raise DatabaseError(f"Database query failed: {e}", original_error=e)
        except Exception as e:
            self._logger.error(f"Unexpected error in fetchrow: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected database error: {e}", original_error=e)
    
    async def _fetch(self, query: str, *params: Any) -> List[asyncpg.Record]:
        """
        Execute a query and return multiple rows.
        
        Args:
            query: SQL query with parameter placeholders ($1, $2, etc.)
            *params: Query parameters
            
        Returns:
            List of database records (empty list if no results)
            
        Raises:
            DatabaseError: If query execution fails
        """
        try:
            self._logger.debug(f"Executing fetch: {query[:100]}...")
            
            if isinstance(self._connection, asyncpg.Pool):
                async with self._connection.acquire() as conn:
                    result = await conn.fetch(query, *params)
            else:
                result = await self._connection.fetch(query, *params)
                
            self._logger.debug(f"fetch returned {len(result)} records")
            return result
            
        except asyncpg.PostgresError as e:
            self._logger.error(f"PostgreSQL error in fetch: {e}", exc_info=True)
            raise DatabaseError(f"Database query failed: {e}", original_error=e)
        except Exception as e:
            self._logger.error(f"Unexpected error in fetch: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected database error: {e}", original_error=e)
    
    async def _fetchval(self, query: str, *params: Any) -> Any:
        """
        Execute a query and return a single value.
        
        Args:
            query: SQL query with parameter placeholders ($1, $2, etc.)
            *params: Query parameters
            
        Returns:
            Single value or None if no results
            
        Raises:
            DatabaseError: If query execution fails
        """
        try:
            self._logger.debug(f"Executing fetchval: {query[:100]}...")
            
            if isinstance(self._connection, asyncpg.Pool):
                async with self._connection.acquire() as conn:
                    result = await conn.fetchval(query, *params)
            else:
                result = await self._connection.fetchval(query, *params)
                
            self._logger.debug(f"fetchval returned: {result}")
            return result
            
        except asyncpg.PostgresError as e:
            self._logger.error(f"PostgreSQL error in fetchval: {e}", exc_info=True)
            raise DatabaseError(f"Database query failed: {e}", original_error=e)
        except Exception as e:
            self._logger.error(f"Unexpected error in fetchval: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected database error: {e}", original_error=e)
    
    async def _execute(self, query: str, *params: Any) -> str:
        """
        Execute a query without returning results (INSERT, UPDATE, DELETE).
        
        Args:
            query: SQL query with parameter placeholders ($1, $2, etc.)
            *params: Query parameters
            
        Returns:
            Status string (e.g., "INSERT 0 1", "UPDATE 3")
            
        Raises:
            DatabaseError: If query execution fails
        """
        try:
            self._logger.debug(f"Executing: {query[:100]}...")
            
            if isinstance(self._connection, asyncpg.Pool):
                async with self._connection.acquire() as conn:
                    result = await conn.execute(query, *params)
            else:
                result = await self._connection.execute(query, *params)
                
            self._logger.debug(f"execute returned: {result}")
            return result
            
        except asyncpg.PostgresError as e:
            self._logger.error(f"PostgreSQL error in execute: {e}", exc_info=True)
            raise DatabaseError(f"Database query failed: {e}", original_error=e)
        except Exception as e:
            self._logger.error(f"Unexpected error in execute: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected database error: {e}", original_error=e)
    
    async def _executemany(self, query: str, params_list: List[tuple]) -> None:
        """
        Execute a query multiple times with different parameters (batch operation).
        
        Args:
            query: SQL query with parameter placeholders ($1, $2, etc.)
            params_list: List of parameter tuples
            
        Raises:
            DatabaseError: If query execution fails
        """
        try:
            self._logger.debug(f"Executing batch operation: {query[:100]}... ({len(params_list)} operations)")
            
            if isinstance(self._connection, asyncpg.Pool):
                async with self._connection.acquire() as conn:
                    await conn.executemany(query, params_list)
            else:
                await self._connection.executemany(query, params_list)
                
            self._logger.debug(f"executemany completed successfully")
            
        except asyncpg.PostgresError as e:
            self._logger.error(f"PostgreSQL error in executemany: {e}", exc_info=True)
            raise DatabaseError(f"Batch operation failed: {e}", original_error=e)
        except Exception as e:
            self._logger.error(f"Unexpected error in executemany: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected batch operation error: {e}", original_error=e)
    
    def _record_to_dict(self, record: Optional[asyncpg.Record]) -> Optional[Dict[str, Any]]:
        """
        Convert an asyncpg Record to a dictionary.
        
        Args:
            record: Database record or None
            
        Returns:
            Dictionary representation of record or None
        """
        if record is None:
            return None
        
        try:
            return dict(record)
        except Exception as e:
            self._logger.warning(f"Failed to convert record to dict: {e}")
            return None
    
    def _records_to_dicts(self, records: List[asyncpg.Record]) -> List[Dict[str, Any]]:
        """
        Convert a list of asyncpg Records to dictionaries.
        
        Args:
            records: List of database records
            
        Returns:
            List of dictionary representations
        """
        result = []
        for record in records:
            converted = self._record_to_dict(record)
            if converted is not None:
                result.append(converted)
        return result


class TransactionalGateway(BaseGateway):
    """
    Gateway that supports transactional operations using the Unit of Work pattern.
    
    Use this when you need atomic operations across multiple tables.
    """
    
    def __init__(self, connection: asyncpg.Connection):
        """
        Initialize with a single connection (required for transactions).
        
        Args:
            connection: Database connection (not a pool)
        """
        if isinstance(connection, asyncpg.Pool):
            raise ValueError("TransactionalGateway requires a single connection, not a pool")
        
        super().__init__(connection)
        self._transaction: Optional[asyncpg.Transaction] = None
    
    async def begin_transaction(self) -> None:
        """Begin a database transaction."""
        if self._transaction is not None:
            raise TransactionError("Transaction already in progress", "begin")
        
        try:
            self._transaction = self._connection.transaction()
            await self._transaction.start()
            self._logger.debug("Transaction started")
        except Exception as e:
            self._logger.error(f"Failed to start transaction: {e}", exc_info=True)
            raise TransactionError("Failed to start transaction", "begin", e)
    
    async def commit_transaction(self) -> None:
        """Commit the current transaction."""
        if self._transaction is None:
            raise TransactionError("No transaction in progress", "commit")
        
        try:
            await self._transaction.commit()
            self._transaction = None
            self._logger.debug("Transaction committed")
        except Exception as e:
            self._logger.error(f"Failed to commit transaction: {e}", exc_info=True)
            raise TransactionError("Failed to commit transaction", "commit", e)
    
    async def rollback_transaction(self) -> None:
        """Rollback the current transaction."""
        if self._transaction is None:
            self._logger.warning("Attempted to rollback with no transaction in progress")
            return
        
        try:
            await self._transaction.rollback()
            self._transaction = None
            self._logger.debug("Transaction rolled back")
        except Exception as e:
            self._logger.error(f"Failed to rollback transaction: {e}", exc_info=True)
            raise TransactionError("Failed to rollback transaction", "rollback", e)
    
    async def __aenter__(self):
        """Context manager entry - begins transaction."""
        await self.begin_transaction()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - commits or rolls back transaction."""
        if exc_type is not None:
            await self.rollback_transaction()
        else:
            await self.commit_transaction()