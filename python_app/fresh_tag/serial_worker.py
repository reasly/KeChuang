import queue
import threading
from typing import List, Optional

from .config import SERIAL_BAUD


def list_serial_ports() -> List[str]:
    try:
        from serial.tools import list_ports
        return [port.device for port in list_ports.comports()]
    except ImportError:
        return []


class SerialWorker:
    def __init__(self, output: "queue.Queue[tuple]") -> None:
        self.output = output
        self._serial = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    @property
    def connected(self) -> bool:
        return bool(self._serial and self._serial.is_open)

    def connect(self, port: str) -> None:
        if self.connected:
            self.disconnect()
        try:
            import serial
        except ImportError as exc:
            raise RuntimeError("缺少 pyserial，请先运行 pip install -r requirements.txt") from exc
        self._serial = serial.Serial(port, SERIAL_BAUD, timeout=0.5)
        self._stop.clear()
        self._thread = threading.Thread(target=self._read_loop, name="rf-serial", daemon=True)
        self._thread.start()

    def _read_loop(self) -> None:
        while not self._stop.is_set() and self.connected:
            try:
                raw = self._serial.readline()
                if raw:
                    self.output.put(("serial", raw.decode("utf-8", errors="ignore").strip()))
            except Exception as exc:  # 串口拔出时把错误交给界面显示
                self.output.put(("error", f"串口读取失败：{exc}"))
                break

    def disconnect(self) -> None:
        self._stop.set()
        serial_port, self._serial = self._serial, None
        if serial_port:
            try:
                serial_port.close()
            except Exception:
                pass
