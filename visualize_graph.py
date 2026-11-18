from pathlib import Path
from app.graph.workflow import build_devpilot_graph

graph = build_devpilot_graph()

# Generate Mermaid diagram
mermaid = graph.get_graph().draw_mermaid()

# Save Mermaid source
Path("devpilot_graph.mmd").write_text(mermaid)

# Generate PNG image
png_data = graph.get_graph().draw_mermaid_png()

Path("devpilot_graph.png").write_bytes(png_data)

print("Graph saved as devpilot_graph.png")