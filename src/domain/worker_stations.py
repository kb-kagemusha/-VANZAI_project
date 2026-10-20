"""追加駅の共通入力形式。1駅目は既存の列を維持する。"""
import json

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class WorkerStation(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    nearest_station: str = Field(min_length=1, max_length=100)
    station_walk_minutes: int | None = Field(None, ge=0, le=300, strict=True)


def parse_additional_stations(value):
    if isinstance(value, str):
        value = json.loads(value)
    return [station.model_dump() for station in TypeAdapter(list[WorkerStation]).validate_python(value)]


def station_comparison_value(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) if value else ""
