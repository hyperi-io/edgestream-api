"""
Project:   edgestream-api
File:      edgestream/backend_pre_start.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

import logging
from tenacity import after_log, before_log, retry, stop_after_attempt, wait_fixed
from sqlalchemy import text

from edgestream.db.session import SessionLocal
from edgestream.core.config import Logger

# Configuration for retry logic
max_tries = 60 * 5  # 5 minutes
wait_seconds = 1

@retry(
    stop=stop_after_attempt(max_tries),
    wait=wait_fixed(wait_seconds),
    before=before_log(Logger.logger, logging.INFO),
    after=after_log(Logger.logger, logging.WARN),
)
def init_connection() -> None:
    """
    Attempts to execute a simple query to verify database connectivity.
    """
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        Logger.logger.error(f"Database connection check failed: {e}")
        raise e
    finally:
        db.close()

def main() -> None:
    Logger.logger.info("Checking database connectivity before service start...")
    try:
        init_connection()
        Logger.logger.info("Database is responsive.")
    except Exception:
        Logger.logger.error("Database connectivity check timed out.")
        import sys
        sys.exit(1)

if __name__ == "__main__":
    main()
