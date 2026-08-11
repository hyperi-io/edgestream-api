from sqlalchemy.orm import Session
from edgestream.db.session import SessionLocal

def get_db():
    db: Session = SessionLocal()
    db.current_user_id = None
    try:
        yield db
    finally:
        db.close()
