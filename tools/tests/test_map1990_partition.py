import sys
import unittest
from pathlib import Path

import numpy as np
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from map1990.common import MIN_PROVINCE_PX  # noqa: E402

FOUR = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], bool)


def blob(h=60, w=80):
    yy, xx = np.mgrid[:h, :w]
    return ((yy - 30) ** 2 / 28 ** 2 + (xx - 40) ** 2 / 38 ** 2) < 1


class PartitionTest(unittest.TestCase):
    def test_counts_and_cover(self):
        from map1990.partition import partition
        m = blob()
        lab, seeds = partition(m, np.zeros(m.shape, np.uint8), [(30, 40), (20, 20)], 12, seed=1)
        self.assertTrue(((lab > 0) == m).all())
        self.assertEqual(lab.max(), 12)
        self.assertEqual(lab[30, 40], 1)
        self.assertEqual(lab[20, 20], 2)
        self.assertEqual(seeds[0], (30, 40))

    def test_connected_and_big_enough(self):
        from map1990.partition import partition
        m = blob()
        lab, _ = partition(m, np.zeros(m.shape, np.uint8), [], 20, seed=2)
        for k in range(1, lab.max() + 1):
            self.assertGreaterEqual((lab == k).sum(), MIN_PROVINCE_PX)
            self.assertEqual(ndimage.label(lab == k, structure=FOUR)[1], 1)

    def test_islands_get_labels(self):
        from map1990.partition import partition
        m = blob()
        m[0:3, 0:3] = True            # a 9 px island
        m[55:60, 0:6] = True          # a 30 px island
        lab, _ = partition(m, np.zeros(m.shape, np.uint8), [], 6, seed=3)
        self.assertTrue(((lab > 0) == m).all())
        self.assertGreaterEqual((lab == lab[57, 2]).sum(), 30)

    def test_deterministic(self):
        from map1990.partition import partition
        m = blob()
        a, _ = partition(m, np.zeros(m.shape, np.uint8), [(30, 40)], 9, seed=5)
        b, _ = partition(m, np.zeros(m.shape, np.uint8), [(30, 40)], 9, seed=5)
        self.assertTrue((a == b).all())

    def test_tiny_mask_is_one_province(self):
        from map1990.partition import partition
        m = np.zeros((10, 10), bool)
        m[4:7, 4:7] = True
        lab, _ = partition(m, np.zeros(m.shape, np.uint8), [], 3, seed=1)
        self.assertEqual(lab.max(), 1)

    def test_borders_are_not_straight(self):
        # a square split in two by noise-free Voronoi would give a straight border; ours wanders
        from map1990.partition import partition
        m = np.ones((40, 40), bool)
        lab, _ = partition(m, np.zeros(m.shape, np.uint8), [(20, 5), (20, 34)], 2, seed=4)
        cols = [np.nonzero(lab[r] == 2)[0].min() for r in range(40)]
        self.assertGreater(len(set(cols)), 3)


if __name__ == "__main__":
    unittest.main()
