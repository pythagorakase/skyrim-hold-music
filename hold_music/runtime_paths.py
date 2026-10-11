"""Read-only discovery of PapyrusUtil runtime storage under MO2 (stdlib only)."""
from dataclasses import dataclass
from pathlib import Path
import stat

DEFAULT_MOD_NAME = 'MGO Experimental - Hold Music Performances'
STORAGE = Path('SKSE/Plugins/StorageUtilData/HoldMusic')


@dataclass(frozen=True)
class Located:
    path: Path
    mtime: float
    size: int


def storage_dirs(mo2_root, mod_name, data_mod=None) -> list[Path]:
    root = Path(mo2_root)
    folders = [root / 'mods' / mod_name, root / 'overwrite']
    if data_mod is not None:
        folders.append(root / 'mods' / data_mod)
    return [folder / STORAGE for folder in folders]


def locate(filename, dirs) -> list[Located]:
    """Newest files first; ties retain the caller's directory priority."""
    found = []
    for directory in dirs:
        path = Path(directory) / filename
        try:
            info = path.stat()
        except FileNotFoundError:
            continue
        if stat.S_ISREG(info.st_mode):
            found.append(Located(path, info.st_mtime, info.st_size))
    return sorted(found, key=lambda item: item.mtime, reverse=True)


def resolve_receipts(mo2_root, mod_name, data_mod=None) -> Path | None:
    found = locate('receipts.json', storage_dirs(mo2_root, mod_name, data_mod))
    return found[0].path if found else None


def resolve_trace(mo2_root, mod_name, data_mod=None) -> Path | None:
    found = locate('trace.json', storage_dirs(mo2_root, mod_name, data_mod))
    return found[0].path if found else None
