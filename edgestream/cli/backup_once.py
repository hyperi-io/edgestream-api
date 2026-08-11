# python -m edgestream.cli.backup_once
from edgestream.db.session import SessionLocal
from edgestream.services.backup.run import run_backup_once

def main():
    db = SessionLocal()
    try:
        print(run_backup_once(db))
    finally:
        db.close()

if __name__ == "__main__":
    main()
