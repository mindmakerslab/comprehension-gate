"""CLI: python -m checkout pedido.json [--json]

Formato de pedido.json:
{
  "direccion": {"pais": "ES", "codigo_postal": "28004"},
  "cupones": ["BIENVENIDA10"],
  "lineas": [{"sku": "CAF-01", "nombre": "Café", "precio": "8.50",
              "peso_kg": "0.5", "categoria": "alimentacion", "cantidad": 2}]
}
"""
import argparse
import json
import sys

from .calculo import calcular_pedido, resumen
from .modelos import Carrito, Direccion, producto


def cargar(data: dict):
    carrito = Carrito()
    for l in data["lineas"]:
        p = producto(l["sku"], l.get("nombre", l["sku"]), l["precio"], l["peso_kg"], l.get("categoria", "general"))
        carrito.anadir(p, int(l.get("cantidad", 1)))
    d = data["direccion"]
    return carrito, Direccion(d["pais"], d["codigo_postal"]), data.get("cupones", [])


def main(argv=None):
    parser = argparse.ArgumentParser(prog="checkout", description="Calcula el total de un pedido")
    parser.add_argument("fichero", help="JSON del pedido, o - para stdin")
    parser.add_argument("--json", action="store_true", help="salida en JSON")
    args = parser.parse_args(argv)
    raw = sys.stdin.read() if args.fichero == "-" else open(args.fichero, encoding="utf-8").read()
    pedido = calcular_pedido(*cargar(json.loads(raw)))
    print(json.dumps(pedido.como_dict(), ensure_ascii=False, indent=2) if args.json else resumen(pedido))
    return 0


if __name__ == "__main__":
    sys.exit(main())
