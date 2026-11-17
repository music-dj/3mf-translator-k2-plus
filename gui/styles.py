"""
Modern Dark Cyberpunk / Slicer UI Stylesheet for PyQt6.
"""

DARK_THEME_QSS = """
/* Global Reset and Background */
QMainWindow, QDialog {
    background-color: #0c1017;
    color: #e2e8f0;
    font-family: "Segoe UI", "Tajawal", -apple-system, sans-serif;
    font-size: 13px;
}

QWidget {
    color: #e2e8f0;
    font-family: "Segoe UI", "Tajawal", -apple-system, sans-serif;
}

/* ScrollBars */
QScrollBar:vertical {
    border: none;
    background: #0f172a;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #334155;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #475569;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Card Containers */
QFrame.CardFrame {
    background-color: #131b2e;
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 12px;
}

QFrame.DropZone {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #111827, stop:1 #1e293b);
    border: 2px dashed #3b82f6;
    border-radius: 14px;
}
QFrame.DropZone:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #172554, stop:1 #1e293b);
    border: 2px dashed #00d2ff;
}

/* Labels */
QLabel {
    color: #e2e8f0;
}
QLabel.TitleLabel {
    font-size: 18px;
    font-weight: 700;
    color: #ffffff;
}
QLabel.SectionTitle {
    font-size: 14px;
    font-weight: 600;
    color: #38bdf8;
    margin-bottom: 4px;
}
QLabel.SubtitleLabel {
    font-size: 12px;
    color: #94a3b8;
}
QLabel.BadgePill {
    background-color: #0f2744;
    color: #38bdf8;
    border: 1px solid #0284c7;
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}
QLabel.BadgePillGreen {
    background-color: #064e3b;
    color: #34d399;
    border: 1px solid #059669;
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}

/* ComboBox */
QComboBox {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 6px 12px;
    color: #f8fafc;
    font-weight: 500;
    min-height: 28px;
}
QComboBox:hover {
    border: 1px solid #38bdf8;
}
QComboBox:focus {
    border: 1px solid #00d2ff;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 25px;
    border-left: none;
}
QComboBox QAbstractItemView {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    color: #f8fafc;
    padding: 4px;
}

/* Checkbox */
QCheckBox {
    color: #e2e8f0;
    font-size: 13px;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #475569;
    background-color: #1e293b;
}
QCheckBox::indicator:hover {
    border: 1px solid #38bdf8;
}
QCheckBox::indicator:checked {
    background-color: #0284c7;
    border: 1px solid #38bdf8;
}

/* Push Buttons */
QPushButton {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    color: #f8fafc;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #334155;
    border: 1px solid #64748b;
}
QPushButton:pressed {
    background-color: #0f172a;
}

/* Primary Action Button (Green Glow) */
QPushButton.PrimaryBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
    border: 1px solid #34d399;
    border-radius: 10px;
    color: #ffffff;
    padding: 10px 22px;
    font-size: 14px;
    font-weight: 700;
}
QPushButton.PrimaryBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #34d399);
    border: 1px solid #6ee7b7;
}
QPushButton.PrimaryBtn:pressed {
    background: #047857;
}

/* Secondary Action Button (Cyan / Blue Glow) */
QPushButton.SecondaryBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #06b6d4);
    border: 1px solid #38bdf8;
    border-radius: 10px;
    color: #ffffff;
    padding: 10px 20px;
    font-size: 13px;
    font-weight: 700;
}
QPushButton.SecondaryBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369a1, stop:1 #0891b2);
    border: 1px solid #7dd3fc;
}

/* Log Terminal Box */
QTextEdit.TerminalBox {
    background-color: #080c14;
    border: 1px solid #1e293b;
    border-radius: 8px;
    color: #38bdf8;
    font-family: "Consolas", "Cascadia Code", monospace;
    font-size: 11px;
    padding: 8px;
}

/* Tables */
QTableWidget {
    background-color: #131b2e;
    border: 1px solid #1e293b;
    border-radius: 8px;
    gridline-color: #1e293b;
    color: #e2e8f0;
}
QHeaderView::section {
    background-color: #1e293b;
    color: #94a3b8;
    border: none;
    padding: 6px;
    font-weight: 600;
    font-size: 12px;
}
"""
