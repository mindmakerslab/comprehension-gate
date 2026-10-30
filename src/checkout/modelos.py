"""Modelos del dominio."""
from dataclasses import dataclass, field
from decimal import Decimal

from .dinero import CERO, euros

CATEGORIAS = ("general", "alimentacion", "libros")


@dataclass(frozen=True)
class Producto:
    sku: str
    nombre: str
    precio: Decimal  # sin IVA
    peso_kg: Decimal
    categoria: str = "general"

    def __post_init__(self):
        if self.categoria not in CATEGORIAS:
            raise ValueError(f"Categoría desconocida: {self.categoria}")
        if self.precio < 0:
            raise ValueError("El precio no puede ser negativo")


@dataclass
class Linea:
    producto: Producto
    cantidad: int = 1

    def __post_init__(self):
        if self.cantidad <= 0:
            raise ValueError("La cantidad debe ser positiva")

    @property
    def importe(self) -> Decimal:
        return self.producto.precio * self.cantidad

    @property
    def peso(self) -> Decimal:
        return self.producto.peso_kg * self.cantidad


@dataclass
class Carrito:
    lineas: list[Linea] = field(default_factory=list)

    def anadir(self, producto: Producto, cantidad: int = 1) -> "Carrito":
        for linea in self.lineas:
            if linea.producto.sku == producto.sku:
                linea.cantidad += cantidad
                return self
        self.lineas.append(Linea(producto, cantidad))
        return self

    @property
    def subtotal(self) -> Decimal:
        return sum((l.importe for l in self.lineas), CERO)

    @property
    def peso(self) -> Decimal:
        return sum((l.peso for l in self.lineas), CERO)

    def vacio(self) -> bool:
        return not self.lineas


@dataclass(frozen=True)
class Direccion:
    pais: str  # ISO 3166-1 alfa-2
    codigo_postal: str

    @property
    def region_fiscal(self) -> str:
        """Canarias, Ceuta y Melilla no aplican IVA peninsular."""
        if self.pais != "ES":
            return self.pais
        prefijo = self.codigo_postal[:2]
        if prefijo in ("35", "38"):
            return "ES-CN"
        if prefijo in ("51", "52"):
            return "ES-CE-ML"
        return "ES"


@dataclass
class LineaFactura:
    sku: str
    categoria: str
    bruto: Decimal
    descuento: Decimal
    base: Decimal
    tipo_iva: Decimal
    iva: Decimal


@dataclass
class Pedido:
    lineas: list[LineaFactura]
    cupones_aplicados: list[str]
    subtotal: Decimal
    descuentos: Decimal
    base_imponible: Decimal
    iva: Decimal
    envio: Decimal
    total: Decimal
    avisos: list[str] = field(default_factory=list)

    def como_dict(self) -> dict:
        def s(d):
            return str(d)
        return {
            "lineas": [
                {"sku": l.sku, "categoria": l.categoria, "bruto": s(l.bruto), "descuento": s(l.descuento),
                 "base": s(l.base), "tipo_iva": s(l.tipo_iva), "iva": s(l.iva)}
                for l in self.lineas
            ],
            "cupones_aplicados": self.cupones_aplicados,
            "subtotal": s(self.subtotal),
            "descuentos": s(self.descuentos),
            "base_imponible": s(self.base_imponible),
            "iva": s(self.iva),
            "envio": s(self.envio),
            "total": s(self.total),
            "avisos": self.avisos,
        }


def producto(sku, nombre, precio, peso_kg, categoria="general") -> Producto:
    """Atajo para construir productos con importes en str."""
    return Producto(sku, nombre, euros(precio), euros(peso_kg), categoria)
