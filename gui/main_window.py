"""
Main Window for K2 Plus 3MF Studio Translator.
"""
import os
import tempfile
from typing import Optional
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QCheckBox, QFrame, QTextEdit,
    QFileDialog, QMessageBox, QSplitter, QProgressBar, QTableWidget,
    QTableWidgetItem, QHeaderView, QTabWidget
)
from PyQt6.QtGui import QPixmap, QImage, QColor, QFont, QIcon
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal

from core.detector import MF3Detector
from core.translator import K2PlusTranslator
from core.slicer_finder import SlicerFinder
from core.profile_policy import LocalProfiles
from gui.components.drop_zone import DropZone
from gui.components.filament_bar import FilamentBarWidget
from gui.styles import DARK_THEME_QSS


class TranslationWorker(QThread):
    """Background worker for translating 3MF files to keep UI responsive."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)

    def __init__(self, translator: K2PlusTranslator, params: dict):
        super().__init__()
        self.translator = translator
        self.params = params

    def run(self):
        try:
            res = self.translator.translate(
                src_path=self.params['src'],
                dst_path=self.params['dst'],
                nozzle=self.params['nozzle'],
                printer_preset_name=self.params['printer_preset'],
                center_on_bed=self.params['center'],
                preserve_hueforge=self.params['preserve_hueforge'],
                target_slicer=self.params.get('slicer', 'orca')
            )
        except Exception as error:
            res = {'success': False, 'errors': [str(error)], 'logs': []}
        self.finished.emit(res)


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("K2 Plus 3MF Studio Translator • مترجم مشاريع 3MF لـ Creality K2 Plus")
        self.setMinimumSize(1020, 750)
        self.setStyleSheet(DARK_THEME_QSS)

        self.translator = K2PlusTranslator()
        self.current_detector: Optional[MF3Detector] = None
        self.current_file: Optional[str] = None
        self.filament_mapping: dict = {}

        self._init_ui()
        self._check_installed_slicers()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(12)

        # 1. Header Bar
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        app_title = QLabel("🚀 K2 Plus 3MF Studio Translator")
        app_title.setStyleSheet("font-size: 20px; font-weight: 800; color: #ffffff;")
        title_box.addWidget(app_title)

        app_subtitle = QLabel("نقل إعدادات المشروع إلى بروفايل K2 Plus الموجود لديك — الفلمنت تختاره في السلايسر")
        app_subtitle.setStyleSheet("font-size: 12px; color: #94a3b8;")
        title_box.addWidget(app_subtitle)
        header_layout.addLayout(title_box)

        header_layout.addStretch()

        # Slicer detection pills
        self.creality_pill = QLabel("Creality Print: جاري الفحص...")
        self.creality_pill.setProperty("class", "BadgePill")
        header_layout.addWidget(self.creality_pill)

        self.orca_pill = QLabel("OrcaSlicer: جاري الفحص...")
        self.orca_pill.setProperty("class", "BadgePill")
        header_layout.addWidget(self.orca_pill)

        main_layout.addLayout(header_layout)

        # 2. DropZone
        self.drop_zone = DropZone()
        self.drop_zone.file_selected.connect(self.load_file)
        self.drop_zone.batch_selected.connect(self.load_batch)
        main_layout.addWidget(self.drop_zone)

        # 3. Middle Section: Model Info & Settings Cards
        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(12)

        # Left Card: Model & Source Info
        self.info_card = QFrame()
        self.info_card.setProperty("class", "CardFrame")
        info_layout = QVBoxLayout(self.info_card)
        info_layout.setContentsMargins(12, 12, 12, 12)
        info_layout.setSpacing(8)

        card_title = QLabel("📋 تفاصيل الملف الأصلي (Source Model)")
        card_title.setProperty("class", "SectionTitle")
        info_layout.addWidget(card_title)

        thumb_row = QHBoxLayout()
        self.thumb_lbl = QLabel()
        self.thumb_lbl.setFixedSize(110, 110)
        self.thumb_lbl.setStyleSheet("""
            background-color: #0b0f17;
            border: 1px solid #1e293b;
            border-radius: 8px;
        """)
        self.thumb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_lbl.setText("لا توجد معاينة")
        thumb_row.addWidget(self.thumb_lbl)

        details_vbox = QVBoxLayout()
        details_vbox.setSpacing(4)
        self.file_name_lbl = QLabel("الملف: لم يتم اختيار ملف")
        self.file_name_lbl.setStyleSheet("font-weight: 700; color: #f8fafc;")
        details_vbox.addWidget(self.file_name_lbl)

        self.source_printer_lbl = QLabel("الطابعة المصدر: -")
        self.source_printer_lbl.setStyleSheet("color: #38bdf8;")
        details_vbox.addWidget(self.source_printer_lbl)

        self.source_bed_lbl = QLabel("أبعاد السطح الأصلي: -")
        details_vbox.addWidget(self.source_bed_lbl)

        self.layer_info_lbl = QLabel("ارتفاع الطبقة: -")
        details_vbox.addWidget(self.layer_info_lbl)

        self.hueforge_badge = QLabel("🎨 بروفايل HueForge مدمج")
        self.hueforge_badge.setProperty("class", "BadgePillGreen")
        self.hueforge_badge.setVisible(False)
        details_vbox.addWidget(self.hueforge_badge)

        thumb_row.addLayout(details_vbox)
        thumb_row.addStretch()
        info_layout.addLayout(thumb_row)

        middle_layout.addWidget(self.info_card, 1)

        # Right Card: Target Settings & Options
        self.settings_card = QFrame()
        self.settings_card.setProperty("class", "CardFrame")
        settings_layout = QVBoxLayout(self.settings_card)
        settings_layout.setContentsMargins(12, 12, 12, 12)
        settings_layout.setSpacing(10)

        set_title = QLabel("⚙️ إعدادات الترجمة لـ Creality K2 Plus")
        set_title.setProperty("class", "SectionTitle")
        settings_layout.addWidget(set_title)

        grid = QGridLayout()
        grid.setSpacing(8)

        grid.addWidget(QLabel("قطر الفوهة (Nozzle):"), 0, 0)
        self.nozzle_combo = QComboBox()
        self.nozzle_combo.addItem("0.4 mm (الافتراضي - سرعة وجودة متوازنة)", "0.4")
        self.nozzle_combo.addItem("0.2 mm (فائق الدقة - موصى به لـ HueForge)", "0.2")
        self.nozzle_combo.addItem("0.6 mm (سرعة عالية)", "0.6")
        self.nozzle_combo.addItem("0.8 mm (طباعة خشنة سريعة)", "0.8")
        grid.addWidget(self.nozzle_combo, 0, 1)

        grid.addWidget(QLabel("السلايسر المستهدف:"), 1, 0)
        self.slicer_combo = QComboBox()
        self.slicer_combo.addItem("Creality Print 7.x / 5.x (موصى به)", "creality")
        self.slicer_combo.addItem("OrcaSlicer", "orca")
        self.slicer_combo.setCurrentIndex(1)
        grid.addWidget(self.slicer_combo, 1, 1)
        grid.addWidget(QLabel("بروفايل الطابعة الموجود في السلايسر:"), 2, 0)
        self.printer_combo = QComboBox()
        grid.addWidget(self.printer_combo, 2, 1)
        self.slicer_combo.currentIndexChanged.connect(self._refresh_printer_profiles)
        self.nozzle_combo.currentIndexChanged.connect(self._refresh_printer_profiles)
        self._refresh_printer_profiles()

        settings_layout.addLayout(grid)

        # Checkboxes
        self.center_checkbox = QCheckBox("توسيط النموذج تلقائياً في منتصف سطح K2 Plus (350x350 مم)")
        self.center_checkbox.setChecked(False)
        settings_layout.addWidget(self.center_checkbox)

        self.hueforge_checkbox = QCheckBox("الحفاظ على ارتفاعات الطبقات والحشوة وإعدادات الطباعة من الملف")
        self.hueforge_checkbox.setChecked(True)
        settings_layout.addWidget(self.hueforge_checkbox)

        self.klipper_checkbox = QCheckBox("استخدام بروفايل الطابعة المحدد دون تغيير اسمه أو بيانات اتصاله")
        self.klipper_checkbox.setChecked(True)
        self.klipper_checkbox.setEnabled(False)
        settings_layout.addWidget(self.klipper_checkbox)

        settings_layout.addStretch()
        middle_layout.addWidget(self.settings_card, 1)

        main_layout.addLayout(middle_layout)

        # 4. Filament & CFS Remapper Card
        self.filament_card = QFrame()
        self.filament_card.setProperty("class", "CardFrame")
        filament_card_layout = QVBoxLayout(self.filament_card)
        filament_card_layout.setContentsMargins(12, 10, 12, 10)
        filament_card_layout.setSpacing(6)

        fil_header = QHBoxLayout()
        fil_title = QLabel("الفلمنت: بروفايلات السلايسر المحلية")
        fil_title.setProperty("class", "SectionTitle")
        fil_header.addWidget(fil_title)
        fil_header.addStretch()
        fil_hint = QLabel("لا تُستورد حرارة الفلمنت أو تدفقه أو ألوانه من الملف. تختارها أنت بعد الفتح.")
        fil_hint.setStyleSheet("font-size: 11px; color: #94a3b8;")
        fil_header.addWidget(fil_hint)
        filament_card_layout.addLayout(fil_header)

        self.filament_bar = FilamentBarWidget()
        self.filament_bar.hide()

        main_layout.addWidget(self.filament_card)

        # 5. Action Buttons Bar
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)

        self.btn_creality = QPushButton("⚡ ترجمة وفتح فوراً في Creality Print")
        self.btn_creality.setProperty("class", "PrimaryBtn")
        self.btn_creality.clicked.connect(self.translate_and_open_creality)
        actions_layout.addWidget(self.btn_creality, 2)

        self.btn_orca = QPushButton("🌀 فتح في OrcaSlicer")
        self.btn_orca.setProperty("class", "SecondaryBtn")
        self.btn_orca.clicked.connect(self.translate_and_open_orca)
        actions_layout.addWidget(self.btn_orca, 1)

        self.btn_save = QPushButton("💾 حفظ الملف المترجم (.3mf)")
        self.btn_save.clicked.connect(self.translate_and_save)
        actions_layout.addWidget(self.btn_save, 1)

        self.btn_batch = QPushButton("📁 ترجمة دفعة مجلد...")
        self.btn_batch.clicked.connect(self.open_batch_dialog)
        actions_layout.addWidget(self.btn_batch, 1)

        main_layout.addLayout(actions_layout)

        # 6. Terminal Log Box
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFixedHeight(110)
        self.log_box.setProperty("class", "TerminalBox")
        self.log_box.setPlaceholderText("سجل العمليات والترجمة يظهر هنا...")
        main_layout.addWidget(self.log_box)

        # Status Bar / Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #0f172a;
                border: none;
            }
            QProgressBar::chunk {
                background: #10b981;
            }
        """)
        main_layout.addWidget(self.progress_bar)

        self.log("مرحباً بك في K2 Plus 3MF Studio Translator! جاهز للعمل.")

    def _refresh_printer_profiles(self, *_):
        slicer = self.slicer_combo.currentData()
        nozzle = self.nozzle_combo.currentData()
        profiles = LocalProfiles(slicer)
        previous = self.printer_combo.currentText()
        names = profiles.names(nozzle)
        preferred = previous if previous in names else profiles.default_name(nozzle)
        self.printer_combo.clear()
        self.printer_combo.addItems(names)
        self.printer_combo.setCurrentText(preferred)

    def _check_installed_slicers(self):
        slicers = SlicerFinder.find_all()
        cp = slicers.get('creality_print')
        orca = slicers.get('orca_slicer')

        if cp:
            self.creality_pill.setText("Creality Print: متصل ✓")
            self.creality_pill.setProperty("class", "BadgePillGreen")
            self.creality_pill.style().unpolish(self.creality_pill)
            self.creality_pill.style().polish(self.creality_pill)
        else:
            self.creality_pill.setText("Creality Print: غير موجود")

        if orca:
            self.orca_pill.setText("OrcaSlicer: متصل ✓")
            self.orca_pill.setProperty("class", "BadgePillGreen")
            self.orca_pill.style().unpolish(self.orca_pill)
            self.orca_pill.style().polish(self.orca_pill)
        else:
            self.orca_pill.setText("OrcaSlicer: غير موجود")

    def log(self, msg: str):
        self.log_box.append(f"> {msg}")
        self.log_box.verticalScrollBar().setValue(self.log_box.verticalScrollBar().maximum())

    def load_file(self, file_path: str):
        if not os.path.isfile(file_path):
            return

        self.current_file = file_path
        self.log(f"تم تحميل الملف: {file_path}")

        detector = MF3Detector(file_path)
        if not detector.is_valid_3mf:
            QMessageBox.critical(self, "خطأ", f"الملف المختار ليس أرشيف 3MF صالح:\n{file_path}")
            return

        self.current_detector = detector
        info = detector.to_dict()

        # Update UI Labels
        self.file_name_lbl.setText(f"الملف: {info['file_name']} ({info['file_size_mb']} MB)")
        self.source_printer_lbl.setText(f"الطابعة المصدر: {info['source_printer_model']} ({info['source_slicer']})")
        self.source_bed_lbl.setText(f"أبعاد السطح الأصلي: {info['bed_size'][0]}x{info['bed_size'][1]}x{info['bed_size'][2]} مم  ➔  K2 Plus: 350x350x350 مم")
        self.layer_info_lbl.setText(f"ارتفاع الطبقة: {info['layer_height']} مم (الأولى: {info['initial_layer_height']} مم) • الحشوة: {info['infill_density']}%")

        if info['is_hueforge']:
            self.hueforge_badge.setVisible(True)
            self.log("🎨 تم التحقق: الملف يحتوي على بروفايل لوحة HueForge فائقة الدقة!")
        else:
            self.hueforge_badge.setVisible(False)

        # Update thumbnail
        if detector.thumbnail_bytes:
            pixmap = QPixmap()
            pixmap.loadFromData(detector.thumbnail_bytes)
            scaled = pixmap.scaled(110, 110, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.thumb_lbl.setPixmap(scaled)
        else:
            self.thumb_lbl.setText("3MF\nProject")

        # Update Filaments
        self.log("لن يتم استيراد بروفايلات الفلمنت من الملف. ستختار الفلمنت في السلايسر.")

    def load_batch(self, files: list):
        if not files:
            return
        reply = QMessageBox.question(
            self,
            "ترجمة دفعة ملفات",
            f"تم إفلات {len(files)} ملفات 3MF. هل ترغب في ترجمتها دفعة واحدة لـ Creality K2 Plus؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            out_dir = QFileDialog.getExistingDirectory(self, "اختر مجلد الحفظ للملفات المترجمة")
            if out_dir:
                self._run_batch_translate(files, out_dir)

    def _on_filament_mapping_updated(self, mapping: dict):
        self.filament_mapping = mapping

    def translate_and_open_creality(self):
        if not self.current_file:
            QMessageBox.warning(self, "تنبيه", "يرجى اختيار ملف 3MF أولاً!")
            return

        cp_path = SlicerFinder.find_creality_print()
        if not cp_path:
            QMessageBox.critical(self, "خطأ", "لم يتم العثور على برنامج Creality Print على جهازك!")
            return

        base_name = os.path.splitext(os.path.basename(self.current_file))[0]
        temp_dir = os.path.dirname(self.current_file)
        dst_path = os.path.join(temp_dir, f"{base_name}_K2_Plus.3mf")

        self._start_translation(dst_path, open_slicer='creality_print')

    def translate_and_open_orca(self):
        if not self.current_file:
            QMessageBox.warning(self, "تنبيه", "يرجى اختيار ملف 3MF أولاً!")
            return

        orca_path = SlicerFinder.find_orca_slicer()
        if not orca_path:
            QMessageBox.critical(self, "خطأ", "لم يتم العثور على برنامج OrcaSlicer على جهازك!")
            return

        base_name = os.path.splitext(os.path.basename(self.current_file))[0]
        temp_dir = os.path.dirname(self.current_file)
        dst_path = os.path.join(temp_dir, f"{base_name}_K2_Plus.3mf")

        self._start_translation(dst_path, open_slicer='orca_slicer')

    def translate_and_save(self):
        if not self.current_file:
            QMessageBox.warning(self, "تنبيه", "يرجى اختيار ملف 3MF أولاً!")
            return

        base_name = os.path.splitext(os.path.basename(self.current_file))[0]
        default_name = f"{base_name}_K2_Plus.3mf"

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "حفظ ملف Creality K2 Plus 3MF المترجم",
            default_name,
            "3MF Project (*.3mf)"
        )
        if save_path:
            self._start_translation(save_path, open_slicer=None)

    def _start_translation(self, dst_path: str, open_slicer: Optional[str] = None):
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.btn_creality.setEnabled(False)
        self.btn_orca.setEnabled(False)
        self.btn_save.setEnabled(False)

        nozzle_val = self.nozzle_combo.currentData()
        slicer_val = {'orca_slicer': 'orca', 'creality_print': 'creality'}.get(open_slicer, self.slicer_combo.currentData())
        if slicer_val != self.slicer_combo.currentData():
            self.slicer_combo.setCurrentIndex(0 if slicer_val == 'creality' else 1)

        params = {
            'src': self.current_file,
            'dst': dst_path,
            'nozzle': nozzle_val,
            'center': self.center_checkbox.isChecked(),
            'preserve_hueforge': self.hueforge_checkbox.isChecked(),
            'printer_preset': self.printer_combo.currentText(),
            'slicer': slicer_val
        }

        self.worker = TranslationWorker(self.translator, params)
        self.worker.finished.connect(lambda res: self._on_translation_finished(res, open_slicer))
        self.worker.start()

    def _on_translation_finished(self, res: dict, open_slicer: Optional[str]):
        self.progress_bar.setVisible(False)
        self.btn_creality.setEnabled(True)
        self.btn_orca.setEnabled(True)
        self.btn_save.setEnabled(True)

        for line in res.get('logs', []):
            self.log(line)

        if res.get('success'):
            dst = res['destination_file']
            self.log(f"🎉 تم تحويل المشروع بنجاح إلى Creality K2 Plus ({res['nozzle']}mm)!")

            if open_slicer:
                self.log(f"جاري فتح الملف في {open_slicer}...")
                ok = SlicerFinder.launch(open_slicer, dst)
                if ok:
                    self.log(f"تم إطلاق السلايسر بنجاح مع تحميل المشروع!")
                else:
                    self.log("تعذر تشغيل السلايسر تلقائياً.")
            else:
                QMessageBox.information(
                    self,
                    "نجاح التحويل",
                    f"تم تحويل الملف وحفظه في:\n{dst}\n\nاختر بروفايلات الفلمنت داخل السلايسر، ثم أعد التقطيع وراجع المعاينة."
                )
        else:
            err = "\n".join(res.get('errors', ['خطأ غير معروف']))
            QMessageBox.critical(self, "فشل التحويل", f"حدث خطأ أثناء الترجمة:\n{err}")

    def open_batch_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "اختر ملفات 3MF للترجمة الدفعية",
            "",
            "3MF Files (*.3mf)"
        )
        if files:
            out_dir = QFileDialog.getExistingDirectory(self, "اختر مجلد الحفظ")
            if out_dir:
                self._run_batch_translate(files, out_dir)

    def _run_batch_translate(self, files: list, out_dir: str):
        self.log(f"بدء ترجمة دفعة من {len(files)} ملف...")
        success_count = 0
        nozzle_val = self.nozzle_combo.currentData()
        slicer_val = self.slicer_combo.currentData()

        for f in files:
            bname = os.path.splitext(os.path.basename(f))[0]
            dst = os.path.join(out_dir, f"{bname}_K2_Plus.3mf")
            res = self.translator.translate(
                src_path=f,
                dst_path=dst,
                nozzle=nozzle_val,
                printer_preset_name=self.printer_combo.currentText(),
                center_on_bed=self.center_checkbox.isChecked(),
                preserve_hueforge=self.hueforge_checkbox.isChecked(),
                target_slicer=slicer_val
            )
            if res.get('success'):
                success_count += 1
                self.log(f"✓ تم تحويل: {os.path.basename(f)}")
            else:
                self.log(f"✗ فشل: {os.path.basename(f)}")

        QMessageBox.information(
            self,
            "اكتمال الترجمة الدفعية",
            f"تمت ترجمة {success_count} من أصل {len(files)} ملفات بنجاح وحفظها في:\n{out_dir}"
        )
