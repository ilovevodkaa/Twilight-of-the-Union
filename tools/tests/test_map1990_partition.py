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

    def test_diagonal_island_is_not_a_province(self):
        # 10 px + 2 px touching only at a corner: under 4-connectivity both are too small for a province
        from map1990.partition import partition
        m = blob()
        m[0:2, 0:5] = True
        m[2:4, 5:6] = True
        lab, _ = partition(m, np.zeros(m.shape, np.uint8), [], 6, seed=6)
        for k in range(1, lab.max() + 1):
            self.assertGreaterEqual((lab == k).sum(), MIN_PROVINCE_PX)

    def test_city_on_a_tiny_island_gets_no_province(self):
        from map1990.partition import partition
        m = blob()
        m[0:3, 0:3] = True                     # a 9 px island with a city on it
        lab, seeds = partition(m, np.zeros(m.shape, np.uint8), [(1, 1), (30, 40)], 5, seed=7)
        for k in range(1, lab.max() + 1):
            self.assertGreaterEqual((lab == k).sum(), MIN_PROVINCE_PX)
        self.assertGreater(lab[1, 1], 0)

    def test_stray_piece_goes_to_a_side_neighbour(self):
        # a 1 px piece of province 1 cut off from it; its nearest pixel of 1 is diagonal, its side neighbour is 2
        from map1990.partition import _cleanup
        out = np.zeros((10, 10), np.int32)
        out[0:5, 0:5] = 1
        out[5:10, 0:10] = 2
        out[0:5, 5:10] = 3
        out[5, 5] = 1                          # touches 1 only at the corner (4, 4)
        res = _cleanup(out.copy(), out > 0, [(2, 2), (8, 2), (2, 8)])
        for k in (1, 2, 3):
            self.assertEqual(ndimage.label(res == k, structure=FOUR)[1], 1, k)

    def test_islet_goes_whole_to_one_province(self):
        # a 3 px islet between two provinces must not be split between them
        from map1990.partition import partition
        m = np.zeros((30, 41), bool)
        m[5:25, 0:18] = True
        m[5:25, 23:41] = True
        m[0, 19:22] = True                     # the islet, as far from both halves
        lab, _ = partition(m, np.zeros(m.shape, np.uint8), [(15, 5), (15, 35)], 2, seed=8)
        self.assertEqual(len(set(lab[0, 19:22].tolist())), 1)

    def test_small_isolated_piece_does_not_stop_merging(self):
        from map1990.partition import _cleanup
        out = np.zeros((20, 40), np.int32)
        out[0:3, 0:3] = 1                      # 9 px, no neighbour: cannot merge
        out[10:20, 0:20] = 2
        out[10:20, 20:21] = 3                  # 10 px next to province 2: must merge
        out[10:20, 21:40] = 4
        res = _cleanup(out.copy(), out > 0, [(1, 1), (15, 5), (15, 20), (15, 30)])
        self.assertFalse((res == 3).any())

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
