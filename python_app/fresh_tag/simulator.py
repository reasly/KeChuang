import queue
import random
import threading
import time
from typing import Optional

# 前三段各保持 10 秒，最后停在 34°C，不再循环。
DEMO_STAGES = ((4.0, 10.0), (14.0, 10.0), (24.0, 10.0), (34.0, None))
DEMO_NOISE_C = 1.0


def demo_temperature(elapsed: float) -> float:
    cursor = 0.0
    for temperature, duration in DEMO_STAGES:
        if duration is None:
            return temperature
        cursor += duration
        if elapsed < cursor:
            return temperature
    return DEMO_STAGES[-1][0]


def demo_reading(elapsed: float, noise: float) -> float:
    """设定温度附近的读数，偏离不超过 ±1°C。"""
    limited = max(-DEMO_NOISE_C, min(DEMO_NOISE_C, noise))
    return demo_temperature(elapsed) + limited


class TemperatureSimulator:
    def __init__(self, output: "queue.Queue[tuple]") -> None:
        self.output = output
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="temperature-demo", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        sequence = 0
        started = time.monotonic()
        last_stage: Optional[float] = None
        while not self._stop.is_set():
            elapsed = time.monotonic() - started
            stage = demo_temperature(elapsed)
            if last_stage is None:
                last_stage = stage
            elif stage > last_stage:
                last_stage = stage
                self.output.put(("demo_stage", stage))
            temperature = demo_reading(elapsed, random.uniform(-DEMO_NOISE_C, DEMO_NOISE_C))
            self.output.put(("demo", f"BOX01,{temperature:.2f},{sequence}"))
            sequence += 1
            time.sleep(1.0)
