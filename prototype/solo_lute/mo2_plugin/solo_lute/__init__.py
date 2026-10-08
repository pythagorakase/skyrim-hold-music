"""MO2 companion for the Solo Lute SkyrimNet content plugin."""
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import mobase
from PyQt6.QtCore import QCoreApplication

from .engine import Adapter, ConfigOverlay


class SoloLute(mobase.IPluginFileMapper):
    def __init__(self):
        super().__init__()
        self.organizer = None
        self.adapter = None
        self.bridge = None
        self.endpoint = None
        self.ready = False
        self.log = logging.getLogger("solo_lute")

    def name(self):
        return "MGO Solo Lute Adapter"

    def localizedName(self):
        return "Solo Lute (experimental music adapter)"

    def author(self):
        return "Local experiment"

    def description(self):
        return "Optional instrumental lute performances. Enabled by the Solo Lute mod in the configured profile."

    def version(self):
        return mobase.VersionInfo(0, 1, 0)

    def settings(self):
        return []

    def init(self, organizer):
        self.organizer = organizer
        self.root = Path(__file__).resolve().parents[2]
        self.local = json.loads((Path(__file__).parent / "local.json").read_text(encoding="utf-8"))
        handler = RotatingFileHandler(self.root / "logs" / "SoloLute.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        self.log.addHandler(handler)
        self.log.setLevel(logging.INFO)
        self.log.propagate = False
        organizer.onAboutToRun(self._before)
        organizer.onFinishedRun(self._after)
        QCoreApplication.instance().aboutToQuit.connect(self._close)
        self.log.info("Solo Lute 0.1.0 loaded; music routing is inactive until a configured-profile launch")
        return True

    def _active(self):
        return (self.organizer.profileName() == self.local["profile"]
                and bool(self.organizer.modList().state(self.local["mod"]) & mobase.ModState.ACTIVE))

    def _before(self, application):
        self.ready = False
        if not self._active():
            return True
        try:
            profile = self.root / "profiles" / self.local["profile"]
            data = self.root / "mods" / self.local["data_mod"] / "SKSE" / "Plugins" / "SkyrimNet"
            if not (self.organizer.modList().state(self.local["data_mod"]) & mobase.ModState.ACTIVE):
                raise ValueError("The isolated profile data mod is inactive")
            runtime = profile / "solo-lute-runtime"
            self.bridge = ConfigOverlay(data / "config" / "BardSinging.yaml", runtime)
            if self.adapter is None:
                settings = data / "config" / "plugins" / "SoloLute" / "settings.yaml"
                self.adapter = Adapter(self.bridge.overlay, settings, runtime, self.local.get("port", 18765))
                self.endpoint = self.adapter.start()
            self.bridge.prepare(self.endpoint)
            self.ready = True
            self.log.info("Prepared temporary Bard Singing route for configured profile")
        except Exception as exc:
            # A setup failure leaves the original OpenRouter config visible.
            # Do not block game launch or print config data / credentials.
            self.log.error("Adapter setup failed (%s); keeping the original music provider", type(exc).__name__)
        return True

    def mappings(self):
        if not self.ready or not self._active():
            return []
        mapping = mobase.Mapping()
        mapping.source = self.bridge.overlay.as_posix()
        mapping.destination = (Path(self.organizer.managedGame().dataDirectory().absolutePath()) /
                               "SKSE/Plugins/SkyrimNet/config/BardSinging.yaml").as_posix()
        mapping.isDirectory = False
        mapping.createTarget = False
        self.log.info("Mapping the temporary Bard Singing config")
        return [mapping]

    def _after(self, application, result):
        if self.bridge and self.ready:
            try:
                self.bridge.reconcile()
            except Exception as exc:
                self.log.error("Could not reconcile music dashboard edits (%s); kept recovery files", type(exc).__name__)

    def _close(self):
        if self.adapter:
            self.adapter.stop()


def createPlugin():
    return SoloLute()
