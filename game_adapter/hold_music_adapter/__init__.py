"""MO2 companion for the Hold Music SkyrimNet content plugin."""
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import mobase
from PyQt6.QtCore import QCoreApplication

from .engine import ConfigOverlay
from .service import ProcessAdapter


class HoldMusic(mobase.IPluginFileMapper):
    def __init__(self):
        super().__init__()
        self.organizer = None
        self.adapter = None
        self.bridge = None
        self.endpoint = None
        self.ready = False
        self.log = logging.getLogger("hold_music_adapter")

    def name(self):
        return "MGO Hold Music Adapter"

    def localizedName(self):
        return "Hold Music (experimental music adapter)"

    def author(self):
        return "Local experiment"

    def description(self):
        return "Location-based Nord music recipes. Enabled by the Hold Music mod in the configured profile."

    def version(self):
        return mobase.VersionInfo(0, 2, 1)

    def settings(self):
        return []

    def init(self, organizer):
        self.organizer = organizer
        self.root = Path(__file__).resolve().parents[2]
        self.local = json.loads((Path(__file__).parent / "local.json").read_text(encoding="utf-8"))
        handler = RotatingFileHandler(self.root / "logs" / "HoldMusic.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        self.log.addHandler(handler)
        self.log.setLevel(logging.INFO)
        self.log.propagate = False
        organizer.onAboutToRun(self._before)
        organizer.onFinishedRun(self._after)
        QCoreApplication.instance().aboutToQuit.connect(self._close)
        self.log.info("Hold Music 0.2.1 loaded; music routing is inactive until a configured-profile launch")
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
            runtime = profile / "hold-music-runtime"
            self.bridge = ConfigOverlay(data / "config" / "BardSinging.yaml", runtime)
            if self.adapter is None:
                settings = data / "config" / "plugins" / "HoldMusic" / "settings.yaml"
                self.adapter = ProcessAdapter(self.local["python"], self.bridge.overlay, settings, runtime,
                                              self.root / "logs" / "HoldMusic-Service.log",
                                              port=self.local.get("port", 0))
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
        prompt = mobase.Mapping()
        prompt.source = (Path(__file__).parent / 'bard_song_lyrics.prompt').as_posix()
        prompt.destination = (Path(self.organizer.managedGame().dataDirectory().absolutePath()) /
                              'SKSE/Plugins/SkyrimNet/external/local.hold-music/prompts/bard_song_lyrics.prompt').as_posix()
        prompt.isDirectory = False
        prompt.createTarget = False
        # Publish the context template only when its matching adapter is healthy.
        # A failed helper startup leaves the original provider AND prompt visible.
        self.log.info("Mapping the temporary Bard Singing config and request-context prompt")
        return [mapping, prompt]

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
    return HoldMusic()
