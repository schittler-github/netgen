from PySide6 import QtCore

from graph_items import GraphNode


class Command:
    def __init__(self, editor, label):
        self.editor = editor
        self.label = label

    def do(self):
        raise NotImplementedError

    def undo(self):
        raise NotImplementedError


class MacroCommand(Command):
    def __init__(self, editor, label, commands):
        super().__init__(editor, label)
        self.commands = commands

    def do(self):
        for command in self.commands:
            command.do()

    def undo(self):
        for command in reversed(self.commands):
            command.undo()


class AddNodeCommand(Command):
    def __init__(self, editor, node_id, x, y, radius, color, node_type, N=1.0, w_scale=1.0, tau=1.0):
        super().__init__(editor, f"Add node {node_id}")
        self.node_id = node_id
        self.x = x
        self.y = y
        self.radius = radius
        self.color = color
        self.node_type = node_type
        self.N = N
        self.w_scale = w_scale
        self.tau = tau

    def do(self):
        self.editor._create_node(
            self.node_id,
            self.x,
            self.y,
            self.radius,
            self.color,
            self.node_type,
            N=self.N,
            w_scale=self.w_scale,
            tau=self.tau,
        )

    def undo(self):
        self.editor._remove_node(self.node_id)


class AddEdgeCommand(Command):
    def __init__(self, editor, source_id, target_id):
        super().__init__(editor, f"Add edge {source_id} -> {target_id}")
        self.source_id = source_id
        self.target_id = target_id

    def do(self):
        self.editor._add_edge(self.source_id, self.target_id)

    def undo(self):
        self.editor._remove_edge(self.source_id, self.target_id)


class MoveNodeCommand(Command):
    def __init__(self, editor, node_id, old_pos, new_pos):
        super().__init__(editor, f"Move node {node_id}")
        self.node_id = node_id
        self.old_pos = QtCore.QPointF(old_pos)
        self.new_pos = QtCore.QPointF(new_pos)

    def do(self):
        self.editor._move_node(self.node_id, self.new_pos)

    def undo(self):
        self.editor._move_node(self.node_id, self.old_pos)


class DeleteEdgeCommand(Command):
    def __init__(self, editor, source_id, target_id):
        super().__init__(editor, f"Delete edge {source_id} -> {target_id}")
        self.source_id = source_id
        self.target_id = target_id

    def do(self):
        self.editor._remove_edge(self.source_id, self.target_id)

    def undo(self):
        self.editor._add_edge(self.source_id, self.target_id)


class DeleteNodeCommand(Command):
    def __init__(self, editor, node_id):
        super().__init__(editor, f"Delete node {node_id}")
        self.node_id = node_id
        node = editor.nodes[node_id]
        self.x = node["x"]
        self.y = node["y"]
        self.radius = node.get("radius", GraphNode.NODE_RADIUS)
        self.color = node.get("color", "#6fa8dc")
        self.node_type = node.get("type", node_id)
        self.N = node.get("N", node.get("size", 1.0))
        self.w_scale = node.get("w_scale", 1.0)
        self.tau = node.get("tau", 1.0)
        self.outgoing = [edge.copy() for edge in editor.edges if edge["source"] == node_id]
        self.incoming = [edge.copy() for edge in editor.edges if edge["target"] == node_id]

    def do(self):
        self.editor._remove_node(self.node_id)

    def undo(self):
        self.editor._create_node(
            self.node_id,
            self.x,
            self.y,
            self.radius,
            self.color,
            self.node_type,
            N=self.N,
            w_scale=self.w_scale,
            tau=self.tau,
        )
        for edge in self.outgoing + self.incoming:
            if edge["source"] != edge["target"] and edge["source"] in self.editor.nodes and edge["target"] in self.editor.nodes:
                self.editor._add_edge(edge["source"], edge["target"])


class DeleteNodesCommand(Command):
    def __init__(self, editor, node_ids):
        node_ids = list(node_ids)
        super().__init__(editor, f"Delete nodes {', '.join(node_ids)}")
        self.node_ids = node_ids
        self.node_snapshots = {}
        for node_id in self.node_ids:
            node = editor.nodes[node_id]
            self.node_snapshots[node_id] = {
                "x": node["x"],
                "y": node["y"],
                "radius": node.get("radius", GraphNode.NODE_RADIUS),
                "color": node.get("color", "#6fa8dc"),
                "type": node.get("type", node_id),
                "N": node.get("N", node.get("size", 1.0)),
                "w_scale": node.get("w_scale", 1.0),
                "tau": node.get("tau", 1.0),
            }
        self.edges = [edge.copy() for edge in editor.edges if edge["source"] in self.node_ids or edge["target"] in self.node_ids]

    def do(self):
        for node_id in list(self.node_ids):
            self.editor._remove_node(node_id)

    def undo(self):
        for node_id in self.node_ids:
            snapshot = self.node_snapshots[node_id]
            self.editor._create_node(
                node_id,
                snapshot["x"],
                snapshot["y"],
                snapshot["radius"],
                snapshot["color"],
                snapshot["type"],
                N=snapshot["N"],
                w_scale=snapshot["w_scale"],
                tau=snapshot["tau"],
            )
        for edge in self.edges:
            if edge["source"] in self.editor.nodes and edge["target"] in self.editor.nodes:
                self.editor._add_edge(edge["source"], edge["target"])
