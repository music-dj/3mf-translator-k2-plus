"""
K2 Plus 3MF Studio Translator - Entry Point
"""
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from gui.main_window import MainWindow


def main():
    if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("K2 Plus 3MF Studio Translator")
    app.setOrganizationName("Creality K2 Plus Tools")

    window = MainWindow()

    if len(sys.argv) > 1:
        initial_file = sys.argv[1]
        if os.path.isfile(initial_file) and initial_file.lower().endswith('.3mf'):
            window.load_file(initial_file)

    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
