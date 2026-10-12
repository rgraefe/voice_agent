"""Atomic updates; SQLite for local use and Firestore for multiple API replicas."""
from __future__ import annotations
from collections.abc import Callable
from typing import TYPE_CHECKING, cast
from app.types import Document

if TYPE_CHECKING:
    from google.cloud.firestore_v1 import CollectionReference, Query, Transaction
import json
import sqlite3
from pathlib import Path
from app.errors import ServiceError


# Apply the same conservative document-size limit to local and deployed persistence.
def check_size(result: Document) -> str:
    body = json.dumps(result, ensure_ascii=False)
    if len(body.encode()) > 850_000:
        raise ServiceError("SESSION_LIMIT", "Das Gespräch hat die maximale Größe erreicht.", 409)
    return body


class SqliteStore:
    def __init__(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS documents (kind TEXT, id TEXT, body TEXT, PRIMARY KEY(kind,id))")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def get(self, kind: str, key: str) -> Document | None:
        with self._connect() as db:
            row = db.execute("SELECT body FROM documents WHERE kind=? AND id=?", (kind, key)).fetchone()
            return json.loads(row[0]) if row else None

    def list(self, kind: str, owner: str | None=None) -> list[Document]:
        with self._connect() as db:
            rows = db.execute("SELECT body FROM documents WHERE kind=?", (kind,)).fetchall()
        docs = [json.loads(row[0]) for row in rows]
        return [d for d in docs if owner is None or d.get("owner") == owner]

    def update(self, kind: str, key: str, mutate: Callable[[Document | None], Document]) -> Document:
        with self._connect() as db:
            # Serialize read-modify-write operations so simultaneous callbacks cannot lose updates.
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body FROM documents WHERE kind=? AND id=?", (kind, key)).fetchone()
            result = mutate(json.loads(row[0]) if row else None)
            db.execute("INSERT OR REPLACE INTO documents VALUES (?,?,?)", (kind, key, check_size(result)))
            return result


class FirestoreStore:
    def __init__(self, project: str | None, database: str) -> None:
        from google.cloud import firestore
        self.db = firestore.Client(project=project, database=database)

    def collection(self, kind: str) -> CollectionReference:
        return self.db.collection("founder_" + kind)

    def get(self, kind: str, key: str) -> Document | None:
        return self.collection(kind).document(key).get().to_dict()

    def list(self, kind: str, owner: str | None=None) -> list[Document]:
        from google.cloud.firestore_v1.base_query import FieldFilter
        query: CollectionReference | Query = self.collection(kind)
        if owner is not None:
            query = query.where(filter=FieldFilter("owner", "==", owner))
        # Query streams contain existing documents, unlike direct document gets.
        return [cast(Document, snapshot.to_dict()) for snapshot in query.stream()]

    def update(self, kind: str, key: str, mutate: Callable[[Document | None], Document]) -> Document:
        from google.cloud import firestore
        ref = self.collection(kind).document(key)

        # Firestore may rerun this callback: mutations must not perform external side effects.
        @firestore.transactional
        def commit(transaction: Transaction) -> Document:
            result = mutate(ref.get(transaction=transaction).to_dict())
            check_size(result)
            transaction.set(ref, result)
            return result

        return commit(self.db.transaction())
