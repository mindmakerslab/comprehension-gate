"""Cupones y reglas de acumulación.

Reglas:
  1. Todos los descuentos se calculan sobre importes SIN IVA. El IVA se calcula
     después sobre la base ya descontada (así lo exige la factura).
  2. Los cupones porcentuales se combinan de forma multiplicativa y el descuento
     porcentual total de una línea nunca supera TOPE_PORCENTAJE.
  3. Los cupones de importe fijo se aplican después de los porcentuales y se
     reparten entre las líneas en proporción a su importe.
  4. Un cupón no acumulable no se combina con ningún otro: si aparece, gana el
     que más descuenta y se descartan los demás con un aviso.
  5. El mínimo de compra se mira sobre el subtotal sin IVA y antes de descuentos.
"""
from dataclasses import dataclass, field
from decimal import Decimal

from .dinero import CERO, euros, prorratear, redondear
from .modelos import Carrito

TOPE_PORCENTAJE = Decimal("0.30")


@dataclass(frozen=True)
class Cupon:
    codigo: str
    tipo: str  # "porcentaje", "fijo", "envio_gratis" o "sobre_total"
    valor: Decimal = CERO
    minimo: Decimal = CERO
    acumulable: bool = True
    categoria: str | None = None  # solo aplica a esa categoría


CATALOGO = {
    c.codigo: c for c in [
        Cupon("BIENVENIDA10", "porcentaje", euros("0.10")),
        Cupon("VIP20", "porcentaje", euros("0.20"), minimo=euros("40")),
        Cupon("LIBROS15", "porcentaje", euros("0.15"), categoria="libros"),
        Cupon("MENOS5", "fijo", euros("5"), minimo=euros("30")),
        Cupon("ENVIOGRATIS", "envio_gratis"),
        Cupon("FLASH40", "porcentaje", euros("0.40"), acumulable=False),
        # Black Friday: se anuncia como "15 % sobre el precio final", así que va sobre el total con IVA.
        Cupon("BF15", "sobre_total", euros("0.15")),
    ]
}


@dataclass
class ResultadoDescuentos:
    por_linea: list[Decimal]
    aplicados: list[str]
    envio_gratis: bool = False
    sobre_total: Decimal = CERO
    avisos: list[str] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return sum(self.por_linea, CERO)


def buscar(codigos: list[str]) -> tuple[list[Cupon], list[str]]:
    """Normaliza códigos, quita duplicados conservando el orden y descarta los desconocidos."""
    vistos, cupones, avisos = set(), [], []
    for codigo in codigos or []:
        c = codigo.strip().upper()
        if not c or c in vistos:
            continue
        vistos.add(c)
        if c in CATALOGO:
            cupones.append(CATALOGO[c])
        else:
            avisos.append(f"Cupón {c} no existe")
    return cupones, avisos


def _porcentajes(carrito: Carrito, cupones: list[Cupon]) -> list[Decimal]:
    """Fracción de descuento porcentual de cada línea, ya con el tope."""
    fracciones = []
    for linea in carrito.lineas:
        restante = Decimal("1")
        for c in cupones:
            if c.tipo == "porcentaje" and (c.categoria is None or c.categoria == linea.producto.categoria):
                restante *= 1 - c.valor
        fracciones.append(min(1 - restante, TOPE_PORCENTAJE))
    return fracciones


def _simular(carrito: Carrito, cupones: list[Cupon]) -> list[Decimal]:
    fracciones = _porcentajes(carrito, cupones)
    por_linea = [redondear(l.importe * f) for l, f in zip(carrito.lineas, fracciones)]
    restantes = [l.importe - d for l, d in zip(carrito.lineas, por_linea)]
    fijo = sum((c.valor for c in cupones if c.tipo == "fijo"), CERO)
    if fijo:
        fijo = min(fijo, sum(restantes, CERO))  # nunca por debajo de cero
        for i, parte in enumerate(prorratear(fijo, restantes)):
            por_linea[i] += parte
    return por_linea


def aplicar(carrito: Carrito, codigos: list[str]) -> ResultadoDescuentos:
    cupones, avisos = buscar(codigos)
    subtotal = carrito.subtotal

    validos = []
    for c in cupones:
        if subtotal < c.minimo:
            avisos.append(f"Cupón {c.codigo} requiere una compra mínima de {c.minimo} euros")
        else:
            validos.append(c)

    exclusivos = [c for c in validos if not c.acumulable]
    if exclusivos:
        # Gana el cupón (o la combinación de acumulables) que más descuenta.
        candidatos = [[c] for c in exclusivos] + [[c for c in validos if c.acumulable]]
        mejor = max(candidatos, key=lambda cs: sum(_simular(carrito, cs), CERO))
        for c in validos:
            if c not in mejor:
                avisos.append(f"Cupón {c.codigo} no se acumula con {', '.join(x.codigo for x in mejor)}")
        validos = mejor

    return ResultadoDescuentos(
        por_linea=_simular(carrito, validos),
        aplicados=[c.codigo for c in validos],
        envio_gratis=any(c.tipo == "envio_gratis" for c in validos),
        sobre_total=sum((c.valor for c in validos if c.tipo == "sobre_total"), CERO),
        avisos=avisos,
    )
