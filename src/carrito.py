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


DESCUENTO_MAXIMO = 0.25


def descuento_combinado(cupones):
    """Combina cupones de forma multiplicativa, sin repetir, con un tope global."""
    restante = 1.0
    for c in {c.upper() for c in cupones or []}:
        restante *= 1 - CUPONES.get(c, 0)
    return min(1 - restante, DESCUENTO_MAXIMO)


def aplicar_cupones(importe, cupones=None):
    return importe * (1 - descuento_combinado(cupones))


def total(lineas, cupones=None, envio=4.95, envio_gratis_desde=50):
    if isinstance(cupones, str):
        cupones = [cupones]
    bruto = subtotal(lineas)
    importe = aplicar_cupones(bruto, cupones)
    # El envío gratis se decide sobre el subtotal antes de descuentos.
    if bruto < envio_gratis_desde:
        importe += envio
    return round(importe, 2)
