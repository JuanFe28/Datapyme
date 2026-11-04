from alembic import context
from research.models import Base

connection=context.config.attributes.get('connection')
if connection is None:
    from research.config import Settings
    from research.database import make_engine
    engine=make_engine(Settings.from_env().database_url)
    with engine.begin() as connection:
        context.configure(connection=connection,target_metadata=Base.metadata,render_as_batch=connection.dialect.name=='sqlite')
        with context.begin_transaction(): context.run_migrations()
else:
    context.configure(connection=connection,target_metadata=Base.metadata,render_as_batch=connection.dialect.name=='sqlite')
    with context.begin_transaction(): context.run_migrations()
