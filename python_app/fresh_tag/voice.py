import queue
import sys
import threading


class VoiceAnnouncer:
    """离线语音播报。Windows 优先用同步 SAPI，避免 pyttsx3 事件泵卡死/只响一次。"""

    def __init__(self) -> None:
        self._messages: "queue.Queue[str]" = queue.Queue()
        threading.Thread(target=self._run, name="voice", daemon=True).start()

    def speak(self, message: str) -> None:
        text = (message or "").strip()
        if not text:
            return
        # 演示加速时状态跳变很快，丢掉过旧提醒，避免语音严重滞后
        while self._messages.qsize() >= 3:
            try:
                self._messages.get_nowait()
            except queue.Empty:
                break
        self._messages.put(text)

    def _run(self) -> None:
        self._init_com()
        while True:
            message = self._messages.get()
            if not self._speak_sapi(message):
                if not self._speak_pyttsx3(message):
                    self._beep()

    @staticmethod
    def _init_com() -> None:
        if sys.platform != "win32":
            return
        try:
            import pythoncom

            pythoncom.CoInitialize()
        except Exception:
            pass

    def _speak_sapi(self, message: str) -> bool:
        if sys.platform != "win32":
            return False
        try:
            import comtypes.client

            speaker = comtypes.client.CreateObject("SAPI.SpVoice")
            self._prefer_chinese_voice(speaker)
            # 0 = 同步播报，不依赖 pyttsx3 的消息泵，连续播报更稳
            speaker.Speak(message, 0)
            return True
        except Exception:
            return False

    @staticmethod
    def _prefer_chinese_voice(speaker) -> None:
        try:
            voices = speaker.GetVoices()
        except Exception:
            return
        keywords = (
            "chinese",
            "中文",
            "zh-cn",
            "zh_cn",
            "huihui",
            "yaoyao",
            "kangkang",
            "xiaoxiao",
            "xiaoyi",
            "yunxi",
            "yunyang",
        )
        for index in range(voices.Count):
            try:
                token = voices.Item(index)
                blob = f"{token.GetDescription()} {token.Id}".lower()
            except Exception:
                continue
            if any(key in blob for key in keywords):
                speaker.Voice = token
                return

    def _speak_pyttsx3(self, message: str) -> bool:
        engine = None
        try:
            import pyttsx3

            # 每次新建引擎：复用同一实例时，Windows/SAPI 上第二次常失效
            engine = pyttsx3.init()
            engine.setProperty("rate", 170)
            self._prefer_chinese_pyttsx3(engine)
            engine.say(message)
            engine.runAndWait()
            return True
        except Exception:
            return False
        finally:
            if engine is not None:
                try:
                    engine.stop()
                except Exception:
                    pass

    @staticmethod
    def _prefer_chinese_pyttsx3(engine) -> None:
        try:
            voices = engine.getProperty("voices") or []
        except Exception:
            return
        keywords = ("chinese", "中文", "zh-cn", "zh_cn", "huihui")
        for voice in voices:
            blob = f"{getattr(voice, 'name', '')} {getattr(voice, 'id', '')}".lower()
            if any(key in blob for key in keywords):
                try:
                    engine.setProperty("voice", voice.id)
                except Exception:
                    pass
                return

    @staticmethod
    def _beep() -> None:
        try:
            import winsound

            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass
