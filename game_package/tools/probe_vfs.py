"""READ ONLY. Orchestrator runs this Python process THROUGH MO2 later.

No MO2/game launcher is embedded. Emits observed Windows file-handle destinations
and SHA256 values. Outside MO2 this observes ordinary filesystem resolution only.
"""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'game_adapter/hold_music_adapter'))
from engine import get_scalar

BARD_CONFIG = 'SKSE/Plugins/SkyrimNet/config/BardSinging.yaml'


def bard_enabled(raw):
    """Return only the ownership flag, never any provider credentials."""
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        text = raw.decode('utf-16')
    else:
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = raw.decode('cp1252')
    enabled = get_scalar(text, ('bard_singing', 'enabled'))
    if type(enabled) is not bool:
        raise ValueError('Bard enabled field is not a boolean')
    return enabled


def observe_file(data_root, name, *, resolve_handle, expected=None):
    """Read the observed handle's bytes and destination in the same open."""
    row = {'virtual_path': name}
    try:
        with (Path(data_root) / name).open('rb') as stream:
            row['opened_path'] = resolve_handle(stream)
            if name == BARD_CONFIG:
                raw = stream.read()
                row['sha256'] = hashlib.sha256(raw).hexdigest()
                try:
                    row['bard_enabled'] = bard_enabled(raw)
                except (UnicodeError, ValueError) as exc:
                    row['bard_enabled'] = None
                    row['configuration_error'] = type(exc).__name__
            else:
                row['sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
        if expected is not None:
            row['matches_package'] = row['sha256'] == expected
    except OSError as exc:
        row['error'] = type(exc).__name__
    return row


def final_path(handle):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    fn=kernel.GetFinalPathNameByHandleW
    fn.argtypes=[wintypes.HANDLE,wintypes.LPWSTR,wintypes.DWORD,wintypes.DWORD]
    fn.restype=wintypes.DWORD
    buf=ctypes.create_unicode_buffer(32768)
    n=fn(handle,buf,len(buf),0)
    if not n or n>=len(buf): raise ctypes.WinError(ctypes.get_last_error())
    return buf.value


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root',type=Path,required=True,help='SkyrimVR Data as visible inside the MO2-launched process')
    parser.add_argument('--manifest',type=Path,required=True,help='Offline build/package-hashes.json')
    parser.add_argument('--profile', help='Operator-supplied profile label for the observation; not proof of MO2 injection')
    args=parser.parse_args(argv)
    if os.name!='nt': raise SystemExit('Windows file-handle probe only; run later through MO2')
    import msvcrt
    manifest=json.loads(args.manifest.read_text())
    targets=list(manifest)+[BARD_CONFIG,'SKSE/Plugins/StorageUtilData/HoldMusic/library.json','SKSE/Plugins/StorageUtilData/HoldMusic/receipts.json']+[f'Sound/fx/holdmusic/hm_slot_{i:02}.wav' for i in range(1,25)]
    result=[]
    for name in dict.fromkeys(targets):
        result.append(observe_file(args.data_root, name,
                                  resolve_handle=lambda stream: final_path(msvcrt.get_osfhandle(stream.fileno())),
                                  expected=manifest.get(name)))
    print(json.dumps({'version':2, 'observed_at':datetime.now(timezone.utc).isoformat(),
                      'profile':args.profile, 'data_root':str(args.data_root),
                      'scope':'Observed reads only; no write-location proof and no automated claim that MO2 injection succeeded. Review opened_path against intended profile mod/overwrite.',
                      'files':result},indent=2))
    return int(any('error' in row or 'configuration_error' in row or row.get('matches_package') is False for row in result))

if __name__=='__main__': raise SystemExit(main())
