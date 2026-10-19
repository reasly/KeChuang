from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from math import pow
from typing import Dict, List, Optional

from .config import (
    CRITICAL_FRACTION,
    MAX_HISTORY_POINTS,
    MAX_SAMPLE_GAP_SECONDS,
    OFFLINE_SECONDS,
    Q10,
    REFERENCE_TEMP_C,
    SPECIES,
    WARNING_FRACTION,
)
from .protocol import QrPayload, Telemetry


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def aging_factor(temperature_c: float) -> float:
    """Q10=2：温度每升高 10°C，等效老化速度约增至 2 倍。"""
    return pow(Q10, (temperature_c - REFERENCE_TEMP_C) / 10.0)


@dataclass
class HistoryPoint:
    timestamp: str
    temperature_c: float
    remaining_hours: float


@dataclass
class BoxState:
    box_id: str
    temperature_c: Optional[float] = None
    last_seen: Optional[str] = None
    last_sequence: int = -1

    def online(self, now: Optional[datetime] = None) -> bool:
        if not self.last_seen:
            return False
        now = now or utc_now()
        seen = datetime.fromisoformat(self.last_seen)
        return (now - seen).total_seconds() <= OFFLINE_SECONDS


@dataclass
class SeafoodItem:
    item_id: str
    box_id: str
    species_code: str
    qr_raw: str
    created_at: str
    equivalent_age_hours: float = 0.0
    overtemp_degree_minutes: float = 0.0
    history: List[HistoryPoint] = field(default_factory=list)
    last_status: str = "fresh"

    @property
    def profile(self):
        return SPECIES[self.species_code]

    @property
    def remaining_hours(self) -> float:
        return max(0.0, self.profile.base_hours - self.equivalent_age_hours)

    @property
    def remaining_fraction(self) -> float:
        return self.remaining_hours / self.profile.base_hours

    @property
    def status(self) -> str:
        fraction = self.remaining_fraction
        if fraction <= 0:
            return "expired"
        if fraction <= CRITICAL_FRACTION:
            return "critical"
        if fraction <= WARNING_FRACTION:
            return "warning"
        return "fresh"

    def add_history(self, timestamp: datetime, temperature_c: float) -> None:
        self.history.append(HistoryPoint(timestamp.isoformat(), temperature_c, self.remaining_hours))
        if len(self.history) > MAX_HISTORY_POINTS:
            del self.history[:-MAX_HISTORY_POINTS]


class FreshnessStore:
    def __init__(self) -> None:
        self.boxes: Dict[str, BoxState] = {}
        self.items: Dict[str, SeafoodItem] = {}

    def begin_demo(self, box_id: str, now: Optional[datetime] = None) -> None:
        """让模拟序号从 0 重新计数，并避免把演示前的间隔一次扣掉。"""
        now = now or utc_now()
        box = self.boxes.setdefault(box_id, BoxState(box_id))
        box.last_sequence = -1
        box.last_seen = now.isoformat()

    def register(self, qr: QrPayload, now: Optional[datetime] = None) -> SeafoodItem:
        now = now or utc_now()
        existing = self.items.get(qr.item_id)
        if existing:
            existing.box_id = qr.box_id
            existing.species_code = qr.species_code
            existing.qr_raw = qr.raw
            return existing
        item = SeafoodItem(qr.item_id, qr.box_id, qr.species_code, qr.raw, now.isoformat())
        self.items[item.item_id] = item
        self.boxes.setdefault(qr.box_id, BoxState(qr.box_id))
        return item

    def ingest(self, telemetry: Telemetry, now: Optional[datetime] = None, time_scale: float = 1.0) -> List[SeafoodItem]:
        now = now or utc_now()
        box = self.boxes.setdefault(telemetry.box_id, BoxState(telemetry.box_id))
        changed: List[SeafoodItem] = []
        dt_seconds = 0.0
        if box.last_seen:
            previous_time = datetime.fromisoformat(box.last_seen)
            dt_seconds = max(0.0, min((now - previous_time).total_seconds(), MAX_SAMPLE_GAP_SECONDS))
        previous_temp = box.temperature_c if box.temperature_c is not None else telemetry.temperature_c
        mean_temp = (previous_temp + telemetry.temperature_c) / 2.0

        # 重复或倒序无线包只刷新在线状态，不重复累计鲜度损耗。
        is_new_packet = telemetry.sequence > box.last_sequence
        if is_new_packet and dt_seconds > 0:
            scaled_hours = dt_seconds * max(0.0, time_scale) / 3600.0
            for item in self.items.values():
                if item.box_id != telemetry.box_id:
                    continue
                item.equivalent_age_hours += scaled_hours * aging_factor(mean_temp)
                excess = max(0.0, mean_temp - REFERENCE_TEMP_C)
                item.overtemp_degree_minutes += excess * dt_seconds * max(0.0, time_scale) / 60.0
                item.add_history(now, telemetry.temperature_c)
                changed.append(item)

        box.temperature_c = telemetry.temperature_c
        box.last_seen = now.isoformat()
        box.last_sequence = max(box.last_sequence, telemetry.sequence)
        return changed

    def to_dict(self) -> dict:
        return {
            "boxes": {key: asdict(value) for key, value in self.boxes.items()},
            "items": {key: asdict(value) for key, value in self.items.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FreshnessStore":
        store = cls()
        for key, value in data.get("boxes", {}).items():
            store.boxes[key] = BoxState(**value)
        for key, value in data.get("items", {}).items():
            history = [HistoryPoint(**point) for point in value.pop("history", [])]
            store.items[key] = SeafoodItem(history=history, **value)
        return store
