from alembic import context

from studio.adapters.database import engine
from studio.settings import settings

if context.is_offline_mode():
    context.configure(url=settings().database_url, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with engine().connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
