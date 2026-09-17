"""Synthetic layouts make taskbar tests independent of the current displays."""
import unittest
from desktop_layout import floor_at, FloorTransition


def monitor(left=0, right=1920, bottom=1080, taskbar=0, top=0, primary=False):
    return dict(left=left, right=right, top=top, bottom=bottom-taskbar,
                screen=(left, top, right, bottom), primary=primary)


class DesktopLayoutTests(unittest.TestCase):
    def test_taskbar_only_on_primary(self):
        displays = [monitor(taskbar=40), monitor(1920, 3840)]
        self.assertEqual(floor_at(displays, 500, 144, 1000), 944)
        self.assertEqual(floor_at(displays, 2500, 144, 1000), 984)
        # Remain on the higher edge until the whole pet clears it.
        self.assertEqual(floor_at(displays, 1919, 144, 1000), 944)
        self.assertEqual(floor_at(displays, 1920, 144, 1000), 984)

    def test_jump_before_leading_edge_hits_taskbar(self):
        displays = [monitor(), monitor(1920, 3840, taskbar=40)]
        self.assertEqual(floor_at(displays, 1776, 144, 1000), 984)
        self.assertEqual(floor_at(displays, 1777, 144, 1000), 944)

    def test_taskbars_on_all_screens_and_none(self):
        for bar, expected in ((40, 944), (0, 984)):
            displays = [monitor(taskbar=bar), monitor(1920, 3840, taskbar=bar)]
            for x in (100, 1800, 2500):
                self.assertEqual(floor_at(displays, x, 144, 1000), expected)

    def test_negative_coordinates_and_different_heights(self):
        displays = [monitor(-1680, 0, bottom=1079, top=29), monitor(taskbar=40),
                    monitor(1920, 3840, bottom=1067, top=-13)]
        self.assertEqual(floor_at(displays, -500, 144, 1000), 983)
        self.assertEqual(floor_at(displays, -100, 144, 1000), 944)
        self.assertEqual(floor_at(displays, 2500, 144, 1000), 971)

    def test_stacked_monitors_use_current_row(self):
        displays = [monitor(top=-1080, bottom=0, taskbar=40), monitor(taskbar=40)]
        self.assertEqual(floor_at(displays, 500, 144, -100), -136)
        self.assertEqual(floor_at(displays, 500, 144, 1000), 944)

    def test_upward_hop_clears_surface_before_crossing(self):
        transition = FloorTransition(1776, 984, 1780, 944)
        for _ in range(50):
            x, y, done = transition.advance(0.02)
            if x > 1776:
                self.assertLessEqual(y, 944)
            if done:
                break
        self.assertTrue(done)
        self.assertEqual((x, y), (1780, 944))

    def test_drop_accelerates_and_lands_exactly(self):
        transition = FloorTransition(1918, 944, 1921, 984)
        samples = [transition.advance(0.05) for _ in range(20)]
        self.assertEqual(samples[-1], (1921, 984, True))
        self.assertTrue(all(a[1] <= b[1] <= 984 for a, b in zip(samples, samples[1:])))


if __name__ == "__main__":
    unittest.main()
