"""Reviewed preparation and first-boot inspection for the isolated SkyrimNet tier.

Installation is explicit and only publishes a new, separate MO2 directory.
Explicit first-boot launch and local collection are separate from installation.
There is no HTTP, provider, MCP, arm, configuration-update or retry operation.
Config seeds describe observed beta26 controls; successful file inspection does
not prove the native plugin accepted them or that network egress is blocked.
"""
from __future__ import annotations

import configparser
import ctypes
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import threading
import time
import uuid
import zipfile

from hold_music.installed_library import _Snapshot, _profile_text
from hold_music.library_merge import _json
from hold_music.promotion import _component, _no_alias, _relative
from hold_music.job_store import _writer_lock
from hold_music.promotion_transaction import _atomic_write, _closed, _sync_directory
from hold_music.runtime_contract import (RUNTIME_CONTRACT_FIELDS, manifest_runtime_selection_errors,
                                        recording_contract_errors)
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
    """Return a launch environment; never inherit arbitrary credentials.

    This helper launches nothing and does not claim filesystem credential isolation.
    Values are intentionally excluded from public reports.
    """
    environment = os.environ if environment is None else environment
    # MO2 2.5.2 initLogging() concatenates getenv("USERNAME") without a null
    # check. Preserve exactly one inherited value under its canonical Windows
    # name; do not invent one from a path or accept ambiguous casing aliases.
    usernames = [value for key, value in environment.items() if key.casefold() == "username"]
    if (len(usernames) != 1 or not isinstance(usernames[0], str)
            or not usernames[0] or "\0" in usernames[0]):
        raise ValueError("One nonempty inherited USERNAME is required for MO2 startup")
    allowed = {"systemroot", "windir", "comspec", "temp", "tmp", "userprofile",
               "appdata", "localappdata", "programdata", "programfiles",
               "programfiles(x86)", "commonprogramfiles", "commonprogramfiles(x86)",
               "path", "pathext", "systemdrive", "homedrive", "homepath"}
    result = {key: value for key, value in environment.items() if key.casefold() in allowed}
    result.update(USERNAME=usernames[0], SteamAppId="489830", SteamGameId="489830")
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
        instance_seeds = _instance_seeds(root, dict(active_mods=active, enabled_plugins=expected_plugins))
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
            # This is a fixed fresh instance, not an arbitrary user INI. Qt's
            # escape, key/group alias and encoding rules differ from Python's.
            # Only exact generated bytes authorize first boot; parsing below
            # supplies diagnostics and cannot admit a noncanonical file.
            if raw != instance_seeds["ModOrganizer.ini"].encode("utf-8"):
                block("mo2_ini_seed", "Initial MO2 configuration must exactly match the generated seed")
            ini = configparser.ConfigParser(interpolation=None, strict=True, delimiters=("=",))
            ini.read_string(_profile_text(raw or b""))
            def equivalent(value, expected):
                value = _qt_ini_string(value).replace("%BASE_DIR%", str(target))
                candidate = Path(value)
                if not candidate.is_absolute():
                    candidate = target / candidate
                return os.path.normcase(os.path.abspath(candidate)) == os.path.normcase(str(expected))
            if (not equivalent(ini.get("General", "gamePath"), root / "Game")
                    or _qt_ini_string(ini.get("General", "selected_profile")) != PROFILE
                    or _qt_ini_string(ini.get("General", "gameName")) != "Skyrim Special Edition"
                    or _qt_ini_string(ini.get("General", "game_edition")) != "Steam"):
                block("mo2_identity", "Second instance must select only the fixed lab Game and tier profile")
            directory_keys = {"base_directory": "", "mod_directory": "mods", "mods_directory": "mods",
                "profiles_directory": "profiles", "overwrite_directory": "overwrite", "download_directory": "downloads",
                "downloads_directory": "downloads", "cache_directory": "webcache"}
            for section in ini.sections():
                for key, value in ini.items(section):
                    if key in directory_keys and (not value.strip() or not equivalent(value, target / directory_keys[key])):
                        block("directory_redirect", "MO2 directory override leaves its fixed tier location: " + key)
        except (configparser.Error, ValueError, UnicodeError):
            block("mo2_ini", "Cannot establish the second instance configuration")
        profile = target / "profiles" / PROFILE
        try:
            _, raw = snapshot.read(profile / "settings.ini", content=True)
            if raw != instance_seeds["profiles/" + PROFILE + "/settings.ini"].encode("utf-8"):
                block("local_profile_seed", "Initial local profile settings must exactly match the generated seed")
            ini = configparser.ConfigParser(interpolation=None, strict=True, delimiters=("=",))
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


def _qt_ini_string(value):
    """Decode only the literal Qt INI subset used by this fixed instance.

    ConfigParser does not decode Qt escapes. Unknown/single backslashes,
    quoted/list values and other typed values must fail closed, not acquire
    different filesystem meaning when MO2 reads them with QSettings.
    """
    if not isinstance(value, str):
        raise ValueError("Unsupported Qt INI value")
    if value.startswith("@ByteArray(") and value.endswith(")"):
        value = value[11:-1]
    elif value.startswith("@"):
        raise ValueError("Unsupported Qt INI type")
    if any(ord(char) < 32 or char in '\",;' for char in value):
        raise ValueError("Unsupported Qt INI string syntax")
    decoded, index = [], 0
    while index < len(value):
        char = value[index]
        if char == "\\":
            if index + 1 == len(value) or value[index + 1] != "\\":
                raise ValueError("Ambiguous Qt INI path escape")
            index += 1
        decoded.append(char)
        index += 1
    return "".join(decoded)


def _instance_seeds(root, recipe):
    """Fresh local state only; never read or copy an existing application INI."""
    target = root / INSTANCE
    profile = "profiles/" + PROFILE + "/"
    return {
        "portable.txt": "",
        "ModOrganizer.ini": "[General]\ngameName=Skyrim Special Edition\ngame_edition=Steam\nselected_profile=@ByteArray(" + PROFILE
            + ")\ngamePath=@ByteArray(" + (root / "Game").as_posix() + ")\n[Settings]\n"
            + "\n".join(key + "=" + (target / child).as_posix() for key, child in (
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
             "hold_music/installed_library.py", "hold_music/library_merge.py",
             "hold_music/runtime_contract.py", "hold_music/recording_identity.py")
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


# Deliberately one first boot, separate from the installation transaction. The
# original baseline runner and its request/result protocol are not generalized.
RUNTIME_CONTROL = ".skyrimnet-tier-runtime"
CAPTURE_ID = re.compile(r"^[0-9a-f]{32}$")
BASELINE_LOGS = {"harness": baseline.STORAGE + "/result.json",
                 "receipts": "SKSE/Plugins/StorageUtilData/HoldMusic/receipts.json",
                 "trace": "SKSE/Plugins/StorageUtilData/HoldMusic/trace.json"}


def _document(snapshot, path):
    path = _no_alias(path)
    if not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Required bounded evidence document is unavailable")
    state, raw = snapshot.read(path, content=True)
    try:
        value = _json(raw)
    except (ValueError, UnicodeError):
        raise ValueError("Evidence document is not valid JSON") from None
    if not isinstance(value, dict):
        raise ValueError("Evidence document must be an object")
    return value, state


def _capture_reference(root, reference):
    if (not isinstance(reference, dict) or set(reference) != {"run_id", "capture_id"}
            or not isinstance(reference["run_id"], str) or not baseline.RUN_ID.fullmatch(reference["run_id"])
            or not isinstance(reference["capture_id"], str) or not CAPTURE_ID.fullmatch(reference["capture_id"])):
        raise ValueError("Baseline reference requires a run ID and capture ID")
    run = _no_alias(root / "runs" / reference["run_id"])
    return run, _no_alias(run / "captures" / reference["capture_id"])


def _capture_documents(root, reference, snapshot):
    run_dir, capture = _capture_reference(root, reference)
    evidence, _ = _document(snapshot, capture / "evidence.json")
    if (evidence.get("run_id") != reference["run_id"] or evidence.get("capture_id") != reference["capture_id"]
            or not isinstance(evidence.get("logs"), list)):
        raise ValueError("Captured evidence identity is inconsistent")
    rows = evidence["logs"]
    if (any(not isinstance(row, dict) or not isinstance(row.get("id"), str) for row in rows)
            or len({row["id"] for row in rows}) != len(rows)):
        raise ValueError("Captured evidence sources are ambiguous")
    documents, states = {}, {}
    for name, virtual in BASELINE_LOGS.items():
        spec = next((row for row in rows if row.get("id") == name), None)
        value, state = _document(snapshot, capture / "logs" / (name + ".bin"))
        if (spec is None or spec.get("source") != "MO2/overwrite/" + virtual
                or spec.get("archived_file") != "logs/" + name + ".bin"
                or not isinstance(spec.get("after"), dict) or spec["after"].get("sha256") != state["sha256"]):
            raise ValueError("Captured evidence bytes do not match their fixed source")
        documents[name], states[name] = value, state
    return run_dir, evidence, documents, states


def _number(value):
    return type(value) in (int, float) and float("-inf") < value < float("inf")


def _object(value):
    return value if isinstance(value, dict) else {}


def _ascii_case(value):
    return value.translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"))


def _baseline_fixture(root, recipe, snapshot):
    path = root / "MO2/mods/Hold Music Lab Data/SKSE/Plugins/StorageUtilData/HoldMusic/library.json"
    manifest, state = _document(snapshot, path)
    inputs = [row for row in recipe["files"] if row.get("source", {}).get("path") == str(path)]
    if (len(inputs) != 1 or inputs[0]["sha256"] != state["sha256"]
            or manifest_runtime_selection_errors(manifest, required=True)):
        raise ValueError("Baseline fixture is not a validated copied runtime projection")
    return manifest


def _receipt_identity(receipt, slot, key, manifest):
    rows = [row for row in manifest["recordings"] if row.get("slot") == slot]
    contracts = [row for row in manifest["runtime_selection"]["contracts"] if row["identity_key"] == key]
    identity = receipt.get("runtime_identity")
    if (len(rows) != 1 or len(contracts) != 1 or type(rows[0].get("slot")) is not int
            or recording_contract_errors(rows[0], contracts[0])
            or _object(rows[0].get("provenance")).get("kind") != "synthetic_test_fixture"
            or any(not isinstance(rows[0].get(field), str) or not rows[0][field]
                   for field in ("performer_id", "region", "composition_id"))
            or not isinstance(identity, dict) or set(identity) != {*RUNTIME_CONTRACT_FIELDS, "identity_key", "version"}
            or type(identity.get("version")) is not int or identity["version"] != 1
            or identity.get("identity_key") != key
            or any(not isinstance(identity.get(field), str)
                   or _ascii_case(identity[field]) != _ascii_case(contracts[0][field]) for field in RUNTIME_CONTRACT_FIELDS)
            or any(not isinstance(receipt.get(field), str)
                   or _ascii_case(receipt[field]) != _ascii_case(rows[0][field])
                   for field in ("performer_id", "region", "composition_id"))
            or not isinstance(receipt.get("save_id"), str) or not receipt["save_id"]):
        raise ValueError("Receipt requires the complete selected source identity")
    return rows[0]


def _accept_baseline(root, references, recipe, snapshot):
    if not isinstance(references, dict) or set(references) != {"focused_complete", "focused_interrupt", "ambient_entry"}:
        raise ValueError("Completed, requested-interruption and ambient-entry baseline captures are required")
    manifest = _baseline_fixture(root, recipe, snapshot)
    accepted = {}
    for scenario, expected in (("focused_complete", "completed"), ("focused_interrupt", "interrupted"), ("ambient_entry", "completed")):
        reference = references[scenario]
        if not isinstance(reference, dict) or set(reference) not in ({"capture"}, {"capture", "before"}):
            raise ValueError("Baseline evidence requires capture and optional before references")
        run_dir, evidence, docs, states = _capture_documents(root, reference["capture"], snapshot)
        run, _ = _document(snapshot, run_dir / "run.json")
        prior, _ = _document(snapshot, run_dir / "preflight.json")
        result, receipts, trace = docs["harness"], docs["receipts"], docs["trace"]
        if (run.get("run_id") != reference["capture"]["run_id"] or run.get("request_published") is not True
                or run.get("scenario") != scenario.replace("_", "-")
                or type(run.get("started_ns")) is not int or run["started_ns"] <= 0
                or not isinstance(run.get("started_at_utc"), str) or not run["started_at_utc"]
                or result.get("run_id") != run["run_id"] or result.get("started_at_utc") != run["started_at_utc"]
                or result.get("scenario") != scenario or result.get("status") != "passed"
                or result.get("world_id") != "hold-music-se-lab"
                or result.get("expected_outcome") != expected or result.get("runtime_engine_observed") is not True
                or evidence.get("fresh_required_evidence") is not True
                or prior.get("operation") != "se_lab_preflight" or prior.get("status") != "ready_for_explicit_launch"
                or prior.get("profile") != baseline.PROFILE
                or not isinstance(run.get("review_token"), str) or not run["review_token"]
                or run["review_token"] != prior.get("review_token")):
            raise ValueError("Baseline capture is not a fresh accepted scenario")
        for row in evidence["logs"]:
            if row.get("id") in BASELINE_LOGS:
                if (row.get("fresh") is not True or row.get("content_changed") is not True
                        or row.get("written_after_start") is not True
                        or type(row["after"].get("mtime_ns")) is not int
                        or row["after"]["mtime_ns"] < run["started_ns"]):
                    raise ValueError("Baseline capture freshness is incomplete")
        flags = result.get("assertions", {})
        required = ("evidence_valid", "slot_selection", "performance_start", "performance_stop",
                    "receipt", "receipt_identity_key", "cleanup_trace_and_receipt")
        if (not isinstance(flags, dict) or any(flags.get(name) is not True for name in required)
                or result.get("globals_restored") is not True
                or result.get("focused_start_in_flight") is not False
                or result.get("focused_start_cleanup_pending") is not False
                or type(result.get("boolean_serialization_errors")) is not int
                or result["boolean_serialization_errors"] != 0):
            raise ValueError("Baseline cleanup or identity assertions are incomplete")
        if "admission" in result:
            admission = result["admission"]
            pending = ("acquire_in_flight", "resume_in_flight", "fault", "cleanup_pending", "initial_drain_pending",
                       "begin_in_flight", "baseline_work_in_flight", "transition_in_flight")
            optional_pending = ("fixture_transition_in_flight", "fixture_movement_unresolved")
            if (not isinstance(admission, dict) or type(admission.get("ticket")) is not int or admission["ticket"] != 0
                    or any(admission.get(name) is not True for name in ("baselines_ready", "resumed", "drained_observed"))
                    or any(admission.get(name) is not False for name in pending)
                    or any(name in admission and admission[name] is not False for name in optional_pending)
                    or admission.get("pending_finish_reason") != ""):
                raise ValueError("Baseline admission has unresolved work or ownership")
        if scenario == "ambient_entry":
            if (any(flags.get(name) is not True for name in ("production_scan", "eligible_owned_sven", "real_inn_entry"))
                    or result.get("ambient_scheduling_bypassed") is not False
                    or result.get("controller_entry_setup_injected") is not False):
                raise ValueError("Ambient baseline did not exercise the production entry path")
        for name in ("fixture_ai", "vanilla_autostart"):
            state = result.get(name)
            if not isinstance(state, dict):
                raise ValueError("Controlled baseline fixture evidence is missing")
            if type(state.get("requested")) is not bool:
                raise ValueError("Controlled baseline fixture request is malformed")
            if state["requested"]:
                pending = ("acquisition_in_flight", "acquisition_intent") if name == "fixture_ai" else ("intent", "mutation_in_flight", "conflict")
                if state.get("released") is not True or any(state.get(key) is not False for key in pending):
                    raise ValueError("Baseline fixture has unresolved ownership")
        if _object(result.get("world_setup")).get("game_hour_restored") is not True:
            raise ValueError("Baseline world setup restoration is unverified")
        baseline_index = result.get("receipt_baseline")
        original_trace = None
        rows = receipts.get("performances")
        if (type(baseline_index) is not int or baseline_index < 0 or not isinstance(rows, list)
                or len(rows) != baseline_index + 1 or type(result.get("receipt_index")) is not int
                or result["receipt_index"] != baseline_index):
            raise ValueError("Baseline must contain exactly one new receipt")
        if baseline_index:
            if "before" not in reference:
                raise ValueError("Nonempty receipt history requires its original before capture")
            _, _, before_docs, before_states = _capture_documents(root, reference["before"], snapshot)
            if (not isinstance(run.get("logs"), list) or any(not isinstance(row, dict) for row in run["logs"])
                    or any(not isinstance(row.get("id"), str) for row in run["logs"])
                    or len({row["id"] for row in run["logs"]}) != len(run["logs"])):
                raise ValueError("Original run log inventory is malformed")
            run_logs = {row["id"]: row for row in run["logs"]}
            for name in ("receipts", "trace"):
                if _object(run_logs.get(name, {}).get("before")).get("sha256") != before_states[name]["sha256"]:
                    raise ValueError("Before capture is not the original run baseline")
            if before_docs["receipts"].get("performances") != rows[:baseline_index]:
                raise ValueError("Original baseline receipt history changed")
            old_entries = before_docs["trace"].get("entries", [])
            if (not isinstance(old_entries, list) or any(not isinstance(r, dict) for r in old_entries)
                    or any("seq" in r and type(r["seq"]) is not int for r in old_entries)
                    or max((r.get("seq", 0) for r in old_entries), default=0) != result.get("trace_baseline")):
                raise ValueError("Original trace baseline changed")
            original_trace = old_entries
        elif "before" in reference:
            raise ValueError("An empty history must not carry an unrelated before capture")
        row = rows[-1]
        slot, key = result.get("selected_slot"), result.get("selected_identity_key")
        began, ended = result.get("started_real_seconds"), result.get("observed_real_seconds")
        if (not isinstance(row, dict) or type(slot) is not int or not 1 <= slot <= 24
                or not isinstance(key, str) or not baseline.SHA.fullmatch(key)
                or not _number(began) or not _number(ended) or not began <= ended
                or type(row.get("slot")) is not int or row["slot"] != slot or row.get("outcome") != expected
                or row.get("performer_id") not in ("sven", "Sven")
                or row.get("world_id") != "hold-music-se-lab"
                or not _number(row.get("at_hours"))
                or not _number(row.get("started_real_seconds")) or not began <= row["started_real_seconds"] <= ended
                or _object(row.get("runtime_identity")).get("identity_key") != key):
            raise ValueError("Baseline receipt does not match the selected performance")
        recording = _receipt_identity(row, slot, key, manifest)
        duration = _object(result.get("timing")).get("fixture_duration_seconds")
        if (not _number(recording.get("duration_seconds")) or recording["duration_seconds"] <= 0
                or (scenario != "ambient_entry" and (not _number(duration) or duration <= 0
                                                     or duration != recording["duration_seconds"]))):
            raise ValueError("Baseline duration differs from its selected fixture")
        trace_baseline = result.get("trace_baseline")
        entries = trace.get("entries")
        if (type(trace_baseline) is not int or trace_baseline < 0 or not isinstance(entries, list)
                or any(not isinstance(r, dict) for r in entries)
                or any("seq" in r and type(r["seq"]) is not int for r in entries)):
            raise ValueError("Baseline trace is malformed")
        if original_trace is not None and entries[:len(original_trace)] != original_trace:
            raise ValueError("Original trace history changed")
        fresh = [r for r in entries if type(r.get("seq")) is int and r["seq"] > trace_baseline]
        if len({r["seq"] for r in fresh}) != len(fresh):
            raise ValueError("Baseline trace sequence is ambiguous")
        def matches(event, text):
            return [r for r in fresh if r.get("event") == event and isinstance(r.get("detail"), str)
                    and r["detail"].lower().startswith(text) and _number(r.get("real_seconds"))
                    and began <= r["real_seconds"] <= ended]
        starts = matches("performance_start", "id=sven slot=" + str(slot) + " ")
        stop_text = "outcome=" + expected + " id=sven slot=" + str(slot)
        stops = [r for r in matches("performance_stop", stop_text) if r["detail"].lower() == stop_text]
        if (len(starts) != 1 or len(stops) != 1
                or sum(r.get("event") == "performance_start" for r in fresh) != 1
                or sum(r.get("event") == "performance_stop" for r in fresh) != 1
                or starts[0]["real_seconds"] > stops[0]["real_seconds"]):
            raise ValueError("Baseline requires one matching start and stop")
        if scenario == "ambient_entry":
            # This cache is populated by focused setup only. Ambient duration
            # comes from the production start trace and the pinned source row.
            match = re.fullmatch(r"id=sven slot=" + str(slot) + r" duration=([0-9]+(?:\.[0-9]+)?)",
                                 starts[0]["detail"].lower())
            if match is None or float(match.group(1)) != recording["duration_seconds"]:
                raise ValueError("Ambient production duration differs from its selected fixture")
        if scenario == "focused_interrupt":
            request = result.get("interruption_request_real_seconds")
            guards = matches("performance_interrupt_guard", "id=sven slot=" + str(slot) + " reason=stop_requested ")
            if (flags.get("requested_interruption_guard") is not True or flags.get("stop_request_issued") is not True
                    or not _number(request) or not _number(duration) or duration <= 0
                    or not row["started_real_seconds"] <= request < row["started_real_seconds"] + duration
                    or len(guards) != 1 or not request <= guards[0]["real_seconds"] <= stops[0]["real_seconds"]):
                raise ValueError("Baseline interruption was not caused by its timely request")
        # Match every copied baseline source to its original preflight bytes;
        # paths are compared only, never opened from the historical document.
        original = _object(prior.get("snapshot")).get("files", [])
        if (not isinstance(original, list) or any(not isinstance(r, dict) for r in original)
                or any(not isinstance(r.get("path"), str) for r in original)
                or len({r["path"] for r in original}) != len(original)):
            raise ValueError("Baseline artifact inventory is missing")
        original_hashes = {r.get("path"): r.get("sha256") for r in original}
        copied = 0
        for item in recipe["files"]:
            source = item.get("source", {}).get("path")
            if source and Path(source).is_relative_to(root / "MO2/mods"):
                if original_hashes.get(source) != item["sha256"]:
                    raise ValueError("Accepted baseline artifacts differ from the tier recipe")
                copied += 1
        if not copied:
            raise ValueError("No baseline artifacts were bound to acceptance")
        accepted[scenario] = dict(reference=reference, identity_key=key, slot=slot,
                                  new_receipt_count=1, copied_files_bound=copied,
                                  controlled_actor_ai=result.get("controlled_actor_ai") is True,
                                  document_hashes={k: v["sha256"] for k, v in states.items()})
    return accepted


def _launch_inputs(references):
    root = _root()
    status = installation_status()
    prepared = preflight()
    if status["status"] != "installed_disabled" or status["blockers"] or prepared["status"] != "prepared_files_verified":
        raise ValueError("Exact installed first-boot preflight is required")
    snapshot = _Snapshot()
    accepted = _accept_baseline(root, references, prepared, snapshot)
    observed = snapshot.finish()
    environment = clean_launch_environment()
    return dict(tier=TIER, operation="skyrimnet_disabled_first_boot", acceptance=accepted,
                acceptance_snapshot=observed, preflight_token=prepared["review_token"],
                installation_transaction=status["transaction_id"], installation_journal_hash=status["journal_hash"],
                implementation=status["implementation"], protected=_protected(root),
                instance=_inventory(root / INSTANCE),
                environment=dict(policy="allowlist-v1", names=sorted(environment), sha256=_digest(environment)))


def launch_plan(baseline_evidence):
    """Read-only, first-boot-only review. No process, provider or HTTP request."""
    inputs = _launch_inputs(baseline_evidence)
    runtime = _fixed(_root(), RUNTIME_CONTROL)
    if runtime.exists():
        raise ValueError("A first-boot attempt already exists; no automatic retry or reset")
    return dict(version=1, tier=TIER, operation="skyrimnet_se_lab_launch_plan",
                status="ready_for_explicit_launch", can_launch=True, writes_performed=False,
                baseline_evidence=baseline_evidence, inputs=inputs,
                review_token="skyrimnet-launch-v1:" + _digest(inputs),
                native_verified=False, runtime_verified=False, effective_config_verified=False,
                egress_verified=False, paid_generation=False)


def _runtime_command(root):
    return [str(root / INSTANCE / "ModOrganizer.exe"), "-p", PROFILE, "--logs", "run", "--cwd",
            str(root / "Game"), str(root / "Game/skse64_loader.exe")]


PROCESS_OBSERVER = "native-filetime-v1"
PROCESS_NAMES = {"modorganizer.exe", "skse64_loader.exe", "skyrimse.exe", "skyrimvr.exe",
                 "sksevr_loader.exe", "usvfs_proxy_x64.exe", "usvfs_proxy_x86.exe"}
FILETIME_TO_DOTNET_TICKS = 504911232000000000
UNIX_TO_DOTNET_TICKS = 621355968000000000


class _NativeProcesses:
    """Read-only Win32 metadata; handles carry no write/terminate rights."""
    def __init__(self):
        if os.name != "nt":
            raise ValueError("Process identity observation requires Windows")
        from ctypes import wintypes as w
        class Entry(ctypes.Structure):
            _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("pid", w.DWORD),
                ("heap", ctypes.c_size_t), ("module", w.DWORD), ("threads", w.DWORD),
                ("parent_pid", w.DWORD), ("priority", w.LONG), ("flags", w.DWORD), ("name", w.WCHAR * 260)]
        self.w, self.Entry = w, Entry
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateToolhelp32Snapshot": ([w.DWORD, w.DWORD], w.HANDLE),
            "Process32FirstW": ([w.HANDLE, ctypes.POINTER(Entry)], w.BOOL),
            "Process32NextW": ([w.HANDLE, ctypes.POINTER(Entry)], w.BOOL),
            "OpenProcess": ([w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
            "QueryFullProcessImageNameW": ([w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)], w.BOOL),
            "GetProcessTimes": ([w.HANDLE, *([ctypes.POINTER(w.FILETIME)] * 4)], w.BOOL),
            "CloseHandle": ([w.HANDLE], w.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.api, name)
            function.argtypes, function.restype = arguments, result

    def entries(self):
        began = time.time_ns() // 100 + UNIX_TO_DOTNET_TICKS
        handle = self.api.CreateToolhelp32Snapshot(2, 0)  # TH32CS_SNAPPROCESS only
        if handle == ctypes.c_void_p(-1).value:
            raise ValueError("Native process snapshot is unavailable")
        try:
            entry = self.Entry()
            entry.dwSize = ctypes.sizeof(entry)
            found = self.api.Process32FirstW(handle, ctypes.byref(entry))
            rows = {}
            while found:
                if entry.name.lower() in PROCESS_NAMES:
                    if entry.pid in rows:
                        raise ValueError("Native process snapshot has duplicate identities")
                    rows[entry.pid] = dict(pid=entry.pid, parent_pid=entry.parent_pid, name=entry.name.lower())
                found = self.api.Process32NextW(handle, ctypes.byref(entry))
            if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
                raise ValueError("Native process enumeration is incomplete")
            return began, rows
        finally:
            self.api.CloseHandle(handle)

    def identity(self, entry, snapshot_started):
        process = self.api.OpenProcess(0x1000, False, entry["pid"])  # PROCESS_QUERY_LIMITED_INFORMATION
        if not process:
            raise ValueError("Native process identity disappeared or is inaccessible")
        try:
            name = ctypes.create_unicode_buffer(32768)
            size = self.w.DWORD(len(name))
            times = [self.w.FILETIME() for _ in range(4)]
            if (not self.api.QueryFullProcessImageNameW(process, 0, name, ctypes.byref(size))
                    or not self.api.GetProcessTimes(process, *[ctypes.byref(value) for value in times])):
                raise ValueError("Native process identity is incomplete")
            created = ((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime) + FILETIME_TO_DOTNET_TICKS
            if created > snapshot_started:
                # PID may have been reused after the first snapshot. Keep this
                # exact handle open and confirm its parent in a fresh snapshot.
                confirmed_at, current = self.entries()
                if created > confirmed_at or current.get(entry["pid"]) != entry:
                    raise ValueError("Native process identity changed during observation")
            return dict(pid=entry["pid"], parent_pid=entry["parent_pid"], path=name.value, created_ticks=created)
        finally:
            self.api.CloseHandle(process)


def _runtime_process_snapshot():
    """Exact native creation ticks; shared by launch and collector, never CIM."""
    native = _NativeProcesses()
    began, entries = native.entries()
    return [native.identity(entry, began) for entry in entries.values()]


class _ProcessObserver:
    """Bounded pre-armed sampler retaining verified short-lived parent rows."""
    def __init__(self, *, timeout_seconds, snapshot=None, interval=0.02, max_identities=128):
        self.snapshot = snapshot or _runtime_process_snapshot
        self.timeout, self.interval, self.maximum = timeout_seconds, interval, max_identities
        self.ready, self.stopped, self.lock = threading.Event(), threading.Event(), threading.Lock()
        self.history, self.current, self.initial = {}, [], []
        self.failed, self.expired = False, False
        self.samples, self.max_gap, self.last_sample = 0, 0.0, None
        self.thread = threading.Thread(target=self._run, name="hold-music-native-observer", daemon=True)

    def _run(self):
        deadline = time.monotonic() + self.timeout
        try:
            while not self.stopped.is_set():
                if time.monotonic() >= deadline:
                    with self.lock: self.expired = True
                    return
                rows = self.snapshot()
                if not isinstance(rows, list):
                    raise ValueError("Invalid process observation")
                with self.lock:
                    seen = set()
                    for row in rows:
                        if (not isinstance(row, dict) or set(row) != {"pid", "parent_pid", "path", "created_ticks"}
                                or any(type(row.get(key)) is not int for key in ("pid", "parent_pid", "created_ticks"))
                                or row["pid"] <= 0 or row["parent_pid"] < 0 or row["created_ticks"] <= 0
                                or not isinstance(row["path"], str) or not row["path"] or row["pid"] in seen):
                            raise ValueError("Invalid process observation")
                        seen.add(row["pid"])
                        prior = self.history.get(row["pid"])
                        if prior is not None and prior != row:
                            raise ValueError("Observed process identity was reused")
                        self.history[row["pid"]] = dict(row)
                    if len(self.history) > self.maximum:
                        raise ValueError("Process observation exceeded its bound")
                    observed = time.monotonic()
                    if self.last_sample is not None:
                        self.max_gap = max(self.max_gap, observed - self.last_sample)
                    self.last_sample = observed
                    self.current = [dict(row) for row in rows]
                    if self.samples == 0:
                        self.initial = list(self.current)
                    self.samples += 1
                self.ready.set()
                self.stopped.wait(self.interval)
        except Exception:
            # Preserve only a failure flag, never native exception text.
            with self.lock: self.failed = True
        finally:
            self.ready.set()

    def start(self):
        self.thread.start()
        if not self.ready.wait(min(5, self.timeout)):
            self.stop()
            raise ValueError("Native observer did not become ready")
        self.capture()
        return list(self.initial)

    def capture(self):
        with self.lock:
            if self.failed or self.expired or not self.samples:
                raise ValueError("Native process observation is incomplete")
            return dict(history=[dict(row) for row in self.history.values()],
                        current=[dict(row) for row in self.current], samples=self.samples,
                        max_sample_gap_seconds=self.max_gap)

    def stop(self):
        self.stopped.set()
        if self.thread.ident is not None:
            self.thread.join(timeout=1)
        return not self.thread.is_alive()


def _process_history(rows, prior, root, started_ns, launcher_pid):
    allowed = {str(root / INSTANCE / "ModOrganizer.exe"), str(root / "Game/skse64_loader.exe"),
               str(root / "Game/SkyrimSE.exe"), str(root / INSTANCE / "usvfs_proxy_x64.exe"),
               str(root / INSTANCE / "usvfs_proxy_x86.exe")}
    normalized = {os.path.normcase(path): path for path in allowed}
    if (not isinstance(rows, list) or not isinstance(prior, list)
            or type(started_ns) is not int or started_ns <= 0
            or type(launcher_pid) is not int or launcher_pid <= 0):
        raise ValueError("Malformed process observation context")
    earliest = started_ns // 100 + 621355968000000000
    def checked(row):
        if (not isinstance(row, dict) or set(row) != {"pid", "parent_pid", "path", "created_ticks"}
                or any(type(row.get(k)) is not int for k in ("pid", "parent_pid", "created_ticks"))
                or row["pid"] <= 0 or row["parent_pid"] < 0 or row["created_ticks"] < earliest
                or not isinstance(row["path"], str) or os.path.normcase(row["path"]) not in normalized):
            raise ValueError("Unexpected, preexisting or unverifiable process identity")
        return dict(row, path=normalized[os.path.normcase(row["path"])])
    history = {}
    for row in prior:
        value = checked(row)
        if value["pid"] in history:
            raise ValueError("Duplicate retained process identity")
        history[value["pid"]] = value
    current = {}
    for row in rows:
        value = checked(row)
        if value["pid"] in current or (value["pid"] in history and history[value["pid"]] != value):
            raise ValueError("Duplicate or reused process identity")
        current[value["pid"]] = value
        history[value["pid"]] = value
    organizer = history.get(launcher_pid)
    if organizer is not None and organizer["path"] != str(root / INSTANCE / "ModOrganizer.exe"):
        raise ValueError("Launcher identity does not belong to the separate instance")
    games = [r for r in current.values() if r["path"] == str(root / "Game/SkyrimSE.exe")]
    if len(games) > 1:
        raise ValueError("More than one game process is present")
    game = games[0] if games else None
    def lineage(node):
        visited, paths = set(), set()
        while node["pid"] not in visited:
            visited.add(node["pid"])
            paths.add(node["path"])
            if node["pid"] == launcher_pid:
                return paths
            parent = history.get(node["parent_pid"])
            if parent is None or parent["created_ticks"] > node["created_ticks"]:
                break
            node = parent
        return set()
    linked = False
    if game and organizer:
        linked = (str(root / "Game/skse64_loader.exe") in lineage(game)
                  and all(lineage(row) for row in current.values()))
    return list(history.values()), game if linked else None


def _runtime_json(path, value, *, new=False, expected=None):
    raw = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    if new:
        baseline._write_new(_no_alias(path), raw)
    else:
        _atomic_write(_no_alias(path), raw, expected=expected)
    return dict(exists=True, sha256=hashlib.sha256(raw).hexdigest(), size=len(raw))


def launch(baseline_evidence, review_token, *, timeout_seconds=30, process_probe=None):
    """Explicit one-shot launch. Timeout never kills, retries or enables anything."""
    baseline._require_windows()
    if type(timeout_seconds) not in (int, float) or not 1 <= timeout_seconds <= 60:
        raise ValueError("Launch observation timeout must be between 1 and 60 seconds")
    plan = launch_plan(baseline_evidence)
    if not _matches(review_token, plan["review_token"]):
        raise ValueError("Launch review is stale or belongs to another operation")
    _assert_closed(process_probe)
    root = _root()
    with _writer_lock(_no_alias(root / ".se-lab-writer.lock")), _writer_lock(_no_alias(root / CONTROL / "writer.lock")):
        fresh = launch_plan(baseline_evidence)
        if not _matches(review_token, fresh["review_token"]):
            raise ValueError("Launch inputs changed before admission")
        _assert_closed(process_probe)
        runtime = _fixed(root, RUNTIME_CONTROL)
        runtime.mkdir(exist_ok=False)
        started_ns = time.time_ns()
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:12]
        run = dict(version=1, tier=TIER, operation="skyrimnet_disabled_first_boot", run_id=run_id,
                   started_ns=started_ns, baseline_evidence=baseline_evidence, inputs=fresh["inputs"],
                   inputs_sha256=_digest(fresh["inputs"]), launch_command=_runtime_command(root),
                   process_observer=PROCESS_OBSERVER)
        run_state = _runtime_json(runtime / "run.json", run, new=True)
        result = dict(version=1, tier=TIER, run_id=run_id, status="launch_intent", process_started=False,
                      launcher_pid=None, processes=[], game=None, launch_attributed=False,
                      native_verified=False, effective_config_verified=False, runtime_verified=False,
                      egress_verified=False, paid_generation=False, processes_terminated=False, writes_performed=True,
                      process_observer=PROCESS_OBSERVER, observer_samples=0, max_sample_gap_seconds=None)
        result_state = _runtime_json(runtime / "launch-result.json", result, new=True)
        # The immutable intent survives unknown spawn outcomes. Never recycle it.
        if _digest(_launch_inputs(baseline_evidence)) != run["inputs_sha256"]:
            raise ValueError("Launch inputs changed while recording intent; attempt retained")
        _assert_closed(process_probe)
        environment = clean_launch_environment()
        if _digest(environment) != run["inputs"]["environment"]["sha256"]:
            raise ValueError("Launch environment changed after review")
        if _Snapshot().read(runtime / "run.json")["sha256"] != run_state["sha256"]:
            raise ValueError("Launch intent changed before dispatch")
        observer = None
        try:
            observer = _ProcessObserver(timeout_seconds=timeout_seconds + 5)
            if observer.start():
                raise ValueError("A process appeared before observer admission")
            _assert_closed(process_probe)
            if observer.capture()["history"]:
                raise ValueError("A process appeared before dispatch")
            process = subprocess.Popen(run["launch_command"], cwd=str(root / INSTANCE), shell=False,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=environment)
            result.update(status="launched_unattributed", process_started=True, launcher_pid=process.pid)
            result_state = _runtime_json(runtime / "launch-result.json", result, expected=result_state)
            deadline = time.monotonic() + timeout_seconds
            while True:
                observed = observer.capture()
                history, game = _process_history(observed["current"], observed["history"], root, started_ns, process.pid)
                result.update(processes=history, game=game, launch_attributed=game is not None,
                              observer_samples=observed["samples"], max_sample_gap_seconds=observed["max_sample_gap_seconds"])
                if game is not None:
                    result["status"] = "launched_attributed"
                    break
                if time.monotonic() >= deadline:
                    break
                time.sleep(0.02)
            result["protected_paths_unchanged"] = _protected(root) == run["inputs"]["protected"]
            if not result["protected_paths_unchanged"]:
                result["status"] = "protected_state_changed"
            last = observer.capture()
            history, last_game = _process_history(last["current"], last["history"], root, started_ns, process.pid)
            result.update(processes=history, observer_samples=last["samples"],
                          max_sample_gap_seconds=last["max_sample_gap_seconds"])
            if game is not None and last_game != game:
                result.update(status="launch_observation_incomplete", game=None, launch_attributed=False)
        except (OSError, ValueError, subprocess.SubprocessError):
            # No exception bodies, paths, output or environment values are copied.
            result["status"] = "launch_observation_incomplete" if result["process_started"] else "launch_failed_or_unknown"
            result.update(game=None, launch_attributed=False)
        finally:
            if observer is not None and not observer.stop():
                result.update(status="launch_observation_incomplete", game=None, launch_attributed=False)
            elif observer is not None:
                try:
                    # Use the final joined frame, including rows observed after
                    # the last main-thread poll. Never upgrade an unattributed
                    # launch merely because a game appeared during shutdown.
                    final = observer.capture()
                    if result["process_started"]:
                        history, final_game = _process_history(final["current"], final["history"], root,
                                                               started_ns, result["launcher_pid"])
                        result.update(processes=history, observer_samples=final["samples"],
                                      max_sample_gap_seconds=final["max_sample_gap_seconds"])
                        if result["launch_attributed"] and final_game != result["game"]:
                            result.update(status="launch_observation_incomplete", game=None, launch_attributed=False)
                except ValueError:
                    result.update(status="launch_observation_incomplete" if result["process_started"] else "launch_failed_or_unknown",
                                  game=None, launch_attributed=False)
        _runtime_json(runtime / "launch-result.json", result, expected=result_state)
        return result


def collect(run_id):
    """Serialize local capture with this tool's writers; never arm or launch."""
    root = _root()
    runtime = _fixed(root, RUNTIME_CONTROL)
    if not runtime.is_dir():
        raise ValueError("No retained first-boot attempt exists")
    with _writer_lock(_no_alias(root / ".se-lab-writer.lock")), _writer_lock(_no_alias(root / CONTROL / "writer.lock")):
        return _collect(run_id)


def _collect(run_id):
    """Local metadata collection only; does not contact listeners or read secrets.

    Effective config and native initialization remain unverified in this bounded
    checkpoint. Changed first-boot state is observed, never accepted as a new seed.
    """
    if not isinstance(run_id, str) or not baseline.RUN_ID.fullmatch(run_id):
        raise ValueError("Invalid first-boot run ID")
    root = _root()
    runtime = _fixed(root, RUNTIME_CONTROL)
    snapshot = _Snapshot()
    run, _ = _document(snapshot, runtime / "run.json")
    launched, _ = _document(snapshot, runtime / "launch-result.json")
    if (run.get("version") != 1 or run.get("tier") != TIER or run.get("run_id") != run_id
            or run.get("operation") != "skyrimnet_disabled_first_boot"
            or run.get("launch_command") != _runtime_command(root)
            or not isinstance(run.get("inputs"), dict) or _digest(run["inputs"]) != run.get("inputs_sha256")
            or launched.get("tier") != TIER or launched.get("run_id") != run_id
            or run.get("process_observer") != PROCESS_OBSERVER or launched.get("process_observer") != PROCESS_OBSERVER
            or launched.get("process_started") is not True or type(launched.get("launcher_pid")) is not int
            or type(run.get("started_ns")) is not int or not isinstance(launched.get("processes"), list)):
        raise ValueError("No valid retained launch observation exists")
    implementation = _implementation(snapshot)
    if implementation != run["inputs"].get("implementation"):
        raise ValueError("Collector implementation changed since this launch")
    history, game = _process_history(_runtime_process_snapshot(), launched["processes"], root,
                                     run["started_ns"], launched["launcher_pid"])
    before = run["inputs"].get("instance")
    if not isinstance(before, dict) or not isinstance(before.get("files"), dict):
        raise ValueError("Retained tier inventory is malformed")
    current = _inventory(root / INSTANCE)
    protected = _protected(root)
    history, after_game = _process_history(_runtime_process_snapshot(), history, root,
                                          run["started_ns"], launched["launcher_pid"])
    if current != _inventory(root / INSTANCE) or protected != _protected(root):
        raise ValueError("Runtime evidence changed during collection")
    snapshot.finish()
    attributed = game is not None and game == after_game and game == launched.get("game")
    changed = [name for name in before["files"].keys() | current["files"].keys()
               if before["files"].get(name) != current["files"].get(name)]
    capture_id = uuid.uuid4().hex
    report = dict(version=1, tier=TIER, run_id=run_id, capture_id=capture_id,
                  process_observer=PROCESS_OBSERVER,
                  status="local_evidence_collected" if attributed else "incomplete_process_evidence",
                  launch_attributed=attributed, game=game if attributed else None,
                  protected_paths_unchanged=protected == run["inputs"].get("protected"),
                  changed_file_count=len(changed), instance_inventory_sha256=_digest(current),
                  changed_inventory_sha256=_digest(changed),
                  private_runtime_file_count=sum(_private_path(name) for name in current["files"]),
                  native_verified=False, effective_config_verified=False, vfs_verified=False,
                  runtime_verified=False, egress_verified=False, paid_generation=False,
                  writes_performed=True, network_requests_performed=False,
                  limitations=["Local file hashes and exact process lineage only; no native initialization or effective config smoke proof.",
                      "No HTTP, MCP, provider, raw log, Auth.yaml, database or environment body is collected.",
                      "First-boot changes are retained, never reset or promoted into the installation contract."])
    if not report["protected_paths_unchanged"]:
        report["status"] = "protected_state_changed"
    captures = _no_alias(runtime / "captures")
    captures.mkdir(exist_ok=True)
    _runtime_json(captures / (capture_id + ".json"), report, new=True)
    return report
