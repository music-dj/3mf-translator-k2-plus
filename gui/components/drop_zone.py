"""
Drag and Drop zone widget for .3mf files.
"""
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QPushButton, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent


class DropZone(QFrame):
    """Interactive drag and drop zone for 3MF files."""
    file_selected = pyqtSignal(str)
    batch_selected = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setProperty("class", "DropZone")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(120)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(6)

        self.icon_lbl = QLabel("📥")
        self.icon_lbl.setStyleSheet("font-size: 28px; background: transparent;")
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_lbl)

        self.text_lbl = QLabel("اسحب وأفلت ملف 3MF هنا، أو انقر للاختيار")
        self.text_lbl.setStyleSheet("font-size: 14px; font-weight: 600; color: #f8fafc; background: transparent;")
        self.text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.text_lbl)

        self.sub_lbl = QLabel("يدعم ملفات MakerWorld و Bambu Studio و HueForge و PrusaSlicer")
        self.sub_lbl.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent;")
        self.sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.sub_lbl)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._browse_file()

    def _browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "اختر ملف 3MF للترجمة",
            "",
            "3MF Project Files (*.3mf);;All Files (*.*)"
        )
        if file_path:
            self.file_selected.emit(file_path)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(u.toLocalFile().lower().endswith('.3mf') for u in urls):
                event.acceptProposedAction()
                self.setStyleSheet("""
                    QFrame {
                        background-color: #172554 !important;
                        border: 2px dashed #00d2ff !important;
                    }
                """)

    def dragLeaveEvent(self, event):
        self.setStyleSheet("")

    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet("")
        urls = event.mimeData().urls()
        mf_files = [u.toLocalFile() for u in urls if u.toLocalFile().lower().endswith('.3mf')]
        if len(mf_files) == 1:
            self.file_selected.emit(mf_files[0])
        elif len(mf_files) > 1:
            self.batch_selected.emit(mf_files)
