"""结构校验工具：确认 .mix 包含可解析的图形 XML、配置与 Base64 代码。"""
import base64
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def validate(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    xml_end = text.index("</xml>") + len("</xml>")
    config_start = text.index("<config>", xml_end) + len("<config>")
    config_end = text.index("</config>", config_start)
    code_start = text.index("<code>", config_end) + len("<code>")
    code_end = text.index("</code>", code_start)
    root = ET.fromstring(text[:xml_end])
    json.loads(text[config_start:config_end])
    code = base64.b64decode(text[code_start:code_end]).decode("utf-8")
    block_types = {block.attrib["type"] for block in root.iter("block")}
    radio_line = "RF24 radio(7,8)" if "发送端" in path.name else "RF24 radio(10,9)"
    required_code = ("void setup()", "void loop()", radio_line)
    if not all(piece in code for piece in required_code):
        raise AssertionError("嵌入代码不完整")
    return f"通过：{path.name}；{len(list(root.iter('block')))} 个图形块；{len(block_types)} 种块"


if __name__ == "__main__":
    folder = Path(__file__).resolve().parent
    for mix_file in sorted(folder.glob("*.mix")):
        print(validate(mix_file))
