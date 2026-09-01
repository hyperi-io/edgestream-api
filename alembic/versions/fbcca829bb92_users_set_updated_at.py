"""
Project:   edgestream-api
File:      alembic/versions/fbcca829bb92_users_set_updated_at.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

"""User database timestamp triggers

Revision ID: fbcca829bb92
Revises: baf4beec17e4
Create Date: 2025-08-28 14:25:35.707060

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'fbcca829bb92'
down_revision: Union[str, Sequence[str], None] = 'baf4beec17e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UPGRADE_TRIGGER_SQL = sa.text("""
    CREATE TRIGGER IF NOT EXISTS tg_users_updated_at
    AFTER UPDATE ON users
    FOR EACH ROW
    BEGIN
        UPDATE users
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.id;
    END;
""")

DOWNGRADE_TRIGGER_SQL = sa.text("DROP TRIGGER IF EXISTS tg_users_updated_at")

def upgrade():
    # Ensure existing rows have valid timestamps
    op.execute(sa.text("""
        UPDATE users
        SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
            updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)
    """))

    with op.batch_alter_table("users", recreate="always") as batch_op:
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )

    op.execute(UPGRADE_TRIGGER_SQL)

def downgrade():
    op.execute(DOWNGRADE_TRIGGER_SQL)

    with op.batch_alter_table("users", recreate="always") as batch_op:
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(),
            nullable=False,
            server_default=None,
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(),
            nullable=False,
            server_default=None,
        )