# tests/db/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlmodel import SQLModel


@pytest.fixture
def memory_engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine
