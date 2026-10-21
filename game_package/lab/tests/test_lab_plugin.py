"""Independent HM_Lab ESP/VMAD/SEQ checks without Mutagen or game execution."""

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import struct
import unittest
import zlib


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(os.environ["HM_LAB_PACKAGE"]) if os.environ.get("HM_LAB_PACKAGE") else None
FORMS = ROOT / "data/forms.json"


def records(data):
    result = []

    def walk(start, end):
        while start < end:
            tag, size = struct.unpack_from("<4sI", data, start)
            if tag == b"GRUP":
                assert size >= 24 and start + size <= end
                walk(start + 24, start + size)
                start += size
                continue
            tag, size, flags, fid, _, _, _ = struct.unpack_from("<4sIIIIHH", data, start)
            assert start + 24 + size <= end
            payload = data[start + 24:start + 24 + size]
            if flags & 0x40000:
                length = struct.unpack_from("<I", payload)[0]
                payload = zlib.decompress(payload[4:])
                assert len(payload) == length
            pos, parts, extended = 0, [], None
            while pos < len(payload):
                sub, length = struct.unpack_from("<4sH", payload, pos)
                pos += 6
                if sub == b"XXXX":
                    assert length == 4 and extended is None
                    extended = struct.unpack_from("<I", payload, pos)[0]
                    pos += 4
                    continue
                if extended is not None:
                    length, extended = extended, None
                value = payload[pos:pos + length]
                assert len(value) == length
                parts.append((sub, value))
                pos += length
            assert pos == len(payload) and extended is None
            result.append(dict(tag=tag, flags=flags, id=fid, parts=parts, values=dict(parts)))
            start += size + 24
        assert start == end

    walk(0, len(data))
    return result


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, fmt):
        result = struct.unpack_from(fmt, self.data, self.pos)
        self.pos += struct.calcsize(fmt)
        return result[0] if len(result) == 1 else result

    def string(self):
        length = self.take("<H")
        result = self.data[self.pos:self.pos + length]
        assert len(result) == length
        self.pos += length
        return result.decode()


class LabPluginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if PACKAGE is None:
            raise unittest.SkipTest("Set HM_LAB_PACKAGE or pass --package to validate a lab build")
        cls.package = PACKAGE.resolve()
        cls.records = records((cls.package / "HM_Lab.esp").read_bytes())
        cls.header = cls.records[0]
        cls.quest = next(x for x in cls.records if x["tag"] == b"QUST")
        cls.masters = [v.rstrip(b"\0").decode() for t, v in cls.header["parts"] if t == b"MAST"]

    def test_normal_esp_two_masters_and_one_owned_quest(self):
        self.assertEqual(self.header["tag"], b"TES4")
        self.assertEqual(self.header["flags"] & 0x201, 0, "Must be neither ESL nor ESM")
        self.assertEqual(self.masters, ["Skyrim.esm", "HoldMusic.esp"])
        self.assertEqual(Counter(r["tag"] for r in self.records), {b"TES4": 1, b"QUST": 1})
        self.assertEqual(struct.unpack("<fII", self.header["values"][b"HEDR"])[2], 0x801)
        self.assertEqual(self.quest["id"], 0x02000800)
        self.assertEqual(self.quest["values"][b"EDID"], b"HM_LabQuest\0")
        self.assertEqual(struct.unpack_from("<H", self.quest["values"][b"DNAM"])[0], 0x101)
        self.assertEqual(self.quest["values"][b"DNAM"][2], 90)

    def test_fixture_alias_is_optional_empty_and_has_only_the_verified_package(self):
        self.assertEqual(self.quest["values"][b"ANAM"], struct.pack("<I", 1))
        parts = self.quest["parts"]
        start = next(i for i, (tag, _) in enumerate(parts) if tag == b"ALST")
        # Exact alias layout excludes forced/unique/event/condition fill rules,
        # actor flags, factions, inventory, and all additional package overrides.
        self.assertEqual(parts[start:], [
            (b"ALST", struct.pack("<I", 0)),
            (b"ALID", b"FixtureActor\0"),
            (b"FNAM", struct.pack("<I", 2)),  # Optional only.
            (b"ALPC", struct.pack("<I", 0x0010FB3F)),
            (b"ALED", b""),
        ])
        self.assertEqual(sum(tag == b"ALST" for tag, _ in parts), 1)
        self.assertFalse(any(tag == b"ALLS" for tag, _ in parts))

    def test_harness_script_and_exact_cross_plugin_properties(self):
        reader = Reader(self.quest["values"][b"VMAD"])
        self.assertEqual(reader.take("<HHH"), (5, 2, 1))
        self.assertEqual(reader.string(), "HM_LabHarness")
        self.assertEqual(reader.take("<B"), 0)
        self.assertEqual(reader.take("<H"), 9)
        properties = {}
        for _ in range(9):
            name = reader.string()
            self.assertNotIn(name, properties)
            self.assertEqual(reader.take("<BB"), (1, 1), name)
            unused, alias, form = reader.take("<HhI")
            self.assertEqual((unused, alias), (0, -1), name)
            properties[name] = form
        # Quest extension version 2, zero fragments, empty file, no aliases.
        self.assertEqual(reader.take("<BH"), (2, 0))
        self.assertEqual(reader.string(), "")
        self.assertEqual(reader.take("<H"), 0)
        self.assertEqual(reader.pos, len(reader.data))
        forms = json.loads(FORMS.read_text(encoding="utf-8"))["forms"]
        inn = [x for x in forms if x["edid"] == "LocTypeInn"
               and x["plugin"].lower() == "skyrim.esm" and x["type"] == "KYWD"]
        self.assertEqual(len(inn), 1)
        self.assertEqual(properties, {
            "Library": 0x01000800,
            "Config": 0x01000800,
            "HoldMusicQuest": 0x01000800,
            "HM_Enabled": 0x01000801,
            "HM_InstrumentalPercent": 0x01000802,
            "HM_SessionCap": 0x01000803,
            "HM_MinDelaySeconds": 0x01000804,
            "HM_MaxDelaySeconds": 0x01000805,
            "LocTypeInn": int(inn[0]["id"], 16),
        })

    def test_seq_references_the_file_local_lab_quest(self):
        self.assertEqual((self.package / "SEQ/HM_Lab.seq").read_bytes(),
                         struct.pack("<I", self.quest["id"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=PACKAGE, required=PACKAGE is None)
    parser.add_argument("--forms", type=Path, default=FORMS)
    arguments, remaining = parser.parse_known_args()
    PACKAGE, FORMS = arguments.package, arguments.forms
    unittest.main(argv=[__file__, *remaining])
