"""
Core translation engine for converting .3mf project files to Creality K2 Plus.
Preserves geometry, process settings and layer assignments; excludes source materials.
Defaults to the user's primary profile: 'Creality K2 Plus 0.4 nozzle - wifi'.
"""
import copy
import json
import os
import re
import shutil
import tempfile
import zipfile
from typing import Dict, Any, List, Optional, Tuple
from core.profile_policy import (LocalProfiles, clean_process_settings, strip_material_overrides,
                                 is_material_key, PRINTER_KEYS, CONNECTION_KEY)


class K2PlusTranslator:
    """Translate process settings while referring to existing local printer/material presets."""

    DEFAULT_PRESET = "Creality K2 Plus 0.4 nozzle - wifi"

    def __init__(self, presets_path: Optional[str] = None):
        self.presets: Dict[str, Any] = {}
        self.slicer_machines: Dict[str, Any] = {}
        if not presets_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            presets_path = os.path.join(base_dir, 'profiles', 'k2_plus_presets.json')

        if os.path.isfile(presets_path):
            try:
                with open(presets_path, 'r', encoding='utf-8') as f:
                    self.presets = json.load(f)
            except Exception:
                pass
        machine_path = os.path.join(os.path.dirname(presets_path), 'machines-by-slicer.json')
        if os.path.isfile(machine_path):
            with open(machine_path, encoding='utf-8') as stream:
                self.slicer_machines = json.load(stream)

    def translate(
        self,
        src_path: str,
        dst_path: str,
        printer_preset_name: Optional[str] = None,
        center_on_bed: bool = True,
        preserve_hueforge: bool = True,
        target_slicer: str = "orca",
        nozzle: str = "0.4",
        filament_mapping: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Executes the conversion process:
        - Excludes source material properties and embedded material presets.
        - Sets printer profile to user's requested preset (e.g. Creality K2 Plus 0.4 nozzle - wifi).
        - Corrects bed dimensions to 350x350x350 mm.
        - Shifting coordinates via regex to preserve 100% 3D geometry data.
        """
        profiles = LocalProfiles(target_slicer)
        printer_preset_name = printer_preset_name or profiles.default_name(nozzle)
        report: Dict[str, Any] = {
            'success': False,
            'source_file': src_path,
            'destination_file': dst_path,
            'printer_preset': printer_preset_name,
            'source_printer': 'Unknown',
            'target_printer': printer_preset_name,
            'bed_offset': [0.0, 0.0],
            'logs': [],
            'errors': []
        }

        if os.path.normcase(os.path.abspath(src_path)) == os.path.normcase(os.path.abspath(dst_path)):
            report['errors'].append("Choose a new output path; the original project is never overwritten.")
            return report

        if not os.path.isfile(src_path):
            report['errors'].append(f"Source file not found: {src_path}")
            return report

        # Extract nozzle size from preset name (e.g. '0.4' from '... 0.4 nozzle ...')
        nozzle_match = re.search(r'(\d+\.\d+)\s*nozzle', printer_preset_name, re.IGNORECASE)
        nozzle = nozzle_match.group(1) if nozzle_match else nozzle
        report['nozzle'] = nozzle
        if printer_preset_name not in profiles.names(nozzle):
            report['errors'].append("The selected printer preset does not exist in this slicer's active presets.")
            return report
        k2_machine = self.slicer_machines.get(target_slicer, {}).get(nozzle) or self.presets.get('machines', {}).get(nozzle, {})
        local_machine, default_materials = profiles.resolve(printer_preset_name, k2_machine)
        if not default_materials:
            default_materials = k2_machine.get('default_filament_profile', [])
        if isinstance(default_materials, str):
            default_materials = [default_materials]
        if not default_materials:
            report['errors'].append("The selected printer has no default material preset. Configure it in the slicer first.")
            return report

        temp_dir = tempfile.mkdtemp(prefix="k2_3mf_")

        try:
            with zipfile.ZipFile(src_path, 'r') as zin:
                namelist = zin.namelist()
                report['logs'].append(f"Reading 3MF archive ({len(namelist)} entries)...")
                if len(set(namelist)) != len(namelist) or len(namelist) > 10000:
                    raise ValueError("Duplicate members or too many archive members")
                if sum(info.file_size for info in zin.infolist()) > 500 * 1024 * 1024:
                    raise ValueError("Expanded project exceeds 500 MB")
                for name in namelist:
                    if name.startswith(('/', '\\')) or '\\' in name or ':' in name or '..' in name.split('/'):
                        raise ValueError("Unsafe archive path")
                zin.extractall(temp_dir)

            # 1. Modify Metadata/project_settings.config
            proj_cfg_path = os.path.join(temp_dir, 'Metadata', 'project_settings.config')
            old_bed_w = 256.0
            old_bed_d = 256.0
            is_hueforge = False

            if os.path.isfile(proj_cfg_path):
                with open(proj_cfg_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)

                report['source_printer'] = cfg.get('printer_model', 'Unknown Bambu/Generic')
                report['logs'].append(f"Source printer identified: {report['source_printer']}")

                # Detect old bed size
                old_printable_area = cfg.get('printable_area', [])
                if isinstance(old_printable_area, list) and len(old_printable_area) >= 3:
                    pts = [p.split('x') for p in old_printable_area if 'x' in p]
                    xs = [float(p[0]) for p in pts if len(p) == 2]
                    ys = [float(p[1]) for p in pts if len(p) == 2]
                    if xs and ys:
                        old_bed_w = max(xs)
                        old_bed_d = max(ys)
                report['logs'].append(f"Original bed dimensions: {old_bed_w}x{old_bed_d} mm")

                # Detect HueForge
                layer_h = float(cfg.get('layer_height', 0.20))
                sparse_infill = str(cfg.get('sparse_infill_density', '15%'))
                print_settings_id = cfg.get('print_settings_id', '')
                if layer_h <= 0.08 or 'hueforge' in print_settings_id.lower() or '100' in sparse_infill:
                    is_hueforge = True
                    report['logs'].append(f"🎨 HueForge profile detected! (Layer height: {layer_h}mm, Infill: {sparse_infill})")

                # Keep process settings; never import source material/connection settings.
                source_slot_count = max(1, *(len(cfg.get(key, [])) if isinstance(cfg.get(key), list) else 1
                                            for key in ('filament_settings_id', 'filament_colour', 'filament_type')))
                cfg, dropped = clean_process_settings(cfg)
                report['excluded_material_fields'] = [k for k in dropped if is_material_key(k)]
                # Only printable fields from the chosen LOCAL preset. Network keys stay in the slicer.
                for key, value in local_machine.items():
                    if key in PRINTER_KEYS and not is_material_key(key) and not CONNECTION_KEY.search(key):
                        cfg[key] = value
                cfg['printer_model'] = "Creality K2 Plus"
                cfg['printer_settings_id'] = printer_preset_name
                cfg['printable_area'] = ["0x0", "350x0", "350x350", "0x350"]
                cfg['printable_height'] = "350"
                cfg['best_object_pos'] = "0.5,0.5"
                cfg['gcode_flavor'] = "klipper"
                cfg['auxiliary_fan'] = "1"
                cfg['nozzle_diameter'] = [nozzle]

                cfg['filament_settings_id'] = [default_materials[i] if i < len(default_materials) else default_materials[0]
                                               for i in range(source_slot_count)]
                cfg['default_filament_profile'] = default_materials
                report['filament_policy'] = 'local-default-presets'
                report['default_material_preset'] = default_materials[0]
                report['logs'].append("Source material profiles, colors, temperatures and flow excluded. Select materials in the slicer.")

                # Sanitize Slicer Differences (Prevents OrcaSlicer warning popups)
                if cfg.get('ensure_vertical_shell_thickness') == 'enabled':
                    cfg['ensure_vertical_shell_thickness'] = 'ensure_all'
                elif cfg.get('ensure_vertical_shell_thickness') in ['0', 0, False]:
                    cfg['ensure_vertical_shell_thickness'] = 'disabled'

                # Machine G-Codes
                if local_machine:
                    for gcode_key in ['machine_start_gcode', 'machine_end_gcode', 'change_filament_gcode',
                                      'before_layer_change_gcode', 'layer_change_gcode']:
                        if gcode_key in local_machine:
                            cfg[gcode_key] = local_machine[gcode_key]
                    report['logs'].append("Used printable settings from the selected local K2 Plus preset; connection remains local.")
                else:
                    cfg['machine_start_gcode'] = (
                        "M140 S0\n"
                        "M104 S0\n"
                        "START_PRINT EXTRUDER_TEMP=[nozzle_temperature_initial_layer] BED_TEMP=[bed_temperature_initial_layer_single]\n"
                    )
                    cfg['machine_end_gcode'] = "END_PRINT\n"

                # Preserve the original process name and exact quality values.
                cfg['compatible_printers'] = [printer_preset_name]
                cfg['compatible_printers_condition'] = ''

                with open(proj_cfg_path, 'w', encoding='utf-8') as f:
                    json.dump(cfg, f, indent=2, ensure_ascii=False)
                report['logs'].append(f"Updated Metadata/project_settings.config (Printer: {printer_preset_name})")
            else:
                raise ValueError("The 3MF has no embedded project_settings.config profile")

            # Remove source presets and old sliced output; never embed a new printer or material.
            metadata_dir = os.path.join(temp_dir, 'Metadata')
            for name in os.listdir(metadata_dir):
                file_path = os.path.join(metadata_dir, name)
                if (re.match(r'(?:machine_settings_|filament_settings?_)', name, re.I)
                        or name in ('slice_info.config', 'K2Translator-original-project.json', 'K2Translator-report.json')
                        or re.search(r'\.(?:gcode|bgcode)(?:\.|$)', name, re.I)):
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                elif re.match(r'(?:process_settings_|print_setting_)', name, re.I) and os.path.isfile(file_path):
                    with open(file_path, encoding='utf-8-sig') as stream:
                        process, _ = clean_process_settings(json.load(stream))
                    process['compatible_printers'] = [printer_preset_name]
                    process['compatible_printers_condition'] = ''
                    with open(file_path, 'w', encoding='utf-8') as stream:
                        json.dump(process, stream, ensure_ascii=False, indent=2)
            model_config = os.path.join(metadata_dir, 'model_settings.config')
            if os.path.isfile(model_config):
                with open(model_config, encoding='utf-8') as stream:
                    text = strip_material_overrides(stream.read())
                with open(model_config, 'w', encoding='utf-8', newline='') as stream:
                    stream.write(text)
            layer_path = os.path.join(metadata_dir, 'custom_gcode_per_layer.xml')
            if os.path.isfile(layer_path):
                with open(layer_path, encoding='utf-8') as stream:
                    layer_text = stream.read()
                layer_text = re.sub(r'(<(?:[\w.-]+:)?(?:layer|code)\b[^<>]*)(>)',
                                    lambda m: re.sub(r'\s+color\s*=\s*([\'"])[^\'"]*\1', '', m.group(1)) + m.group(2),
                                    layer_text)
                with open(layer_path, 'w', encoding='utf-8', newline='') as stream:
                    stream.write(layer_text)

            # 2. Bed Centering Calculation
            offset_x = 0.0
            offset_y = 0.0
            if center_on_bed:
                offset_x = (350.0 - old_bed_w) / 2.0
                offset_y = (350.0 - old_bed_d) / 2.0
                report['bed_offset'] = [round(offset_x, 2), round(offset_y, 2)]
                report['logs'].append(f"Centering offset calculated: +{offset_x:.2f}mm in X, +{offset_y:.2f}mm in Y")

            # 3. Update 3D/3dmodel.model using REGEX ONLY (Preserves 100% geometry data & XML namespaces)
            model_3d_path = os.path.join(temp_dir, '3D', '3dmodel.model')
            if os.path.isfile(model_3d_path):
                with open(model_3d_path, encoding='utf-8') as stream:
                    model_text = stream.read()
                compatible_application = 'OrcaSlicer-2.3.2' if target_slicer == 'orca' else 'CrealityPrint-7.3.0'
                model_text = re.sub(r'(<(?:[\w.-]+:)?metadata\b[^>]*\bname=[\'"]Application[\'"][^>]*>)[\s\S]*?(</(?:[\w.-]+:)?metadata\s*>)',
                                    lambda m: m.group(1) + compatible_application + m.group(2), model_text, count=1)
                with open(model_3d_path, 'w', encoding='utf-8', newline='') as stream:
                    stream.write(model_text)
            if os.path.isfile(model_3d_path) and (offset_x != 0.0 or offset_y != 0.0):
                self._update_3dmodel_regex(model_3d_path, offset_x, offset_y, report)

            # 4. Update Metadata/model_settings.config using REGEX ONLY
            model_settings_path = os.path.join(temp_dir, 'Metadata', 'model_settings.config')
            if os.path.isfile(model_settings_path) and (offset_x != 0.0 or offset_y != 0.0):
                self._update_model_settings_regex(model_settings_path, offset_x, offset_y, report)

            # 5. Update Metadata/plate_*.json bounding boxes if present
            for fn in os.listdir(os.path.join(temp_dir, 'Metadata')):
                if fn.startswith('plate_') and fn.endswith('.json'):
                    p_json_path = os.path.join(temp_dir, 'Metadata', fn)
                    self._update_plate_json(p_json_path, offset_x, offset_y)

            # 6. Add Metadata/creality.config for Creality Print compatibility
            creality_cfg_path = os.path.join(temp_dir, 'Metadata', 'creality.config')
            creality_xml = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<config>\n'
                '    <metadata key="Company" value="Creality"/>\n'
                '    <metadata key="Application" value="Creality_Print"/>\n'
                '    <metadata key="AppVersion" value="7.3.0"/>\n'
                '    <metadata key="AppStage" value="Release"/>\n'
                '    <metadata key="FileVersion" value="1.0"/>\n'
                '    <metadata key="FileType" value="Undefined"/>\n'
                '</config>\n'
            )
            if target_slicer == 'creality':
                with open(creality_cfg_path, 'w', encoding='utf-8') as f:
                    f.write(creality_xml)
            elif os.path.isfile(creality_cfg_path):
                os.remove(creality_cfg_path)

            # 7. Ensure [Content_Types].xml includes .config
            content_types_path = os.path.join(temp_dir, '[Content_Types].xml')
            if os.path.isfile(content_types_path):
                self._ensure_content_type(content_types_path)

            # 8. Repack cleanly
            dst_dir = os.path.dirname(os.path.abspath(dst_path))
            if dst_dir and not os.path.exists(dst_dir):
                os.makedirs(dst_dir, exist_ok=True)

            handle, staged_path = tempfile.mkstemp(prefix='.k2-translator-', suffix='.3mf', dir=dst_dir)
            os.close(handle)
            try:
                with zipfile.ZipFile(staged_path, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
                    for root, _, files in os.walk(temp_dir):
                        for file in files:
                            full_path = os.path.join(root, file)
                            rel_path = os.path.relpath(full_path, temp_dir).replace('\\', '/')
                            zout.write(full_path, rel_path)
                with zipfile.ZipFile(staged_path) as verify:
                    if verify.testzip() is not None:
                        raise ValueError('Output archive verification failed')
                os.replace(staged_path, dst_path)
            finally:
                if os.path.exists(staged_path):
                    os.remove(staged_path)

            report['logs'].append(f"Successfully created K2 Plus 3MF project: {dst_path}")
            report['success'] = True

        except Exception as e:
            report['errors'].append(f"Translation failed: {str(e)}")
            report['logs'].append(f"ERROR: {str(e)}")
            import traceback
            report['logs'].append(traceback.format_exc())
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        return report

    def _update_3dmodel_regex(self, file_path: str, offset_x: float, offset_y: float, report: Dict[str, Any]):
        """
        Shifts coordinates in 3D/3dmodel.model WITHOUT re-serializing XML,
        preserving 100% of the geometries, meshes, vertices, and namespaces.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()

            def shift_transform(match):
                prefix = match.group(1)
                trans = match.group(2).strip().split()
                suffix = match.group(3)
                if len(trans) >= 12:
                    try:
                        x = float(trans[9]) + offset_x
                        y = float(trans[10]) + offset_y
                        trans[9] = f"{x:.6f}".rstrip('0').rstrip('.')
                        trans[10] = f"{y:.6f}".rstrip('0').rstrip('.')
                        return f"{prefix}{' '.join(trans)}{suffix}"
                    except Exception:
                        pass
                return match.group(0)

            # Matches <item ... transform="..." ...>
            pattern = r'(<item\b[^>]*\btransform=")([^"]*)("[^>]*>)'
            new_text, count = re.subn(pattern, shift_transform, text)

            if count > 0:
                report['logs'].append(f"Shifted {count} build object(s) to center of K2 Plus bed (geometry 100% preserved).")

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_text)

        except Exception as e:
            report['logs'].append(f"Warning updating 3D/3dmodel.model: {e}")

    def _update_model_settings_regex(
        self,
        file_path: str,
        offset_x: float,
        offset_y: float,
        report: Dict[str, Any]
    ):
        """
        Updates assemble matrices via regex to avoid namespace errors.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()

            # Shift assemble_item with instance_id
            if offset_x != 0.0 or offset_y != 0.0:
                def shift_assemble(match):
                    prefix = match.group(1)
                    trans = match.group(2).strip().split()
                    suffix = match.group(3)
                    if len(trans) >= 12:
                        try:
                            x = float(trans[9]) + offset_x
                            y = float(trans[10]) + offset_y
                            trans[9] = f"{x:.6f}".rstrip('0').rstrip('.')
                            trans[10] = f"{y:.6f}".rstrip('0').rstrip('.')
                            return f"{prefix}{' '.join(trans)}{suffix}"
                        except Exception:
                            pass
                    return match.group(0)

                ms_pattern = r'(<assemble_item\b[^>]*\binstance_id=\"\d+\"[^>]*\btransform=\")([^\"]*)(\"[^>]*>)'
                text = re.sub(ms_pattern, shift_assemble, text)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(text)

            report['logs'].append("Updated Metadata/model_settings.config transforms.")

        except Exception as e:
            report['logs'].append(f"Warning updating model_settings.config: {e}")

    def _update_plate_json(self, file_path: str, offset_x: float, offset_y: float):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                pj = json.load(f)
            def without_materials(value):
                if isinstance(value, dict):
                    return {key: without_materials(item) for key, item in value.items()
                            if not is_material_key(key) and key != 'filaments'}
                if isinstance(value, list):
                    return [without_materials(item) for item in value]
                return value
            pj = without_materials(pj)

            if offset_x != 0.0 or offset_y != 0.0:
                if 'bbox_all' in pj and len(pj['bbox_all']) == 4:
                    pj['bbox_all'][0] += offset_x
                    pj['bbox_all'][1] += offset_y
                    pj['bbox_all'][2] += offset_x
                    pj['bbox_all'][3] += offset_y
                if 'bbox_objects' in pj:
                    for bo in pj['bbox_objects']:
                        if 'bbox' in bo and len(bo['bbox']) == 4:
                            bo['bbox'][0] += offset_x
                            bo['bbox'][1] += offset_y
                            bo['bbox'][2] += offset_x
                            bo['bbox'][3] += offset_y

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(pj, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _ensure_content_type(self, file_path: str):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if 'Extension="config"' not in content:
                tag = '<Default Extension="config" ContentType="application/xml" />\n</Types>'
                content = content.replace('</Types>', tag)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
        except Exception:
            pass
