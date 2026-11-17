import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.profile_policy import LocalProfiles, WIFI_PRESET, is_material_key
from core.translator import K2PlusTranslator

SOURCE = {
    'printer_model': 'Source printer', 'printer_settings_id': 'Source printer preset',
    'print_settings_id': 'Original 0.04mm art', 'layer_height': '0.04',
    'initial_layer_print_height': '0.16', 'sparse_infill_density': '100%',
    'wall_loops': '4', 'outer_wall_speed': ['25'], 'printable_area': ['0x0', '256x0', '256x256', '0x256'],
    'filament_settings_id': ['Source red ABS', 'Source blue PETG'], 'filament_colour': ['#ff0011', '#1122ff'],
    'filament_type': ['ABS', 'PETG'], 'filament_flow_ratio': ['0.91', '0.92'],
    'filament_diameter': ['2.85', '2.85'], 'nozzle_temperature': ['999', '999'],
    'nozzle_temperature_initial_layer': ['999', '999'], 'hot_plate_temp': ['999', '999'],
    'fan_min_speed': ['81', '82'], 'pressure_advance': ['0.999', '0.888'],
    'chamber_temperatures': ['90', '100'], 'filament_start_gcode': ['SOURCE_MATERIAL_CODE'],
    'machine_start_gcode': 'SOURCE_MACHINE_CODE', 'print_host': 'source-private-host',
}
MODEL = b'<model xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"><metadata name="Application">BambuStudio-2.0.0</metadata><resources><object id="1"><mesh><vertices><vertex x="1" y="2" z="3"/></vertices><triangles/></mesh></object></resources><build><item objectid="1" transform="1 0 0 0 1 0 0 0 1 10 20 0"/></build></model>'
OBJECTS = b'<config><object id="1"><metadata key="extruder" value="2"/><metadata key="filament_flow_ratio" value="0.777"/><metadata key="nozzle_temperature" value="999"/><metadata key="wall_loops" value="6"/></object></config>'
LAYERS = b'<custom_gcodes_per_layer><plate id="1"><layer top_z="0.44" type="2" extruder="2" color="#1122ff" gcode="tool_change"/></plate></custom_gcodes_per_layer>'


class TranslationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.appdata = self.root / 'appdata'
        user = self.appdata / 'OrcaSlicer' / 'user' / 'default' / 'machine'
        user.mkdir(parents=True)
        self.wifi_file = user / (WIFI_PRESET + '.json')
        self.wifi_file.write_text(json.dumps({'name': WIFI_PRESET, 'printer_settings_id': WIFI_PRESET,
                                             'inherits': 'Creality K2 Plus 0.4 nozzle',
                                             'print_host': 'local-device-address', 'printhost_apikey': 'LOCAL_SECRET'}))
        self.before_wifi = self.wifi_file.read_bytes()
        resources = self.root / 'install' / 'resources' / 'profiles' / 'Creality' / 'machine'
        resources.mkdir(parents=True)
        (resources / 'Creality K2 Plus 0.4 nozzle.json').write_text(json.dumps({
            'name': 'Creality K2 Plus 0.4 nozzle', 'default_filament_profile': ['Native PLA'],
            'nozzle_diameter': ['0.4'], 'machine_start_gcode': 'START_PRINT', 'machine_end_gcode': 'END_PRINT',
            'change_filament_gcode': 'NATIVE_TOOLCHANGE', 'machine_pause_gcode': 'PAUSE'}))
        (self.appdata / 'OrcaSlicer' / 'OrcaSlicer.conf').write_text(json.dumps({
            'filaments': ['Native PLA'], 'orca_presets': [{'machine': WIFI_PRESET, 'filament': 'External SOURCE preset'}]
        }) + '\n# checksum')
        self.profiles = LocalProfiles('orca', self.appdata, self.root / 'install' / 'orca-slicer.exe')
        self.source = self.root / 'source.3mf'
        with zipfile.ZipFile(self.source, 'w') as z:
            z.writestr('[Content_Types].xml', '<Types></Types>')
            z.writestr('3D/3dmodel.model', MODEL)
            z.writestr('3D/Objects/object_1.model', b'unchanged-external-mesh')
            z.writestr('Metadata/project_settings.config', json.dumps(SOURCE))
            z.writestr('Metadata/model_settings.config', OBJECTS)
            z.writestr('Metadata/custom_gcode_per_layer.xml', LAYERS)
            z.writestr('Metadata/machine_settings_1.config', json.dumps({'name': 'SOURCE_MACHINE_CODE'}))
            z.writestr('Metadata/filament_settings_1.config', json.dumps({'name': 'Source red ABS'}))
            z.writestr('Metadata/process_settings_1.config', json.dumps(SOURCE))
            z.writestr('Metadata/plate_1.gcode', 'SOURCE_MATERIAL_CODE')
            z.writestr('Metadata/slice_info.config', 'Source red ABS')
            z.writestr('Metadata/plate_1.json', json.dumps({'bbox_all': [1, 2, 3, 4],
                'filament_colors': ['#ff0011'], 'filament_ids': ['SOURCE_MATERIAL_ID']}))
        self.source_before = self.source.read_bytes()

    def convert(self, **kwargs):
        output = self.root / 'output.3mf'
        with patch('core.translator.LocalProfiles', return_value=self.profiles):
            report = K2PlusTranslator().translate(str(self.source), str(output), center_on_bed=False, **kwargs)
        self.assertTrue(report['success'], report['errors'])
        with zipfile.ZipFile(output) as z:
            files = {n: z.read(n) for n in z.namelist()}
        return files, json.loads(files['Metadata/project_settings.config']), report

    def test_wifi_name_is_exact_and_no_printer_or_material_preset_imported(self):
        files, settings, _ = self.convert()
        self.assertEqual(settings['printer_settings_id'], WIFI_PRESET)
        self.assertEqual(settings['printer_model'], 'Creality K2 Plus')
        self.assertFalse(any(n.startswith(('Metadata/machine_settings_', 'Metadata/filament_settings_')) for n in files))
        self.assertNotIn('K2T', settings['printer_settings_id'])

    def test_all_source_material_values_excluded_but_native_references_remain(self):
        files, settings, _ = self.convert()
        self.assertEqual(settings['filament_settings_id'], ['Native PLA', 'Native PLA'])
        for key in SOURCE:
            if is_material_key(key) and key != 'filament_settings_id':
                self.assertNotIn(key, settings, key)
        combined = b'\n'.join(files.values())
        for marker in (b'Source red ABS', b'Source blue PETG', b'#ff0011', b'#1122ff', b'SOURCE_MATERIAL_CODE'):
            self.assertNotIn(marker, combined)

    def test_process_values_and_name_preserved_exactly(self):
        _, settings, _ = self.convert()
        for key in ('print_settings_id', 'layer_height', 'initial_layer_print_height', 'sparse_infill_density', 'wall_loops', 'outer_wall_speed'):
            self.assertEqual(settings[key], SOURCE[key])

    def test_material_overrides_removed_from_objects_and_embedded_process(self):
        files, _, _ = self.convert()
        objects = files['Metadata/model_settings.config']
        self.assertNotIn(b'filament_flow_ratio', objects)
        self.assertNotIn(b'nozzle_temperature', objects)
        self.assertIn(b'key="extruder" value="2"', objects)
        self.assertIn(b'key="wall_loops" value="6"', objects)
        process = json.loads(files['Metadata/process_settings_1.config'])
        self.assertNotIn('filament_settings_id', process)
        self.assertNotIn('nozzle_temperature', process)
        self.assertEqual(process['compatible_printers'], [WIFI_PRESET])

    def test_layers_keep_height_and_slot_but_not_source_palette(self):
        files, _, _ = self.convert()
        layer = files['Metadata/custom_gcode_per_layer.xml']
        self.assertIn(b'top_z="0.44"', layer)
        self.assertIn(b'extruder="2"', layer)
        self.assertNotIn(b'color=', layer)

    def test_saved_wifi_profile_and_original_file_not_modified_and_no_credentials_exported(self):
        files, settings, _ = self.convert()
        self.assertEqual(self.wifi_file.read_bytes(), self.before_wifi)
        self.assertEqual(self.source.read_bytes(), self.source_before)
        for key in ('print_host', 'printhost_apikey'):
            self.assertNotIn(key, settings)
        self.assertNotIn(b'LOCAL_SECRET', b'\n'.join(files.values()))
        self.assertNotIn(b'local-device-address', b'\n'.join(files.values()))

    def test_geometry_and_positions_preserved_when_centering_disabled(self):
        files, _, _ = self.convert()
        self.assertEqual(files['3D/Objects/object_1.model'], b'unchanged-external-mesh')
        self.assertIn(b'transform="1 0 0 0 1 0 0 0 1 10 20 0"', files['3D/3dmodel.model'])
        self.assertIn(b'<vertex x="1" y="2" z="3"/>', files['3D/3dmodel.model'])

    def test_stale_toolpath_and_slice_info_removed(self):
        files, _, _ = self.convert()
        self.assertNotIn('Metadata/plate_1.gcode', files)
        self.assertNotIn('Metadata/slice_info.config', files)
        self.assertNotIn('Metadata/creality.config', files)

    def test_plate_sidecar_has_no_source_palette_or_material_ids(self):
        files, _, _ = self.convert()
        plate = json.loads(files['Metadata/plate_1.json'])
        self.assertEqual(plate['bbox_all'], [1, 2, 3, 4])
        self.assertNotIn('filament_colors', plate)
        self.assertNotIn('filament_ids', plate)

    def test_native_profile_resolver_skips_external_material_selection(self):
        self.assertEqual(self.profiles.default_name(), WIFI_PRESET)
        settings, materials = self.profiles.resolve(WIFI_PRESET)
        self.assertEqual(materials, ['Native PLA'])
        self.assertNotIn('print_host', settings)
        self.assertNotIn('printhost_apikey', settings)

    def test_same_output_path_does_not_touch_source(self):
        with patch('core.translator.LocalProfiles', return_value=self.profiles):
            report = K2PlusTranslator().translate(str(self.source), str(self.source))
        self.assertFalse(report['success'])
        self.assertEqual(self.source.read_bytes(), self.source_before)

    def test_invalid_member_path_rejected_without_output(self):
        bad = self.root / 'bad.3mf'
        with zipfile.ZipFile(bad, 'w') as z:
            z.writestr('../escape', 'bad')
        with patch('core.translator.LocalProfiles', return_value=self.profiles):
            report = K2PlusTranslator().translate(str(bad), str(self.root / 'bad-out.3mf'))
        self.assertFalse(report['success'])
        self.assertFalse((self.root / 'bad-out.3mf').exists())


if __name__ == '__main__':
    unittest.main()
