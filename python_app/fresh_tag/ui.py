import ctypes
import queue
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Dict, Optional

from .camera import scan_qr
from .config import APP_NAME, DEMO_TIME_SCALE, NORMAL_TIME_SCALE, REFERENCE_TEMP_C, SERIAL_BAUD
from .models import FreshnessStore, SeafoodItem
from .protocol import parse_qr, parse_telemetry
from .serial_worker import SerialWorker, list_serial_ports
from .simulator import TemperatureSimulator
from .storage import load_store, save_store
from .voice import VoiceAnnouncer


# 高对比、明快的海洋主题；界面不依赖 Emoji，避免不同电脑出现低清或错形字。
BG = "#F3F7FF"
INK = "#16324F"
MUTED = "#6E8299"
CARD = "#FFFFFF"
DEEP_BLUE = "#0B1F3A"
OCEAN = "#1479E8"
CYAN = "#18C7C8"
MINT = "#26BE8B"
CORAL = "#FF6B6B"
ORANGE = "#F59E42"
YELLOW = "#FFC857"
VIOLET = "#7357E8"
FRESH = "#24B47E"
WARNING = "#F29E38"
DANGER = "#E94F64"
FONT = "Microsoft YaHei UI"

SPECIES_MARKS = {"FISH": "鱼", "SHRIMP": "虾", "CRAB": "蟹", "SHELL": "贝"}


def enable_high_dpi() -> None:
    """让 Windows 在 125%/150% 缩放下仍使用清晰的原生像素绘制。"""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def format_remaining(hours: float) -> str:
    total_minutes = max(0, round(hours * 60))
    return f"{total_minutes // 60} 小时 {total_minutes % 60} 分"


def blend(start: str, end: str, fraction: float) -> str:
    start_rgb = tuple(int(start[index:index + 2], 16) for index in (1, 3, 5))
    end_rgb = tuple(int(end[index:index + 2], 16) for index in (1, 3, 5))
    rgb = tuple(round(a + (b - a) * fraction) for a, b in zip(start_rgb, end_rgb))
    return "#" + "".join(f"{value:02x}" for value in rgb)


class MiniProgress(tk.Canvas):
    def __init__(self, master, height: int = 7, **kwargs):
        super().__init__(master, height=height, bg=kwargs.pop("bg", CARD), highlightthickness=0, **kwargs)
        self.fraction = 0.0
        self.color = MINT
        self.bind("<Configure>", lambda _event: self.redraw())

    def set(self, fraction: float, color: str) -> None:
        self.fraction = max(0.0, min(1.0, fraction))
        self.color = color
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        width, height = max(2, self.winfo_width()), max(2, self.winfo_height())
        radius = height / 2
        self.create_rectangle(radius, 0, width - radius, height, fill="#E6EDF6", outline="")
        self.create_oval(0, 0, height, height, fill="#E6EDF6", outline="")
        self.create_oval(width - height, 0, width, height, fill="#E6EDF6", outline="")
        filled = width * self.fraction
        if filled <= 1:
            return
        if filled < height:
            self.create_oval(0, 0, filled, height, fill=self.color, outline="")
        else:
            self.create_rectangle(radius, 0, filled - radius, height, fill=self.color, outline="")
            self.create_oval(0, 0, height, height, fill=self.color, outline="")
            self.create_oval(filled - height, 0, filled, height, fill=self.color, outline="")


class TrendChart(tk.Canvas):
    def __init__(self, master, **kwargs):
        super().__init__(master, background=CARD, highlightthickness=0, **kwargs)
        self.item: Optional[SeafoodItem] = None
        self.bind("<Configure>", lambda _event: self.redraw())

    def show(self, item: Optional[SeafoodItem]) -> None:
        self.item = item
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        width, height = max(self.winfo_width(), 320), max(self.winfo_height(), 210)
        left, top, right, bottom = 62, 50, width - 58, height - 44
        self.create_text(22, 17, text="温度与剩余鲜度趋势", anchor="w", fill=INK, font=(FONT, 13, "bold"))
        self.create_oval(width - 250, 12, width - 238, 24, fill=OCEAN, outline="")
        self.create_text(width - 232, 18, text="温度", anchor="w", fill=MUTED, font=(FONT, 9))
        self.create_oval(width - 166, 12, width - 154, 24, fill=MINT, outline="")
        self.create_text(width - 148, 18, text="剩余鲜度", anchor="w", fill=MUTED, font=(FONT, 9))

        if not self.item or len(self.item.history) < 2:
            self.create_oval(width / 2 - 30, height / 2 - 44, width / 2 + 30, height / 2 + 16, fill="#E8F3FF", outline="")
            self.create_text(width / 2, height / 2 - 14, text="温", fill=OCEAN, font=(FONT, 20, "bold"))
            self.create_text(width / 2, height / 2 + 38, text="等待至少两条温度数据", fill=MUTED, font=(FONT, 10))
            return

        points = self.item.history[-60:]
        temperatures = [point.temperature_c for point in points]
        temp_min = min(-2.0, min(temperatures) - 1.0)
        temp_max = max(14.0, max(temperatures) + 1.0)
        for fraction in (0, 0.25, 0.5, 0.75, 1):
            y = bottom - fraction * (bottom - top)
            self.create_line(left, y, right, y, fill="#DFE8F4", dash=(4, 5))
            temp_label = temp_min + fraction * (temp_max - temp_min)
            self.create_text(left - 10, y, text=f"{temp_label:.0f}°", anchor="e", fill=MUTED, font=(FONT, 8))
            self.create_text(right + 10, y, text=f"{fraction * 100:.0f}%", anchor="w", fill=MUTED, font=(FONT, 8))

        threshold_y = bottom - (REFERENCE_TEMP_C - temp_min) / (temp_max - temp_min) * (bottom - top)
        self.create_line(left, threshold_y, right, threshold_y, fill=CORAL, dash=(7, 5), width=2)
        self.create_text(left + 6, threshold_y - 11, text="4°C 参考线", anchor="w", fill=CORAL, font=(FONT, 8, "bold"))

        def x_at(index: int) -> float:
            return left + index / (len(points) - 1) * (right - left)

        temp_xy, remain_xy = [], []
        for index, point in enumerate(points):
            x = x_at(index)
            temp_y = bottom - (point.temperature_c - temp_min) / (temp_max - temp_min) * (bottom - top)
            remain_fraction = max(0.0, min(1.0, point.remaining_hours / self.item.profile.base_hours))
            remain_y = bottom - remain_fraction * (bottom - top)
            temp_xy.extend((x, temp_y))
            remain_xy.extend((x, remain_y))

        temp_fill = [left, bottom, *temp_xy, right, bottom]
        self.create_polygon(*temp_fill, fill="#E8F3FF", outline="")
        self.create_line(*temp_xy, fill=OCEAN, width=4, smooth=True, splinesteps=20)
        self.create_line(*remain_xy, fill=MINT, width=4, smooth=True, splinesteps=20)
        self.create_oval(temp_xy[-2] - 5, temp_xy[-1] - 5, temp_xy[-2] + 5, temp_xy[-1] + 5, fill=CARD, outline=OCEAN, width=3)
        self.create_oval(remain_xy[-2] - 5, remain_xy[-1] - 5, remain_xy[-2] + 5, remain_xy[-1] + 5, fill=CARD, outline=MINT, width=3)
        self.create_text(left, height - 15, text="较早", anchor="w", fill="#9AAABC", font=(FONT, 8))
        self.create_text(right, height - 15, text="现在", anchor="e", fill="#9AAABC", font=(FONT, 8))


class FreshTagApp:
    def __init__(self) -> None:
        enable_high_dpi()
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} · 科创展示系统")
        self.root.geometry("1280x960")
        self.root.minsize(1080, 820)
        self.root.configure(bg=BG)
        self.root.option_add("*Font", (FONT, 10))
        try:
            dpi = self.root.winfo_fpixels("1i")
            self.root.tk.call("tk", "scaling", max(1.0, dpi / 72.0))
        except tk.TclError:
            pass

        self.events: "queue.Queue[tuple]" = queue.Queue()
        self.store: FreshnessStore = load_store()
        self.serial = SerialWorker(self.events)
        self.simulator = TemperatureSimulator(self.events)
        self.voice = VoiceAnnouncer()
        self.demo_mode = False
        self._logged_demo_pause = False
        self.selected_id: Optional[str] = next(iter(self.store.items), None)
        self.item_rows: Dict[str, tk.Frame] = {}
        self._build_styles()
        self._build_ui()
        self._log("调试窗口已启动，等待连接接收端")
        self._refresh_ports()
        self._refresh_all()
        self.root.after(100, self._process_events)
        self.root.after(1000, self._heartbeat)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _build_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Ocean.TCombobox", padding=8, fieldbackground="white", background="white", bordercolor="#B8D2EE", lightcolor="#B8D2EE", darkcolor="#B8D2EE")
        style.configure("Ocean.Vertical.TScrollbar", background="#B7C8DB", troughcolor=BG, bordercolor=BG, arrowcolor=INK)

    def _build_ui(self) -> None:
        self.header = tk.Canvas(self.root, height=112, highlightthickness=0)
        self.header.pack(fill="x")
        self.header.bind("<Configure>", self._draw_header)

        controls = tk.Frame(self.header, bg="#10345C", padx=10, pady=10)
        self.port_box = ttk.Combobox(controls, width=10, state="readonly", style="Ocean.TCombobox")
        self.port_box.grid(row=0, column=0, padx=4)
        self.connect_button = self._button(controls, "连接设备", self._toggle_serial, OCEAN)
        self.connect_button.grid(row=0, column=1, padx=4)
        self._button(controls, "扫码登记", self._start_scan, CYAN).grid(row=0, column=2, padx=4)
        self.demo_button = self._button(controls, "演示模式", self._toggle_demo, ORANGE)
        self.demo_button.grid(row=0, column=3, padx=4)
        self.header_controls = self.header.create_window(1255, 56, window=controls, anchor="e")

        notice = tk.Frame(self.root, bg="#FFF6D9", height=40)
        notice.pack(fill="x")
        notice.pack_propagate(False)
        tk.Frame(notice, bg=YELLOW, width=5).pack(side="left", fill="y")
        tk.Label(
            notice,
            text="科创实验模型  ·  倒计时展示温度对鲜度的影响，不替代食品安全检测与食用判断",
            bg="#FFF6D9",
            fg="#805A17",
            font=(FONT, 9, "bold"),
        ).pack(side="left", padx=18)

        self._build_debug_panel()

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=22, pady=18)

        left = tk.Frame(body, bg=BG, width=365)
        left.pack(side="left", fill="y", padx=(0, 16))
        left.pack_propagate(False)
        title_row = tk.Frame(left, bg=BG)
        title_row.pack(fill="x", pady=(0, 12))
        tk.Label(title_row, text="海鲜标签", bg=BG, fg=INK, font=(FONT, 16, "bold")).pack(side="left")
        self.count_label = tk.Label(title_row, text="0 件", bg="#DFEBFA", fg=OCEAN, padx=12, pady=5, font=(FONT, 9, "bold"))
        self.count_label.pack(side="right")

        list_shell = tk.Frame(left, bg=CARD, highlightbackground="#D7E3F1", highlightthickness=1)
        list_shell.pack(fill="both", expand=True)
        self.list_canvas = tk.Canvas(list_shell, bg="#F8FAFE", highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_shell, orient="vertical", command=self.list_canvas.yview, style="Ocean.Vertical.TScrollbar")
        self.list_frame = tk.Frame(self.list_canvas, bg="#F8FAFE")
        self.list_window = self.list_canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.list_frame.bind("<Configure>", lambda _e: self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all")))
        self.list_canvas.bind("<Configure>", lambda event: self.list_canvas.itemconfigure(self.list_window, width=event.width))
        self.list_canvas.configure(yscrollcommand=scrollbar.set)
        self.list_canvas.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        scrollbar.pack(side="right", fill="y")

        right = tk.Frame(body, bg=CARD, highlightbackground="#D7E3F1", highlightthickness=1)
        right.pack(side="left", fill="both", expand=True)
        top = tk.Frame(right, bg=CARD)
        top.pack(fill="x", padx=24, pady=(20, 10))
        self.detail_mark = tk.Label(top, text="鲜", width=2, bg=OCEAN, fg="white", font=(FONT, 15, "bold"), padx=6, pady=7)
        self.detail_mark.pack(side="left", padx=(0, 12))
        self.detail_title = tk.Label(top, text="请选择一个标签", bg=CARD, fg=INK, font=(FONT, 18, "bold"))
        self.detail_title.pack(side="left")
        self.status_badge = tk.Label(top, text="等待数据", bg="#E9EFF7", fg=MUTED, padx=14, pady=7, font=(FONT, 9, "bold"))
        self.status_badge.pack(side="right")

        metrics = tk.Frame(right, bg=CARD)
        metrics.pack(fill="x", padx=20, pady=4)
        for column in range(3):
            metrics.columnconfigure(column, weight=1, uniform="metric")
        self.metric_temp = self._metric(metrics, 0, "当前温度", "-- °C", "温", "#E8F3FF", OCEAN)
        self.metric_remaining = self._metric(metrics, 1, "预计剩余", "--", "时", "#E7F8F1", MINT)
        self.metric_overtemp = self._metric(metrics, 2, "超温累计", "0 度·分", "累", "#FFF0E2", ORANGE)

        gauge_box = tk.Frame(right, bg="#F8FAFE", padx=16, pady=10)
        gauge_box.pack(fill="x", padx=24, pady=(8, 2))
        gauge_top = tk.Frame(gauge_box, bg="#F8FAFE")
        gauge_top.pack(fill="x")
        tk.Label(gauge_top, text="剩余鲜度", bg="#F8FAFE", fg=INK, font=(FONT, 10, "bold")).pack(side="left")
        self.gauge_label = tk.Label(gauge_top, text="--", bg="#F8FAFE", fg=MINT, font=(FONT, 10, "bold"))
        self.gauge_label.pack(side="right")
        self.gauge = MiniProgress(gauge_box, height=10, bg="#F8FAFE")
        self.gauge.pack(fill="x", pady=(8, 0))

        self.chart = TrendChart(right, height=305)
        self.chart.pack(fill="both", expand=True, padx=20, pady=(8, 8))

        footer = tk.Frame(right, bg=CARD)
        footer.pack(fill="x", padx=24, pady=(0, 18))
        self.connection_label = tk.Label(footer, text="● 接收设备未连接", bg=CARD, fg=MUTED, font=(FONT, 9, "bold"))
        self.connection_label.pack(side="left")
        self._button(footer, "测试语音", self._test_voice, VIOLET).pack(side="right")
        self._button(footer, "清空数据", self._clear_data, "#7890A8").pack(side="right", padx=8)

    def _build_debug_panel(self) -> None:
        panel = tk.Frame(self.root, bg="#0E1C2E", highlightbackground="#16324F", highlightthickness=1)
        panel.pack(side="bottom", fill="x", padx=22, pady=(0, 16))
        columns = tk.Frame(panel, bg="#0E1C2E")
        columns.pack(fill="both", expand=True, padx=10, pady=(8, 10))
        columns.columnconfigure(0, weight=1, uniform="debug")
        columns.columnconfigure(1, weight=1, uniform="debug")
        self.rx_text = self._debug_column(columns, 0, "无线温度", "等待无线温度")
        self.ops_text = self._debug_column(columns, 1, "操作记录", "串口、扫码和登记会显示在这里")

    def _debug_column(self, master, column: int, title: str, hint: str) -> tk.Text:
        column_frame = tk.Frame(master, bg="#0E1C2E")
        column_frame.grid(row=0, column=column, sticky="nsew", padx=6)
        bar = tk.Frame(column_frame, bg="#0E1C2E")
        bar.pack(fill="x", pady=(0, 4))
        tk.Label(bar, text=title, bg="#0E1C2E", fg="#9FD4FF", font=(FONT, 10, "bold")).pack(side="left")
        tk.Button(
            bar,
            text="清空",
            command=lambda: self._clear_debug(column_frame.text),
            bg="#1C3A5A",
            fg="white",
            activebackground="#24507A",
            activeforeground="white",
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            padx=10,
            pady=3,
            font=(FONT, 8, "bold"),
        ).pack(side="right")
        shell = tk.Frame(column_frame, bg="#0B1726")
        shell.pack(fill="both", expand=True)
        text = tk.Text(
            shell,
            height=8,
            bg="#0B1726",
            fg="#D6E4F0",
            insertbackground="#D6E4F0",
            relief="flat",
            borderwidth=0,
            wrap="char",
            font=("Consolas", 10),
            state="disabled",
            padx=8,
            pady=6,
        )
        column_frame.text = text
        scroll = tk.Scrollbar(shell, command=text.yview, bg="#16324F", troughcolor="#0B1726", activebackground="#2A4A6E")
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        for name, color in (
            ("info", "#D6E4F0"),
            ("ok", "#7DFFC3"),
            ("rx", "#9FD4FF"),
            ("warn", "#FFC857"),
            ("error", "#FF8B9A"),
            ("time", "#7F93A8"),
            ("hint", "#7F93A8"),
        ):
            text.tag_configure(name, foreground=color)
        text.bind("<MouseWheel>", lambda event, widget=text: self._scroll_debug(event, widget))
        self._write_log(text, hint, "hint")
        return text

    def _scroll_debug(self, event, widget: tk.Text) -> str:
        widget.yview_scroll(int(-event.delta / 120), "units")
        return "break"

    def _write_log(self, widget: tk.Text, message: str, tag: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        widget.configure(state="normal")
        widget.insert("end", f"[{stamp}] ", "time")
        widget.insert("end", f"{message}\n", tag)
        line_count = int(widget.index("end-1c").split(".")[0])
        if line_count > 300:
            widget.delete("1.0", f"{line_count - 300}.0")
        widget.configure(state="disabled")
        widget.see("end")

    def _log(self, message: str, tag: str = "info", channel: str = "ops") -> None:
        widget = self.rx_text if channel == "rx" else self.ops_text
        self._write_log(widget, message, tag)

    def _clear_debug(self, widget: tk.Text) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.configure(state="disabled")
        self._write_log(widget, "日志已清空", "info")

    def _draw_header(self, event) -> None:
        width, height = event.width, event.height
        self.header.delete("header-art")
        for x in range(0, width, 8):
            color = blend(DEEP_BLUE, "#174D78", x / max(width, 1))
            self.header.create_rectangle(x, 0, x + 9, height, fill=color, outline="", tags="header-art")
        self.header.create_oval(-40, 48, 110, 198, fill="#17669B", outline="", tags="header-art")
        self.header.create_oval(30, 74, 170, 214, fill="#187FA8", outline="", tags="header-art")
        self.header.create_oval(28, 24, 78, 74, fill=CYAN, outline="", tags="header-art")
        self.header.create_text(53, 49, text="鲜", fill="white", font=(FONT, 17, "bold"), tags="header-art")
        self.header.create_text(96, 40, text="海鲜鲜度倒计时", anchor="w", fill="white", font=(FONT, 23, "bold"), tags="header-art")
        self.header.create_text(98, 76, text="温度全程跟随  ·  鲜度动态计算  ·  临期及时提醒", anchor="w", fill="#BCEEFF", font=(FONT, 10), tags="header-art")
        self.header.coords(self.header_controls, width - 18, height / 2)
        self.header.tag_lower("header-art")

    def _button(self, master, text: str, command, color: str) -> tk.Button:
        return tk.Button(
            master,
            text=text,
            command=command,
            bg=color,
            fg="white",
            activebackground=blend(color, "#FFFFFF", 0.12),
            activeforeground="white",
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            padx=14,
            pady=8,
            font=(FONT, 9, "bold"),
        )

    def _metric(self, master, column: int, title: str, value: str, symbol: str, background: str, accent: str) -> tk.Label:
        frame = tk.Frame(master, bg=background, padx=14, pady=13, highlightbackground=blend(background, accent, 0.16), highlightthickness=1)
        frame.grid(row=0, column=column, sticky="nsew", padx=5)
        top = tk.Frame(frame, bg=background)
        top.pack(fill="x")
        tk.Label(top, text=symbol, bg=accent, fg="white", width=2, padx=2, pady=3, font=(FONT, 9, "bold")).pack(side="left")
        tk.Label(top, text=title, bg=background, fg=MUTED, font=(FONT, 9, "bold")).pack(side="left", padx=8)
        label = tk.Label(frame, text=value, bg=background, fg=INK, font=(FONT, 15, "bold"))
        label.pack(anchor="w", pady=(10, 0))
        return label

    def _refresh_ports(self) -> None:
        ports = list_serial_ports()
        self.port_box["values"] = ports
        if ports and not self.port_box.get():
            self.port_box.current(0)

    def _toggle_serial(self) -> None:
        if self.serial.connected:
            port = self.port_box.get() or "串口"
            self.serial.disconnect()
            self.connect_button.configure(text="连接设备")
            self.connection_label.configure(text="● 接收设备未连接", fg=MUTED)
            self._log(f"已断开 {port}", "warn")
            return
        port = self.port_box.get()
        if not port:
            self._refresh_ports()
            self._log("连接失败：没有找到串口", "error")
            messagebox.showinfo("没有串口", "请插入电脑端 RF Nano，再点击连接设备。")
            return
        try:
            self.serial.connect(port)
            self.connect_button.configure(text="断开设备")
            self.connection_label.configure(text=f"● {port}  ·  {SERIAL_BAUD} bps", fg=FRESH)
            self._log(f"连接成功 {port} · {SERIAL_BAUD} bps", "ok")
        except RuntimeError as exc:
            self._log(f"连接失败：{exc}", "error")
            messagebox.showerror("连接失败", str(exc))

    def _start_scan(self) -> None:
        self._log("正在打开摄像头扫码")

        def worker() -> None:
            try:
                text = scan_qr(0)
                if text:
                    self.events.put(("qr", text))
                else:
                    self.events.put(("log", ("warn", "扫码结束，没有读到二维码")))
            except RuntimeError as exc:
                self.events.put(("error", str(exc)))

        threading.Thread(target=worker, name="qr-camera", daemon=True).start()

    def _toggle_demo(self) -> None:
        if self.demo_mode:
            self.simulator.stop()
            self.demo_mode = False
            self._logged_demo_pause = False
            self.demo_button.configure(text="演示模式")
            self.connection_label.configure(text="● 演示已停止", fg=MUTED)
            self._log("演示模式已停止", "warn")
            return
        demo_items = []
        for text in ("SEAFOOD|FISH|BOX01|F001", "SEAFOOD|SHRIMP|BOX01|S001", "SEAFOOD|CRAB|BOX01|C001"):
            demo_items.append(self.store.register(parse_qr(text)))
        self.demo_mode = True
        self.store.begin_demo("BOX01")
        self.selected_id = demo_items[0].item_id
        self.simulator.start()
        self.demo_button.configure(text="停止演示")
        self.connection_label.configure(text=f"● 模拟温度  ·  时间 ×{int(DEMO_TIME_SCALE)}", fg=ORANGE)
        added = "，".join(f"添加{item.profile.name} {item.item_id} 成功" for item in demo_items)
        self._log(added, "ok")
        self.voice.speak("。".join(f"添加{item.profile.name}成功" for item in demo_items) + "。")
        self._log(f"演示模式已启动：4°C、14°C、24°C 各 10 秒，之后保持 34°C，时间加速 ×{int(DEMO_TIME_SCALE)}", "ok")
        self._refresh_all()

    def _process_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "serial":
                    if self.demo_mode:
                        if not self._logged_demo_pause:
                            self._logged_demo_pause = True
                            self._log("演示中，已暂停真实无线温度", "warn")
                        continue
                    self._handle_telemetry(payload, simulated=False)
                elif kind == "demo":
                    if self.demo_mode:
                        self._handle_telemetry(payload, simulated=True)
                elif kind == "demo_stage":
                    if self.demo_mode:
                        self._announce_demo_temperature(payload)
                elif kind == "qr":
                    self._handle_qr(payload)
                elif kind == "log":
                    level, message = payload
                    self._log(message, level)
                elif kind == "error":
                    self._log(f"错误：{payload}", "error")
                    messagebox.showerror("提示", payload)
        except queue.Empty:
            pass
        self.root.after(100, self._process_events)

    def _announce_demo_temperature(self, temperature_c: float) -> None:
        degrees = int(round(float(temperature_c)))
        notice = f"注意，演示温度升高为{degrees}度"
        self._log(f"语音提醒：{notice}", "warn")
        self.voice.speak(f"{notice}。")

    def _handle_telemetry(self, line: str, simulated: bool = False) -> None:
        source = "演示数据" if simulated else "收到"
        try:
            telemetry = parse_telemetry(line)
        except ValueError as exc:
            self._log(f"{source} {line} · 已忽略：{exc}", "warn", channel="rx")
            return
        self._log(
            f"{source} {line} · {telemetry.box_id} {telemetry.temperature_c:.2f}°C 序号 {telemetry.sequence}",
            "rx",
            channel="rx",
        )
        scale = DEMO_TIME_SCALE if simulated else NORMAL_TIME_SCALE
        changed = self.store.ingest(telemetry, time_scale=scale)
        for item in changed:
            status = item.status
            if status != item.last_status and status in ("warning", "critical", "expired"):
                name = f"{item.profile.name}{item.item_id}"
                wording = {"warning": "即将到期", "critical": "剩余时间很少", "expired": "倒计时已结束"}[status]
                notice = f"语音提醒：{name}{wording}"
                self._log(notice, "warn")
                self.voice.speak(f"注意，{name}{wording}，请及时处理。")
            item.last_status = status
        self._refresh_all()

    def _handle_qr(self, text: str) -> None:
        self._log(f"扫到二维码 {text}")
        try:
            item = self.store.register(parse_qr(text))
        except ValueError as exc:
            self._log(f"二维码不正确：{exc}", "error")
            messagebox.showerror("二维码不正确", str(exc))
            return
        self.selected_id = item.item_id
        self._log(f"登记成功 {item.profile.name} {item.item_id} · 箱号 {item.box_id}", "ok")
        self.voice.speak(f"已登记{item.profile.name}，箱号{item.box_id}。")
        self._refresh_all()

    def _test_voice(self) -> None:
        self._log("测试语音：海鲜即将到期，请及时处理")
        self.voice.speak("语音提醒测试。海鲜即将到期，请及时处理。")

    def _select(self, item_id: str) -> None:
        self.selected_id = item_id
        self._refresh_all()

    def _bind_card(self, widget: tk.Widget, item_id: str) -> None:
        widget.bind("<Button-1>", lambda _event, key=item_id: self._select(key))
        for child in widget.winfo_children():
            self._bind_card(child, item_id)

    def _refresh_all(self) -> None:
        self.count_label.configure(text=f"{len(self.store.items)} 件产品")
        for child in self.list_frame.winfo_children():
            child.destroy()
        for item in self.store.items.values():
            selected = item.item_id == self.selected_id
            background = "#F0F7FF" if selected else CARD
            border = item.profile.color if selected else "#DCE6F2"
            row = tk.Frame(self.list_frame, bg=background, highlightbackground=border, highlightthickness=2 if selected else 1, cursor="hand2")
            row.pack(fill="x", pady=6, padx=4)
            tk.Frame(row, bg=item.profile.color, width=6).pack(side="left", fill="y")
            mark = tk.Label(row, text=SPECIES_MARKS.get(item.species_code, "鲜"), bg=item.profile.color, fg="white", width=2, font=(FONT, 17, "bold"), padx=6, pady=10)
            mark.pack(side="left", padx=10, pady=12)

            info = tk.Frame(row, bg=background)
            info.pack(side="left", fill="both", expand=True, pady=12)
            tk.Label(info, text=f"{item.profile.name}  {item.item_id}", bg=background, fg=INK, font=(FONT, 11, "bold")).pack(anchor="w")
            box = self.store.boxes.get(item.box_id)
            temperature = f"{box.temperature_c:.1f}°C" if box and box.temperature_c is not None else "等待温度"
            tk.Label(info, text=f"{item.box_id}  ·  {temperature}", bg=background, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(4, 6))
            mini = MiniProgress(info, height=6, bg=background)
            mini.pack(fill="x", padx=(0, 8))
            color = {"fresh": FRESH, "warning": WARNING, "critical": DANGER, "expired": "#8B1E3F"}[item.status]
            mini.set(item.remaining_fraction, color)

            remaining = tk.Frame(row, bg=background)
            remaining.pack(side="right", padx=10, pady=12)
            tk.Label(remaining, text="预计剩余", bg=background, fg=MUTED, font=(FONT, 8)).pack(anchor="e")
            tk.Label(remaining, text=format_remaining(item.remaining_hours).replace(" ", ""), bg=background, fg=color, font=(FONT, 9, "bold")).pack(anchor="e", pady=(4, 0))
            self._bind_card(row, item.item_id)

        self._refresh_detail()
        save_store(self.store)

    def _refresh_detail(self) -> None:
        item = self.store.items.get(self.selected_id or "")
        if not item:
            self.detail_mark.configure(text="鲜", bg=OCEAN)
            self.detail_title.configure(text="请选择一个海鲜标签")
            self.status_badge.configure(text="等待数据", bg="#E9EFF7", fg=MUTED)
            self.metric_temp.configure(text="-- °C")
            self.metric_remaining.configure(text="--")
            self.metric_overtemp.configure(text="0 度·分")
            self.gauge_label.configure(text="--", fg=MINT)
            self.gauge.set(0, MINT)
            self.chart.show(None)
            return

        box = self.store.boxes.get(item.box_id)
        mark = SPECIES_MARKS.get(item.species_code, "鲜")
        self.detail_mark.configure(text=mark, bg=item.profile.color)
        self.detail_title.configure(text=f"{item.profile.name}  ·  {item.item_id}  /  {item.box_id}")
        online = bool(box and box.online()) or self.demo_mode
        temp_text = f"{box.temperature_c:.1f} °C" if box and box.temperature_c is not None else "-- °C"
        self.metric_temp.configure(text=temp_text)
        self.metric_remaining.configure(text=format_remaining(item.remaining_hours))
        self.metric_overtemp.configure(text=f"{item.overtemp_degree_minutes:.0f} 度·分")

        labels = {
            "fresh": ("状态良好", FRESH),
            "warning": ("临期提醒", WARNING),
            "critical": ("尽快处理", DANGER),
            "expired": ("倒计时结束", "#8B1E3F"),
        }
        label, color = labels[item.status]
        suffix = "  ·  节点在线" if online else "  ·  信号中断"
        self.status_badge.configure(text=label + suffix, bg=color, fg="white")
        percent = max(0, min(100, round(item.remaining_fraction * 100)))
        self.gauge_label.configure(text=f"{percent}%", fg=color)
        self.gauge.set(item.remaining_fraction, color)
        self.chart.show(item)

    def _heartbeat(self) -> None:
        self._refresh_detail()
        self.root.after(1000, self._heartbeat)

    def _clear_data(self) -> None:
        if messagebox.askyesno("清空数据", "确定清空所有标签和累计数据吗？"):
            self.store = FreshnessStore()
            self.selected_id = None
            self._log("已清空标签和累计数据", "warn")
            self._refresh_all()

    def _close(self) -> None:
        self.simulator.stop()
        self.serial.disconnect()
        save_store(self.store)
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
