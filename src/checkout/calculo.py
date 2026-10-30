"""Orquesta el cálculo de un pedido: descuentos, IVA y envío."""
from decimal import Decimal

from . import descuentos, envio, iva
from .dinero import CERO, redondear
from .modelos import Carrito, Direccion, LineaFactura, Pedido


class CarritoVacio(ValueError):
    pass


def calcular_pedido(carrito: Carrito, direccion: Direccion, cupones: list[str] | None = None) -> Pedido:
    if carrito.vacio():
        raise CarritoVacio("No se puede calcular un pedido sin líneas")

    region = direccion.region_fiscal
    desc = descuentos.aplicar(carrito, cupones or [])

    lineas = []
    for linea, descuento in zip(carrito.lineas, desc.por_linea):
        base = linea.importe - descuento
        tipo = iva.tipo(region, linea.producto.categoria)
        lineas.append(LineaFactura(
            sku=linea.producto.sku,
            categoria=linea.producto.categoria,
            bruto=redondear(linea.importe),
            descuento=descuento,
            base=redondear(base),
            tipo_iva=tipo,
            iva=iva.cuota(base, region, linea.producto.categoria),
        ))

    base_productos = sum((l.base for l in lineas), CERO)
    coste_envio = CERO if desc.envio_gratis else envio.coste(direccion, carrito.peso, carrito.subtotal)
    iva_envio = iva.cuota(coste_envio, region, iva.CATEGORIA_ENVIO)

    base_imponible = base_productos + coste_envio
    cuota_total = sum((l.iva for l in lineas), CERO) + iva_envio
    return Pedido(
        lineas=lineas,
        cupones_aplicados=desc.aplicados,
        subtotal=redondear(carrito.subtotal),
        descuentos=desc.total,
        base_imponible=base_imponible,
        iva=cuota_total,
        envio=redondear(coste_envio + iva_envio),
        total=base_imponible + cuota_total,
        avisos=desc.avisos,
    )


def resumen(pedido: Pedido) -> str:
    filas = [f"{l.sku:<10} {l.bruto:>9} -{l.descuento:>7} IVA {str((l.tipo_iva * 100).normalize()):>4}% {l.iva:>7}" for l in pedido.lineas]
    filas += [
        f"Subtotal        {pedido.subtotal:>9}",
        f"Descuentos      {-pedido.descuentos:>9}  {' '.join(pedido.cupones_aplicados)}",
        f"Envío (con IVA) {pedido.envio:>9}",
        f"IVA             {pedido.iva:>9}",
        f"Total           {pedido.total:>9}",
    ]
    filas += [f"Aviso: {a}" for a in pedido.avisos]
    return "\n".join(filas)


def total_decimal(pedido: Pedido) -> Decimal:
    return pedido.total
