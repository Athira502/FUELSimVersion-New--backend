from sqlalchemy import Column, String, Integer, DateTime, Text, inspect as sqla_inspect
from sqlalchemy.sql import func
from app.models.database import Base, engine


class AIApiKey(Base):
    """
    Stores encrypted API keys for AI providers.
    Raw keys are NEVER stored - only Fernet-encrypted blobs.
    """
    __tablename__ = "Z_FUE_AI_API_KEY"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    provider = Column(String(50), nullable=False, unique=True)   # 'anthropic', 'openai', 'ollama'
    env_var_name = Column(String(100), nullable=False)           # e.g. 'ANTHROPIC_API_KEY'
    encrypted_key = Column(Text, nullable=False)                 # Fernet-encrypted blob
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


def ensure_api_key_table_exists():
    """Create API key table if it doesn't exist"""
    inspector = sqla_inspect(engine)
    table_name = AIApiKey.__tablename__

    if not inspector.has_table(table_name):
        print(f"Table '{table_name}' not found. Creating...")
        AIApiKey.__table__.create(bind=engine)
        print(f"Table '{table_name}' created successfully.")
    else:
        print(f"Table '{table_name}' already exists.")


# Run on module import — same pattern as ai_config.py
ensure_api_key_table_exists()