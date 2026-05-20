import json
from typing import Dict, List


def build_visual_report(per_image_results: List[Dict], reconstructed: Dict) -> Dict:
    suspicious = sum(1 for r in per_image_results if r.get("is_suspicious"))
    return {
        "summary": {
            "total_images": len(per_image_results),
            "suspicious_images": suspicious,
            "clean_images": len(per_image_results) - suspicious,
            "reconstruction_status": reconstructed.get("status"),
            "reconstruction_mode": reconstructed.get("mode"),
        },
        "images": per_image_results,
        "reconstruction": reconstructed,
    }


def save_report_json(report: Dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

