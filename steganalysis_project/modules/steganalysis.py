import io
from typing import Dict, Tuple

import numpy as np
from PIL import Image

from core.steganalysis import chi_square_test as core_chi_square_test
from core.steganalysis import rs_analysis as core_rs_analysis

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except Exception:
    TORCH_AVAILABLE = False
    torch = None
    nn = None


def preprocess_image(image_bytes: bytes, size: Tuple[int, int] = (512, 512)) -> np.ndarray:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = img.resize(size)
    return np.array(img, dtype=np.uint8)


def chi_square_test(img_arr: np.ndarray) -> float:
    return float(core_chi_square_test(Image.fromarray(img_arr)))


def rs_analysis(img_arr: np.ndarray) -> Dict:
    return core_rs_analysis(Image.fromarray(img_arr))


def lsb_distribution(img_arr: np.ndarray) -> Dict:
    lsb = img_arr & 1
    zeros = int(np.sum(lsb == 0))
    ones = int(np.sum(lsb == 1))
    total = max(zeros + ones, 1)
    p1 = ones / total
    p0 = zeros / total
    entropy = float(-(p0 * np.log2(p0 + 1e-9) + p1 * np.log2(p1 + 1e-9)))
    return {
        "zeros": zeros,
        "ones": ones,
        "ones_ratio": round(p1, 6),
        "entropy": round(entropy, 6),
    }


if TORCH_AVAILABLE:
    class StegoCNN(nn.Module):
        def __init__(self):
            super().__init__()
            self.conv = nn.Sequential(
                nn.Conv2d(3, 16, 3, padding=1),
                nn.ReLU(),
                nn.Conv2d(16, 32, 3, padding=1),
                nn.ReLU(),
                nn.MaxPool2d(2),
                nn.Conv2d(32, 64, 3, padding=1),
                nn.ReLU(),
                nn.AdaptiveAvgPool2d((1, 1)),
            )
            self.fc = nn.Linear(64, 2)

        def forward(self, x):
            x = self.conv(x)
            x = x.view(x.size(0), -1)
            return self.fc(x)


def cnn_stego_detector(img_arr: np.ndarray) -> Dict:
    """
    Skeleton inference method.
    In production, load a trained model from models/cnn_stego_detector.pth.
    """
    if not TORCH_AVAILABLE:
        return {"available": False, "prediction": None, "confidence": 0.0}
    return {"available": True, "prediction": "unknown", "confidence": 0.0}

