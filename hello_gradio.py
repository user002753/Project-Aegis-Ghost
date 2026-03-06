import gradio as gr


def greet(name: str) -> str:
    return f"Hello {name}!!"


demo = gr.Interface(fn=greet, inputs="text", outputs="text", title="Gradio Smoke Test")

if __name__ == "__main__":
    demo.launch()
