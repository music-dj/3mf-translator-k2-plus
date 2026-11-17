"""
Detector and parser for .3mf project files from Bambu Studio, OrcaSlicer, PrusaSlicer, and Creality Print.
"""
import io
import json
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional


class MF3Detector:
    """Extracts metadata, printer information, layer heights, filaments, and color swaps from a .3mf file."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.is_valid_3mf = False
        self.project_settings: Dict[str, Any] = {}
        self.model_settings_xml: Optional[str] = None
        self.custom_gcode_xml: Optional[str] = None
        self.slice_info_xml: Optional[str] = None
        self.threed_model_xml: Optional[str] = None
        self.thumbnail_bytes: Optional[bytes] = None
        self.plate_count = 1
        self.objects_count = 0
        self.triangles_count = 0
        self.source_printer_model = "Unknown"
        self.source_printer_settings_id = ""
        self.source_slicer = "Generic 3MF"
        self.bed_size = [256, 256, 256]
        self.layer_height = 0.20
        self.initial_layer_height = 0.20
        self.infill_density = 15
        self.infill_pattern = "grid"
        self.is_hueforge = False
        self.filaments: List[Dict[str, Any]] = []
        self.color_changes: List[Dict[str, Any]] = []
        self.warnings: List[str] = []

        self._parse()

    def _parse(self):
        if not os.path.exists(self.file_path):
            self.warnings.append(f"File not found: {self.file_path}")
            return

        try:
            with zipfile.ZipFile(self.file_path, 'r') as z:
                self.is_valid_3mf = True
                namelist = z.namelist()

                # Read project_settings.config
                if 'Metadata/project_settings.config' in namelist:
                    try:
                        raw = z.read('Metadata/project_settings.config').decode('utf-8', errors='replace')
                        self.project_settings = json.loads(raw)
                    except Exception as e:
                        self.warnings.append(f"Failed to parse project_settings.config: {e}")

                # Read model_settings.config
                if 'Metadata/model_settings.config' in namelist:
                    try:
                        self.model_settings_xml = z.read('Metadata/model_settings.config').decode('utf-8', errors='replace')
                    except Exception as e:
                        self.warnings.append(f"Failed to read model_settings.config: {e}")

                # Read custom_gcode_per_layer.xml
                if 'Metadata/custom_gcode_per_layer.xml' in namelist:
                    try:
                        self.custom_gcode_xml = z.read('Metadata/custom_gcode_per_layer.xml').decode('utf-8', errors='replace')
                    except Exception as e:
                        self.warnings.append(f"Failed to read custom_gcode_per_layer.xml: {e}")

                # Read slice_info.config
                if 'Metadata/slice_info.config' in namelist:
                    try:
                        self.slice_info_xml = z.read('Metadata/slice_info.config').decode('utf-8', errors='replace')
                    except Exception as e:
                        pass

                # Read 3D/3dmodel.model
                if '3D/3dmodel.model' in namelist:
                    try:
                        self.threed_model_xml = z.read('3D/3dmodel.model').decode('utf-8', errors='replace')
                    except Exception as e:
                        pass

                # Find best thumbnail
                thumb_candidates = [
                    'Metadata/plate_1.png',
                    'Metadata/top_1.png',
                    'Metadata/pick_1.png',
                    'Auxiliaries/.thumbnails/thumbnail_middle.png',
                    'Auxiliaries/.thumbnails/thumbnail_3mf.png'
                ]
                for tc in thumb_candidates:
                    if tc in namelist:
                        self.thumbnail_bytes = z.read(tc)
                        break

                if not self.thumbnail_bytes:
                    for name in namelist:
                        if name.endswith('.png') and ('plate' in name.lower() or 'thumbnail' in name.lower()):
                            self.thumbnail_bytes = z.read(name)
                            break

        except Exception as e:
            self.warnings.append(f"Invalid 3MF archive: {e}")
            self.is_valid_3mf = False
            return

        self._extract_metadata()

    def _extract_metadata(self):
        # 1. Source Printer Model & Settings
        self.source_printer_model = self.project_settings.get('printer_model', '')
        self.source_printer_settings_id = self.project_settings.get('printer_settings_id', '')

        if not self.source_printer_model:
            if 'BBL' in self.source_printer_settings_id or 'Bambu' in self.source_printer_settings_id:
                self.source_printer_model = "Bambu Lab Printer"
            elif 'Creality' in self.source_printer_settings_id:
                self.source_printer_model = "Creality Printer"
            else:
                self.source_printer_model = "Universal 3MF"

        # Determine Slicer
        if self.threed_model_xml and 'BambuStudio' in self.threed_model_xml:
            self.source_slicer = "Bambu Studio"
        elif 'OrcaSlicer' in str(self.project_settings):
            self.source_slicer = "OrcaSlicer"
        elif 'Creality' in str(self.project_settings):
            self.source_slicer = "Creality Print"
        else:
            self.source_slicer = "Bambu/Orca Compatible"

        # 2. Bed Size
        printable_area = self.project_settings.get('printable_area', [])
        if isinstance(printable_area, list) and len(printable_area) >= 3:
            try:
                # Format: ['0x0', '256x0', '256x256', '0x256']
                pts = [tuple(map(float, p.split('x'))) for p in printable_area if 'x' in p]
                max_x = max(p[0] for p in pts)
                max_y = max(p[1] for p in pts)
                max_z = float(self.project_settings.get('printable_height', 250))
                self.bed_size = [int(max_x), int(max_y), int(max_z)]
            except Exception:
                self.bed_size = [256, 256, 256]
        elif isinstance(printable_area, str) and 'x' in printable_area:
            # Comma separated
            parts = printable_area.split(',')
            pts = [tuple(map(float, p.split('x'))) for p in parts if 'x' in p]
            if pts:
                max_x = max(p[0] for p in pts)
                max_y = max(p[1] for p in pts)
                max_z = float(self.project_settings.get('printable_height', 250))
                self.bed_size = [int(max_x), int(max_y), int(max_z)]

        # 3. Layer heights and infill
        try:
            self.layer_height = float(self.project_settings.get('layer_height', 0.20))
        except (ValueError, TypeError):
            self.layer_height = 0.20

        try:
            self.initial_layer_height = float(self.project_settings.get('initial_layer_print_height', 0.20))
        except (ValueError, TypeError):
            self.initial_layer_height = 0.20

        try:
            density_str = str(self.project_settings.get('sparse_infill_density', '15%')).replace('%', '')
            self.infill_density = float(density_str)
        except (ValueError, TypeError):
            self.infill_density = 15.0

        self.infill_pattern = self.project_settings.get('sparse_infill_pattern', 'grid')

        # 4. Filaments
        colours = self.project_settings.get('filament_colour', [])
        types = self.project_settings.get('filament_type', [])
        temps = self.project_settings.get('nozzle_temperature', [])

        if isinstance(colours, str):
            colours = [colours]
        if isinstance(types, str):
            types = [types]
        if isinstance(temps, str):
            temps = [temps]

        count = max(len(colours), len(types), 1)
        for i in range(count):
            c = colours[i] if i < len(colours) else '#00AE42'
            t = types[i] if i < len(types) else 'PLA'
            temp_val = temps[i] if i < len(temps) else '220'
            self.filaments.append({
                'slot': i + 1,
                'target_slot': i + 1, # default 1-to-1 mapping
                'color': c,
                'type': t,
                'temperature': temp_val,
                'name': f"Slot {i + 1} ({t})"
            })

        # 5. Color changes / pauses per layer
        if self.custom_gcode_xml:
            try:
                root = ET.fromstring(self.custom_gcode_xml)
                for plate in root.findall('.//plate'):
                    for layer in plate.findall('layer'):
                        top_z = layer.attrib.get('top_z', '0')
                        ext = layer.attrib.get('extruder', '1')
                        col = layer.attrib.get('color', '')
                        action_type = layer.attrib.get('type', '1')
                        gcode = layer.attrib.get('gcode', '')

                        try:
                            z_val = float(top_z)
                        except ValueError:
                            z_val = 0.0

                        try:
                            ext_val = int(ext)
                        except ValueError:
                            ext_val = 1

                        color_hex = col
                        if not color_hex and 1 <= ext_val <= len(self.filaments):
                            color_hex = self.filaments[ext_val - 1]['color']

                        self.color_changes.append({
                            'z': z_val,
                            'extruder': ext_val,
                            'color': color_hex,
                            'type': action_type, # 1: Tool Change, 2: Pause, 3: Custom
                            'gcode': gcode
                        })
            except Exception as e:
                self.warnings.append(f"Failed to parse custom layer gcodes: {e}")

        # 6. Check HueForge characteristics
        has_thin_layers = self.layer_height <= 0.08 or '0.08' in self.source_printer_settings_id or '0.04' in self.source_printer_settings_id
        has_high_infill = self.infill_density >= 95
        print_settings_id = self.project_settings.get('print_settings_id', '').lower()
        if 'hueforge' in print_settings_id or (has_thin_layers and has_high_infill) or (has_thin_layers and len(self.color_changes) >= 1):
            self.is_hueforge = True

        # 7. Count plates
        if self.model_settings_xml:
            try:
                m_root = ET.fromstring(self.model_settings_xml)
                plates = m_root.findall('.//plate')
                if plates:
                    self.plate_count = len(plates)
                objects = m_root.findall('.//object')
                if objects:
                    self.objects_count = len(objects)
            except Exception:
                pass

    def to_dict(self) -> Dict[str, Any]:
        return {
            'file_path': self.file_path,
            'file_name': os.path.basename(self.file_path),
            'file_size_mb': round(os.path.getsize(self.file_path) / (1024 * 1024), 2) if os.path.exists(self.file_path) else 0,
            'source_printer_model': self.source_printer_model,
            'source_printer_settings_id': self.source_printer_settings_id,
            'source_slicer': self.source_slicer,
            'bed_size': self.bed_size,
            'layer_height': self.layer_height,
            'initial_layer_height': self.initial_layer_height,
            'infill_density': self.infill_density,
            'infill_pattern': self.infill_pattern,
            'is_hueforge': self.is_hueforge,
            'plate_count': self.plate_count,
            'objects_count': self.objects_count,
            'filaments': self.filaments,
            'color_changes': self.color_changes,
            'warnings': self.warnings
        }
