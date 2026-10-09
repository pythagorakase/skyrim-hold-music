from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game_adapter/hold_music_adapter"))
from engine import mp3_duration
from mp3_fixture import ID3V1, id3v2_tag, mp3_frames


class MP3DurationTests(unittest.TestCase):
    def test_mpeg_versions_tags_and_padding(self):
        for version, samples, rate in ((1, 1152, 44100), (2, 576, 22050), (2.5, 576, 11025)):
            for prefix in (b"", id3v2_tag()):
                for suffix in (b"", ID3V1):
                    for padding in (False, True):
                        with self.subTest(version=version, id3v2=bool(prefix), id3v1=bool(suffix), padding=padding):
                            self.assertAlmostEqual(mp3_duration(prefix + mp3_frames(version, padding=padding) + suffix),
                                                   200 * samples / rate)

    def test_garbage_and_incomplete_first_frame(self):
        for data in (b"", b"garbage", b"ID3", b"ID3\x04\x00\x00\xff\x00\x00\x00",
                     mp3_frames(count=1)[:-1], id3v2_tag()[:-1]):
            with self.subTest(data=data[:12]):
                self.assertEqual(mp3_duration(data), 0.0)

    def test_truncation_counts_only_complete_frames(self):
        for version, samples, rate in ((1, 1152, 44100), (2, 576, 22050), (2.5, 576, 11025)):
            with self.subTest(version=version):
                self.assertAlmostEqual(mp3_duration(mp3_frames(version)[:-1]), 199 * samples / rate)
                self.assertAlmostEqual(mp3_duration(mp3_frames(version, count=1) + b"\xff\xfb"), samples / rate)

    def test_invalid_header_stops_without_resynchronizing(self):
        frame = mp3_frames(count=1)
        for bad in (b"garbage", bytes.fromhex("ffeb9064"), bytes.fromhex("fffd9064"),
                    bytes.fromhex("fffbfc64"), bytes.fromhex("fffb9c64")):
            with self.subTest(bad=bad):
                self.assertAlmostEqual(mp3_duration(frame + bad + frame), 1152 / 44100)
        self.assertAlmostEqual(mp3_duration(frame + ID3V1 + frame), 1152 / 44100)

    def test_free_format_is_unsupported(self):
        free_format = bytes.fromhex("fffb0064") + bytes(413)
        self.assertEqual(mp3_duration(free_format), 0.0)
        self.assertEqual(mp3_duration(mp3_frames(count=1) + free_format), 0.0)

    def test_other_sample_rates_and_variable_bitrate(self):
        # MPEG-1, 192 kbps, 48 kHz, padded: floor(144*192000/48000)+1.
        frame = bytes.fromhex("fffbb664") + bytes(573)
        self.assertAlmostEqual(mp3_duration(frame + mp3_frames(count=1)), 1152 / 48000 + 1152 / 44100)

    def test_id3v24_footer(self):
        tag = b"ID3\x04\x00\x10\x00\x00\x00\x00" + b"3DI" + bytes(7)
        self.assertAlmostEqual(mp3_duration(tag + mp3_frames()), 200 * 1152 / 44100)


if __name__ == "__main__":
    unittest.main()
