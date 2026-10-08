"""稼働者登録ポップアップのプロフィール読み書き。"""
from datetime import date

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

_PROFILE_FIELDS = (
    "birth_date",
    "marital_status",
    "postal_code",
    "address",
    "hometown",
    "nearest_station",
    "station_walk_minutes",
    "final_education",
    "licenses_qualifications",
    "car_drive_ok",
    "hiace_drive_ok",
    "truck_drive",
    "work_history",
    "ploomx_sales_experience",
    "smoking_ok",
    "lucky_self",
    "hobbies",
    "personality_strengths",
    "personality_weaknesses",
    "club_activity",
    "motivation",
    "self_pr",
    "life_goal",
    "desired_income",
    "available_days_per_week",
    "available_weekdays",
    "available_day_hours",
    "available_time_from",
    "available_time_to",
    "available_start_date",
    "payment_terms_ok",
)


def completed_years(birth: date | None, today: date | None = None) -> int | None:
    """誕生日を迎えていれば満年齢。未来日は年齢にしない。"""
    if birth is None:
        return None
    if today is None:
        from src.domain.worker_tags import tokyo_today

        today = tokyo_today()
    years = today.year - birth.year
    if (today.month, today.day) < (birth.month, birth.day):
        years -= 1
    if years < 0:
        return None
    return years


def write_worker_profile(worker, profile) -> None:
    data = profile.model_dump()
    for key in _PROFILE_FIELDS:
        setattr(worker, key, data[key])


def read_worker_profile(worker):
    from src.api.schemas import WorkerProfile

    weekdays = worker.available_weekdays if isinstance(worker.available_weekdays, list) else []
    day_hours = worker.available_day_hours if isinstance(worker.available_day_hours, list) else []
    history = worker.work_history if isinstance(worker.work_history, list) else []
    return WorkerProfile.model_validate(
        {
            "birth_date": worker.birth_date,
            "marital_status": worker.marital_status,
            "postal_code": worker.postal_code,
            "address": worker.address,
            "hometown": worker.hometown,
            "nearest_station": worker.nearest_station,
            "station_walk_minutes": worker.station_walk_minutes,
            "final_education": worker.final_education,
            "licenses_qualifications": worker.licenses_qualifications,
            "car_drive_ok": worker.car_drive_ok,
            "hiace_drive_ok": worker.hiace_drive_ok,
            "truck_drive": worker.truck_drive,
            "work_history": [row for row in history if isinstance(row, dict)],
            "ploomx_sales_experience": worker.ploomx_sales_experience,
            "smoking_ok": worker.smoking_ok,
            "lucky_self": worker.lucky_self,
            "hobbies": worker.hobbies,
            "personality_strengths": worker.personality_strengths,
            "personality_weaknesses": worker.personality_weaknesses,
            "club_activity": worker.club_activity,
            "motivation": worker.motivation,
            "self_pr": worker.self_pr,
            "life_goal": worker.life_goal,
            "desired_income": worker.desired_income,
            "available_days_per_week": worker.available_days_per_week,
            "available_weekdays": [day for day in weekdays if day in WEEKDAYS],
            "available_day_hours": [row for row in day_hours if isinstance(row, dict)],
            "available_time_from": worker.available_time_from,
            "available_time_to": worker.available_time_to,
            "available_start_date": worker.available_start_date,
            "payment_terms_ok": worker.payment_terms_ok,
        }
    )
