import json

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt


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
            pixmap = QtGui.QPixmap(140, 34)
            pixmap.fill(QtGui.QColor(self.color))
            painter = QtGui.QPainter(pixmap)
            painter.setPen(QtGui.QPen(QtGui.QColor("#111")))
            painter.drawText(pixmap.rect(), Qt.AlignCenter, self.text)
            painter.end()
            drag.setPixmap(pixmap)
            drag.exec(Qt.CopyAction)
        super().mousePressEvent(event)
