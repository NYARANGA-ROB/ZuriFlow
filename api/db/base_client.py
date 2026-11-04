from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import os

from api.constants import DATABASE_URL

DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
DB_POOL_RECYCLE_S = int(os.getenv("DB_POOL_RECYCLE_S", "1800"))


class BaseDBClient:
    def __init__(self):
        self.engine = create_async_engine(
            DATABASE_URL,
            pool_size=DB_POOL_SIZE,
            max_overflow=DB_MAX_OVERFLOW,
            pool_pre_ping=True,
            pool_recycle=DB_POOL_RECYCLE_S,
        )
        self.async_session = async_sessionmaker(bind=self.engine)

    async def execute_raw_query(
        self, query: str, params: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a raw SQL query and return results as a list of dictionaries.

        Args:
            query: The SQL query to execute
            params: Optional dictionary of query parameters

        Returns:
            List of dictionaries containing the query results
        """
        async with self.async_session() as session:
            result = await session.execute(text(query), params or {})
            rows = result.fetchall()
            if rows:
                # Convert rows to dictionaries
                columns = result.keys()
                return [dict(zip(columns, row)) for row in rows]
            return []
