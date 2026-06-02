import json
import tkinter as tk
from tkinter import filedialog, messagebox


class GraphEditorApp:
    NODE_RADIUS = 28
    GRID_SPACING = 40
    GRID_COLOR = "#d0d0d0"
    NODE_FILL = "#6fa8dc"
    NODE_OUTLINE = "#1c4587"
    EDGE_COLOR = "#3c78d8"

    def __init__(self, root):
        self.root = root
        self.root.title("Graph Editor")
        self.nodes = {}
        self.edges = []
        self.next_node_id = 1
        self.dragging_node = None
        self.drag_start = None
        self.edge_source = None
        self.edge_preview = None
        self.dragging_new_node = False
        self.new_node_preview = None

        self._build_ui()
        self._draw_grid()

    def _build_ui(self):
        toolbar = tk.Frame(self.root, padx=8, pady=8, bg="#e8e8e8")
        toolbar.pack(side=tk.LEFT, fill=tk.Y)

        tk.Label(toolbar, text="Graph Editor", font=("Segoe UI", 14, "bold"), bg="#e8e8e8").pack(pady=(0, 12))

        self.palette_label = tk.Label(
            toolbar,
            text="Drag to canvas\nto create node",
            relief=tk.RAISED,
            borderwidth=2,
            width=18,
            height=4,
            bg="#ffffff",
            fg="#333",
            justify=tk.CENTER,
        )
        self.palette_label.pack(pady=(0, 12), fill=tk.X)
        self.palette_label.bind("<ButtonPress-1>", self._start_new_node_drag)

        tk.Button(toolbar, text="Save JSON", width=18, command=self.save_json).pack(pady=4)
        tk.Button(toolbar, text="Export Gremlin", width=18, command=self.export_gremlin).pack(pady=4)
        tk.Button(toolbar, text="Clear Graph", width=18, command=self.clear_graph).pack(pady=4)

        tk.Label(toolbar, text="Instructions", font=("Segoe UI", 10, "bold")).pack(pady=(16, 4))
        tk.Label(
            toolbar,
            text=(
                "• Drag the palette label into the canvas to add a node.\n"
                "• Left-drag a node to move it.\n"
                "• Right-drag from one node to another to create an edge.\n"
                "• Save JSON or export Gremlin script."
            ),
            justify=tk.LEFT,
            wraplength=180,
        ).pack(pady=0)

        content = tk.Frame(self.root)
        content.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(content, bg="#ffffff")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", lambda event: self._cancel_new_node_drag(event))
        self.canvas.tag_bind("node", "<ButtonPress-1>", self.on_node_press)
        self.canvas.tag_bind("node", "<B1-Motion>", self.on_node_motion)
        self.canvas.tag_bind("node", "<ButtonRelease-1>", self.on_node_release)
        self.canvas.tag_bind("node", "<ButtonPress-3>", self.on_edge_start)
        self.canvas.tag_bind("node", "<B3-Motion>", self.on_edge_motion)
        self.canvas.tag_bind("node", "<ButtonRelease-3>", self.on_edge_release)

        self.status = tk.Label(self.root, text="Ready", anchor="w", relief=tk.SUNKEN)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

    def _draw_grid(self):
        self.canvas.delete("grid")
        width = self.canvas.winfo_width() or self.canvas.winfo_reqwidth() or 800
        height = self.canvas.winfo_height() or self.canvas.winfo_reqheight() or 600
        for x in range(0, width, self.GRID_SPACING):
            self.canvas.create_line(x, 0, x, height, fill=self.GRID_COLOR, tags=("grid",), width=1)
        for y in range(0, height, self.GRID_SPACING):
            self.canvas.create_line(0, y, width, y, fill=self.GRID_COLOR, tags=("grid",), width=1)

        self.canvas.after(100, self._draw_grid)

    def _start_new_node_drag(self, event):
        self.dragging_new_node = True
        self.status.config(text="Drag into the canvas to place a new node.")
        self.root.bind("<Motion>", self._update_new_node_preview)
        self.root.bind("<ButtonRelease-1>", self._finish_new_node_drag)

    def _update_new_node_preview(self, event):
        if not self.dragging_new_node:
            return
        canvas = self.canvas
        x_root, y_root = event.x_root, event.y_root
        canvas_widget = canvas.winfo_containing(x_root, y_root)
        if canvas_widget is canvas:
            x = canvas.canvasx(event.x_root - canvas.winfo_rootx())
            y = canvas.canvasy(event.y_root - canvas.winfo_rooty())
            if self.new_node_preview is None:
                self.new_node_preview = canvas.create_oval(
                    x - self.NODE_RADIUS,
                    y - self.NODE_RADIUS,
                    x + self.NODE_RADIUS,
                    y + self.NODE_RADIUS,
                    outline="#888",
                    dash=(4, 2),
                    width=2,
                    tags=("preview",),
                )
            else:
                canvas.coords(
                    self.new_node_preview,
                    x - self.NODE_RADIUS,
                    y - self.NODE_RADIUS,
                    x + self.NODE_RADIUS,
                    y + self.NODE_RADIUS,
                )
        elif self.new_node_preview is not None:
            canvas.delete(self.new_node_preview)
            self.new_node_preview = None

    def _finish_new_node_drag(self, event):
        if not self.dragging_new_node:
            return
        self.dragging_new_node = False
        self.root.unbind("<Motion>")
        self.root.unbind("<ButtonRelease-1>")
        if self.new_node_preview is not None:
            coords = self.canvas.coords(self.new_node_preview)
            self.canvas.delete(self.new_node_preview)
            self.new_node_preview = None
            x = (coords[0] + coords[2]) / 2
            y = (coords[1] + coords[3]) / 2
            self.create_node(x, y)
            self.status.config(text="New node placed.")
        else:
            self.status.config(text="Node drag canceled.")

    def _cancel_new_node_drag(self, event):
        if self.dragging_new_node and event.widget is self.canvas:
            return
        if self.dragging_new_node:
            self.dragging_new_node = False
            self.root.unbind("<Motion>")
            self.root.unbind("<ButtonRelease-1>")
            if self.new_node_preview is not None:
                self.canvas.delete(self.new_node_preview)
                self.new_node_preview = None
            self.status.config(text="Node drag canceled.")

    def create_node(self, x, y):
        node_id = f"n{self.next_node_id}"
        self.next_node_id += 1
        circle = self.canvas.create_oval(
            x - self.NODE_RADIUS,
            y - self.NODE_RADIUS,
            x + self.NODE_RADIUS,
            y + self.NODE_RADIUS,
            fill=self.NODE_FILL,
            outline=self.NODE_OUTLINE,
            width=2,
            tags=("node", node_id),
        )
        text = self.canvas.create_text(x, y, text=node_id, tags=("node", node_id), font=("Segoe UI", 10, "bold"))
        self.nodes[node_id] = {"id": node_id, "x": x, "y": y, "circle": circle, "text": text}
        self.canvas.tag_bind(node_id, "<ButtonPress-1>", self.on_node_press)
        self.canvas.tag_bind(node_id, "<B1-Motion>", self.on_node_motion)
        self.canvas.tag_bind(node_id, "<ButtonRelease-1>", self.on_node_release)
        self.canvas.tag_bind(node_id, "<ButtonPress-3>", self.on_edge_start)
        self.canvas.tag_bind(node_id, "<B3-Motion>", self.on_edge_motion)
        self.canvas.tag_bind(node_id, "<ButtonRelease-3>", self.on_edge_release)
        print(f"Created node {node_id} at ({int(x)},{int(y)})")

    def on_node_press(self, event):
        item = self.canvas.find_withtag("current")[0]
        node_id = self._item_to_node_id(item)
        if node_id is None:
            return
        self.dragging_node = node_id
        self.drag_start = (event.x, event.y)
        node = self.nodes[node_id]
        self.node_start = (node["x"], node["y"])
        self.status.config(text=f"Moving {node_id}...")

    def on_node_motion(self, event):
        if not self.dragging_node:
            return
        node_id = self.dragging_node
        dx = event.x - self.drag_start[0]
        dy = event.y - self.drag_start[1]
        new_x = self.node_start[0] + dx
        new_y = self.node_start[1] + dy
        self._move_node(node_id, new_x, new_y)

    def on_node_release(self, event):
        if self.dragging_node is None:
            return
        self.status.config(text="Node moved.")
        self.dragging_node = None
        self.drag_start = None

    def on_edge_start(self, event):
        item = self.canvas.find_withtag("current")[0]
        node_id = self._item_to_node_id(item)
        if node_id is None:
            return
        self.edge_source = node_id
        x, y = self.nodes[node_id]["x"], self.nodes[node_id]["y"]
        self.edge_preview = self.canvas.create_line(
            x,
            y,
            event.x,
            event.y,
            fill="#888888",
            dash=(4, 2),
            width=2,
            tags=("preview",),
        )
        self.status.config(text=f"Drawing edge from {node_id}...")

    def on_edge_motion(self, event):
        if self.edge_preview is None:
            return
        source = self.nodes[self.edge_source]
        self.canvas.coords(self.edge_preview, source["x"], source["y"], event.x, event.y)

    def on_edge_release(self, event):
        if self.edge_preview is not None:
            self.canvas.delete(self.edge_preview)
            self.edge_preview = None
        target_id = self._find_node_at_position(event.x, event.y)
        source_id = self.edge_source
        self.edge_source = None
        if source_id and target_id and source_id != target_id:
            self._add_edge(source_id, target_id)
            self.status.config(text=f"Edge added: {source_id} -> {target_id}")
        else:
            self.status.config(text="Edge creation canceled.")

    def _find_node_at_position(self, x, y):
        hits = self.canvas.find_overlapping(x, y, x, y)
        for item in hits:
            node_id = self._item_to_node_id(item)
            if node_id:
                return node_id
        return None

    def _item_to_node_id(self, item):
        for tag in self.canvas.gettags(item):
            if tag.startswith("n"):
                return tag
        return None

    def _move_node(self, node_id, x, y):
        node = self.nodes[node_id]
        node["x"] = x
        node["y"] = y
        self.canvas.coords(
            node["circle"],
            x - self.NODE_RADIUS,
            y - self.NODE_RADIUS,
            x + self.NODE_RADIUS,
            y + self.NODE_RADIUS,
        )
        self.canvas.coords(node["text"], x, y)
        self._refresh_edges()

    def _add_edge(self, source_id, target_id):
        self.edges.append({"source": source_id, "target": target_id})
        self._refresh_edges()

    def _refresh_edges(self):
        self.canvas.delete("edge")
        for edge in self.edges:
            source = self.nodes.get(edge["source"])
            target = self.nodes.get(edge["target"])
            if source and target:
                self.canvas.create_line(
                    source["x"],
                    source["y"],
                    target["x"],
                    target["y"],
                    fill=self.EDGE_COLOR,
                    width=2,
                    arrow=tk.LAST,
                    tags=("edge",),
                )

    def save_json(self):
        if not self.nodes:
            messagebox.showinfo("Save JSON", "No nodes to save.")
            return
        path = filedialog.asksaveasfilename(
            title="Save graph as JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        graph = {
            "nodes": [
                {"id": node_id, "label": node_id, "x": round(data["x"], 2), "y": round(data["y"], 2)}
                for node_id, data in self.nodes.items()
            ],
            "edges": [
                {"source": edge["source"], "target": edge["target"]}
                for edge in self.edges
            ],
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(graph, handle, indent=2)
        messagebox.showinfo("Save JSON", f"Saved graph to {path}")
        self.status.config(text=f"Saved JSON to {path}")

    def export_gremlin(self):
        if not self.nodes:
            messagebox.showinfo("Export Gremlin", "No nodes to export.")
            return
        path = filedialog.asksaveasfilename(
            title="Export Gremlin Script",
            defaultextension=".gremlin",
            filetypes=[("Gremlin script", "*.gremlin"), ("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        script_lines = [
            "// Gremlin script exported from Graph Editor",
            "graph = TinkerGraph.open()",
            "g = graph.traversal()",
            "",
            "// Add vertices",
        ]
        for node_id, node in self.nodes.items():
            script_lines.append(
                f"v_{node_id} = graph.addVertex(T.label, 'node', 'id', '{node_id}', 'name', '{node_id}')"
            )
        script_lines.append("")
        script_lines.append("// Add edges")
        for edge in self.edges:
            script_lines.append(
                f"v_{edge['source']}.addEdge('connected', v_{edge['target']})"
            )
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(script_lines))
        messagebox.showinfo("Export Gremlin", f"Exported Gremlin script to {path}")
        self.status.config(text=f"Exported Gremlin to {path}")

    def clear_graph(self):
        self.canvas.delete("all")
        self.nodes.clear()
        self.edges.clear()
        self.next_node_id = 1
        self._draw_grid()
        self.status.config(text="Graph cleared.")


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1000x700")
    app = GraphEditorApp(root)
    root.mainloop()
