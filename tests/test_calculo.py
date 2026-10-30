import json
from decimal import Decimal as D
from pathlib import Path

import pytest

from checkout import calcular_pedido
from checkout.__main__ import main
from checkout.calculo import CarritoVacio
from checkout.modelos import Carrito, Direccion


def test_pedido_completo(carrito_mixto, madrid):
    p = calcular_pedido(carrito_mixto, madrid, ["BIENVENIDA10", "MENOS5"])
    assert p.subtotal == D("88.70")
    assert p.descuentos == D("13.87")
    assert p.envio == 0  # 88,70 de subtotal supera los 50 de envío gratis
    assert p.iva == D("9.97")
    assert p.total == D("84.80")
    assert p.total == p.base_imponible + p.iva


def test_iva_sobre_base_descontada(libro, madrid):
    p = calcular_pedido(Carrito().anadir(libro), madrid, ["LIBROS15"])
    linea = p.lineas[0]
    assert linea.base == D("20.40")
    assert linea.iva == D("0.82")  # 4 % de 20,40


def test_envio_lleva_iva_de_lo_que_transporta(cafe, madrid):
    p = calcular_pedido(Carrito().anadir(cafe), madrid)
    # Solo alimentación: 3,95 + 10 % = 4,35
    assert p.envio == D("4.35")


def test_envio_iva_prorrateado(cafe):
    from checkout.modelos import producto
    taza = producto("TAZ-01", "Taza", "12.40", "0.4")
    p = calcular_pedido(Carrito().anadir(cafe).anadir(taza), Direccion("ES", "28004"))
    # 3,95 a medias: 1,97 al 10 % (0,20) y 1,98 al 21 % (0,42)
    assert p.envio == D("3.95") + D("0.62")


def test_canarias_sin_iva(molinillo):
    p = calcular_pedido(Carrito().anadir(molinillo), Direccion("ES", "35001"))
    assert p.iva == 0
    assert p.total == D("39.90") + D("12.95")


def test_carrito_vacio(madrid):
    with pytest.raises(CarritoVacio):
        calcular_pedido(Carrito(), madrid)


def test_cli_json(capsys):
    ejemplo = Path(__file__).resolve().parent.parent / "ejemplos" / "pedido.json"
    assert main([str(ejemplo), "--json"]) == 0
    salida = json.loads(capsys.readouterr().out)
    assert salida["total"] == "84.80"


def test_umbral_envio_antes_de_cupones(madrid):
    from checkout.modelos import producto
    c = Carrito().anadir(producto("MOL-02", "Molinillo", "52", "1.6"))
    p = calcular_pedido(c, madrid, ["MENOS5"])  # 47 de base, pero 52 de subtotal
    assert p.envio == 0
