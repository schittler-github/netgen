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
    def __init__(self, editor, node_id, x, y, radius, color, node_type, size=1.0, w_scale=1.0, tau=1.0):
        super().__init__(editor, f"Add node {node_id}")
        self.node_id = node_id
        self.x = x
        self.y = y
        self.radius = radius
        self.color = color
        self.node_type = node_type
        self.size = size
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
            size=self.size,
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
        self.size = node.get("size", 1.0)
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
            size=self.size,
            w_scale=self.w_scale,
            tau=self.tau,
        )
        for edge in self.outgoing + self.incoming:
            if edge["source"] != edge["target"]:
                self.editor._add_edge(edge["source"], edge["target"])
