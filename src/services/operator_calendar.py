"""Minimal availability/assignment calendar; same source records as the admin calendar."""
from datetime import date
from src.models.master import Worker
from src.models.transaction import Assignment, Project, ShiftSlot, WorkerAvailability


def availability(db, start: date, end: date):
    workers = db.query(Worker).filter(Worker.is_active.is_(True), Worker.deleted_at.is_(None)).order_by(Worker.name, Worker.id).all()
    ids = [w.id for w in workers]
    rows = db.query(WorkerAvailability).filter(WorkerAvailability.worker_id.in_(ids), WorkerAvailability.availability_date >= start, WorkerAvailability.availability_date <= end).all() if ids else []
    mapping = {w.id: {"worker_id": w.id, "name": w.name, "days": {}} for w in workers}
    for row in rows:
        mapping[row.worker_id]["days"].setdefault(row.availability_date.isoformat(), {"status": None, "assignments": []})["status"] = row.status
    assignments = db.query(Assignment, Project.name, ShiftSlot.work_date, ShiftSlot.shift_label).join(ShiftSlot, Assignment.shift_slot_id == ShiftSlot.id).join(Project, ShiftSlot.project_id == Project.id).filter(Assignment.worker_id.in_(ids), Assignment.status != "canceled", ShiftSlot.work_date >= start, ShiftSlot.work_date <= end).all() if ids else []
    for row, name, day, label in assignments:
        mapping[row.worker_id]["days"].setdefault(day.isoformat(), {"status": None, "assignments": []})["assignments"].append({"project_name": name, "shift_label": label, "status": row.status})
    return {"kind": "availability", "workers": list(mapping.values())}
