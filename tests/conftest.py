from __future__ import annotations
from pathlib import Path
from collections.abc import Iterator
from fastapi import FastAPI
from app.types import Document
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    return create_app(Settings(_env_file=None, database_path=str(tmp_path / 'test.db'),
                              session_secret='s'*40, worker_secret='w'*40))


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, headers={'X-Requested-With': 'founder-app'}) as client:
        yield client


def login(client: TestClient, role: str='founder') -> None:
    assert client.post('/api/login', json={'demo_role': role}).status_code == 200


def start(client: TestClient) -> Document:
    login(client)
    response = client.post('/api/interviews', json={'mode': 'simulation', 'request_id': 'test-request-123'})
    assert response.status_code == 200
    return response.json()
