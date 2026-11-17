"""
Interactive Filament Palette & Creality CFS Slot Mapper Widget.
"""
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QComboBox, QFrame, QScrollArea
)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt, pyqtSignal
from typing import List, Dict, Any


class FilamentCard(QFrame):
    """Card representing one filament with color swatch and CFS slot selector."""
    mapping_changed = pyqtSignal(int, int) # (source_slot, target_cfs_slot)

    def __init__(self, filament_data: Dict[str, Any], max_cfs_slots: int = 4, parent=None):
        super().__init__(parent)
        self.filament_data = filament_data
        self.source_slot = filament_data.get('slot', 1)
        self.max_cfs_slots = max(max_cfs_slots, self.source_slot)

        self.setObjectName("FilamentCard")
        self.setStyleSheet("""
            QFrame#FilamentCard {
                background-color: #1a2234;
                border: 1px solid #2d3748;
                border-radius: 10px;
                padding: 6px;
                min-width: 140px;
            }
            QFrame#FilamentCard:hover {
                border: 1px solid #3b82f6;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header: Color Swatch + Slot Number
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        color_hex = filament_data.get('color', '#00AE42')
        swatch = QLabel()
        swatch.setFixedSize(24, 24)
        swatch.setStyleSheet(f"""
            background-color: {color_hex};
            border-radius: 12px;
            border: 2px solid #ffffff;
        """)
        top_row.addWidget(swatch)

        slot_title = QLabel(f"<b>خيط #{self.source_slot}</b>")
        slot_title.setStyleSheet("font-size: 13px; color: #f8fafc;")
        top_row.addWidget(slot_title)
        top_row.addStretch()

        layout.addLayout(top_row)

        # Details: Type & Hex
        type_str = filament_data.get('type', 'PLA')
        temp_str = filament_data.get('temperature', '220')
        detail_lbl = QLabel(f"{type_str} • {color_hex.upper()}")
        detail_lbl.setStyleSheet("font-size: 11px; color: #94a3b8;")
        layout.addWidget(detail_lbl)

        # CFS Slot Selector
        cfs_row = QHBoxLayout()
        cfs_lbl = QLabel("محطة CFS:")
        cfs_lbl.setStyleSheet("font-size: 11px; color: #38bdf8; font-weight: 600;")
        cfs_row.addWidget(cfs_lbl)

        self.cfs_combo = QComboBox()
        for i in range(1, self.max_cfs_slots + 1):
            self.cfs_combo.addItem(f"Slot {i}", i)

        cur_target = filament_data.get('target_slot', self.source_slot)
        if 1 <= cur_target <= self.max_cfs_slots:
            self.cfs_combo.setCurrentIndex(cur_target - 1)

        self.cfs_combo.currentIndexChanged.connect(self._on_slot_changed)
        cfs_row.addWidget(self.cfs_combo)

        layout.addLayout(cfs_row)

    def _on_slot_changed(self, index: int):
        target_slot = self.cfs_combo.currentData()
        self.mapping_changed.emit(self.source_slot, target_slot)

    def get_target_slot(self) -> int:
        return self.cfs_combo.currentData()


class FilamentBarWidget(QWidget):
    """Scrollable container of filament cards."""
    mapping_updated = pyqtSignal(dict) # {src_slot: target_slot}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards: List[FilamentCard] = []
        self.current_mapping: Dict[int, int] = {}

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFixedHeight(125)
        self.scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        self.container = QWidget()
        self.container.setStyleSheet("background-color: transparent;")
        self.card_layout = QHBoxLayout(self.container)
        self.card_layout.setContentsMargins(4, 4, 4, 4)
        self.card_layout.setSpacing(10)
        self.card_layout.addStretch()

        self.scroll.setWidget(self.container)
        main_layout.addWidget(self.scroll)

    def set_filaments(self, filaments: List[Dict[str, Any]], cfs_capacity: int = 4):
        for card in self.cards:
            card.setParent(None)
            card.deleteLater()
        self.cards.clear()
        self.current_mapping.clear()

        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        max_slots = max(cfs_capacity, len(filaments))

        for fil in filaments:
            card = FilamentCard(fil, max_cfs_slots=max_slots)
            card.mapping_changed.connect(self._on_card_mapping_changed)
            self.cards.append(card)
            self.card_layout.addWidget(card)
            self.current_mapping[card.source_slot] = card.get_target_slot()

        self.card_layout.addStretch()
        self.mapping_updated.emit(self.current_mapping)

    def _on_card_mapping_changed(self, src: int, tgt: int):
        self.current_mapping[src] = tgt
        self.mapping_updated.emit(self.current_mapping)

    def get_mapping(self) -> Dict[int, int]:
        return self.current_mapping
