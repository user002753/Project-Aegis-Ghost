# Thin wrapper delegating to the core AI engine implementation to avoid duplication.
from core.ai_engine import generate_ghost_carrier as _gen


def generate_ghost_carrier(prompt="Abstract oil painting, high texture, deep colors"):
    # Default behavior: save to ghost_carrier.png using mock fast path unless full model is needed.
    return _gen(prompt=prompt, save_path="ghost_carrier.png", use_mock=True)


if __name__ == "__main__":
    generate_ghost_carrier()