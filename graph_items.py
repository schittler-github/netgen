import math

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
from wcwidth import center


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

"""
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
"""
class GraphEdge(QtWidgets.QGraphicsPathItem):
    ARROW_SIZE = 12.0

    def __init__(self, source_node, target_node, ctrl_x=0.0, ctrl_y=0.0):
        super().__init__()
        self.source_node = source_node
        self.target_node = target_node
        self.angle_of_entry = None
        self.arrow_base = None

        # curvature control (relative offset)
        self.ctrl_x = ctrl_x
        self.ctrl_y = ctrl_y

        self.setPen(QtGui.QPen(QtGui.QColor("#3c78d8"), 2))
        self.setZValue(-2)
        
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, True)
        
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(QtCore.Qt.LeftButton)

        self.update_position()

    def shape(self):
        stroker = QtGui.QPainterPathStroker()
        stroker.setWidth(max(6, self.pen().widthF() + 4))  # clickable width
        return stroker.createStroke(self.path())

    def update_position(self):
        source_pos = self.source_node.scenePos()
        target_pos = self.target_node.scenePos()

        # Compute raw curve endpoints (center-to-center)
        p0 = source_pos
        p2 = target_pos

        # Control point
        mid = (p0 + p2) * 0.5
        p1 = QtCore.QPointF(mid.x() + self.ctrl_x, mid.y() + self.ctrl_y)

        # Compute intersections with node borders
        start = self._point_on_circle_bezier(source_pos, p0, p1, p2, self.source_node.radius)
        end   = self._point_on_circle_bezier(target_pos, p2, p1, p0, self.target_node.radius)
        
        self.arrow_base = end
        # compute the angle of entry at the end point for proper arrowhead orientation
        self.angle_of_entry = math.atan2(end.y() - p1.y(), end.x() - p1.x())

        # Build path
        path = QtGui.QPainterPath(start)
        path.quadTo(p1, end)
        self.setPath(path)

    def hoverEnterEvent(self, event):
        self.setCursor(Qt.OpenHandCursor)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.unsetCursor()
        super().hoverLeaveEvent(event)
        
    # on mouse press and hold left button, change the control point based on mouse movement for interactive curve adjustment
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._ctrl_start = QtCore.QPointF(self.ctrl_x, self.ctrl_y)
            self._mouse_start = event.scenePos()
            event.accept()
        else:
            super().mousePressEvent(event)
            
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            delta = event.scenePos() - self._mouse_start

            # Update curvature
            self.ctrl_x = self._ctrl_start.x() + delta.x()
            self.ctrl_y = self._ctrl_start.y() + delta.y()

            # Recompute the curve
            self.update_position()

            # Request a redraw
            self.update()

            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            event.accept()
        else:
            super().mouseReleaseEvent(event)

       

    def _point_on_circle_bezier(self, center, p0, p1, p2, radius):
        """
        Find intersection between quadratic Bezier curve (p0,p1,p2)
        and circle centered at `center` with radius `radius`.
        Returns the point on the curve closest to p0 that lies on the circle.
        """

        def bezier(t):
            return (
                (1 - t) * (1 - t) * p0 +
                2 * (1 - t) * t * p1 +
                t * t * p2
            )

        def f(t):
            pt = bezier(t)
            return (pt - center).manhattanLength()**2 - radius * radius

        # Binary search for root in [0,1]
        lo, hi = 0.0, 1.0
        for _ in range(100):  # enough precision
            mid = (lo + hi) * 0.5
            if f(mid) > 0:
                hi = mid
            else:
                lo = mid

        return bezier((lo + hi) * 0.5)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        pen = self.pen()
        painter.setPen(pen) 

        # Draw only the curve
        painter.setBrush(QtCore.Qt.NoBrush)
        path = self.path()
        painter.drawPath(path)

        # Draw arrowhead using the helper
        self._draw_arrowhead(
            painter,
            path,
        )

    
    def _draw_arrowhead(self, painter, path):
        """
        Draws an arrowhead at the end of the Bezier curve.
        """
        
        arrow_base = path.pointAtPercent(0.90)

        # --- 4) Tangent direction at arrow base ---
        angle = self.angle_of_entry

        # --- 5) Arrowhead wing points ---
        arrow_p1 = arrow_base + QtCore.QPointF(
            math.cos(angle + math.pi * 5/6) * self.ARROW_SIZE,
            math.sin(angle + math.pi * 5/6) * self.ARROW_SIZE,
        )
        arrow_p2 = arrow_base + QtCore.QPointF(
            math.cos(angle - math.pi * 5/6) * self.ARROW_SIZE,
            math.sin(angle - math.pi * 5/6) * self.ARROW_SIZE,
        )

        # --- 6) Draw the arrowhead ---
        painter.setBrush(self.pen().color())
        painter.drawPolygon(QtGui.QPolygonF([arrow_base, arrow_p1, arrow_p2]))
        
        # draw a small red circle at the true end for debugging
        #painter.setBrush(QtGui.QBrush(QtGui.QColor("#ff0000")))
        #draw on top of the arrowhead for visibility
        #painter.drawEllipse(arrow_base, 2, 2)  




