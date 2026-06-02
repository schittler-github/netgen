from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt

from graph_items import GraphNode


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
