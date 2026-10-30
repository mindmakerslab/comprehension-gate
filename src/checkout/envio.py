"""Gastos de envío por zona y peso."""
from dataclasses import dataclass
from decimal import Decimal

from .dinero import CERO, euros
from .modelos import Direccion


@dataclass(frozen=True)
class Tarifa:
    # (peso máximo en kg, precio sin IVA). El último tramo se repite por cada kg extra.
    tramos: tuple[tuple[Decimal, Decimal], ...]
    kg_extra: Decimal
    gratis_desde: Decimal | None  # sobre la base tras descuentos, sin IVA


def _t(*tramos, extra, gratis):
    return Tarifa(tuple((euros(p), euros(c)) for p, c in tramos), euros(extra),
                  euros(gratis) if gratis is not None else None)


TARIFAS = {
    "peninsula": _t(("2", "3.95"), ("5", "5.95"), ("10", "8.95"), extra="0.60", gratis="50"),
    "baleares": _t(("2", "6.95"), ("5", "9.95"), ("10", "14.95"), extra="1.20", gratis="90"),
    "canarias": _t(("2", "12.95"), ("5", "19.95"), ("10", "29.95"), extra="2.50", gratis=None),
    "ue": _t(("2", "9.95"), ("5", "14.95"), ("10", "22.95"), extra="1.80", gratis="120"),
}


def zona(direccion: Direccion) -> str:
    if direccion.pais == "ES":
        prefijo = direccion.codigo_postal[:2]
        if prefijo == "07":
            return "baleares"
        if prefijo in ("35", "38"):
            return "canarias"
        if prefijo in ("51", "52"):
            return "canarias"  # Ceuta y Melilla comparten operador con Canarias
        return "peninsula"
    if direccion.pais in ("PT", "FR", "DE", "IT"):
        return "ue"
    raise ValueError(f"Sin envío a {direccion.pais}")


def coste(direccion: Direccion, peso_kg: Decimal, base_tras_descuentos: Decimal) -> Decimal:
    """Coste de envío sin IVA."""
    tarifa = TARIFAS[zona(direccion)]
    if tarifa.gratis_desde is not None and base_tras_descuentos >= tarifa.gratis_desde:
        return CERO
    for maximo, precio in tarifa.tramos:
        if peso_kg <= maximo:
            return precio
    maximo, precio = tarifa.tramos[-1]
    exceso = peso_kg - maximo
    kilos_extra = int(exceso) + (1 if exceso % 1 else 0)
    return precio + tarifa.kg_extra * kilos_extra
