from __future__ import annotations
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from app.store import SqliteStore


def test_atomic_concurrent_updates(tmp_path: Path) -> None:
    store=SqliteStore(str(tmp_path/'concurrency.db'))
    def increment(_: int) -> None:
        store.update('counter','one',lambda old:{'value':(old or {'value':0})['value']+1})
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(increment,range(40)))
    counter = store.get('counter','one')
    assert counter is not None
    assert counter['value']==40
