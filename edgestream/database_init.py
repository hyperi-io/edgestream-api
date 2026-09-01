"""
Project:   edgestream-api
File:      edgestream/database_init.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

import sys
from edgestream.db.init_db import init_db
from edgestream.core.config import Logger

def main():
    try:
        # Create all tables
        init_db()
    except Exception as e:
        Logger.logger.error(f"Database bootstrap failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()