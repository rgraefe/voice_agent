"""Atomic updates; SQLite for local use and Firestore for multiple API replicas."""
import json
import sqlite3
from pathlib import Path
from app.errors import ServiceError


def check_size(result):
    body = json.dumps(result, ensure_ascii=False)
    if len(body.encode()) > 850_000:
        raise ServiceError("SESSION_LIMIT", "Das Gespräch hat die maximale Größe erreicht.", 409)
    return body


class SqliteStore:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS documents (kind TEXT, id TEXT, body TEXT, PRIMARY KEY(kind,id))")

    def _connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def get(self, kind, key):
        with self._connect() as db:
            row = db.execute("SELECT body FROM documents WHERE kind=? AND id=?", (kind, key)).fetchone()
            return json.loads(row[0]) if row else None

    def list(self, kind, owner=None):
        with self._connect() as db:
            rows = db.execute("SELECT body FROM documents WHERE kind=?", (kind,)).fetchall()
        docs = [json.loads(row[0]) for row in rows]
        return [d for d in docs if owner is None or d.get("owner") == owner]

    def update(self, kind, key, mutate):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body FROM documents WHERE kind=? AND id=?", (kind, key)).fetchone()
            result = mutate(json.loads(row[0]) if row else None)
            db.execute("INSERT OR REPLACE INTO documents VALUES (?,?,?)", (kind, key, check_size(result)))
            return result


class FirestoreStore:
    def __init__(self, project, database):
        from google.cloud import firestore
        self.db = firestore.Client(project=project, database=database)

    def collection(self, kind):
        return self.db.collection("founder_" + kind)

    def get(self, kind, key):
        return self.collection(kind).document(key).get().to_dict()

    def list(self, kind, owner=None):
        from google.cloud.firestore_v1.base_query import FieldFilter
        query = self.collection(kind)
        if owner is not None:
            query = query.where(filter=FieldFilter("owner", "==", owner))
        return [item.to_dict() for item in query.stream()]

    def update(self, kind, key, mutate):
        from google.cloud import firestore
        ref = self.collection(kind).document(key)

        @firestore.transactional
        def commit(transaction):
            result = mutate(ref.get(transaction=transaction).to_dict())
            check_size(result)
            transaction.set(ref, result)
            return result

        return commit(self.db.transaction())
