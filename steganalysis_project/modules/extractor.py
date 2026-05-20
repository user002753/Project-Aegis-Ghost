import numpy as np


def extract_lsb_data(img_arr: np.ndarray, max_bytes: int = 65536) -> bytes:
    flat = img_arr.reshape(-1).astype(np.uint8, copy=False)
    n_bits = min(flat.size, max_bytes * 8)
    bits = (flat[:n_bits] & 1).astype(np.uint8)
    return np.packbits(bits).tobytes()


def extract_blue_lsb_length_prefixed(img_arr: np.ndarray) -> bytes:
    blue = img_arr[:, :, 2].reshape(-1)
    if blue.size < 32:
        return b""
    header_bits = (blue[:32] & 1).astype(np.uint8)
    header = np.packbits(header_bits).tobytes()
    n = int.from_bytes(header, "big", signed=False)
    if n <= 0 or n > 65536:
        return b""
    total_bits = (4 + n) * 8
    if total_bits > blue.size:
        return b""
    bits = (blue[:total_bits] & 1).astype(np.uint8)
    packed = np.packbits(bits).tobytes()
    return packed[4:4 + n]

