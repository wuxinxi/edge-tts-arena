import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.app.core.hardware import get_hardware_info


class HardwareMemoryTests(unittest.TestCase):
    def hardware_info(self, total_gb, available_gb, platform_used_gb, percent):
        gib = 1024 ** 3
        snapshot = SimpleNamespace(
            total=int(total_gb * gib),
            available=int(available_gb * gib),
            used=int(platform_used_gb * gib),
            percent=percent,
        )
        with patch('backend.app.core.hardware.psutil.virtual_memory', return_value=snapshot), \
                patch('backend.app.core.hardware.get_apple_chip_name', return_value='Apple M1 Pro'), \
                patch('backend.app.core.hardware.check_mps_status', return_value={}):
            return get_hardware_info()

    def test_macos_memory_number_and_progress_share_available_memory_basis(self):
        info = self.hardware_info(16, 2.4, 5.87, 85.0)
        self.assertEqual(info['used_memory_gb'], 13.6)
        self.assertAlmostEqual(
            info['memory_percent'],
            info['used_memory_gb'] / info['total_memory_gb'] * 100,
            delta=0.1,
        )
        self.assertAlmostEqual(
            info['used_memory_gb'] + info['available_memory_gb'],
            info['total_memory_gb'],
            delta=0.01,
        )

    def test_available_memory_and_no_total_do_not_produce_invalid_progress(self):
        for total, available, expected_used, expected_percent in [
            (16, 16, 0, 0),
            (16, 0, 16, 100),
            (0, 0, 0, 0),
        ]:
            with self.subTest(total=total, available=available):
                info = self.hardware_info(total, available, 0, 0)
                self.assertEqual(info['used_memory_gb'], expected_used)
                self.assertEqual(info['memory_percent'], expected_percent)


if __name__ == '__main__':
    unittest.main()
