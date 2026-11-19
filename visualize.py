
from pathlib import Path

from app.graph.workflow import build_devpilot_graph


def main():
    # Build the DevPilot graph
    graph = build_devpilot_graph()

    # Generate Mermaid diagram
    mermaid_diagram = graph.get_graph().draw_mermaid()

    # Save diagram to a file
    output_path = Path("devpilot_graph.mmd")

    output_path.write_text(
        mermaid_diagram,
        encoding="utf-8"
    )

    print("DevPilot graph visualization generated!")
    print(f"Saved to: {output_path.resolve()}")

    print("\nMermaid diagram:\n")
    print(mermaid_diagram)


if __name__ == "__main__":
    main()
