from decimal import Decimal as D

import pytest

from checkout.dinero import euros, prorratear, redondear


def test_redondeo_comercial():
    assert redondear(D("0.005")) == D("0.01")
    assert redondear(D("2.675")) == D("2.68")


def test_euros_rechaza_float():
    with pytest.raises(TypeError):
        euros(0.1)


def test_prorrateo_suma_exacta():
    partes = prorratear(D("10.00"), [D("1"), D("1"), D("1")])
    assert sum(partes) == D("10.00")
    assert sorted(partes) == [D("3.33"), D("3.33"), D("3.34")]


def test_prorrateo_sin_pesos():
    assert prorratear(D("5"), [D("0"), D("0")]) == [D("0"), D("0")]
