import os
from typing import List, Tuple
from PIL import Image
import gradio as gr

# Optional: Gemini captions if API key present
USE_GEMINI = bool(os.getenv("GEMINI_API_KEY"))

if USE_GEMINI:
    try:
        import google.genai as genai
        genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    except Exception:
        USE_GEMINI = False
        genai_client = None


def find_images(folder: str = "data/output_stego") -> List[str]:
    if not os.path.isdir(folder):
        return []
    files = [f for f in os.listdir(folder) if f.lower().endswith(".png")]
    # Prefer ghost_1..ghost_10 naming, but fallback to any PNGs
    files_sorted = []
    for f in files:
        name = os.path.splitext(f)[0]
        try:
            if name.startswith("ghost_"):
                idx = int(name.split("_")[1])
            else:
                idx = 9999
        except Exception:
            idx = 9999
        files_sorted.append((idx, f))
    files_sorted.sort(key=lambda x: x[0])
    return [os.path.join(folder, f) for _, f in files_sorted]


def load_gallery() -> List[Tuple[Image.Image, str]]:
    paths = find_images()
    gallery = []
    for p in paths:
        try:
            img = Image.open(p).convert("RGB")
            gallery.append((img, os.path.basename(p)))
        except Exception:
            continue
    return gallery


def caption_images(images: List[Tuple[Image.Image, str]]) -> List[str]:
    if not USE_GEMINI or not images:
        return []
    caps: List[str] = []
    for img, name in images:
        try:
            # send the image to Gemini for a short caption
            # Using a generic prompt to avoid long outputs
            prompt = "Provide a short 1-sentence visual description."
            # Convert PIL image to bytes (PNG)
            from io import BytesIO
            buf = BytesIO()
            img.save(buf, format="PNG")
            data = buf.getvalue()
            result = genai_client.models.generate_content(
                model="gemini-1.5-flash-latest",
                contents=[
                    {"role": "user", "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": "image/png", "data": data}},
                    ]}
                ],
                config={"temperature": 0.2}
            )
            text = getattr(result, "text", None) or ""
            caps.append(f"{name}: {text.strip()[:200]}")
        except Exception as e:
            caps.append(f"{name}: (caption unavailable)")
    return caps


def build_interface():
    with gr.Blocks(title="Aegis Ghost — Shattered Images") as demo:
        gr.Markdown("""
        # Aegis Ghost — Shattered Images
        Displays the generated ghost shards from `data/output_stego`.
        """)
        with gr.Row():
            refresh_btn = gr.Button("Refresh Gallery", variant="primary")
        gallery = gr.Gallery(
            label="Ghost Shards",
            show_label=True,
            columns=[5],
            rows=[2],
            height=600,
        )
        captions_md = gr.Markdown(visible=False)

        def refresh():
            imgs = load_gallery()
            caps = caption_images(imgs)
            # Show captions if available
            show_caps = bool(caps)
            if show_caps:
                captions_text = "\n".join([f"- {c}" for c in caps])
            else:
                captions_text = ""
            return imgs, gr.update(visible=show_caps, value=captions_text)

        refresh_btn.click(fn=refresh, inputs=None, outputs=[gallery, captions_md])
        # Auto-load on start
        demo.load(fn=lambda: refresh(), inputs=None, outputs=[gallery, captions_md])
    return demo


if __name__ == "__main__":
    app = build_interface()
    app.launch()
