"""Tipos de IVA por región fiscal y categoría de producto."""
from decimal import Decimal

from .dinero import redondear

D = Decimal

TIPOS = {
    "ES": {"general": D("0.21"), "alimentacion": D("0.10"), "libros": D("0.04")},
    "PT": {"general": D("0.23"), "alimentacion": D("0.13"), "libros": D("0.06")},
    "FR": {"general": D("0.20"), "alimentacion": D("0.055"), "libros": D("0.055")},
    "DE": {"general": D("0.19"), "alimentacion": D("0.07"), "libros": D("0.07")},
    "IT": {"general": D("0.22"), "alimentacion": D("0.10"), "libros": D("0.04")},
    # Canarias, Ceuta y Melilla: fuera del territorio IVA. El IGIC/IPSI lo liquida el cliente
    # en destino, así que aquí se factura sin impuesto.
    "ES-CN": {"general": D("0"), "alimentacion": D("0"), "libros": D("0")},
    "ES-CE-ML": {"general": D("0"), "alimentacion": D("0"), "libros": D("0")},
}

# El envío sigue el tipo general del destino.
CATEGORIA_ENVIO = "general"


class RegionNoSoportada(ValueError):
    pass


def tipo(region: str, categoria: str) -> Decimal:
    try:
        return TIPOS[region][categoria]
    except KeyError:
        raise RegionNoSoportada(f"No vendemos a {region} (categoría {categoria})") from None


def cuota(base: Decimal, region: str, categoria: str) -> Decimal:
    """IVA de una base, redondeado a céntimos por línea."""
    return redondear(base * tipo(region, categoria))
