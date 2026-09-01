"""
Project:   edgestream-api
File:      alembic/versions/1aefb8fac77f_transform_text_columns.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

"""transform text columns

Revision ID: 1aefb8fac77f
Revises: 
Create Date: 2025-08-25 20:24:35.159788

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1aefb8fac77f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    with op.batch_alter_table("transforms") as batch:
        batch.alter_column("description", type_=sa.Text(), existing_type=sa.String(length=1024), existing_nullable=True)
        batch.alter_column("query_builder", type_=sa.Text(), existing_type=sa.String(), existing_nullable=True)
        batch.alter_column("query_raw", type_=sa.Text(), existing_type=sa.String(), existing_nullable=True)

def downgrade():
    with op.batch_alter_table("transforms") as batch:
        batch.alter_column("description", type_=sa.String(length=1024), existing_type=sa.Text(), existing_nullable=True)
        batch.alter_column("query_builder", type_=sa.String(), existing_type=sa.Text(), existing_nullable=True)
        batch.alter_column("query_raw", type_=sa.String(), existing_type=sa.Text(), existing_nullable=True)
