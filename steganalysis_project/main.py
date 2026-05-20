import argparse
import os
from typing import Dict, List

from PIL import Image

from modules.loader import extract_fragments, list_fragment_images
from modules.steganalysis import (
    preprocess_image,
    chi_square_test,
    rs_analysis,
    lsb_distribution,
    cnn_stego_detector,
)
from modules.extractor import extract_blue_lsb_length_prefixed, extract_lsb_data
from modules.decoder import decode_hidden
from modules.shamir_reconstruct import parse_share, reconstruct_secret
from modules.visualization import build_visual_report, save_report_json


def run_pipeline(zip_path: str, work_dir: str, password: str = "") -> Dict:
    fragments_dir = os.path.join(work_dir, "fragments")
    os.makedirs(work_dir, exist_ok=True)
    extract_fragments(zip_path, fragments_dir)
    images = list_fragment_images(fragments_dir)

    shares: List[Dict] = []
    per_image_results: List[Dict] = []

    for p in images:
        with open(p, "rb") as f:
            raw = f.read()
        img_arr = preprocess_image(raw)

        chi_p = chi_square_test(img_arr)
        rs = rs_analysis(img_arr)
        lsb = lsb_distribution(img_arr)
        cnn = cnn_stego_detector(img_arr)

        # Stage: hidden data extraction (length-prefixed first, then raw LSB fallback)
        payload = extract_blue_lsb_length_prefixed(img_arr)
        if not payload:
            payload = extract_lsb_data(img_arr, max_bytes=8192)

        decoded, decode_report = decode_hidden(payload)
        share_obj = parse_share(decoded)
        if share_obj:
            shares.append(share_obj)

        is_suspicious = (chi_p > 0.05) or (lsb.get("entropy", 0.0) > 0.92)
        per_image_results.append(
            {
                "file": os.path.basename(p),
                "steganalysis": {
                    "chi_square_p": chi_p,
                    "rs": rs,
                    "lsb_distribution": lsb,
                    "cnn": cnn,
                },
                "decoder": decode_report,
                "share_found": bool(share_obj),
                "is_suspicious": bool(is_suspicious),
            }
        )

    plaintext, mode = reconstruct_secret(shares, password=password)
    reconstruction = {
        "status": "success" if plaintext is not None else "failed",
        "mode": mode,
        "shares_found": len(shares),
        "decrypted_message": plaintext,
    }

    report = build_visual_report(per_image_results, reconstruction)
    out_report = os.path.join(work_dir, "analysis_report.json")
    save_report_json(report, out_report)
    report["report_path"] = out_report
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description="Research-grade Shamir steganalysis pipeline skeleton")
    ap.add_argument("--zip", required=True, help="Path to ZIP containing image fragments")
    ap.add_argument("--work-dir", default="steganalysis_project_output", help="Working directory")
    ap.add_argument("--password", default="", help="Optional fallback password for legacy batches")
    args = ap.parse_args()

    result = run_pipeline(args.zip, args.work_dir, password=args.password)
    print(f"Status: {result['reconstruction']['status']}")
    print(f"Mode: {result['reconstruction']['mode']}")
    if result["reconstruction"]["decrypted_message"] is not None:
        print("Decrypted Message:")
        print(result["reconstruction"]["decrypted_message"])
    print(f"Report: {result['report_path']}")


if __name__ == "__main__":
    main()

