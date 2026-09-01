"""
Project:   edgestream-api
File:      edgestream/db/db.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from sqlalchemy.orm import Session
from edgestream.db.session import SessionLocal

def get_db():
    db: Session = SessionLocal()
    db.current_user_id = None
    try:
        yield db
    finally:
        db.close()
