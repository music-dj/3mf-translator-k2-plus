"""Use an existing local printer preset and exclude source material profiles.

Read-only access to local preset files. Connection credentials are never returned,
copied into a project, or modified.
"""
import json
import os
import re
from pathlib import Path

WIFI_PRESET = "Creality K2 Plus 0.4 nozzle - wifi"
OPTIONS_PATH = Path(__file__).resolve().parent.parent / "profiles" / "slicer-options.json"
OPTIONS = json.loads(OPTIONS_PATH.read_text(encoding="utf-8"))
MATERIAL_KEYS = set().union(*(set(v["filament"]) for v in OPTIONS.values()))
MATERIAL_KEYS.update({"filament_colour", "filament_colors", "filament_ids", "filament_settings_id",
                      "default_filament_colour", "chamber_temperatures", "chamber_temperature",
                      "nozzle_temperature", "nozzle_temperature_initial_layer", "bed_temperature",
                      "bed_temperature_initial_layer", "filament_map", "filament_map_mode"})
MATERIAL_KEYS.difference_update({'compatible_printers', 'compatible_printers_condition',
                                'compatible_prints', 'compatible_prints_condition',
                                'inherits', 'name', 'type', 'from', 'setting_id', 'version'})
PRINTER_KEYS = set().union(*(set(v["printer"]) for v in OPTIONS.values()))
IDENTITY_KEYS = {"printer_settings_id", "printer_model", "printer_variant", "compatible_printers",
                 "compatible_printers_condition", "print_compatible_printers", "inherits",
                 "inherits_group", "different_settings_to_system", "default_filament_profile"}
CONNECTION_KEY = re.compile(r"(?:host|address|api.?key|password|access.?code|authorization|certificate|serial|device.?id|physical_printer)", re.I)


def is_material_key(key):
    # Role selectors (wall_filament, *_filament_id) are print assignments, not material presets.
    return (key in MATERIAL_KEYS or key.startswith("filament_")
            or bool(re.search(r"(?:plate_temp|bed_temperature|nozzle_temperature|chamber_temperature)", key)))


def read_json(path):
    # Orca app config can have a checksum/comment after its JSON object.
    return json.JSONDecoder().raw_decode(Path(path).read_text(encoding="utf-8-sig").lstrip())[0]


class LocalProfiles:
    def __init__(self, slicer="orca", appdata=None, executable=None):
        self.slicer = slicer
        self.appdata = Path(appdata or os.environ.get("APPDATA", ""))
        if executable is None:
            from core.slicer_finder import SlicerFinder
            executable = (SlicerFinder.find_orca_slicer() if slicer == "orca"
                          else SlicerFinder.find_creality_print())
        self.resources = Path(executable).parent / "resources" / "profiles" if executable else None

    def user_roots(self):
        if self.slicer == "orca":
            return [self.appdata / "OrcaSlicer" / "user"]
        base = self.appdata / "Creality" / "CrealityPrint"
        if not base.is_dir():
            return []
        return [p / "user" for p in base.iterdir() if p.is_dir()]

    def _user_files(self):
        # Active user trees only; never choose an old backup preset over the active one.
        for root in self.user_roots():
            if root.is_dir():
                yield from sorted(root.glob("*/machine/*.json"))

    def _find(self, name):
        # Prefer the active/default account when duplicate synchronized presets exist.
        files = sorted(self._user_files(), key=lambda p: (p.parent.parent.name != "default", str(p)))
        for path in files:
            if path.stem == name:
                return path
        if self.resources and self.resources.is_dir():
            for path in self.resources.glob("*/machine/*.json"):
                if path.stem == name:
                    return path
        return None

    def names(self, nozzle="0.4"):
        official = f"Creality K2 Plus {nozzle} nozzle"
        names = [official]
        for path in self._user_files():
            if "K2 Plus" in path.stem and re.search(rf"\b{re.escape(nozzle)}\s*nozzle", path.stem):
                names.append(path.stem)
        return sorted(set(names), key=lambda n: (n != WIFI_PRESET, n != official, n))

    def default_name(self, nozzle="0.4"):
        if nozzle == "0.4" and self._find(WIFI_PRESET):
            return WIFI_PRESET
        return f"Creality K2 Plus {nozzle} nozzle"

    def resolve(self, name, fallback=None):
        def load(current, seen):
            if current in seen:
                raise ValueError("Printer preset inheritance cycle")
            path = self._find(current)
            if not path:
                return dict(fallback or {})
            data = read_json(path)
            inherited = data.get("inherits")
            base = load(inherited, seen | {current}) if inherited else {}
            return {**base, **data}
        resolved = load(name, set())
        # Return only printable machine data, never network/account settings.
        printable = {k: v for k, v in resolved.items()
                     if not CONNECTION_KEY.search(k) and k not in {"name", "from", "type", "setting_id", "inherits"}}
        defaults = resolved.get("default_filament_profile", [])
        if isinstance(defaults, str):
            defaults = [defaults]
        # New Orca releases store per-printer material references in orca_presets.
        # Use only names already selected locally, never colors/calibration/connection values.
        if self.slicer == 'orca':
            config_path = self.appdata / 'OrcaSlicer' / 'OrcaSlicer.conf'
            if config_path.is_file():
                config = read_json(config_path)
                enabled = {v for v in config.get('filaments', []) if isinstance(v, str) and v}
                saved = {p.stem for root in self.user_roots() if root.is_dir()
                         for p in root.glob('*/filament/**/*.json')}
                for item in config.get('orca_presets', []):
                    if item.get('machine') == name:
                        keys = sorted(k for k in item if k == 'filament' or re.fullmatch(r'filament_\d+', k))
                        selected = [item[k] for k in keys if isinstance(item[k], str)
                                    and item[k] in enabled | saved]
                        if selected:
                            defaults = selected
                        break
                # An external project preset can be the last active selection.
                # It is not a local default: use an enabled native material instead.
                if not defaults or not all(v in enabled | saved for v in defaults):
                    candidates = ['Creality Generic PLA @K2-all', 'Generic PLA @Creality K2-all',
                                  'Generic PLA @System', 'Generic PLA']
                    native = next((v for v in candidates if v in enabled), None)
                    if native:
                        defaults = [native]
        return printable, defaults


def clean_process_settings(source):
    dropped = []
    result = {}
    for key, value in source.items():
        if is_material_key(key) or key in PRINTER_KEYS or key in IDENTITY_KEYS or CONNECTION_KEY.search(key):
            dropped.append(key)
        else:
            result[key] = value
    return result, dropped


def strip_material_overrides(text):
    """Remove object/range material overrides without reserializing mesh/XML data."""
    pattern = r'<(?:[\w.-]+:)?metadata\b[^<>]*(?:/>|>[\s\S]*?</(?:[\w.-]+:)?metadata\s*>)'
    def replace(match):
        key = re.search(r'\bkey\s*=\s*([\'"])(.*?)\1', match.group(0))
        return "" if key and is_material_key(key.group(2)) else match.group(0)
    return re.sub(pattern, replace, text)
