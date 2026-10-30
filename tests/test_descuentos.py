from decimal import Decimal as D

from checkout import descuentos
from checkout.modelos import Carrito, producto


def test_cupon_desconocido_avisa(carrito_mixto):
    r = descuentos.aplicar(carrito_mixto, ["NOEXISTE"])
    assert r.total == 0
    assert "NOEXISTE" in r.avisos[0]


def test_duplicados_y_mayusculas(carrito_mixto):
    r = descuentos.aplicar(carrito_mixto, ["bienvenida10", "BIENVENIDA10 "])
    assert r.aplicados == ["BIENVENIDA10"]


def test_porcentajes_multiplicativos(libro):
    c = Carrito().anadir(libro)  # 24 euros, libros
    r = descuentos.aplicar(c, ["BIENVENIDA10", "LIBROS15"])
    # 1 - 0,9 x 0,85 = 23,5 %
    assert r.total == D("5.64")


def test_tope_porcentual():
    caro = producto("TV", "Tele", "500", "8")
    r = descuentos.aplicar(Carrito().anadir(caro), ["BIENVENIDA10", "VIP20"])
    # 1 - 0,9 x 0,8 = 28 %, por debajo del tope
    assert r.total == D("140.00")
    assert descuentos.TOPE_PORCENTAJE == D("0.30")


def test_minimo_de_compra(cafe):
    r = descuentos.aplicar(Carrito().anadir(cafe), ["VIP20"])  # 12,40 < 40
    assert r.total == 0
    assert "mínima" in r.avisos[0]


def test_fijo_despues_de_porcentajes(carrito_mixto):
    r = descuentos.aplicar(carrito_mixto, ["BIENVENIDA10", "MENOS5"])
    assert r.total == D("8.87") + D("5.00")
    assert sum(r.por_linea) == r.total


def test_fijo_no_deja_negativo():
    barato = producto("PEG", "Pegatina", "31", "0.01")
    r = descuentos.aplicar(Carrito().anadir(barato), ["MENOS5"])
    assert r.total == D("5")


def test_no_acumulable_gana_el_mejor(carrito_mixto):
    r = descuentos.aplicar(carrito_mixto, ["BIENVENIDA10", "FLASH40"])
    assert r.aplicados == ["FLASH40"]
    assert any("no se acumula" in a for a in r.avisos)


def test_envio_gratis(carrito_mixto):
    assert descuentos.aplicar(carrito_mixto, ["ENVIOGRATIS"]).envio_gratis


def test_comida10_solo_alimentacion(cafe, libro):
    c = Carrito().anadir(cafe, 2).anadir(libro)  # 2 cafés (24.80) + 1 libro (24.00)
    r = descuentos.aplicar(c, ["COMIDA10"])
    # Descuento 10% solo sobre café: 24.80 * 0.10 = 2.48
    assert r.total == D("2.48")
    assert r.aplicados == ["COMIDA10"]


def test_comida10_acumulable_con_bienvenida(cafe):
    c = Carrito().anadir(cafe, 2)  # 24.80 euros, alimentacion
    r = descuentos.aplicar(c, ["BIENVENIDA10", "COMIDA10"])
    # 1 - 0.9 x 0.9 = 19%
    # 24.80 * 0.19 = 4.712 -> 4.71
    assert r.total == D("4.71")
    assert set(r.aplicados) == {"BIENVENIDA10", "COMIDA10"}
