"""Reviewed preparation and first-boot inspection for the isolated SkyrimNet tier.

Installation is explicit and only publishes a new, separate MO2 directory.
There is deliberately no HTTP, provider, arm or launch operation.
Config seeds describe observed beta26 controls; successful file inspection does
not prove the native plugin accepted them or that network egress is blocked.
"""
from __future__ import annotations

import configparser
import ctypes
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import uuid
import zipfile

from hold_music.installed_library import _Snapshot, _profile_text
from hold_music.library_merge import _json
from hold_music.promotion import _component, _no_alias, _relative
from hold_music.job_store import _writer_lock
from hold_music.promotion_transaction import _atomic_write, _closed, _sync_directory
from tools import se_lab as baseline

LAB_ROOT = Path(r"C:\MGO\HoldMusic-SE-Lab")
REPO = Path(__file__).resolve().parents[1]
INSTANCE = "MO2-SkyrimNet"
PROFILE = "Hold Music SE Lab - SkyrimNet Disabled"
TIER = "skyrimnet-beta26-rc4-disabled-v1"
CONFIG_MOD = "Hold Music SkyrimNet Disabled Config"
CONFIG = "SKSE/Plugins/SkyrimNet/config/"
PORTS = {"web": 18880, "mcp": 18889, "fake_provider": 18881}
LOOPBACK = "http://127.0.0.1:18881/v1/chat/completions"
BASE_MODS = ("Hold Music Lab Data", "Hold Music SE Lab Harness", "Hold Music Candidate",
             "SkyUI SE 5.2", "PapyrusUtil SE 4.6", "Address Library AE",
             "MCM Helper SE 1.6.2", "SKSE Scripts 2.2.6")
BASE_PLUGINS = ("SkyUI_SE.esp", "MCMHelper.esp", "HoldMusic.esp", "HM_Lab.esp")
NATIVE_DLLS = {"papyrusutil.dll", "mcmhelper.dll", "po3_papyrusextender.dll",
               "po3_tweaks.dll", "prismaui.dll", "mediakeysfix.dll", "skyrimnet.dll"}
MO2_ARCHIVE = dict(path=Path(r"C:\MGO\download\Mod.Organizer-2.5.2.7z"),
    sha256="e6376efd87fd5ddd95aee959405e8f067afa526ea6c2c0c5aa03c5108bf4a815",
    kind="tar", prefixes=("",))
CONTROL = ".skyrimnet-tier-install"
INSTALL_VERSION = 1
ARCHIVES = (
    dict(mod="SkyrimNet beta26-rc4 Clean", path=REPO / "local/se-lab-downloads/skyrimnet-beta26-rc4.zip",
         sha256="6b1646d52d10f71b938d09b55bb766b57af517ece11ea174b646d0a1a51fbcef", kind="zip", prefixes=("",)),
    dict(mod="PrismaUI 1.5.1", path=REPO / "local/se-lab-downloads/PrismaUI_1.5.1.zip",
         sha256="1b87a4b370de2222d14df146f7a18fe7517f9fc116d4436c4f565c2a539c1c58", kind="zip", prefixes=("PrismaUI_1.5.1/",)),
    dict(mod="Media Keys Fix 1.0.1", path=REPO / "local/se-lab-downloads/Media.Keys.Fix-1.0.1.7z",
         sha256="2ab31c13c8bf4b0e1a4647caaccd64d70a60429c3ae740aa8c12c57690499a1d", kind="tar", prefixes=("",)),
    dict(mod="Papyrus Extender SE 6.4.3", path=Path(r"C:\MGO\download\Papyrus Extender 22854 6.4.3 2026-07-20T04-04Z OyYrPubih.7z"),
         sha256="7d31be5949eef75583de0972ca7bff2109c9b2473eb00b98505d40411c0aa637", kind="tar",
         prefixes=("powerofthree's Papyrus Extender FOMOD Installer/Required/",
                   "powerofthree's Papyrus Extender FOMOD Installer/AE/")),
    dict(mod="powerofthree Tweaks SE 1.15.1", path=Path(r"C:\MGO\download\powerofthree's Tweaks-51073-1-1-5-1-1756670335.7z"),
         sha256="d20b6ffc7369de040b914e55e3ce6b6bde1f56b59d5151ae0d9b82d8d014e0ed", kind="tar",
         prefixes=("powerofthree's Tweaks FOMOD Installer/Required/",
                   "powerofthree's Tweaks FOMOD Installer/AE/")),
)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def clean_launch_environment(environment=None):
    """Return a future launch environment; never inherit arbitrary credentials.

    This helper launches nothing and does not claim filesystem credential isolation.
    Values are intentionally excluded from public reports.
    """
    environment = os.environ if environment is None else environment
    allowed = {"systemroot", "windir", "comspec", "temp", "tmp", "userprofile",
               "appdata", "localappdata", "programdata", "programfiles",
               "programfiles(x86)", "commonprogramfiles", "commonprogramfiles(x86)",
               "path", "pathext", "systemdrive", "homedrive", "homepath"}
    result = {key: value for key, value in environment.items() if key.casefold() in allowed}
    result.update(SteamAppId="489830", SteamGameId="489830")
    return result


def configuration_seeds():
    """JSON is valid YAML; exact seed bytes are reviewed, never installed here."""
    data = {
        "SkyrimNet.yaml": {"general": {"globalAIEnabled": False},
            "gamemaster": {"agentEnabled": False}, "narration": {"enabled": False},
            "tts": {"engine": "noop"}, "content": {"autoUpdateBase": False},
            "dialogue": {"decisions": {"useForMood": False, "useForSpeakerSelection": False,
                                       "useForPlayerTarget": False}}},
        "Providers.yaml": {"providers": [{"id": "hold_music_lab", "name": "Hold Music Lab",
            "endpoint": LOOPBACK, "api_key": "", "api_style": "chat", "use_sse": False, "builtin": False}]},
        "OpenRouter.yaml": {"openrouter": {"endpoint": LOOPBACK, "api_key": "",
            "model_name": "hold-music-lab-disabled", "model_params": [{"provider_id": "hold_music_lab", "use_sse": False}],
            "variants": {}}},
        "STT.yaml": {"backend": "none", "external_whisper": {"api_key": "",
            "api_endpoint": "http://127.0.0.1:18881/v1/audio/transcriptions"}},
        "BardSinging.yaml": {"bard_singing": {"enabled": False, "provider": "acestep_local",
            "backup_provider": "none", "acestep_local": {"base_url": LOOPBACK},
            **{name: {"api_key": ""} for name in ("suno", "nano_gpt", "openrouter", "acestep_cloud", "minimax")}}},
        "VastAI.yaml": {"general": {"enabled": False}, "connection": {"apiKey": ""}},
        "Events.yaml": {"global": {"npcReactionsEnabled": False}},
        "PlayerDialogue.yaml": {"enabled": False},
        "Memory.yaml": {"performance": {"enable_background_processing": False}},
        "DynamicBio.yaml": {"enabled": False}, "UniversalTranslator.yaml": {"enabled": False},
        "OmniSight.yaml": {"omnisight": {"enabled": False}},
        "Agents.yaml": {"agents": {"enable": False}},
        "WebServer.yaml": {"enabled": True, "host": "127.0.0.1", "port": PORTS["web"]},
        "MCP.yaml": {"mcp": {"enabled": True, "host": "127.0.0.1", "port": PORTS["mcp"]}},
    }
    result = {CONFIG + name: json.dumps(value, indent=2, ensure_ascii=False) + "\n" for name, value in data.items()}
    # Do not automatically run the Papyrus fixture while inspecting native load.
    result[baseline.CONTROL] = json.dumps({"version": 1, "enabled": False,
                                         "world_id": "hold-music-se-lab"}, indent=2) + "\n"
    # Tagged po3-Tweaks v1.15.1 Settings.cpp reads this under [Fixes].
    result["SKSE/Plugins/po3_Tweaks.ini"] = "[Fixes]\nLoad EditorIDs = true\n"
    return result


def _root():
    root = _no_alias(LAB_ROOT)
    if not root.is_absolute() or not root.is_dir():
        raise ValueError("The fixed SE lab root is missing")
    return root


def _ports_available():
    """Bind only; no listener, connection, HTTP request or provider is started."""
    sockets = []
    try:
        for port in PORTS.values():
            handle = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sockets.append(handle)
            if os.name == "nt":
                handle.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            handle.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        for handle in sockets:
            handle.close()


def _tree(snapshot, root):
    """Inventory with alias and case collision guards, without reading file data."""
    result = {}
    def visit(path, relative):
        state, names = snapshot.directory(path)
        if not state["exists"]:
            return
        if len({name.casefold() for name in names}) != len(names):
            raise ValueError("Ambiguous case-insensitive inventory")
        for name in names:
            _component(name)
            child = _no_alias(path / name)
            rel = relative + name
            if child.is_dir():
                visit(child, rel + "/")
            else:
                info = child.stat()
                if not child.is_file() or info.st_nlink > 1:
                    raise ValueError("Inventory contains a nonregular or aliased file")
                result[rel] = dict(path=str(child), size=info.st_size,
                                   mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
                                   device=info.st_dev, inode=info.st_ino)
    visit(root, "")
    return result


def _archive_payloads(spec, snapshot):
    """Decode pinned archives in memory, never extracting archive paths to disk.

    A single tar stream avoids repeatedly decompressing a large solid archive.
    Its complete, validated regular-file listing supplies exact byte boundaries.
    """
    path = _no_alias(spec["path"])
    state = snapshot.read(path)
    if state.get("sha256") != spec["sha256"]:
        raise ValueError("Pinned archive missing or changed: " + path.name)
    seen, selected = set(), set()
    if spec["kind"] == "zip":
        archive = zipfile.ZipFile(path)
        entries = []
        for item in archive.infolist():
            mode = (item.external_attr >> 16) & 0o170000
            if mode not in (0, 0o100000, 0o040000):
                archive.close()
                raise ValueError("Archive contains a nonregular member")
            entries.append((item.filename.rstrip("/"), item.file_size, item.is_dir(), item.filename))
        read = lambda row: archive.read(row[3])
    else:
        archive = None
        listing = subprocess.run(["tar", "-tvf", str(path)], check=True, capture_output=True,
                                 timeout=30).stdout.decode("utf-8")
        entries = []
        for line in listing.splitlines():
            parts = line.split(maxsplit=8)
            if len(parts) == 9 and parts[4].isdigit():  # BSD tar (Windows/macOS).
                mode, size, name = parts[0], parts[4], parts[8]
            else:  # GNU tar, useful for portable synthetic tests.
                parts = line.split(maxsplit=5)
                if len(parts) != 6 or not parts[2].isdigit():
                    raise ValueError("Unsupported archive member listing")
                mode, size, name = parts[0], parts[2], parts[5]
            if mode[0] not in ("d", "-"):
                raise ValueError("Unsupported archive member listing")
            entries.append((name.rstrip("/"), int(size), mode[0] == "d", name))
        read = None
    try:
        total = 0
        for name, size, directory, _ in entries:
            _relative(name)
            if name.casefold() in seen:
                raise ValueError("Archive has duplicate case-insensitive members")
            seen.add(name.casefold())
            if not directory:
                total += size
        if not entries or total > 1024 * 1024 * 1024:
            raise ValueError("Archive exceeds the bounded payload size")
        if archive is None:
            raw = subprocess.run(["tar", "-xOf", str(path)], check=True,
                                 capture_output=True, timeout=180).stdout
            if len(raw) != total:
                raise ValueError("Archive byte stream disagrees with its listing")
            position = 0
        for row in entries:
            name, size, directory, member = row
            if directory:
                continue
            if archive is None:
                payload = memoryview(raw)[position:position + size]
                position += size
            else:
                payload = read(row)
            for prefix in spec["prefixes"]:
                if name.startswith(prefix):
                    relative = _relative(name[len(prefix):])
                    if relative.casefold() in selected:
                        raise ValueError("Archive mappings overlap")
                    selected.add(relative.casefold())
                    yield relative, payload, dict(archive=str(path), member=member)
                    break
        if not selected:
            raise ValueError("Archive mapping selects no files")
        snapshot.read(path)
    finally:
        if archive is not None:
            archive.close()


def _archive_files(spec, snapshot):
    return {relative: dict(sha256=hashlib.sha256(raw).hexdigest(), source=source)
            for relative, raw, source in _archive_payloads(spec, snapshot)}


def _recipe(snapshot, root):
    _, raw = snapshot.read(root / baseline.MANIFEST, content=True)
    manifest = _json(raw) if raw is not None else None
    if (not isinstance(manifest, dict) or type(manifest.get("version")) is not int or manifest.get("version") != 1
            or manifest.get("paid_generation") is not False
            or manifest.get("required_mods") != list(BASE_MODS)
            or manifest.get("required_plugins") != list(BASE_PLUGINS)):
        raise ValueError("The fixed first-tier baseline manifest does not match")
    files, shared, seen = {}, {}, set()
    declarations = manifest.get("files")
    if not isinstance(declarations, list) or any(not isinstance(row, dict) for row in declarations):
        raise ValueError("Baseline manifest files must be declarations")
    declarations = list(declarations)
    for key, relative in (("runtime", "Game/SkyrimSE.exe"), ("loader", "Game/skse64_loader.exe"),
                          ("mo2", "MO2/ModOrganizer.exe")):
        row = manifest.get(key, {})
        if row.get("path") != relative or (key == "runtime" and row.get("version") != baseline.RUNTIME_VERSION):
            raise ValueError("Baseline executable declaration changed")
        declarations.append(row)
    for row in declarations:
        relative = _relative(row.get("path"))
        if relative.startswith("MO2/mods/") and _private_path(relative):
            raise ValueError("Baseline manifest contains private runtime state")
        digest = row.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest):
            raise ValueError("Invalid baseline digest")
        if relative.casefold() in seen:
            raise ValueError("Duplicate baseline file declaration")
        seen.add(relative.casefold())
        state = snapshot.read(_no_alias(root / relative))
        if state.get("sha256") != digest:
            raise ValueError("Baseline source does not match its manifest: " + relative)
        if relative.startswith("Game/"):
            shared[relative] = digest
        elif relative == "MO2/ModOrganizer.exe":
            files[INSTANCE + "/ModOrganizer.exe"] = dict(sha256=digest, source=dict(path=state["path"]))
        else:
            parts = relative.split("/")
            if len(parts) < 4 or parts[:2] != ["MO2", "mods"] or parts[2] not in BASE_MODS:
                raise ValueError("Baseline manifest contains an unapproved source")
            if "skyrimnet" in relative.casefold():
                raise ValueError("Baseline cannot supply SkyrimNet config or private data")
            files[INSTANCE + relative[len("MO2"):]] = dict(sha256=digest, source=dict(path=state["path"]))
    if "Game/skse64_1_6_1170.dll" not in shared:
        raise ValueError("Baseline must pin SKSE 2.2.6's 1.6.1170 DLL")
    if baseline._file_version(root / "Game/SkyrimSE.exe") != baseline.RUNTIME_VERSION:
        raise ValueError("Actual runtime must be Skyrim SE 1.6.1170.0")
    for spec in ARCHIVES:
        for relative, row in _archive_files(spec, snapshot).items():
            files[INSTANCE + "/mods/" + spec["mod"] + "/" + relative] = row
    seeds = configuration_seeds()
    for relative, text in seeds.items():
        files[INSTANCE + "/mods/" + CONFIG_MOD + "/" + relative] = dict(
            sha256=hashlib.sha256(text.encode()).hexdigest(), source=dict(kind="observed-disabled-seed"))
    return files, shared, seeds


def _inspect(prepared):
    root, snapshot, blockers = _root(), _Snapshot(), []
    def block(code, detail):
        blockers.append(dict(code=code, detail=detail))
    files, shared, seeds = _recipe(snapshot, root)
    game_inventory = _tree(snapshot, root / "Game")
    for relative in game_inventory:
        lower = relative.casefold()
        if "skyrimnet" in lower or lower.endswith("auth.yaml"):
            block("physical_game_skyrimnet", "Shared Game contains SkyrimNet config, native code or data")
        if lower.startswith("data/skse/plugins/") and lower.endswith(".dll"):
            block("physical_game_plugin", "Native plugins must live only in the isolated tier mods")
    active = [CONFIG_MOD, *(spec["mod"] for spec in ARCHIVES), *BASE_MODS]
    expected_plugins = [*BASE_PLUGINS, "SkyrimNet.esp"]
    native_paths = [path for path in files if "/skse/plugins/" in path.casefold()
                    and path.casefold().rsplit("/skse/plugins/", 1)[1].count("/") == 0
                    and path.lower().endswith(".dll")]
    expected_native = {Path(path).name.casefold() for path in native_paths}
    if expected_native != NATIVE_DLLS or len(native_paths) != len(NATIVE_DLLS):
        block("native_recipe", "The recipe must contain exactly the seven approved native plugins")
    target = root / INSTANCE
    observed_winners = {}
    native_winners = {}
    if prepared:
        target_tree = _tree(snapshot, target)
        for path, row in files.items():
            state = snapshot.read(_no_alias(root / path))
            if state.get("sha256") != row["sha256"]:
                block("file_hash", "Prepared file missing or changed: " + path)
        # MO2's application support files are independent of mod payload; all
        # files inside mods/ and overwrite/ must belong to the explicit recipe.
        expected_payload = {path[len(INSTANCE) + 1:].casefold() for path in files}
        for relative in target_tree:
            lower = relative.casefold()
            if (Path(lower).name == "auth.yaml" or lower.endswith((".db", ".sqlite", ".sqlite3"))
                    or "/saves/" in lower):
                block("private_runtime_state", "Initial tier must not contain auth, databases or saves")
            if (lower.startswith(("mods/", "overwrite/")) and lower not in expected_payload):
                block("unapproved_payload", "Unexpected mod or overwrite file: " + relative)
        if not snapshot.read(target / "portable.txt")["exists"]:
            block("portable", "The second instance must have its own portable.txt")
        try:
            _, raw = snapshot.read(target / "ModOrganizer.ini", content=True)
            ini = configparser.ConfigParser(interpolation=None, strict=True)
            ini.read_string(_profile_text(raw or b""))
            def equivalent(value, expected):
                value = baseline._unwrap(value).replace("%BASE_DIR%", str(target))
                candidate = Path(value)
                if not candidate.is_absolute():
                    candidate = target / candidate
                return os.path.normcase(os.path.abspath(candidate)) == os.path.normcase(str(expected))
            if (not equivalent(ini.get("General", "gamePath"), root / "Game")
                    or baseline._unwrap(ini.get("General", "selected_profile")) != PROFILE
                    or ini.get("General", "gameName") != "Skyrim Special Edition"):
                block("mo2_identity", "Second instance must select only the fixed lab Game and tier profile")
            directory_keys = {"base_directory": "", "mod_directory": "mods", "mods_directory": "mods",
                "profiles_directory": "profiles", "overwrite_directory": "overwrite", "download_directory": "downloads",
                "downloads_directory": "downloads", "cache_directory": "webcache"}
            for section in ini.sections():
                for key, value in ini.items(section):
                    if key in directory_keys and value.strip() and not equivalent(value, target / directory_keys[key]):
                        block("directory_redirect", "MO2 directory override leaves its fixed tier location: " + key)
        except (configparser.Error, ValueError, UnicodeError):
            block("mo2_ini", "Cannot establish the second instance configuration")
        profile = target / "profiles" / PROFILE
        try:
            _, raw = snapshot.read(profile / "settings.ini", content=True)
            ini = configparser.ConfigParser(interpolation=None, strict=True)
            ini.read_string(_profile_text(raw or b""))
            if not (ini.getboolean("General", "LocalSaves") and ini.getboolean("General", "LocalSettings")):
                block("local_profile", "Local saves and local settings must both be enabled")
        except (configparser.Error, ValueError, UnicodeError):
            block("local_profile", "Cannot establish profile-local saves and settings")
        for name in ("Skyrim.ini", "SkyrimPrefs.ini"):
            if not snapshot.read(profile / name)["exists"]:
                block("profile_ini", "Missing local profile INI: " + name)
        snapshot.read(profile / "SkyrimCustom.ini")
        for name, expected, marker in (("modlist.txt", active, "+"), ("plugins.txt", expected_plugins, "*"),
                                        ("loadorder.txt", expected_plugins, "")):
            _, raw = snapshot.read(profile / name, content=True)
            lines = [line for line in _profile_text(raw or b"").splitlines() if line and not line.startswith("#")]
            if lines != [marker + value for value in expected]:
                block("profile_list", "The initial tier requires its exact ordered " + name)
        # Record priority winners independently of physical expected hashes.
        for relative in seeds:
            winner = None
            for layer in [target / "overwrite", *(target / "mods" / mod for mod in active), root / "Game/Data"]:
                path, exists = snapshot.resolve(layer, relative)
                state = snapshot.read(path) if exists else dict(path=str(path), exists=False)
                if winner is None and state["exists"]:
                    winner = state
            observed_winners[relative] = winner
            expected = target / "mods" / CONFIG_MOD / relative
            if winner is None or Path(winner["path"]) != expected:
                block("config_winner", "Disabled seed is not the physical loose winner: " + relative)
        for physical in native_paths:
            relative = "SKSE/Plugins/" + Path(physical).name
            winner = None
            for layer in [target / "overwrite", *(target / "mods" / mod for mod in active), root / "Game/Data"]:
                path, exists = snapshot.resolve(layer, relative)
                state = snapshot.read(path) if exists else dict(path=str(path), exists=False)
                if winner is None and state["exists"]:
                    winner = state
            native_winners[relative] = winner
            if (winner is None or Path(winner["path"]) != root / physical
                    or winner.get("sha256") != files[physical]["sha256"]):
                block("native_winner", "Native plugin is not its reviewed loose winner: " + relative)
    ports_available = _ports_available() if prepared else None
    if ports_available is False:
        block("ports_busy", "At least one fixed loopback port is already bound")
    final = snapshot.finish()
    # Inventory metadata also covers large vanilla archives without repeatedly
    # hashing tens of GB. It is not advertised as an immutable OS filesystem.
    if game_inventory != _tree(snapshot, root / "Game"):
        raise ValueError("Shared Game changed during inspection")
    report = dict(version=1, operation="skyrimnet_se_lab_preflight" if prepared else "skyrimnet_se_lab_plan",
        tier=TIER, lab_root=str(root), instance=str(target), profile=PROFILE,
        status="blocked" if blockers else ("prepared_files_verified" if prepared else "preparation_plan"),
        blockers=blockers, active_mods=active, enabled_plugins=expected_plugins,
        files=[dict(path=path, **row) for path, row in sorted(files.items())],
        configuration_seeds=[dict(virtual_path=path, text=text) for path, text in seeds.items()],
        config_winners=observed_winners, native_winners=native_winners, shared_native_hashes=shared,
        shared_game_inventory=game_inventory, snapshot=final, ports=PORTS,
        ports_available=ports_available,
        environment=dict(policy="allowlist-v1", retained_names=sorted(clean_launch_environment()),
                         values_disclosed=False),
        writes_performed=False, can_apply=False, can_launch=False, paid_generation=False,
        native_verified=False, runtime_verified=False, egress_verified=False, vfs_verified=False,
        limitations=["Read-only first-boot preparation; no installation, game launch, HTTP or MCP action is implemented.",
            "File controls and absent credentials do not independently prove zero network egress.",
            "Native config acceptance, startup migrations and actual writes require separate runtime evidence.",
            "Future HTTP/MCP access must bind listener PID, executable path and start time to the launched tier.",
            "Shared Game inventory is a drift guard, not filesystem write protection; no Game files may be installed.",
            "Global SKSE Documents logs remain shared; serialize runs and archive only fresh, attributed evidence.",
            "This inspection token cannot authorize installation or the baseline runner."])
    report["review_token"] = _digest(report)
    return report


def preparation_plan():
    return _inspect(False)


def preflight():
    return _inspect(True)


def _private_path(relative):
    lower = relative.casefold()
    return (Path(lower).name == "auth.yaml" or lower.endswith((".db", ".sqlite", ".sqlite3", ".ess", ".skse"))
            or "/saves/" in lower)


def _instance_seeds(root, recipe):
    """Fresh local state only; never read or copy an existing application INI."""
    target = root / INSTANCE
    profile = "profiles/" + PROFILE + "/"
    return {
        "portable.txt": "",
        "ModOrganizer.ini": "[General]\ngameName=Skyrim Special Edition\nselected_profile=@ByteArray(" + PROFILE
            + ")\ngamePath=@ByteArray(" + str(root / "Game") + ")\n[Settings]\n"
            + "\n".join(key + "=" + str(target / child) for key, child in (
                ("base_directory", ""), ("mod_directory", "mods"), ("profiles_directory", "profiles"),
                ("overwrite_directory", "overwrite"), ("download_directory", "downloads"),
                ("cache_directory", "webcache"))) + "\n",
        profile + "settings.ini": "[General]\nLocalSaves=true\nLocalSettings=true\n",
        profile + "Skyrim.ini": "[General]\nsLanguage=ENGLISH\n",
        profile + "SkyrimPrefs.ini": "[Display]\nbFull Screen=0\nbBorderless=0\niSize W=1280\niSize H=720\n",
        profile + "modlist.txt": "".join("+" + value + "\n" for value in recipe["active_mods"]),
        profile + "plugins.txt": "".join("*" + value + "\n" for value in recipe["enabled_plugins"]),
        profile + "loadorder.txt": "".join(value + "\n" for value in recipe["enabled_plugins"]),
    }


def _fixed(root, name):
    """Reject case aliases even in case-sensitive fixture filesystems."""
    _component(name)
    matches = [p.name for p in root.iterdir() if p.name.casefold() == name.casefold()]
    if matches and matches != [name]:
        raise ValueError("Ambiguous or differently cased fixed tier path")
    return _no_alias(root / name)


def _inventory(path, *, exclude=()):
    snapshot = _Snapshot()
    rows = _tree(snapshot, path)
    files = {relative: snapshot.read(Path(row["path"])) for relative, row in rows.items() if relative not in exclude}
    snapshot.finish()
    if rows != _tree(snapshot, path):
        raise ValueError("Tier tree changed during inspection")
    return dict(exists=path.exists(), files=files,
                directories=sorted(Path(p).relative_to(path).as_posix() for p, state in snapshot.directories.items()
                                   if state["exists"]))


def _protected(root):
    snapshot = _Snapshot()
    result = {name: _tree(snapshot, root / name) for name in ("Game", "MO2")}
    result["manifest"] = snapshot.read(root / baseline.MANIFEST)
    # The large vanilla archives and baseline app state use metadata drift guards;
    # the reviewed recipe independently hashes every source it will copy.
    snapshot.finish()
    for name in ("Game", "MO2"):
        if result[name] != _tree(snapshot, root / name):
            raise ValueError("Protected first-tier tree changed")
    result["directories"] = {key: row for key, row in snapshot.directories.items()}
    result["root_identity"] = dict(device=root.stat().st_dev, inode=root.stat().st_ino)
    return result


def _implementation(snapshot):
    paths = ("hold_music/se_lab_skyrimnet.py", "tools/se_lab_skyrimnet.py", "tools/se_lab.py",
             "hold_music/promotion.py", "hold_music/promotion_transaction.py", "hold_music/job_store.py",
             "hold_music/installed_library.py", "hold_music/library_merge.py")
    return {path: snapshot.read(REPO / path)["sha256"] for path in paths}


def _install_inputs():
    root, snapshot = _root(), _Snapshot()
    recipe = preparation_plan()
    files = {row["path"][len(INSTANCE) + 1:]: {key: value for key, value in row.items() if key != "path"}
             for row in recipe["files"]}
    application = _archive_files(MO2_ARCHIVE, snapshot)
    if application.get("ModOrganizer.exe", {}).get("sha256") != files["ModOrganizer.exe"]["sha256"]:
        raise ValueError("Clean MO2 distribution does not match the baseline executable")
    for relative, row in application.items():
        if relative == "ModOrganizer.exe":
            files[relative] = row
        elif relative.casefold() in {name.casefold() for name in files}:
            raise ValueError("Clean application distribution overlaps mod payload")
        else:
            files[relative] = row
    seeds = _instance_seeds(root, recipe)
    for relative, text in seeds.items():
        if relative.casefold() in {name.casefold() for name in files}:
            raise ValueError("Application archive contains instance state")
        files[relative] = dict(sha256=hashlib.sha256(text.encode()).hexdigest(),
                               source=dict(kind="fresh-instance-seed"))
    directories = {".", "overwrite", "downloads", "webcache", "profiles/" + PROFILE + "/saves"}
    for relative in files:
        parent = Path(_relative(relative)).parent
        directories.update(p.as_posix() for p in (parent, *parent.parents))
    for relative in list(directories):
        directories.update(p.as_posix() for p in Path(relative).parents)
    children = {}
    for relative in [*files, *(name for name in directories if name != ".")]:
        parts = _relative(relative).split("/")
        for index, part in enumerate(parts):
            key = (tuple(value.casefold() for value in parts[:index]), part.casefold())
            if key in children and children[key] != part:
                raise ValueError("Payload contains a component case alias")
            children[key] = part
    if {name.casefold() for name in files} & {name.casefold() for name in directories}:
        raise ValueError("Payload file overlaps a directory")
    protected = _protected(root)
    result = dict(version=INSTALL_VERSION, tier=TIER, root=str(root), instance=str(root / INSTANCE),
        recipe_token=recipe["review_token"], files=files, directories=sorted(directories),
        instance_seeds=seeds, config_seeds=configuration_seeds(), blockers=recipe["blockers"],
        implementation=_implementation(snapshot), application_archive=dict(
            path=str(MO2_ARCHIVE["path"]), sha256=MO2_ARCHIVE["sha256"]), protected=protected,
        application_snapshot=snapshot.finish())
    if protected != _protected(root):
        raise ValueError("Protected baseline changed during installation review")
    result["inputs_token"] = _digest(result)
    return result


def _control_inventory(root):
    control = _fixed(root, CONTROL)
    value = _inventory(control, exclude=("writer.lock",))
    # The persistent kernel lock file is not transaction evidence. Its presence
    # or access timestamps cannot invalidate the review acquired before locking.
    value["files"].pop("writer.lock", None)
    if not value["files"] and value["directories"] in ([], ["."]):
        return dict(exists=False, files={}, directories=[])
    return value


def installation_plan():
    """Read-only install review. Only this action's token can authorize install."""
    root = _root()
    target, control = _fixed(root, INSTANCE), _fixed(root, CONTROL)
    inputs = _install_inputs()
    state = dict(target=_inventory(target), control=_control_inventory(root))
    blockers = list(inputs["blockers"])
    if state["target"]["exists"]:
        blockers.append(dict(code="target_exists", detail="Install requires an absent dedicated instance"))
    if state["control"]["exists"]:
        blockers.append(dict(code="retained_transaction", detail="Inspect the retained transaction; automatic retry is forbidden"))
    result = dict(version=INSTALL_VERSION, operation="skyrimnet_se_lab_install", tier=TIER,
        status="blocked" if blockers else "installation_plan", blockers=blockers,
        instance=str(target), control=str(control), inputs=inputs, before=state,
        can_apply=not blockers, can_launch=False, writes_performed=False,
        paid_generation=False, native_verified=False, runtime_verified=False, egress_verified=False,
        process_verification="Required again at apply; no process proof is inferred from a review")
    result["review_token"] = "skyrimnet-install-v1:" + _digest(result)
    return result


def _matches(left, right):
    return isinstance(left, str) and left.isascii() and hmac.compare_digest(left, right)


def _assert_closed(probe):
    if not _closed(probe):
        raise ValueError("Verified closure of Skyrim and Mod Organizer processes is required")


def _expect_tree(path, journal):
    observed = _inventory(path)
    if (not observed["exists"] or observed["directories"] != journal["directories"]
            or {name: row["sha256"] for name, row in observed["files"].items()} != journal["files"]):
        raise ValueError("Prepared instance differs from the journaled payload")
    return observed


def _exclusive_rename(source, destination):
    """Same-filesystem rename with a no-replace primitive, including empty dirs."""
    source, destination = _no_alias(source), _no_alias(destination)
    if source.parent.stat().st_dev != destination.parent.stat().st_dev:
        raise ValueError("Tier publication must remain on one filesystem")
    if os.name == "nt":
        os.rename(source, destination)  # Windows refuses any existing destination.
    else:
        libc = ctypes.CDLL(None, use_errno=True)
        if sys.platform == "darwin":
            result = libc.renamex_np(os.fsencode(source), os.fsencode(destination), 4)  # RENAME_EXCL
        elif hasattr(libc, "renameat2"):
            result = libc.renameat2(-100, os.fsencode(source), -100, os.fsencode(destination), 1)
        else:
            raise ValueError("Platform lacks exclusive directory publication")
        if result:
            raise OSError(ctypes.get_errno(), "Exclusive tier directory publication failed")
    _sync_directory(source.parent)
    _sync_directory(destination.parent)


def _journal_write(control, journal, prior):
    raw = (json.dumps(journal, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    _atomic_write(_no_alias(control / "journal.json"), raw, expected=prior)
    return dict(exists=True, sha256=hashlib.sha256(raw).hexdigest(), size=len(raw))


def _new_file(stage, relative, raw, expected):
    path = _no_alias(stage / _relative(relative))
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Source changed before staging")
    if not path.parent.is_dir():
        raise ValueError("Missing predeclared staging directory")
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    _sync_directory(path.parent)


def _stage_payload(stage, inputs, guard):
    files = inputs["files"]
    archive_map = {(row["source"]["archive"], row["source"]["member"]): relative
                   for relative, row in files.items() if "archive" in row["source"]}
    for relative in sorted(inputs["directories"], key=lambda value: (value.count("/"), value)):
        if relative != ".":
            guard()
            _no_alias(stage / relative).mkdir(exist_ok=False)
    # Consume every archive fully so the final hash/drift check always runs.
    for spec in (MO2_ARCHIVE, *ARCHIVES):
        for _, raw, source in _archive_payloads(spec, _Snapshot()):
            relative = archive_map.get((source["archive"], source["member"]))
            if relative is None:
                raise ValueError("Archive source is not uniquely mapped in the review")
            guard()
            _new_file(stage, relative, raw, files[relative]["sha256"])
    for relative, row in files.items():
        source = row["source"]
        if "archive" in source:
            continue
        if "path" in source:
            _, raw = _Snapshot().read(Path(source["path"]), content=True)
            if raw is None:
                raise ValueError("Baseline copy source disappeared")
        elif source["kind"] == "fresh-instance-seed":
            raw = inputs["instance_seeds"][relative].encode()
        else:
            virtual = relative.split("mods/" + CONFIG_MOD + "/", 1)[1]
            raw = inputs["config_seeds"][virtual].encode()
        guard()
        _new_file(stage, relative, raw, row["sha256"])


def install(review_token, *, process_probe=None):
    """Publish exactly one new disabled instance; never retry an interrupted one."""
    plan = installation_plan()
    if plan["blockers"] or not _matches(review_token, plan["review_token"]):
        raise ValueError("Installation review is stale, blocked or from another operation")
    _assert_closed(process_probe)
    root = _root()
    target, control = _fixed(root, INSTANCE), _fixed(root, CONTROL)
    control.mkdir(exist_ok=True)
    _sync_directory(root)
    with _writer_lock(_no_alias(control / "writer.lock")):
        plan = installation_plan()
        if plan["blockers"] or not _matches(review_token, plan["review_token"]):
            raise ValueError("Installation changed before acquiring its writer lock")
        _assert_closed(process_probe)
        inputs = plan["inputs"]
        journal = dict(version=INSTALL_VERSION, tier=TIER, transaction_id=uuid.uuid4().hex,
            state="staging", root=str(root), instance=INSTANCE,
            review_token=review_token, inputs_token=inputs["inputs_token"],
            protected=inputs["protected"], files={name: row["sha256"] for name, row in inputs["files"].items()},
            directories=inputs["directories"], implementation=inputs["implementation"])
        prior = _journal_write(control, journal, dict(exists=False))
        stage = _fixed(control, "stage")
        stage.mkdir(exist_ok=False)
        _sync_directory(control)
        identities = {path: (path.stat().st_dev, path.stat().st_ino) for path in (root, control, stage)}
        def guard():
            for path, identity in identities.items():
                info = _no_alias(path).stat()
                if not path.is_dir() or (info.st_dev, info.st_ino) != identity:
                    raise ValueError("A fixed staging ancestor was replaced")
            if _fixed(root, INSTANCE).exists():
                raise ValueError("Dedicated target appeared while staging")
        _stage_payload(stage, inputs, guard)
        _expect_tree(stage, journal)
        guard()
        fresh = _install_inputs()
        if fresh["inputs_token"] != inputs["inputs_token"] or fresh["blockers"]:
            raise ValueError("Installation inputs changed while staging; retained for inspection")
        _assert_closed(process_probe)
        _fixed(root, INSTANCE)
        if target.exists():
            raise ValueError("Dedicated target appeared while staging")
        _expect_tree(stage, journal)
        journal["state"] = "publishing"
        prior = _journal_write(control, journal, prior)
        _exclusive_rename(stage, target)
        _expect_tree(target, journal)
        if _protected(root) != inputs["protected"]:
            raise ValueError("Protected first-tier files changed during publication")
        _assert_closed(process_probe)
        journal["state"] = "installed_disabled"
        _journal_write(control, journal, prior)
    result = installation_status()
    result["writes_performed"] = True
    return result


def _load_journal(root):
    control = _fixed(root, CONTROL)
    state, raw = _Snapshot().read(control / "journal.json", content=True)
    if raw is None:
        return None, dict(exists=False)
    journal = _json(raw)
    if (not isinstance(journal, dict) or type(journal.get("version")) is not int
            or journal["version"] != INSTALL_VERSION or journal.get("tier") != TIER
            or journal.get("root") != str(root) or journal.get("instance") != INSTANCE
            or not isinstance(journal.get("state"), str)
            or journal["state"] not in {"staging", "publishing", "installed_disabled", "retaining", "retained_partial"}
            or not re.fullmatch("[0-9a-f]{32}", str(journal.get("transaction_id", "")))
            or not isinstance(journal.get("protected"), dict)
            or not isinstance(journal.get("implementation"), dict)
            or not isinstance(journal.get("directories"), list) or not isinstance(journal.get("files"), dict)
            or not journal["files"]):
        raise ValueError("Invalid or foreign installation journal")
    names = []
    for name, digest in journal["files"].items():
        _relative(name)
        if not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest):
            raise ValueError("Invalid retained payload digest")
        names.append(name.casefold())
    if len(names) != len(set(names)):
        raise ValueError("Ambiguous retained payload")
    directories = journal["directories"]
    if (any(not isinstance(name, str) for name in directories)
            or directories != sorted(set(directories)) or "." not in directories):
        raise ValueError("Invalid retained directory inventory")
    for name in directories:
        if name != ".":
            _relative(name)
    if not all(p.as_posix() in directories for name in journal["files"] for p in Path(name).parents):
        raise ValueError("Incomplete retained parent inventory")
    return journal, {key: state[key] for key in ("exists", "sha256", "size")}


def installation_status():
    """Read-only transaction evidence; a journal alone does not prove installation."""
    root = _root()
    control, target = _fixed(root, CONTROL), _fixed(root, INSTANCE)
    journal, prior = _load_journal(root)
    implementation_snapshot = _Snapshot()
    implementation = _implementation(implementation_snapshot)
    observed = dict(control=_control_inventory(root), target=_inventory(target), protected=_protected(root))
    if journal and observed["control"]["files"].get("journal.json", {}).get("sha256") != prior["sha256"]:
        raise ValueError("Installation journal changed during inspection")
    blockers, actions = [], []
    state = "not_started" if journal is None else journal["state"]
    protected_changed = bool(journal and journal["protected"] != observed["protected"])
    if journal is None and (observed["control"]["exists"] or observed["target"]["exists"]):
        blockers.append(dict(code="unowned_state", detail="Existing state has no valid transaction journal"))
    if journal:
        if journal["protected"].get("root_identity") != observed["protected"]["root_identity"]:
            blockers.append(dict(code="root_replaced", detail="The original lab root was replaced"))
        expected_names = {"writer.lock", "journal.json", "stage", "retained"}
        if any(p.name not in expected_names for p in control.iterdir()):
            blockers.append(dict(code="unknown_control_file", detail="Unrecognized transaction residue is preserved"))
        stage, retained = _fixed(control, "stage"), _fixed(control, "retained")
        if (target.exists() and (stage.exists() or retained.exists() or state in {"staging", "retaining", "retained_partial"})):
            blockers.append(dict(code="conflicting_target", detail="A target coexists with unpublished or retained state; no overwrite is permitted"))
        if stage.exists() and retained.exists():
            blockers.append(dict(code="conflicting_evidence", detail="Both staging and retained evidence exist"))
        if state in {"staging", "publishing", "retaining"}:
            if not target.exists() and (stage.exists() != retained.exists() or
                                        (state in {"staging", "retaining"} and not stage.exists() and not retained.exists())):
                actions.append("retain_partial")
            if state == "publishing" and target.exists() and not stage.exists() and not retained.exists():
                try:
                    _expect_tree(target, journal)
                    actions.append("acknowledge_published")
                except ValueError:
                    blockers.append(dict(code="target_drift", detail="Published payload no longer matches the retained intent"))
        if state == "installed_disabled":
            try:
                _expect_tree(target, journal)
                if stage.exists() or retained.exists():
                    raise ValueError("Unexpected staging residue")
            except ValueError:
                blockers.append(dict(code="target_drift", detail="Installed payload no longer matches the retained intent"))
        if state == "publishing" and not target.exists() and not stage.exists() and not retained.exists():
            blockers.append(dict(code="missing_payload", detail="Publication intent has no observable payload"))
        if state == "retained_partial" and stage.exists():
            blockers.append(dict(code="unexpected_stage", detail="Terminal retention still has a staging directory"))
    if observed != dict(control=_control_inventory(root), target=_inventory(target), protected=_protected(root)):
        raise ValueError("Installation evidence changed during status inspection")
    implementation_snapshot.finish()
    result = dict(version=INSTALL_VERSION, tier=TIER, operation="skyrimnet_se_lab_install_status",
        status=state, blockers=blockers, recovery_actions=[] if blockers else actions,
        transaction_id=journal["transaction_id"] if journal else None, journal_hash=prior.get("sha256"),
        protected_changed_since_install=protected_changed,
        implementation=implementation,
        observation=observed, can_apply=False, can_launch=False, writes_performed=False,
        paid_generation=False, native_verified=False, runtime_verified=False, egress_verified=False)
    result["review_token"] = "skyrimnet-status-v1:" + _digest(result)
    return result


def recover_installation(action, *, review_token=None, apply=False, process_probe=None):
    """Review explicit evidence retention/acknowledgement, never resume copying."""
    if action not in {"retain_partial", "acknowledge_published"}:
        raise ValueError("Unsupported installation recovery action")
    status = installation_status()
    report = dict(status="recovery_plan", operation="skyrimnet_se_lab_recovery", tier=TIER, action=action,
        observation=status, blockers=list(status["blockers"]), writes_performed=False, can_launch=False)
    if action not in status["recovery_actions"]:
        report["blockers"].append(dict(code="recovery_state", detail="Action does not match the retained transaction state"))
    report["can_apply"] = not report["blockers"]
    report["review_token"] = "skyrimnet-recover-v1:" + _digest(report)
    if not apply:
        return report
    if report["blockers"] or not _matches(review_token, report["review_token"]):
        raise ValueError("Recovery review is stale, blocked or from another operation")
    _assert_closed(process_probe)
    root, control = _root(), _fixed(_root(), CONTROL)
    with _writer_lock(_no_alias(control / "writer.lock")):
        fresh = recover_installation(action)
        if not _matches(review_token, fresh["review_token"]) or fresh["blockers"]:
            raise ValueError("Recovery changed before acquiring its writer lock")
        _assert_closed(process_probe)
        journal, prior = _load_journal(root)
        protected_before = fresh["observation"]["observation"]["protected"]
        if action == "retain_partial":
            stage_before = _inventory(_fixed(control, "stage"))
            journal["state"] = "retaining"
            prior = _journal_write(control, journal, prior)
            stage, retained = _fixed(control, "stage"), _fixed(control, "retained")
            if stage.exists():
                _exclusive_rename(stage, retained)
                after = _inventory(retained)
                content = lambda tree: (tree["directories"], {key: row["sha256"] for key, row in tree["files"].items()})
                if content(stage_before) != content(after):
                    raise ValueError("Partial evidence changed during retention")
            journal["state"] = "retained_partial"
        else:
            _expect_tree(_fixed(root, INSTANCE), journal)
            journal["state"] = "installed_disabled"
        if _protected(root) != protected_before:
            raise ValueError("Protected first-tier state changed during recovery")
        _assert_closed(process_probe)
        if action == "acknowledge_published":
            _expect_tree(_fixed(root, INSTANCE), journal)
        _journal_write(control, journal, prior)
    result = installation_status()
    result["writes_performed"] = True
    return result
