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


def final_path(handle):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    fn=kernel.GetFinalPathNameByHandleW
    fn.argtypes=[wintypes.HANDLE,wintypes.LPWSTR,wintypes.DWORD,wintypes.DWORD]
    fn.restype=wintypes.DWORD
    buf=ctypes.create_unicode_buffer(32768)
    n=fn(handle,buf,len(buf),0)
    if not n or n>=len(buf): raise ctypes.WinError(ctypes.get_last_error())
    return buf.value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root',type=Path,required=True,help='SkyrimVR Data as visible inside the MO2-launched process')
    parser.add_argument('--manifest',type=Path,required=True,help='Offline build/package-hashes.json')
    args=parser.parse_args()
    if os.name!='nt': raise SystemExit('Windows file-handle probe only; run later through MO2')
    import msvcrt
    manifest=json.loads(args.manifest.read_text())
    targets=list(manifest)+['SKSE/Plugins/StorageUtilData/HoldMusic/library.json','SKSE/Plugins/StorageUtilData/HoldMusic/receipts.json']+[f'Sound/fx/holdmusic/hm_slot_{i:02}.wav' for i in range(1,25)]
    result=[]
    for name in dict.fromkeys(targets):
        row={'virtual_path':name}
        try:
            with (args.data_root/name).open('rb') as f:
                row['opened_path']=final_path(msvcrt.get_osfhandle(f.fileno()))
                row['sha256']=hashlib.file_digest(f,'sha256').hexdigest()
            if name in manifest: row['matches_package']=row['sha256']==manifest[name]
        except OSError as exc:
            row['error']=str(exc)
        result.append(row)
    print(json.dumps({'scope':'Observed reads only; no write-location proof and no automated claim that MO2 injection succeeded. Review opened_path against intended profile mod/overwrite.','files':result},indent=2))
    return int(any('error' in row or row.get('matches_package') is False for row in result))

if __name__=='__main__': raise SystemExit(main())
