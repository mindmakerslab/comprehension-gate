from decimal import Decimal as D

import pytest

from checkout import envio, iva
from checkout.modelos import Direccion


@pytest.mark.parametrize("cp,zona", [("28004", "peninsula"), ("07001", "baleares"), ("35001", "canarias"), ("38001", "canarias")])
def test_zonas(cp, zona):
    assert envio.zona(Direccion("ES", cp)) == zona


def test_tramos_de_peso(madrid):
    assert envio.coste(madrid, D("1.5"), D("10")) == D("3.95")
    assert envio.coste(madrid, D("7"), D("10")) == D("8.95")
    # 12,3 kg: 2,3 kg por encima de 10 cuentan como 3 kg extra
    assert envio.coste(madrid, D("12.3"), D("10")) == D("8.95") + D("1.80")


def test_envio_gratis_por_umbral(madrid):
    assert envio.coste(madrid, D("3"), D("50")) == 0
    assert envio.coste(madrid, D("3"), D("49.99")) == D("5.95")


def test_canarias_nunca_gratis():
    assert envio.coste(Direccion("ES", "35001"), D("1"), D("1000")) == D("12.95")


def test_iva_por_pais():
    assert iva.tipo("ES", "libros") == D("0.04")
    assert iva.tipo("PT", "general") == D("0.23")
    assert iva.cuota(D("10"), "FR", "alimentacion") == D("0.55")


def test_region_fiscal_canarias():
    assert Direccion("ES", "38001").region_fiscal == "ES-CN"
    assert iva.tipo("ES-CN", "general") == 0


def test_pais_no_soportado():
    with pytest.raises(iva.RegionNoSoportada):
        iva.tipo("US", "general")
