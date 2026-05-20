import base64
import json
from typing import Any, Dict, Tuple


def decode_hidden(data: bytes) -> Tuple[Any, Dict]:
    report = {"strategy": None, "attempts": []}

    # Binary/UTF-8 path.
    try:
        text = data.decode("utf-8").strip("\x00").strip()
        if text:
            try:
                obj = json.loads(text)
                report["strategy"] = "binary_json"
                report["attempts"].append({"name": "binary", "ok": True})
                return obj, report
            except Exception:
                report["strategy"] = "binary_text"
                report["attempts"].append({"name": "binary", "ok": True})
                return text, report
    except Exception as e:
        report["attempts"].append({"name": "binary", "ok": False, "error": str(e)})

    # Base64 path.
    try:
        b64 = base64.b64decode(data, validate=True)
        text = b64.decode("utf-8").strip("\x00").strip()
        try:
            obj = json.loads(text)
            report["strategy"] = "base64_json"
            report["attempts"].append({"name": "base64", "ok": True})
            return obj, report
        except Exception:
            report["strategy"] = "base64_text"
            report["attempts"].append({"name": "base64", "ok": True})
            return text, report
    except Exception as e:
        report["attempts"].append({"name": "base64", "ok": False, "error": str(e)})

    # Hex path.
    try:
        hx = bytes.fromhex(data.decode("ascii").strip())
        text = hx.decode("utf-8").strip("\x00").strip()
        try:
            obj = json.loads(text)
            report["strategy"] = "hex_json"
            report["attempts"].append({"name": "hex", "ok": True})
            return obj, report
        except Exception:
            report["strategy"] = "hex_text"
            report["attempts"].append({"name": "hex", "ok": True})
            return text, report
    except Exception as e:
        report["attempts"].append({"name": "hex", "ok": False, "error": str(e)})

    return None, report

