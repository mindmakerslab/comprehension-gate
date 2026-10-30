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
    assert p.envio == 0  # 74,83 de base supera los 50 de envío gratis
    assert p.iva == D("9.97")
    assert p.total == D("84.80")
    assert p.total == p.base_imponible + p.iva


def test_iva_sobre_base_descontada(libro, madrid):
    p = calcular_pedido(Carrito().anadir(libro), madrid, ["LIBROS15"])
    linea = p.lineas[0]
    assert linea.base == D("20.40")
    assert linea.iva == D("0.82")  # 4 % de 20,40


def test_envio_lleva_iva(cafe, madrid):
    p = calcular_pedido(Carrito().anadir(cafe), madrid)
    # 3,95 + 21 % = 4,78
    assert p.envio == D("4.78")


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
