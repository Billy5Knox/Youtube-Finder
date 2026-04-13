import pytest
from app.database import init_db, get_connection


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


@pytest.fixture
def db_conn(db_path):
    conn = get_connection(db_path)
    yield conn
    conn.close()
