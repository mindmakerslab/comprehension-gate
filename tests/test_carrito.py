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

    def test_cupones_acumulables_con_tope(self):
        # 10% y 20% darían 28%, pero el tope es 25%
        self.assertEqual(total([Linea("cafetera", 100.0)], ["BIENVENIDA10", "VIP20"]), 75.0)

    def test_cupon_repetido_cuenta_una_vez(self):
        self.assertEqual(total([Linea("cafetera", 100.0)], ["vip20", "VIP20"]), 80.0)

    def test_envio_gratis_antes_de_descuento(self):
        # 55 de subtotal, 44 tras VIP20: sigue sin pagar envío
        self.assertEqual(total([Linea("tostadora", 55.0)], "VIP20"), 44.0)


if __name__ == "__main__":
    unittest.main()
