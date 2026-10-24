"""Explicit complete registered-worker fixtures for partial-update tests."""
from datetime import date


def complete_registered_worker(worker):
    if " " not in worker.name:
        worker.name += " 氏"
    if not worker.furigana:
        worker.furigana = "とうろく ずみ"
    worker.phone = worker.phone or "09000001111"
    worker.email = worker.email or "existing@example.com"
    worker.birth_date = worker.birth_date or date(1990, 1, 2)
    worker.postal_code = worker.postal_code or "1000001"
    worker.address = worker.address or "東京都千代田区1-1"
    worker.nearest_station = worker.nearest_station or "登録駅"
    if worker.station_walk_minutes is None:
        worker.station_walk_minutes = 10
    worker.emergency_contact_phone = worker.emergency_contact_phone or "09000002222"
    worker.emergency_contact_name = worker.emergency_contact_name or "架空の連絡先"
    worker.emergency_contact_relationship = worker.emergency_contact_relationship or "実母"
    return worker


def submission_headers(client, token, key):
    auth = {"Authorization": f"Bearer {token}"}
    form = client.get("/api/line/registration/form", headers=auth)
    ticket = form.json().get("form_ticket") if form.status_code == 200 else None
    return {**auth, "Idempotency-Key": key, **({"X-Registration-Form-Ticket": ticket} if ticket else {})}
