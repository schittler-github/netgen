import json
import math
import sys
import os

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Qt
except ImportError:
    try:
        from PyQt5 import QtCore, QtGui, QtWidgets
        from PyQt5.QtCore import Qt
    except ImportError as exc:
        raise ImportError(
            "Qt bindings not found. Install PySide6 or PyQt5 to run this file."
        ) from exc


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


class GraphNode(QtWidgets.QGraphicsEllipseItem):
    NODE_RADIUS = 28

    def __init__(self, node_id, x, y, editor, radius=None, color="#6fa8dc", node_type=None, size=1.0, w_scale=1.0, tau=1.0):
        radius = radius or self.NODE_RADIUS
        self.node_id = node_id
        self.editor = editor
        self.radius = radius
        self.color = color
        self.node_type = node_type or node_id
        self.size = 1.0 if size is None else size
        self.w_scale = 1.0 if w_scale is None else w_scale
        self.tau = 1.0 if tau is None else tau
        super().__init__(-self.radius, -self.radius, self.radius * 2, self.radius * 2)
        self.setBrush(QtGui.QBrush(QtGui.QColor(self.color)))
        self.setPen(QtGui.QPen(QtGui.QColor("#1c4587"), 2))
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QtWidgets.QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setPos(x, y)

        self.label = QtWidgets.QGraphicsTextItem(self._format_label(), self)
        self.label.setDefaultTextColor(QtGui.QColor("#111"))
        font = QtGui.QFont("Segoe UI", 10, QtGui.QFont.Bold)
        self.label.setFont(font)
        self._update_label_position()
        self.setToolTip(self.node_type)

        self.edge_preview = None
        self.dragging_edge = False
        self._right_dragging = False
        self._right_press_scene = None

    def hoverEnterEvent(self, event):
        self.setCursor(Qt.OpenHandCursor)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.unsetCursor()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if self.editor.active_properties_dialog is not None:
            self.editor.close_properties_dialog()
            self.editor.suppress_open_node_properties = True
            QtCore.QTimer.singleShot(150, self.editor._reset_open_properties_suppression)
        if event.button() == Qt.LeftButton:
            self._move_start = self.scenePos()
        if event.button() == Qt.RightButton:
            self._right_dragging = False
            self._right_press_scene = event.scenePos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.RightButton:
            if not self._right_dragging and self._right_press_scene is not None:
                distance = (event.scenePos() - self._right_press_scene).manhattanLength()
                if distance > 8:
                    self._right_dragging = True
                    self.dragging_edge = True
                    self.edge_preview = QtWidgets.QGraphicsLineItem(QtCore.QLineF(self.scenePos(), self.scenePos()))
                    self.edge_preview.setPen(QtGui.QPen(QtGui.QColor("#888888"), 2, Qt.DashLine))
                    self.edge_preview.setZValue(-1)
                    self.scene().addItem(self.edge_preview)
            if self.dragging_edge and self.edge_preview is not None:
                line = QtCore.QLineF(self.scenePos(), event.scenePos())
                self.edge_preview.setLine(line)
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and hasattr(self, "_move_start"):
            new_pos = self.scenePos()
            if new_pos != self._move_start:
                self.editor.handle_node_moved(self.node_id, self._move_start, new_pos)
        if event.button() == Qt.RightButton:
            if self.dragging_edge:
                self.dragging_edge = False
                if self.edge_preview is not None:
                    end_pos = event.scenePos()
                    self.scene().removeItem(self.edge_preview)
                    self.edge_preview = None
                    target_item = self._find_target_node(end_pos)
                    if isinstance(target_item, GraphNode) and target_item is not self:
                        self.editor.add_edge(self.node_id, target_item.node_id)
            elif not self._right_dragging:
                self.editor.open_node_properties(self.node_id)
            self._right_dragging = False
            self._right_press_scene = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _find_target_node(self, scene_pos):
        for item in self.scene().items(scene_pos):
            if item is self:
                continue
            if isinstance(item, GraphNode):
                return item
            if isinstance(item, QtWidgets.QGraphicsTextItem) and isinstance(item.parentItem(), GraphNode):
                return item.parentItem()
        return None

    def itemChange(self, change, value):
        if change == QtWidgets.QGraphicsItem.ItemPositionChange and isinstance(value, QtCore.QPointF):
            return self.editor.snap_to_grid(value)
        if change == QtWidgets.QGraphicsItem.ItemPositionHasChanged:
            if self.node_id in self.editor.nodes:
                self.editor.update_node_position(self.node_id, self.scenePos())
        return super().itemChange(change, value)

    def _format_label(self):
        return self.node_id

    def _update_label_position(self):
        self.label.setPlainText(self._format_label())
        self.label.setPos(-self.label.boundingRect().width() / 2, -self.label.boundingRect().height() / 2)

    def update_style(self):
        self.setRect(-self.radius, -self.radius, self.radius * 2, self.radius * 2)
        self.setBrush(QtGui.QBrush(QtGui.QColor(self.color)))
        self._update_label_position()


class GraphEdge(QtWidgets.QGraphicsLineItem):
    ARROW_SIZE = 12.0

    def __init__(self, source_node, target_node):
        super().__init__()
        self.source_node = source_node
        self.target_node = target_node
        self.setPen(QtGui.QPen(QtGui.QColor("#3c78d8"), 2))
        self.setZValue(-2)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, True)
        self.update_position()

    def update_position(self):
        source_pos = self.source_node.scenePos()
        target_pos = self.target_node.scenePos()
        if source_pos == target_pos:
            self.setLine(QtCore.QLineF(source_pos, target_pos))
            return

        line = QtCore.QLineF(source_pos, target_pos)
        start = self._point_on_circle(source_pos, target_pos, self.source_node.radius)
        end = self._point_on_circle(target_pos, source_pos, self.target_node.radius)
        self.setLine(QtCore.QLineF(start, end))

    def _point_on_circle(self, center, toward, radius):
        direction = QtCore.QLineF(center, toward)
        if direction.length() == 0:
            return QtCore.QPointF(center)
        direction.setLength(radius)
        return direction.p2()

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        pen = self.pen()
        painter.setPen(pen)
        painter.setBrush(pen.color())
        line = self.line()
        painter.drawLine(line)

        if line.length() <= 0:
            return

        angle = math.atan2(-line.dy(), line.dx())
        arrow_p1 = line.p2() - QtCore.QPointF(
            math.cos(angle + math.pi / 6) * self.ARROW_SIZE,
            -math.sin(angle + math.pi / 6) * self.ARROW_SIZE,
        )
        arrow_p2 = line.p2() - QtCore.QPointF(
            math.cos(angle - math.pi / 6) * self.ARROW_SIZE,
            -math.sin(angle - math.pi / 6) * self.ARROW_SIZE,
        )
        arrow_head = QtGui.QPolygonF([line.p2(), arrow_p1, arrow_p2])
        painter.drawPolygon(arrow_head)


class NodePropertiesDialog(QtWidgets.QDialog):
    def __init__(self, node_data, parent=None):
        super().__init__(parent)
        title = node_data.get("type", node_data["id"])
        self.setWindowTitle(f"Node Properties - {title}")
        self.setWindowModality(Qt.NonModal)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.id_label = QtWidgets.QLabel(node_data["id"])
        self.type_edit = QtWidgets.QLineEdit(node_data.get("type", node_data["id"]))
        self.x_spin = QtWidgets.QDoubleSpinBox()
        self.x_spin.setRange(-10000, 10000)
        self.x_spin.setValue(node_data["x"])
        self.y_spin = QtWidgets.QDoubleSpinBox()
        self.y_spin.setRange(-10000, 10000)
        self.y_spin.setValue(node_data["y"])
        self.radius_spin = QtWidgets.QDoubleSpinBox()
        self.radius_spin.setRange(8, 200)
        self.radius_spin.setValue(node_data.get("radius", GraphNode.NODE_RADIUS))
        self.radius_spin.setSingleStep(1)
        self.size_spin = QtWidgets.QDoubleSpinBox()
        self.size_spin.setRange(0, 1000)
        self.size_spin.setValue(node_data.get("size", 1.0))
        self.size_spin.setSingleStep(0.1)
        self.w_scale_spin = QtWidgets.QDoubleSpinBox()
        self.w_scale_spin.setRange(0, 1000)
        self.w_scale_spin.setValue(node_data.get("w_scale", 1.0))
        self.w_scale_spin.setSingleStep(0.1)
        self.tau_spin = QtWidgets.QDoubleSpinBox()
        self.tau_spin.setRange(0, 1000)
        self.tau_spin.setValue(node_data.get("tau", 1.0))
        self.tau_spin.setSingleStep(0.1)
        self.color_button = QtWidgets.QPushButton()
        self.color = node_data.get("color", "#6fa8dc")
        self._update_color_button()
        self.color_button.clicked.connect(self.choose_color)

        form = QtWidgets.QFormLayout(self)
        form.addRow("ID:", self.id_label)
        form.addRow("Type:", self.type_edit)
        form.addRow("X:", self.x_spin)
        form.addRow("Y:", self.y_spin)
        form.addRow("Radius:", self.radius_spin)
        form.addRow("Color:", self.color_button)
        #add horizontal line separator
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        form.addRow(separator)
        form.addRow("Size:", self.size_spin)
        form.addRow("w_scale:", self.w_scale_spin)
        form.addRow("Tau:", self.tau_spin)
        

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def choose_color(self):
        color = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.color), self, "Choose node color")
        if color.isValid():
            self.color = color.name()
            self._update_color_button()

    def _update_color_button(self):
        self.color_button.setText(self.color)
        self.color_button.setStyleSheet(f"background: {self.color}; color: #111; border: 1px solid #888;")

    def values(self):
        return {
            "type": self.type_edit.text().strip() or self.id_label.text(),
            "x": self.x_spin.value(),
            "y": self.y_spin.value(),
            "radius": self.radius_spin.value(),
            "size": self.size_spin.value(),
            "w_scale": self.w_scale_spin.value(),
            "tau": self.tau_spin.value(),
            "color": self.color,
        }


class GraphScene(QtWidgets.QGraphicsScene):
    GRID_SPACING = 40

    def __init__(self, parent=None):
        super().__init__(parent)

    def drawBackground(self, painter, rect):
        painter.fillRect(rect, QtGui.QColor("#f8f8f8"))
        minor_pen = QtGui.QPen(QtGui.QColor("#e0e0e0"))
        minor_pen.setWidth(1)
        major_pen = QtGui.QPen(QtGui.QColor("#c0c0c0"))
        major_pen.setWidth(1)

        left = int(rect.left()) - (int(rect.left()) % self.GRID_SPACING)
        top = int(rect.top()) - (int(rect.top()) % self.GRID_SPACING)

        x = left
        while x <= rect.right():
            painter.setPen(major_pen if x % (self.GRID_SPACING * 5) == 0 else minor_pen)
            painter.drawLine(x, rect.top(), x, rect.bottom())
            x += self.GRID_SPACING

        y = top
        while y <= rect.bottom():
            painter.setPen(major_pen if y % (self.GRID_SPACING * 5) == 0 else minor_pen)
            painter.drawLine(rect.left(), y, rect.right(), y)
            y += self.GRID_SPACING


class GraphView(QtWidgets.QGraphicsView):
    def __init__(self, scene, editor):
        super().__init__(scene)
        self.editor = editor
        self.setRenderHint(QtGui.QPainter.Antialiasing)
        self.setAcceptDrops(True)
        self.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag)
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.FullViewportUpdate)
        self.setBackgroundBrush(Qt.NoBrush)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self._zoom = 1.0
        self._zoom_step = 1.15
        self._zoom_range = (0.2, 10.0)
        self._panning = False
        self._pan_start = None

    def mousePressEvent(self, event):
        if self.editor.active_properties_dialog is not None:
            self.editor.close_properties_dialog()
            self.editor.suppress_open_node_properties = True
            QtCore.QTimer.singleShot(150, self.editor._reset_open_properties_suppression)
        if event.button() == Qt.LeftButton and self.itemAt(event.pos()) is None:
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            angle = event.angleDelta().y()
            if angle == 0:
                return
            factor = self._zoom_step if angle > 0 else 1 / self._zoom_step
            new_zoom = self._zoom * factor
            if new_zoom < self._zoom_range[0] or new_zoom > self._zoom_range[1]:
                return
            self.scale(factor, factor)
            self._zoom = new_zoom
            self.editor.status_bar.showMessage(f"Zoom: {self._zoom:.2f}x")
            event.accept()
        else:
            super().wheelEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning and self._pan_start is not None:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._panning:
            self._panning = False
            self._pan_start = None
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-graph-node"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-graph-node"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasFormat("application/x-graph-node"):
            pos = self.mapToScene(event.position().toPoint()) if hasattr(event, "position") else self.mapToScene(event.pos())
            data = event.mimeData().data("application/x-graph-node")
            template = None
            try:
                payload = bytes(data).decode("utf-8")
                template = json.loads(payload)
            except Exception:
                template = None
            self.editor.create_node_from_template(pos.x(), pos.y(), template)
            event.acceptProposedAction()
        else:
            event.ignore()


class PaletteLabel(QtWidgets.QLabel):
    def __init__(self, text, color="#6fa8dc", template=None, parent=None):
        super().__init__(text, parent)
        self.text = text
        self.color = color
        self.template = template or {"type": text, "color": color}
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(40)
        self.setStyleSheet(f"background: {self.color}; border: 1px solid #1c4587; border-radius: 6px; color: #111;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            drag = QtGui.QDrag(self)
            mime = QtCore.QMimeData()
            try:
                payload = json.dumps(self.template).encode("utf-8")
            except Exception:
                payload = b"{}"
            mime.setData("application/x-graph-node", payload)
            drag.setMimeData(mime)
            # create a pixmap preview
            pixmap = QtGui.QPixmap(140, 34)
            pixmap.fill(QtGui.QColor(self.color))
            painter = QtGui.QPainter(pixmap)
            painter.setPen(QtGui.QPen(QtGui.QColor("#111")))
            painter.drawText(pixmap.rect(), Qt.AlignCenter, self.text)
            painter.end()
            drag.setPixmap(pixmap)
            drag.exec(Qt.CopyAction)
        super().mousePressEvent(event)


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

        # File menu: expose load/save/export/clear/exit
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

        # Palette area for node templates (loaded from JSON)
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

        # try to autoload a node palette file if present
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

        # clear existing
        while self.palette_nodes_layout.count():
            item = self.palette_nodes_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # expect list of node defs
        for entry in data:
            type = entry.get("type") or entry.get("label") or entry.get("type") or "Node"
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


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = GraphEditorWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

