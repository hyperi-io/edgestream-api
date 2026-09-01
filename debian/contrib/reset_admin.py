#!/opt/edgestream-api/bin/python3
"""
Project:   edgestream-api
File:      debian/contrib/reset_admin.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

import os
import pwd
import re
from pathlib import Path
import typer

ENV_FILE = Path("/etc/default/edgestream-api")
EXPECTED_USER = "edgestream"


def parse_db_path_from_env() -> Path | None:
    if not ENV_FILE.exists():
        return None
    try:
        content = ENV_FILE.read_text()
        match = re.search(r'^SQLALCHEMY_DATABASE_URI\s*=\s*(.*)$', content, re.MULTILINE)
        if match:
            uri = match.group(1).strip()
            if uri.startswith("sqlite:///"):
                db_path_str = uri.replace("sqlite:////", "/", 1) if uri.startswith("sqlite:////") else uri.replace(
                    "sqlite:///", "", 1)
                db_path_str = db_path_str.split("?")[0]
                return Path(db_path_str)
    except Exception:
        pass
    return None


def ensure_ownership(db_path: Path):
    try:
        target_uid = pwd.getpwnam(EXPECTED_USER).pw_uid
        target_gid = pwd.getpwnam(EXPECTED_USER).pw_gid
    except KeyError:
        return

    parent_dir = db_path.parent
    if parent_dir.exists() and parent_dir.stat().st_uid != target_uid:
        try:
            os.chown(parent_dir, target_uid, target_gid)
        except PermissionError:
            pass

    if db_path.exists() and db_path.stat().st_uid != target_uid:
        try:
            os.chown(db_path, target_uid, target_gid)
        except PermissionError:
            pass


# 1. Intercept and configure environment BEFORE importing app database modules
db_path = parse_db_path_from_env()
if db_path:
    db_dir = db_path.parent
    if db_dir.exists():
        os.chdir(db_dir)
        ensure_ownership(db_path)
    os.environ["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path.resolve()}?check_same_thread=False"

# 2. Import database, ORM models, and SQLAlchemy query tools
from sqlalchemy import select
from edgestream.db.session import SessionLocal
from edgestream.models.system.user import User
from edgestream.services.auth.security import hash_password
from edgestream.core.config import Logger

app = typer.Typer(help="EdgeStream Hub Admin Management Utility")


@app.command()
def reset_password(
        email: str = typer.Option("admin@edgestream.local", help="Email of the admin user to reset"),
        password: str = typer.Option(..., prompt=True, hide_input=True, confirmation_prompt=True,
                                     help="New password for the account")
):
    """
    Force-resets an admin password directly in the database.
    This bypasses all Web API security and MFA.
    """
    typer.secho(f"Current working directory: {os.getcwd()}", fg="cyan")

    if db_path:
        typer.secho(f"Using database at: {db_path.resolve()}", fg="cyan")
        if not db_path.exists():
            typer.secho(f"Error: Database file not found at {db_path.resolve()}", fg="red")
            typer.secho("Make sure the actual SQLite database file exists in /var/lib/edgestream/", fg="yellow")
            raise typer.Exit(code=1)

    db = SessionLocal()
    try:
        query = select(User).where(User.email == email.lower())
        user = db.execute(query).scalar_one_or_none()

        if not user:
            typer.secho(f"Error: User with email '{email}' not found.", fg="red")
            raise typer.Exit(code=1)

        user.hashed_password = hash_password(password)
        user.otp_secret = None

        db.commit()

        Logger.logger.info(f"CLI: Password reset successful for {email}")
        typer.secho(f"Successfully updated password for {email}.", fg="green")
        typer.secho("Note: MFA (OTP) has been disabled for this account for recovery purposes.", fg="yellow")

    except Exception as e:
        db.rollback()
        typer.secho(f"Internal Error: {e}", fg="red")
        raise typer.Exit(code=1)
    finally:
        db.close()


if __name__ == "__main__":
    app()