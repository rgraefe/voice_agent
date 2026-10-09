from concurrent.futures import ThreadPoolExecutor
from app.store import SqliteStore


def test_atomic_concurrent_updates(tmp_path):
    store=SqliteStore(str(tmp_path/'concurrency.db'))
    def increment(_):
        store.update('counter','one',lambda old:{'value':(old or {'value':0})['value']+1})
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(increment,range(40)))
    assert store.get('counter','one')['value']==40
