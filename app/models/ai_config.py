from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, inspect as sqla_inspect
from sqlalchemy.sql import func
from app.models.database import Base, engine


class AIModelConfig(Base):
    """
    Stores AI model configurations.
    API keys are NEVER stored here - only in environment variables.
    """
    __tablename__ = "Z_FUE_AI_MODEL_CONFIG"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    model_provider = Column(String(50), nullable=False)  # 'anthropic', 'openai', 'azure'
    model_name = Column(String(100), nullable=False)  # 'claude-opus-4-20250514', 'gpt-4o-mini'
    model_version = Column(String(50))  # Optional version string
    is_active = Column(Boolean, default=False)  # Only one can be active
    max_tokens = Column(Integer, default=4096)
    temperature = Column(Float, default=0.7)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by = Column(String(100))


def ensure_ai_model_config_table_exists():
    """Create AI model config table if it doesn't exist"""
    inspector = sqla_inspect(engine)
    table_name = AIModelConfig.__tablename__

    if not inspector.has_table(table_name):
        print(f"Table '{table_name}' not found. Creating...")
        AIModelConfig.__table__.create(bind=engine)
        print(f"Table '{table_name}' created successfully.")

        # Insert default configurations
        from app.models.database import SessionLocal
        db = SessionLocal()
        try:
            default_configs = [
                AIModelConfig(
                    model_provider="anthropic",
                    model_name="claude-sonnet-4-20250514",
                    model_version="claude-sonnet-4-20250514",
                    is_active=True,
                    max_tokens=4096,
                    temperature=0.7,
                    description="Claude Sonnet 4 - Fast and efficient for SAP analysis"
                ),
                AIModelConfig(
                    model_provider="anthropic",
                    model_name="claude-opus-4-20250514",
                    model_version="claude-opus-4-20250514",
                    is_active=False,
                    max_tokens=4096,
                    temperature=0.7,
                    description="Claude Opus 4 - Most capable model"
                ),
                AIModelConfig(
                    model_provider="openai",
                    model_name="gpt-4o-mini",
                    model_version="gpt-4o-mini-2024-07-18",
                    is_active=False,
                    max_tokens=4096,
                    temperature=0.3,
                    description="GPT-4o Mini - Cost-effective OpenAI model"
                )
            ]

            db.add_all(default_configs)
            db.commit()
            print(f"Inserted {len(default_configs)} default AI model configurations.")
        except Exception as e:
            print(f"Error inserting default configs: {e}")
            db.rollback()
        finally:
            db.close()
    else:
        print(f"Table '{table_name}' already exists.")


# Run on module import
ensure_ai_model_config_table_exists()