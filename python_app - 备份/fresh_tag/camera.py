from typing import Optional


def scan_qr(camera_index: int = 0) -> Optional[str]:
    """打开电脑 0 号摄像头；识别成功返回二维码文本，Esc 取消。"""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("缺少 opencv-python，请先安装 requirements.txt") from exc

    camera = cv2.VideoCapture(camera_index)
    if not camera.isOpened():
        camera.release()
        raise RuntimeError("无法打开 0 号摄像头，请关闭占用摄像头的软件")
    detector = cv2.QRCodeDetector()
    result = None
    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                break
            text, points, _ = detector.detectAndDecode(frame)
            if points is not None:
                pts = points.astype(int).reshape(-1, 2)
                for index in range(len(pts)):
                    cv2.line(frame, tuple(pts[index]), tuple(pts[(index + 1) % len(pts)]), (50, 220, 130), 3)
            cv2.putText(frame, "Show QR code - ESC to cancel", (18, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)
            cv2.imshow("Seafood QR Scanner", frame)
            if text:
                result = text.strip()
                cv2.waitKey(350)
                break
            if cv2.waitKey(1) & 0xFF == 27:
                break
    finally:
        camera.release()
        cv2.destroyAllWindows()
    return result
