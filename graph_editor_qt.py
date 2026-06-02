import sys

from PySide6 import QtWidgets
from editor_window import GraphEditorWindow


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = GraphEditorWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
