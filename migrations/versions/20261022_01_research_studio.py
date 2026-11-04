"""Esquema inicial y ampliación conservadora del MVP de tres tablas.

La instantánea schema_v1 es inmutable. No se importan modelos futuros.
"""
from alembic import op
import sqlalchemy as sa
from migrations.schema_v1 import Base

revision='20261022_01'
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    connection=op.get_bind()
    existing=set(sa.inspect(connection).get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in existing:
            table.create(connection)
            continue
        inspector=sa.inspect(connection)
        columns={c['name'] for c in inspector.get_columns(table.name)}
        missing=[c for c in table.columns if c.name not in columns]
        if not missing: continue
        for column in missing:
            default=column.server_default.arg if column.server_default is not None else None
            if connection.dialect.name=='sqlite' and table.name=='responses' and column.name=='consent_id':
                # SQLite admite esta FK nullable al añadir la columna: no recrear
                # tablas padre ni desactivar integridad de registros existentes.
                op.execute('ALTER TABLE responses ADD COLUMN consent_id INTEGER REFERENCES consents(id)')
            else:
                op.add_column(table.name,sa.Column(column.name,column.type,nullable=column.nullable,server_default=default))
                if connection.dialect.name!='sqlite':
                    for fk in column.foreign_keys:
                        target_table,target_column=fk.target_fullname.split('.')
                        op.create_foreign_key('fk_'+table.name+'_'+column.name,table.name,target_table,[column.name],[target_column])
            if column.unique: op.create_index('uq_'+table.name+'_'+column.name,table.name,[column.name],unique=True)
        if table.name=='tasks':
            connection.execute(sa.text("UPDATE tasks SET status='completada' WHERE completed=:completed"),{'completed':True})
    # Base accedida solo por backend. Supabase no debe exponer estas tablas por Data API.
    if connection.dialect.name=='postgresql':
        for table in Base.metadata.sorted_tables:
            connection.execute(sa.text('ALTER TABLE "'+table.name+'" ENABLE ROW LEVEL SECURITY'))
            for role in ('anon','authenticated'):
                exists=connection.execute(sa.text('SELECT 1 FROM pg_roles WHERE rolname=:role'),{'role':role}).scalar()
                if exists: connection.execute(sa.text('REVOKE ALL ON TABLE "'+table.name+'" FROM '+role))

def downgrade():
    raise RuntimeError('No hay downgrade destructivo. Restaurar una copia en una base nueva.')
