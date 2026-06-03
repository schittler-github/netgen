import math

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt


class GraphNode(QtWidgets.QGraphicsEllipseItem):
    NODE_RADIUS = 28

    def __init__(self, node_id, x, y, editor, radius=None, color="#6fa8dc", node_type=None, N=1.0, w_scale=1.0, tau=1.0):
        radius = radius or self.NODE_RADIUS
        self.node_id = node_id
        self.editor = editor
        self.radius = radius
        self.color = color
        self.node_type = node_type or node_id
        self.N = 1.0 if N is None else N
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
