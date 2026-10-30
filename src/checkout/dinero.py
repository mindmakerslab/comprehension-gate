"""Utilidades de dinero. Todo importe es Decimal; nunca float."""
from decimal import ROUND_HALF_UP, Decimal

CENTIMO = Decimal("0.01")
CERO = Decimal("0")


def euros(valor) -> Decimal:
    """Convierte a Decimal sin pasar por float (acepta str, int o Decimal)."""
    if isinstance(valor, float):
        raise TypeError("Usa str o Decimal para importes, no float")
    return Decimal(str(valor))


def redondear(importe: Decimal) -> Decimal:
    """Redondeo comercial a céntimos: 0,005 sube."""
    return importe.quantize(CENTIMO, rounding=ROUND_HALF_UP)


def prorratear(total: Decimal, pesos: list[Decimal]) -> list[Decimal]:
    """Reparte `total` en proporción a `pesos`, en céntimos exactos.

    La suma de las partes es siempre igual a `total`: el céntimo que sobra por
    redondeo va a la parte con mayor peso.
    """
    suma = sum(pesos, CERO)
    if suma == 0:
        return [CERO for _ in pesos]
    partes = [redondear(total * p / suma) for p in pesos]
    diferencia = redondear(total) - sum(partes, CERO)
    if diferencia and partes:
        i = max(range(len(pesos)), key=lambda k: pesos[k])
        partes[i] += diferencia
    return partes
