from dataclasses import dataclass
import re

from .config import SPECIES, SPECIES_ALIASES


IDENTIFIER = re.compile(r"^[A-Z0-9_-]{1,12}$")


@dataclass(frozen=True)
class Telemetry:
    box_id: str
    temperature_c: float
    sequence: int


@dataclass(frozen=True)
class QrPayload:
    species_code: str
    box_id: str
    item_id: str
    raw: str


def parse_telemetry(line: str) -> Telemetry:
    """解析 RF 接收端输出：BOX01,3.75,123。"""
    cleaned = line.strip().strip("\x00")
    parts = [part.strip() for part in cleaned.split(",")]
    if len(parts) != 3:
        raise ValueError("温度数据必须是：箱号,温度,序号")
    box_id = parts[0].upper()
    if not IDENTIFIER.fullmatch(box_id):
        raise ValueError("箱号只能包含字母、数字、下划线或短横线")
    try:
        temperature = float(parts[1])
        sequence = int(parts[2])
    except ValueError as exc:
        raise ValueError("温度或序号不是数字") from exc
    if not -40.0 < temperature < 80.0:
        raise ValueError("温度超出合理范围")
    if sequence < 0:
        raise ValueError("序号不能为负数")
    return Telemetry(box_id, temperature, sequence)


def parse_qr(text: str) -> QrPayload:
    """解析二维码：SEAFOOD|FISH|BOX01|F001。"""
    raw = text.strip()
    parts = [part.strip() for part in raw.split("|")]
    if len(parts) != 4 or parts[0].upper() != "SEAFOOD":
        raise ValueError("二维码格式应为 SEAFOOD|品种|箱号|产品编号")
    species_code = SPECIES_ALIASES.get(parts[1].upper(), SPECIES_ALIASES.get(parts[1]))
    if species_code not in SPECIES:
        raise ValueError("品种只支持 FISH、SHRIMP、CRAB、SHELL")
    box_id, item_id = parts[2].upper(), parts[3].upper()
    if not IDENTIFIER.fullmatch(box_id) or not IDENTIFIER.fullmatch(item_id):
        raise ValueError("箱号和产品编号只能包含字母、数字、下划线或短横线")
    return QrPayload(species_code, box_id, item_id, raw)


def make_qr_text(species_code: str, box_id: str, item_id: str) -> str:
    return f"SEAFOOD|{species_code.upper()}|{box_id.upper()}|{item_id.upper()}"
