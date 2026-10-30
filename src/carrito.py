"""Cálculo del total de un carrito con cupones. Código de ejemplo para la demo."""
from dataclasses import dataclass


@dataclass
class Linea:
    producto: str
    precio: float  # euros, IVA incluido
    cantidad: int = 1


CUPONES = {
    "BIENVENIDA10": 0.10,
    "VIP20": 0.20,
}


def subtotal(lineas):
    return sum(l.precio * l.cantidad for l in lineas)


def aplicar_cupon(importe, cupon=None):
    """Aplica un cupón porcentual. Un cupón desconocido no descuenta nada."""
    if not cupon:
        return importe
    return importe * (1 - CUPONES.get(cupon.upper(), 0))


def total(lineas, cupon=None, envio=4.95, envio_gratis_desde=50):
    importe = aplicar_cupon(subtotal(lineas), cupon)
    if importe < envio_gratis_desde:
        importe += envio
    return round(importe, 2)
