"""Read-only MO2 probe. Writes only its report; never requests music."""
from pathlib import Path
import hashlib
import json
import sys
import urllib.request

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "mo2_plugin/solo_lute"))
import engine

record = json.loads((PROJECT / "local/installation.json").read_text())
root = Path(record["root"])
source = root / "mods/MGO Experimental - Profile Data/SKSE/Plugins/SkyrimNet/config/BardSinging.yaml"
virtual = Path(r"C:\Steam\steamapps\common\SkyrimVR\Data\SKSE\Plugins\SkyrimNet")
result = {}
disabled = "--disabled" in sys.argv
try:
    data = engine.read_text(virtual / "config/BardSinging.yaml")
    result["provider"] = engine.get_scalar(data, ("bard_singing", "provider"))
    result["local_model"] = engine.get_scalar(data, ("bard_singing", "acestep_local", "model"))
    result["source_config_unchanged"] = hashlib.sha256(source.read_bytes()).hexdigest() == record["source_config_sha256"]
    try:
        manifest = json.loads(engine.read_text(virtual / "external/local.solo-lute/manifest.json"))
        result["content_plugin_visible"] = manifest["id"] == "local.solo-lute"
    except OSError as exc:
        result["content_plugin_visible"] = False
        result["content_read_error"] = type(exc).__name__
    if result["provider"] == "acestep_local":
        url = engine.get_scalar(data, ("bard_singing", "acestep_local", "base_url"))
        result["loopback_route"] = url.startswith("http://127.0.0.1:18765/solo-lute/")
        with urllib.request.urlopen("http://127.0.0.1:18765/health", timeout=5) as response:
            result["adapter"] = json.load(response)
    if disabled:
        result["ok"] = result["provider"] == "openrouter" and result["source_config_unchanged"] and not result["content_plugin_visible"]
    else:
        result["ok"] = result["provider"] == "acestep_local" and result["source_config_unchanged"] and result["content_plugin_visible"] and result.get("loopback_route", False)
except Exception as exc:
    result["ok"] = False
    result["error_type"] = type(exc).__name__
(PROJECT / ("local/vfs-disabled.json" if disabled else "local/vfs-probe.json")).write_text(json.dumps(result, indent=2) + "\n")
sys.exit(0 if result["ok"] else 1)
