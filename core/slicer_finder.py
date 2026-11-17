"""
Detects installed 3D slicers on Windows (Creality Print, OrcaSlicer, Bambu Studio)
and launches translated project files.
"""
import os
import subprocess
import winreg
from typing import Dict, Optional, List


class SlicerFinder:
    """Finds and launches slicers installed on the system."""

    DEFAULT_PATHS = {
        'creality_print': [
            r"e:\Program Files\Creality\Creality Print 7.1\CrealityPrint.exe",
            r"C:\Program Files\Creality\Creality Print 7.1\CrealityPrint.exe",
            r"C:\Program Files\Creality\Creality Print 6.0\CrealityPrint.exe",
            r"C:\Program Files\Creality\Creality Print 5.1\CrealityPrint.exe",
            r"C:\Program Files\Creality\Creality Print 5.0\CrealityPrint.exe",
            r"C:\Program Files\Creality\CrealityPrint.exe",
            r"D:\Program Files\Creality\Creality Print 7.1\CrealityPrint.exe",
        ],
        'orca_slicer': [
            r"e:\Program Files\OrcaSlicer\orca-slicer.exe",
            r"C:\Program Files\OrcaSlicer\orca-slicer.exe",
            r"C:\Program Files\Orca Slicer\orca-slicer.exe",
            r"D:\Program Files\OrcaSlicer\orca-slicer.exe",
        ],
        'bambu_studio': [
            r"C:\Program Files\Bambu Studio\bambu-studio.exe",
            r"e:\Program Files\Bambu Studio\bambu-studio.exe",
            r"C:\Program Files\Bambu Lab\Bambu Studio\bambu-studio.exe",
        ]
    }

    @classmethod
    def find_all(cls) -> Dict[str, Optional[str]]:
        results = {
            'creality_print': cls.find_creality_print(),
            'orca_slicer': cls.find_orca_slicer(),
            'bambu_studio': cls.find_bambu_studio()
        }
        return results

    @classmethod
    def find_creality_print(cls) -> Optional[str]:
        # 1. Check known paths
        for path in cls.DEFAULT_PATHS['creality_print']:
            if os.path.isfile(path):
                return path

        # 2. Check registry
        reg_path = cls._check_registry("Creality Print")
        if reg_path and os.path.isfile(reg_path):
            return reg_path

        return None

    @classmethod
    def find_orca_slicer(cls) -> Optional[str]:
        for path in cls.DEFAULT_PATHS['orca_slicer']:
            if os.path.isfile(path):
                return path

        reg_path = cls._check_registry("OrcaSlicer")
        if reg_path and os.path.isfile(reg_path):
            return reg_path

        return None

    @classmethod
    def find_bambu_studio(cls) -> Optional[str]:
        for path in cls.DEFAULT_PATHS['bambu_studio']:
            if os.path.isfile(path):
                return path

        reg_path = cls._check_registry("Bambu Studio")
        if reg_path and os.path.isfile(reg_path):
            return reg_path

        return None

    @classmethod
    def _check_registry(cls, pattern: str) -> Optional[str]:
        reg_roots = [
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall")
        ]

        for hkey, subkey in reg_roots:
            try:
                key = winreg.OpenKey(hkey, subkey)
                num_subkeys = winreg.QueryInfoKey(key)[0]
                for i in range(num_subkeys):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        item_key = winreg.OpenKey(key, subkey_name)
                        try:
                            display_name, _ = winreg.QueryValueEx(item_key, "DisplayName")
                            if pattern.lower() in display_name.lower():
                                # Check DisplayIcon or InstallLocation
                                try:
                                    icon, _ = winreg.QueryValueEx(item_key, "DisplayIcon")
                                    icon_clean = icon.strip('"').split(',')[0]
                                    if icon_clean.lower().endswith('.exe') and os.path.isfile(icon_clean):
                                        return icon_clean
                                except Exception:
                                    pass

                                try:
                                    loc, _ = winreg.QueryValueEx(item_key, "InstallLocation")
                                    if loc and os.path.isdir(loc):
                                        for root, _, files in os.walk(loc):
                                            for f in files:
                                                if f.lower().endswith('.exe') and ('creality' in f.lower() or 'orca' in f.lower() or 'bambu' in f.lower()):
                                                    return os.path.join(root, f)
                                except Exception:
                                    pass
                        finally:
                            winreg.CloseKey(item_key)
                    except Exception:
                        continue
                winreg.CloseKey(key)
            except Exception:
                continue

        return None

    @classmethod
    def launch(cls, slicer_key: str, file_path: str) -> bool:
        slicers = cls.find_all()
        exe_path = slicers.get(slicer_key)
        if not exe_path or not os.path.isfile(exe_path):
            return False

        try:
            subprocess.Popen([exe_path, file_path], shell=False)
            return True
        except Exception as e:
            print(f"Error launching slicer {exe_path}: {e}")
            return False
