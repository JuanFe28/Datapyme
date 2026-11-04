from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from .config import ROOT

def make_engine(url):
    engine=create_engine(url,pool_pre_ping=True,hide_parameters=True,connect_args={'check_same_thread':False,'timeout':20} if url.startswith('sqlite') else {'connect_timeout':15})
    if url.startswith('sqlite'):
        @event.listens_for(engine,'connect')
        def sqlite_constraints(connection,_): connection.execute('PRAGMA foreign_keys=ON')
    return engine

def upgrade_database(engine):
    config=Config(str(ROOT/'alembic.ini'))
    config.set_main_option('script_location',str(ROOT/'migrations'))
    with engine.begin() as connection:
        config.attributes['connection']=connection
        command.upgrade(config,'head')

def get_db(request):
    with request.app.state.Session() as db:
        yield db
