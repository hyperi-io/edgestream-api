#!/opt/edgestream-api/bin/python3
"""
Project:   edgestream-api
File:      debian/contrib/edgestream_users.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

import os
import pwd
import re
from pathlib import Path
from typing import Optional
import typer

ENV_FILE = Path("/etc/default/edgestream-api")
EXPECTED_USER = "edgestream"


def parse_db_path_from_env() -> Path | None:
    if not ENV_FILE.exists():
        return None
    try:
        content = ENV_FILE.read_text()
        match = re.search(r"^SQLALCHEMY_DATABASE_URI\s*=\s*(.*)$", content, re.MULTILINE)
        if match:
            uri = match.group(1).strip()
            if uri.startswith("sqlite:///"):
                db_path_str = (
                    uri.replace("sqlite:////", "/", 1)
                    if uri.startswith("sqlite:////")
                    else uri.replace("sqlite:///", "", 1)
                )
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

app = typer.Typer(
    help="EdgeStream Hub User Management Utility",
    add_completion=False,
)


def list_users(db):
    """Enumerates all existing Web UI users."""
    users = db.execute(select(User).order_by(User.id)).scalars().all()
    if not users:
        typer.secho("No registered users found.", fg="yellow")
        return

    headers = f"{'ID':<4} {'EMAIL':<30} {'FULL NAME':<25} {'MFA':<6} {'SUPERUSER':<10} {'APPROVED':<9}"
    typer.echo("\n" + headers)
    typer.echo("-" * len(headers))

    for u in users:
        has_mfa = "Yes" if bool(u.otp_secret) else "No"
        is_su = "Yes" if bool(u.is_superuser) else "No"
        is_app = "Yes" if bool(u.is_approved) else "No"
        full_name = (u.full_name or "")[:24]
        typer.echo(
            f"{u.id:<4} {u.email:<30} {full_name:<25} {has_mfa:<6} {is_su:<10} {is_app:<9}"
        )
    typer.echo()


def remove_mfa(db, username: str):
    """Removes MFA secret for a given user without modifying password."""
    user = db.execute(
        select(User).where(User.email == username.lower())
    ).scalar_one_or_none()

    if not user:
        typer.secho(f"Error: User '{username}' not found.", fg="red")
        raise typer.Exit(code=1)

    if not user.otp_secret:
        typer.secho(f"User '{username}' does not have MFA configured.", fg="yellow")
        return

    user.otp_secret = None
    db.commit()

    Logger.logger.info(f"CLI: MFA cleared for {username}")
    typer.secho(f"MFA enforcement successfully removed for {username}.", fg="green")


def update_password(db, username: str, new_password: str):
    """Updates password for a given user and clears MFA."""
    user = db.execute(
        select(User).where(User.email == username.lower())
    ).scalar_one_or_none()

    if not user:
        typer.secho(f"Error: User '{username}' not found.", fg="red")
        raise typer.Exit(code=1)

    user.hashed_password = hash_password(new_password)
    user.otp_secret = None
    db.commit()

    Logger.logger.info(f"CLI: Password reset successful for {username}")
    typer.secho(f"Successfully updated password for {username}.", fg="green")
    typer.secho("Note: MFA (OTP) has been disabled for this account for recovery purposes.", fg="yellow")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    username: Optional[str] = typer.Argument(
        None, help="Email/username of the account"
    ),
    new_password: Optional[str] = typer.Argument(
        None, help="New password for the account"
    ),
    clear_mfa: bool = typer.Option(
        False, "--remove-mfa", help="Clear MFA/TOTP enforcement without changing password"
    ),
):
    """
    EdgeStream Hub user account and recovery utility.
    """
    if db_path and not db_path.exists():
        typer.secho(f"Error: Database file not found at {db_path.resolve()}", fg="red")
        raise typer.Exit(code=1)

    db = SessionLocal()
    try:
        # Case 1: sudo reset_admin (No arguments -> List users)
        if username is None:
            if clear_mfa:
                typer.secho("Error: --remove-mfa requires a username.", fg="red")
                raise typer.Exit(code=1)
            list_users(db)
            return

        # Case 2: sudo reset_admin --remove-mfa <username>
        if clear_mfa:
            remove_mfa(db, username)
            return

        # Case 3: sudo reset_admin <username> '<new_password>'
        if new_password is not None:
            update_password(db, username, new_password)
            return

        # Case 4: sudo reset_admin <username> (No password provided -> Prompt securely)
        prompted_pw = typer.prompt(
            f"Enter new password for {username}",
            hide_input=True,
            confirmation_prompt=True,
        )
        update_password(db, username, prompted_pw)

    except typer.Exit:
        raise
    except Exception as e:
        db.rollback()
        typer.secho(f"Internal Error: {e}", fg="red")
        raise typer.Exit(code=1)
    finally:
        db.close()


if __name__ == "__main__":
    app()
