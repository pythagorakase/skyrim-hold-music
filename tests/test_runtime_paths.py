import os
from pathlib import Path
import tempfile
import unittest

from hold_music.runtime_paths import Located, locate, resolve_receipts, resolve_trace, storage_dirs


class RuntimePathsTests(unittest.TestCase):
    def test_candidate_order_and_no_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            suffix = Path('SKSE/Plugins/StorageUtilData/HoldMusic')
            expected = [root / 'mods/Performances' / suffix, root / 'overwrite' / suffix,
                        root / 'mods/Profile Data' / suffix]
            self.assertEqual(storage_dirs(str(root), 'Performances', 'Profile Data'), expected)
            self.assertEqual(storage_dirs(root, 'Performances'), expected[:2])
            self.assertEqual(locate('receipts.json', expected), [])
            self.assertIsNone(resolve_receipts(root, 'Performances', 'Profile Data'))
            self.assertIsNone(resolve_trace(root, 'Performances'))
            self.assertEqual(list(root.iterdir()), [])

    def test_newest_file_metadata_ties_and_directory_exclusion(self):
        with tempfile.TemporaryDirectory() as temp:
            dirs = storage_dirs(temp, 'Performances', 'Profile Data')
            for i, directory in enumerate(dirs):
                directory.mkdir(parents=True)
                path = directory / 'receipts.json'
                path.write_bytes(b'x' * (i + 1))
                os.utime(path, (100 + i, 100 + i))
            found = locate('receipts.json', dirs)
            self.assertEqual(found, [Located(dirs[i] / 'receipts.json', 100 + i, i + 1)
                                     for i in (2, 1, 0)])
            self.assertEqual(resolve_receipts(temp, 'Performances', 'Profile Data'), found[0].path)
            self.assertEqual(resolve_receipts(temp, 'Performances'), dirs[1] / 'receipts.json')
            (dirs[0] / 'trace.json').mkdir()
            (dirs[1] / 'trace.json').write_text('{}')
            self.assertEqual(resolve_trace(temp, 'Performances'), dirs[1] / 'trace.json')
            for directory in dirs:
                os.utime(directory / 'receipts.json', (100, 100))
            self.assertEqual([item.path.parent for item in locate('receipts.json', dirs)], dirs)


if __name__ == '__main__':
    unittest.main()
