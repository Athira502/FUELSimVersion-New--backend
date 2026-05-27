from sqlalchemy import Column, String, Integer, inspect as sqla_inspect
from app.models.database import Base, engine

class clientSysReleaseData(Base):
    __tablename__ = "Z_FUE_CLIENT_SYS_INFO"
    id                  = Column(Integer, primary_key=True, index=True, autoincrement=True)
    SYSTEM_NAME         = Column(String, nullable=False, unique=True)
    SYSTEM_RELEASE_INFO = Column(String, nullable=False)


class ruleSet(Base):
    __tablename__ = "Z_FUE_RULESET"
    id                  = Column(Integer, primary_key=True, index=True, autoincrement=True)
    RULE_DESCRIPTION    = Column(String, nullable=False)
    AUTHOBJECT          = Column(String, nullable=False)
    AUTHFIELD           = Column(String, nullable=False)
    AUTHVALUE           = Column(String, nullable=False)



def ensure_table_exists():
    inspector = sqla_inspect(engine)
    table_name = clientSysReleaseData.__tablename__
    if not inspector.has_table(table_name):
        print(f"Table '{table_name}' not found. Creating...")
        clientSysReleaseData.__table__.create(bind=engine)
        print(f"Table '{table_name}' created.")
    else:
        print(f"Table '{table_name}' already exists.")

def ensure_ruleset_table_exists():
    inspector = sqla_inspect(engine)
    table_name = ruleSet.__tablename__
    if not inspector.has_table(table_name):
        print(f"Table '{table_name}' not found. Creating...")
        ruleSet.__table__.create(bind=engine)
        print(f"Table '{table_name}' created.")
    else:
        print(f"Table '{table_name}' already exists.")


ensure_table_exists()
