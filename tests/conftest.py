import pytest


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    """Isolated data directory and database for each test."""
    monkeypatch.setenv("CTRACK_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("CTRACK_DB", raising=False)
    return tmp_path


@pytest.fixture()
def conn(data_dir):
    from cadence_tracker.storage import db

    connection = db.connect()
    yield connection
    connection.close()
