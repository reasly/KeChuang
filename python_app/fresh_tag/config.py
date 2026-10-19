from dataclasses import dataclass
from pathlib import Path


APP_NAME = "海鲜鲜度倒计时"
SERIAL_BAUD = 9600
REFERENCE_TEMP_C = 4.0
Q10 = 2.0
WARNING_FRACTION = 0.20
CRITICAL_FRACTION = 0.08
OFFLINE_SECONDS = 8.0
MAX_SAMPLE_GAP_SECONDS = 10.0
NORMAL_TIME_SCALE = 1.0
DEMO_TIME_SCALE = 1200.0
MAX_HISTORY_POINTS = 360

APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = APP_DIR / "data"
STATE_FILE = DATA_DIR / "freshness_state.json"


@dataclass(frozen=True)
class SpeciesProfile:
    code: str
    name: str
    icon: str
    base_hours: float
    color: str


# 这里的基准时长是科创演示参数，不是食品安全结论；应通过实测实验重新标定。
SPECIES = {
    "FISH": SpeciesProfile("FISH", "鱼类", "🐟", 48.0, "#42A5F5"),
    "SHRIMP": SpeciesProfile("SHRIMP", "虾类", "🦐", 36.0, "#FF8A65"),
    "CRAB": SpeciesProfile("CRAB", "蟹类", "🦀", 36.0, "#EF5350"),
    "SHELL": SpeciesProfile("SHELL", "贝类", "🐚", 24.0, "#AB47BC"),
}

SPECIES_ALIASES = {
    "鱼": "FISH", "鱼类": "FISH", "FISH": "FISH",
    "虾": "SHRIMP", "虾类": "SHRIMP", "SHRIMP": "SHRIMP",
    "蟹": "CRAB", "蟹类": "CRAB", "CRAB": "CRAB",
    "贝": "SHELL", "贝类": "SHELL", "SHELL": "SHELL",
}
