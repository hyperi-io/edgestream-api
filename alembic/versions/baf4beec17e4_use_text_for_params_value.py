"""
Project:   edgestream-api
File:      alembic/versions/baf4beec17e4_use_text_for_params_value.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

"""use Text for params value

Revision ID: baf4beec17e4
Revises: 1aefb8fac77f
Create Date: 2025-08-26 10:13:22.973210

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'baf4beec17e4'
down_revision: Union[str, Sequence[str], None] = '1aefb8fac77f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    with op.batch_alter_table("source_params") as batch_op:
        batch_op.alter_column(
            "value",
            existing_type=sa.String(length=1024),
            type_=sa.Text(),
            existing_nullable=True,
        )

    with op.batch_alter_table("destination_params") as batch_op:
        batch_op.alter_column(
            "value",
            existing_type=sa.String(length=1024),
            type_=sa.Text(),
            existing_nullable=True,
        )


def downgrade():
    with op.batch_alter_table("source_params") as batch_op:
        batch_op.alter_column(
            "value",
            existing_type=sa.Text(),
            type_=sa.String(length=1024),
            existing_nullable=True,
        )

    with op.batch_alter_table("destination_params") as batch_op:
        batch_op.alter_column(
            "value",
            existing_type=sa.Text(),
            type_=sa.String(length=1024),
            existing_nullable=True,
        )
