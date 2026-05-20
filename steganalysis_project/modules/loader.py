import os
import zipfile
from typing import List


VALID_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


def extract_fragments(zip_path: str, out_dir: str) -> None:
    if not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(out_dir)


def list_fragment_images(fragments_dir: str) -> List[str]:
    if not os.path.isdir(fragments_dir):
        return []
    out = []
    for name in os.listdir(fragments_dir):
        p = os.path.join(fragments_dir, name)
        if not os.path.isfile(p):
            continue
        if os.path.splitext(name)[1].lower() in VALID_EXTS:
            out.append(p)
    return sorted(out)

