import pytest

from checkout.modelos import Carrito, Direccion, producto


@pytest.fixture
def cafe():
    return producto("CAF-01", "Café", "12.40", "1", "alimentacion")


@pytest.fixture
def libro():
    return producto("LIB-07", "Libro", "24.00", "0.8", "libros")


@pytest.fixture
def molinillo():
    return producto("MOL-02", "Molinillo", "39.90", "1.6")


@pytest.fixture
def madrid():
    return Direccion("ES", "28004")


@pytest.fixture
def carrito_mixto(cafe, libro, molinillo):
    return Carrito().anadir(cafe, 2).anadir(libro).anadir(molinillo)
