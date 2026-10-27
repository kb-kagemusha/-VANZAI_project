"""Two formalization requests must return the same independently numbered draft."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from src.models.master import Client
from src.models.order_formalization import OrderFormalization
from src.models.base import generate_ulid
from src.services import order_formalization as service,worker_schedule as ws
from tests.postgres_conflict.test_staffing_conflict import seed


def test_formalization_retries_create_one_draft(conflict_engine,monkeypatch,tmp_path):
    sessions,actor,workers,versions=seed(conflict_engine,monkeypatch,tmp_path)
    actor.display_name=None
    with sessions() as db:
        client=Client(id=generate_ulid(),name='正式化のローカル試験')
        db.add(client);db.commit();client_id=client.id
        value=service.preview(db,versions[0],actor)
    barrier=Barrier(2)
    def submit(_):
        with sessions() as db:
            barrier.wait(timeout=10)
            version=service.create(db,versions[0],source_digest=value['source_digest'],internal_source={'client_id':client_id},worker_ids=[workers[0]],capacities=value['capacities'],masters_reviewed=True,follow_up_due_on=ws.today_jst()+timedelta(days=1),actor=actor)
            result=version.id;db.commit();return result
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(submit,range(2)))
    assert results[0] == results[1]
    with sessions() as db:
        assert db.query(OrderFormalization).filter_by(source_version_id=versions[0]).count() == 1
