import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from carrito import Linea, total  # noqa: E402


class TestTotal(unittest.TestCase):
    def test_sin_cupon_con_envio(self):
        self.assertEqual(total([Linea("taza", 12.0, 2)]), 28.95)

    def test_envio_gratis(self):
        self.assertEqual(total([Linea("cafetera", 60.0)]), 60.0)

    def test_cupon(self):
        self.assertEqual(total([Linea("cafetera", 100.0)], "vip20"), 80.0)

    def test_cupon_desconocido(self):
        self.assertEqual(total([Linea("cafetera", 100.0)], "NOEXISTE"), 100.0)


if __name__ == "__main__":
    unittest.main()
