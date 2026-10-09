"""Run the HTTP adapter outside MO2's embedded Python interpreter."""
from __future__ import annotations

import argparse
import ctypes
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.request

if __package__:
    from .engine import Adapter, VERSION, atomic_text
else:
    # The helper is launched with -I, so explicitly load only its sibling module.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from engine import Adapter, VERSION, atomic_text


def health(endpoint):
    base = endpoint.split('/hold-music/', 1)[0]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(base + '/health', timeout=1) as response:
        result = json.load(response)
    if result.get('service') != 'hold-music' or result.get('version') != VERSION:
        raise RuntimeError('Unexpected music service')
    return result


class ProcessAdapter:
    """Own one hidden helper. Only paths and a parent PID go on its command line."""
    def __init__(self, python, credential_file, settings_file, runtime, log_file,
                 port=0, parent_pid=None):
        self.python = Path(python)
        self.credential_file = Path(credential_file)
        self.settings_file = Path(settings_file)
        self.runtime = Path(runtime)
        self.log_file = Path(log_file)
        self.port = port
        self.parent_pid = os.getpid() if parent_pid is None else parent_pid
        self.process = None
        self.endpoint = None
        self.status_file = None
        self.stop_file = None

    def start(self):
        if self.process is not None and self.process.poll() is None:
            try:
                if health(self.endpoint)['pid'] == self.process.pid:
                    return self.endpoint
            except (OSError, ValueError, KeyError, RuntimeError):
                pass
            self.stop()
        if not self.python.is_file():
            raise ValueError('Configured standalone Python runtime is missing')
        self.runtime.mkdir(parents=True, exist_ok=True)
        run_id = secrets.token_hex(12)
        self.status_file = self.runtime / ('helper-' + run_id + '.json')
        self.stop_file = self.runtime / ('helper-' + run_id + '.stop')
        command = [str(self.python), '-I', str(Path(__file__).resolve()),
                   '--serve', '--credentials', str(self.credential_file),
                   '--settings', str(self.settings_file), '--runtime', str(self.runtime),
                   '--log', str(self.log_file), '--status', str(self.status_file),
                   '--stop', str(self.stop_file), '--parent-pid', str(self.parent_pid),
                   '--port', str(self.port)]
        self.process = subprocess.Popen(
            command, cwd=str(Path(__file__).resolve().parent),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        deadline = time.monotonic() + 10
        try:
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError('Music service exited during startup')
                if self.status_file.is_file():
                    status = json.loads(self.status_file.read_text(encoding='utf-8'))
                    self.endpoint = status['endpoint']
                    if status['pid'] != self.process.pid or health(self.endpoint)['pid'] != self.process.pid:
                        raise RuntimeError('Music service identity mismatch')
                    return self.endpoint
                time.sleep(0.05)
            raise TimeoutError('Music service startup timed out')
        except Exception:
            self.stop()
            raise

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self.stop_file.touch()
            try:
                self.process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                # Only terminate the child we launched, never MO2 or Skyrim.
                self.process.terminate()
                self.process.wait(timeout=3)
        for path in (self.status_file, self.stop_file):
            if path is not None:
                path.unlink(missing_ok=True)
        self.process = None
        self.endpoint = None


class ParentLifetime:
    """Keep a Windows process handle so PID reuse cannot keep an orphan alive."""
    def __init__(self, pid):
        self.pid = pid
        self.handle = None
        if os.name == 'nt':
            from ctypes import wintypes
            self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            self.kernel.OpenProcess.restype = wintypes.HANDLE
            self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            self.kernel.WaitForSingleObject.restype = wintypes.DWORD
            self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            self.kernel.CloseHandle.restype = wintypes.BOOL
            self.handle = self.kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
            if not self.handle:
                raise OSError('Cannot monitor the parent process')

    def alive(self):
        if os.name == 'nt':
            return self.kernel.WaitForSingleObject(self.handle, 0) == 0x102
        try:
            os.kill(self.pid, 0)
            return True
        except ProcessLookupError:
            return False

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def serve(args):
    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=2, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    log = logging.getLogger('hold_music_adapter')
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False
    parent = None
    adapter = None
    status_path, stop_path = Path(args.status), Path(args.stop)
    try:
        parent = ParentLifetime(args.parent_pid)
        adapter = Adapter(args.credentials, args.settings, args.runtime, args.port)
        endpoint = adapter.start()
        atomic_text(status_path, json.dumps({'pid': os.getpid(), 'version': VERSION, 'endpoint': endpoint}))
        log.info('Independent music helper ready pid=%s parent=%s', os.getpid(), args.parent_pid)
        while parent.alive() and not stop_path.exists():
            time.sleep(0.25)
    except Exception as exc:
        log.error('Music helper stopped (%s)', type(exc).__name__)
        raise
    finally:
        if adapter:
            adapter.stop()
        if parent:
            parent.close()
        status_path.unlink(missing_ok=True)
        stop_path.unlink(missing_ok=True)
        log.info('Independent music helper stopped')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--serve', action='store_true', required=True)
    for name in ('credentials', 'settings', 'runtime', 'log', 'status', 'stop'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--parent-pid', type=int, required=True)
    parser.add_argument('--port', type=int, default=0)
    serve(parser.parse_args())
