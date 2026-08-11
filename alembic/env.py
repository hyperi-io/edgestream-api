from alembic import context
from edgestream.db.session import engine as app_engine, Base

target_metadata = Base.metadata

def run_migrations_online():
    connectable = app_engine
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,   # important for SQLite
        )
        with context.begin_transaction():
            context.run_migrations()

