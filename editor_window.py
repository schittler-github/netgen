import json
import os

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt

from commands import (
    AddEdgeCommand,
    AddNodeCommand,
    DeleteEdgeCommand,
    DeleteNodeCommand,
    MacroCommand,
    MoveNodeCommand,
)
from dialogs import NodePropertiesDialog
from graph_items import GraphEdge, GraphNode
from scene_view import GraphScene, GraphView, PaletteLabel


class GraphEditorWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Graph Editor (Qt)")
        self.resize(1100, 720)

        self.nodes = {}
        self.edges = []
        self.next_node_id = 1
        self.undo_stack = []
        self.redo_stack = []
        self.active_properties_dialog = None
        self.suppress_open_node_properties = False

        self.scene = GraphScene(self)
        self.scene.setSceneRect(-1000, -1000, 2000, 2000)
        self.view = GraphView(self.scene, self)
        self.view.setFocusPolicy(Qt.StrongFocus)
        self.view.setFocus()

        self._create_actions()

        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self.load_action)
        file_menu.addAction(self.save_action)
        file_menu.addSeparator()
        file_menu.addAction(self.export_action)
        file_menu.addAction(self.clear_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(self.instructions_action)

        palette = QtWidgets.QFrame()
        palette.setFrameShape(QtWidgets.QFrame.StyledPanel)
        palette.setFixedWidth(240)
        palette_layout = QtWidgets.QVBoxLayout(palette)
        palette_layout.setContentsMargins(12, 12, 12, 12)
        palette_layout.setSpacing(12)

        title = QtWidgets.QLabel("Graph Editor")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        palette_layout.addWidget(title)

        load_palette_btn = QtWidgets.QPushButton("Load Palette")
        load_palette_btn.setFixedHeight(28)
        load_palette_btn.clicked.connect(self.load_palette_dialog)
        palette_layout.addWidget(load_palette_btn)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QtWidgets.QWidget()
        self.palette_nodes_layout = QtWidgets.QVBoxLayout(scroll_widget)
        self.palette_nodes_layout.setContentsMargins(4, 4, 4, 4)
        self.palette_nodes_layout.setSpacing(6)
        scroll.setWidget(scroll_widget)
        scroll.setFixedHeight(220)
        palette_layout.addWidget(scroll)

        palette_layout.addSpacing(8)
        palette_layout.addWidget(self._make_button("Undo", self.undo))
        palette_layout.addWidget(self._make_button("Redo", self.redo))
        palette_layout.addWidget(self._make_button("Delete selection", self.delete_selection))
        palette_layout.addWidget(self._make_button("Clear Graph", self.clear_graph))

        palette_layout.addSpacing(20)
        palette_layout.addStretch()

        content = QtWidgets.QWidget()
        content_layout = QtWidgets.QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(palette)
        content_layout.addWidget(self.view)

        container = QtWidgets.QWidget()
        container.setLayout(content_layout)
        self.setCentralWidget(container)

        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

        try:
            self._try_autoload_palette()
        except Exception:
            pass

    def _create_actions(self):
        undo_action = QtGui.QAction("Undo", self)
        undo_action.setShortcut(QtGui.QKeySequence.Undo)
        undo_action.triggered.connect(self.undo)
        self.addAction(undo_action)

        redo_action = QtGui.QAction("Redo", self)
        redo_action.setShortcut(QtGui.QKeySequence.Redo)
        redo_action.triggered.connect(self.redo)
        self.addAction(redo_action)

        delete_action = QtGui.QAction("Delete", self)
        delete_action.setShortcut(QtGui.QKeySequence.Delete)
        delete_action.triggered.connect(self.delete_selection)
        self.addAction(delete_action)

        self.load_action = QtGui.QAction("Load", self)
        self.load_action.setShortcut(QtGui.QKeySequence.Open)
        self.load_action.triggered.connect(self.load_json)
        self.addAction(self.load_action)

        self.save_action = QtGui.QAction("Save", self)
        self.save_action.setShortcut(QtGui.QKeySequence.Save)
        self.save_action.triggered.connect(self.save_json)
        self.addAction(self.save_action)

        self.export_action = QtGui.QAction("Export Gremlin", self)
        self.export_action.triggered.connect(self.export_gremlin)
        self.addAction(self.export_action)

        self.clear_action = QtGui.QAction("Clear Graph", self)
        self.clear_action.triggered.connect(self.clear_graph)
        self.addAction(self.clear_action)

        self.exit_action = QtGui.QAction("Exit", self)
        self.exit_action.setShortcut(QtGui.QKeySequence.Quit)
        self.exit_action.triggered.connect(self.close)
        self.addAction(self.exit_action)

        self.instructions_action = QtGui.QAction("Instructions", self)
        self.instructions_action.triggered.connect(self.show_instructions)
        self.addAction(self.instructions_action)

    def show_instructions(self):
        message = (
            "Drag a palette node into the canvas to add it.\n"
            "Drag a node with left mouse button to move it.\n"
            "Right-drag from one node to another to create an edge.\n"
            "Use Ctrl + mouse wheel to zoom.\n"
            "Use the File menu for load/save/export.\n"
            "Select a node or edge and press Delete.\n"
            "Use Undo / Redo for changes."
        )
        QtWidgets.QMessageBox.information(self, "Instructions", message)

    def load_palette_dialog(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load node palette",
            "",
            "JSON files (*.json);;All files (*)",
        )
        if not path:
            return
        self._load_palette(path)

    def _load_palette(self, path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Load Palette", f"Failed to load palette:\n{exc}")
            return

        while self.palette_nodes_layout.count():
            item = self.palette_nodes_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        for entry in data:
            type = entry.get("type") or entry.get("label") or "Node"
            color = entry.get("color", "#6fa8dc")
            radius = entry.get("radius", GraphNode.NODE_RADIUS)
            size = entry.get("size", 1.0)
            w_scale = entry.get("w_scale", 1.0)
            tau = entry.get("tau", 1.0)
            template = {"type": type, "color": color, "radius": radius, "size": size, "w_scale": w_scale, "tau": tau}
            lbl = PaletteLabel(type, color=color, template=template)
            self.palette_nodes_layout.addWidget(lbl)
        self.palette_nodes_layout.addStretch()

    def _try_autoload_palette(self):
        default = os.path.join(os.getcwd(), "node_types.json")
        if os.path.exists(default):
            self._load_palette(default)

    def _make_button(self, label, callback):
        button = QtWidgets.QPushButton(label)
        button.setFixedHeight(36)
        button.clicked.connect(callback)
        return button

    def execute_command(self, command):
        command.do()
        self.undo_stack.append(command)
        self.redo_stack.clear()
        self.status_bar.showMessage(command.label)

    def undo(self):
        if not self.undo_stack:
            self.status_bar.showMessage("Nothing to undo")
            return
        command = self.undo_stack.pop()
        command.undo()
        self.redo_stack.append(command)
        self.status_bar.showMessage(f"Undid: {command.label}")

    def redo(self):
        if not self.redo_stack:
            self.status_bar.showMessage("Nothing to redo")
            return
        command = self.redo_stack.pop()
        command.do()
        self.undo_stack.append(command)
        self.status_bar.showMessage(f"Redid: {command.label}")

    def snap_to_grid(self, point):
        grid = self.scene.GRID_SPACING
        x = round(point.x() / grid) * grid
        y = round(point.y() / grid) * grid
        return QtCore.QPointF(x, y)

    def create_node(self, x, y):
        self.create_node_from_template(x, y, None)

    def create_node_from_template(self, x, y, template=None):
        point = self.snap_to_grid(QtCore.QPointF(x, y))
        node_id = f"n{self.next_node_id}"
        self.next_node_id += 1
        type = node_id
        color = "#6fa8dc"
        radius = GraphNode.NODE_RADIUS
        size = 1.0
        w_scale = 1.0
        tau = 1.0
        if template:
            type = template.get("type", type)
            color = template.get("color", color)
            radius = template.get("radius", radius)
            size = template.get("size", size)
            w_scale = template.get("w_scale", w_scale)
            tau = template.get("tau", tau)
        self.execute_command(
            AddNodeCommand(self, node_id, point.x(), point.y(), radius, color, type, size=size, w_scale=w_scale, tau=tau)
        )

    def load_json(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load graph from JSON",
            "",
            "JSON files (*.json);;All files (*)",
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Load JSON", f"Failed to load JSON:\n{exc}")
            return

        self._load_graph(data)
        self.status_bar.showMessage(f"Loaded graph from {path}")

    def _load_graph(self, data):
        self._clear_graph_state()

        node_list = data.get("nodes", [])
        for node_data in node_list:
            node_id = node_data.get("id")
            if not node_id:
                continue
            x = float(node_data.get("x", 0))
            y = float(node_data.get("y", 0))
            radius = float(node_data.get("radius", GraphNode.NODE_RADIUS))
            color = node_data.get("color", "#6fa8dc")
            type = node_data.get("type", node_id)
            size = float(node_data.get("size", 1.0))
            w_scale = float(node_data.get("w_scale", 1.0))
            tau = float(node_data.get("tau", 1.0))
            self._create_node(node_id, x, y, radius, color, type, size=size, w_scale=w_scale, tau=tau)

        edge_list = data.get("edges", [])
        for edge_data in edge_list:
            source = edge_data.get("source")
            target = edge_data.get("target")
            if source in self.nodes and target in self.nodes:
                self._add_edge(source, target)

        self.undo_stack.clear()
        self.redo_stack.clear()

    def _clear_graph_state(self):
        for node_id in list(self.nodes):
            self._remove_node(node_id)
        self.edges.clear()

    def add_edge(self, source_id, target_id):
        self.execute_command(AddEdgeCommand(self, source_id, target_id))

    def handle_node_moved(self, node_id, old_pos, new_pos):
        if old_pos == new_pos:
            return
        self.execute_command(MoveNodeCommand(self, node_id, old_pos, new_pos))

    def delete_selection(self):
        selected_items = self.scene.selectedItems()
        if not selected_items:
            self.status_bar.showMessage("Nothing selected")
            return
        selected_nodes = {item.node_id for item in selected_items if isinstance(item, GraphNode)}
        commands = []
        for item in selected_items:
            if isinstance(item, GraphNode):
                commands.append(DeleteNodeCommand(self, item.node_id))
            elif isinstance(item, GraphEdge):
                if item.source_node.node_id not in selected_nodes and item.target_node.node_id not in selected_nodes:
                    commands.append(DeleteEdgeCommand(self, item.source_node.node_id, item.target_node.node_id))
        if commands:
            self.execute_command(MacroCommand(self, "Delete selection", commands))
        else:
            self.status_bar.showMessage("No deletable items selected")

    def _create_node(self, node_id, x, y, radius, color, node_type, size=1.0, w_scale=1.0, tau=1.0):
        if node_id in self.nodes:
            return
        node = GraphNode(
            node_id,
            x,
            y,
            self,
            radius=radius,
            color=color,
            node_type=node_type,
            size=size,
            w_scale=w_scale,
            tau=tau,
        )
        self.scene.addItem(node)
        self.nodes[node_id] = {
            "id": node_id,
            "x": x,
            "y": y,
            "radius": radius,
            "color": color,
            "type": node_type,
            "size": size,
            "w_scale": w_scale,
            "tau": tau,
            "item": node,
        }
        if node_id.startswith("n") and node_id[1:].isdigit():
            self.next_node_id = max(self.next_node_id, int(node_id[1:]) + 1)
        else:
            self.next_node_id = max(self.next_node_id, len(self.nodes) + 1)

    def _remove_node(self, node_id):
        if node_id not in self.nodes:
            return
        node_item = self.nodes[node_id]["item"]
        for edge in list(self.edges):
            if edge["source"] == node_id or edge["target"] == node_id:
                self._remove_edge(edge["source"], edge["target"])
        self.scene.removeItem(node_item)
        del self.nodes[node_id]

    def _add_edge(self, source_id, target_id):
        if source_id == target_id:
            return
        if any(edge["source"] == source_id and edge["target"] == target_id for edge in self.edges):
            return
        source_item = self.nodes[source_id]["item"]
        target_item = self.nodes[target_id]["item"]
        edge = GraphEdge(source_item, target_item)
        self.scene.addItem(edge)
        self.edges.append({"source": source_id, "target": target_id, "item": edge})

    def _remove_edge(self, source_id, target_id):
        for edge in list(self.edges):
            if edge["source"] == source_id and edge["target"] == target_id:
                self.scene.removeItem(edge["item"])
                self.edges.remove(edge)
                break

    def _move_node(self, node_id, position):
        if node_id not in self.nodes:
            return
        node_item = self.nodes[node_id]["item"]
        node_item.setPos(position)
        self.nodes[node_id]["x"] = position.x()
        self.nodes[node_id]["y"] = position.y()
        for edge_data in self.edges:
            if edge_data["source"] == node_id or edge_data["target"] == node_id:
                edge_data["item"].update_position()

    def open_node_properties(self, node_id):
        if node_id not in self.nodes:
            return
        if self.suppress_open_node_properties:
            return
        self.close_properties_dialog()
        node_data = self.nodes[node_id]
        dialog = NodePropertiesDialog(node_data, self)
        self.active_properties_dialog = dialog
        dialog.finished.connect(lambda result, nid=node_id, dlg=dialog: self._handle_properties_dialog_finished(nid, dlg, result))
        dialog.show()

    def close_properties_dialog(self):
        if self.active_properties_dialog is not None:
            try:
                self.active_properties_dialog.reject()
            except Exception:
                self.active_properties_dialog.close()
            self.active_properties_dialog = None

    def _handle_properties_dialog_finished(self, node_id, dialog, result):
        if self.active_properties_dialog is not dialog:
            return
        self.active_properties_dialog = None
        if result == QtWidgets.QDialog.Accepted and node_id in self.nodes:
            values = dialog.values()
            self._apply_node_properties(node_id, values)
            self.status_bar.showMessage(f"Updated properties for {node_id}")

    def _reset_open_properties_suppression(self):
        self.suppress_open_node_properties = False

    def _apply_node_properties(self, node_id, values):
        if node_id not in self.nodes:
            return
        node_data = self.nodes[node_id]
        node_item = node_data["item"]
        node_data["type"] = values["type"]
        node_data["x"] = values["x"]
        node_data["y"] = values["y"]
        node_data["radius"] = values["radius"]
        node_data["size"] = values["size"]
        node_data["w_scale"] = values.get("w_scale", node_data.get("w_scale", 1.0))
        node_data["tau"] = values["tau"]
        node_data["color"] = values["color"]
        node_item.node_type = values["type"]
        node_item.radius = values["radius"]
        node_item.size = values["size"]
        node_item.w_scale = node_data.get("w_scale", getattr(node_item, "w_scale", 1.0))
        node_item.tau = values["tau"]
        node_item.color = values["color"]
        node_item.update_style()
        self._move_node(node_id, QtCore.QPointF(values["x"], values["y"]))

    def update_node_position(self, node_id, position):
        self.nodes[node_id]["x"] = position.x()
        self.nodes[node_id]["y"] = position.y()
        for edge_data in self.edges:
            if edge_data["source"] == node_id or edge_data["target"] == node_id:
                edge_data["item"].update_position()

    def save_json(self):
        if not self.nodes:
            QtWidgets.QMessageBox.information(self, "Save JSON", "No nodes to save.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save graph as JSON",
            "graph.json",
            "JSON files (*.json);;All files (*)",
        )
        if not path:
            return
        graph = {
            "nodes": [
                {
                    "id": node_id,
                    "label": data.get("type", node_id),
                    "type": data.get("type", node_id),
                    "x": round(data["x"], 2),
                    "y": round(data["y"], 2),
                    "radius": data.get("radius", GraphNode.NODE_RADIUS),
                    "size": data.get("size", 1.0),
                    "w_scale": data.get("w_scale", 1.0),
                    "tau": data.get("tau", 1.0),
                    "color": data.get("color", "#6fa8dc"),
                }
                for node_id, data in self.nodes.items()
            ],
            "edges": [
                {"source": edge["source"], "target": edge["target"]}
                for edge in self.edges
            ],
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(graph, handle, indent=2)
        self.status_bar.showMessage(f"Saved JSON to {path}")

    def export_gremlin(self):
        if not self.nodes:
            QtWidgets.QMessageBox.information(self, "Export Gremlin", "No nodes to export.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Gremlin Script",
            "graph.gremlin",
            "Gremlin script (*.gremlin);;Text files (*.txt);;All files (*)",
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
        for node_id in self.nodes:
            script_lines.append(
                f"v_{node_id} = graph.addVertex(T.label, 'node', 'id', '{node_id}', 'type', '{node_id}')"
            )
        script_lines.append("")
        script_lines.append("// Add edges")
        for edge in self.edges:
            script_lines.append(
                f"v_{edge['source']}.addEdge('connected', v_{edge['target']})"
            )
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(script_lines))
        self.status_bar.showMessage(f"Exported Gremlin to {path}")

    def clear_graph(self):
        self.execute_command(MacroCommand(self, "Clear graph", [DeleteNodeCommand(self, node_id) for node_id in list(self.nodes)]))
