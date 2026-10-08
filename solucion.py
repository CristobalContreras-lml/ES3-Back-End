"""
ES1 - Programacion Back End - INACAP
Monitoreo de Vencimiento de Insumos (semaforo FIFO)
Autor: Cristobal Contreras

Programa de consola: pide los datos de un lote de insumo, decide su estado
con la regla de decision (4 resultados), guarda el registro en datos.json
y muestra el resumen con tabulate.
"""

import json
import os
from datetime import date, datetime

from tabulate import tabulate

# ---------------------------------------------------------------
# 1. VARIABLES DE CONFIGURACION
# ---------------------------------------------------------------

CARPETA = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_DATOS = os.path.join(CARPETA, "datos.json")

# Cada categoria avisa con distinta anticipacion (dias de alerta).
# Un queso hay que avisarlo antes que una caja de empaques.
UMBRALES = {
    "Lacteos": 7,
    "Carnes": 5,
    "Salsas": 10,
    "Verduras": 3,
    "Empaques": 30,
}

FORMATO_FECHA = "%Y-%m-%d"


# ---------------------------------------------------------------
# 2. REGLA DE DECISION (se reutiliza en Django, no se copia)
# ---------------------------------------------------------------

def dias_para_vencer(fecha_texto, hoy=None):
    """Devuelve cuantos dias faltan para el vencimiento.

    Devuelve None si la fecha no se puede leer (dato invalido).
    """
    if hoy is None:
        hoy = date.today()

    try:
        fecha_vencimiento = datetime.strptime(fecha_texto.strip(), FORMATO_FECHA).date()
    except (ValueError, TypeError, AttributeError):
        return None

    diferencia = fecha_vencimiento - hoy
    return diferencia.days


def clasificar_insumo(categoria, cantidad, fecha_texto, hoy=None):
    """Aplica la regla de decision y devuelve uno de los 4 resultados.

    Depende de tres datos: la categoria, la cantidad y la fecha de vencimiento.
    """
    dias = dias_para_vencer(fecha_texto, hoy)
    categoria_normalizada = (categoria or "").strip().capitalize()
    umbral = UMBRALES.get(categoria_normalizada, 7)

    # El dato invalido va PRIMERO. Si queda al final nunca se revisa.
    if dias is None or cantidad <= 0 or categoria_normalizada not in UMBRALES:
        estado = "INVALIDO"
        color = "gris"
        motivo = ("Dato invalido: la categoria debe estar en la lista, "
                  "la cantidad debe ser mayor que 0 y la fecha va en formato AAAA-MM-DD.")

    elif dias <= 0:
        estado = "ROJO"
        color = "rojo"
        motivo = (f"RECHAZADO: el lote esta vencido o vence hoy ({dias} dias). "
                  f"No se puede usar, se registra como merma.")

    elif dias <= umbral and cantidad > 0:
        estado = "AMARILLO"
        color = "amarillo"
        motivo = (f"RECHAZADO para bodega: vence en {dias} dias (alerta de {categoria_normalizada}: "
                  f"{umbral} dias). Sacar de inmediato a produccion por FIFO.")

    else:
        estado = "VERDE"
        color = "verde"
        motivo = (f"ACEPTADO: vigente, quedan {dias} dias. "
                  f"Se guarda detras de los lotes mas antiguos (FIFO).")

    return {
        "estado": estado,
        "color": color,
        "dias": dias,
        "umbral": umbral,
        "motivo": motivo,
    }


# ---------------------------------------------------------------
# 3. GUARDAR Y LEER EL ARCHIVO JSON
# ---------------------------------------------------------------

def leer_registros():
    """Lee datos.json. Si no existe todavia, devuelve una lista vacia."""
    if not os.path.exists(ARCHIVO_DATOS):
        return []

    with open(ARCHIVO_DATOS, encoding="utf-8") as f:
        return json.load(f)


def guardar_registros(registros):
    """Escribe la lista completa de registros dentro de datos.json."""
    with open(ARCHIVO_DATOS, "w", encoding="utf-8") as f:
        json.dump(registros, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------
# 4. ENTRADA DE DATOS POR CONSOLA
# ---------------------------------------------------------------

def leer_entero(mensaje):
    """input() siempre entrega texto. Aca lo convierto a numero con int().

    Si la persona escribe letras devuelvo 0, que cae en el resultado invalido.
    """
    texto = input(mensaje).strip()

    if texto.lstrip("-").isdigit():
        return int(texto)

    return 0


def main():
    print("=" * 62)
    print(" MONITOREO DE VENCIMIENTO DE INSUMOS - Bodega cocina central")
    print("=" * 62)
    print("Categorias validas:", ", ".join(UMBRALES.keys()))
    print()

    registros = leer_registros()
    seguir = "s"

    while seguir == "s":
        # Paso 1: una variable por cada dato de entrada
        nombre = input("Nombre del insumo    : ").strip()
        categoria = input("Categoria            : ").strip().capitalize()
        lote = input("Numero de lote       : ").strip()
        cantidad = leer_entero("Cantidad (unidades)  : ")
        fecha = input("Vence (AAAA-MM-DD)   : ").strip()

        # Paso 2: se aplica la regla de decision
        resultado = clasificar_insumo(categoria, cantidad, fecha)

        # Paso 3: cada resultado muestra un mensaje distinto
        print()
        print(f"  >> {resultado['estado']}")
        print(f"  {resultado['motivo']}")
        print()

        # Paso 4: se guarda el registro en el archivo JSON
        registros.append({
            "nombre": nombre,
            "categoria": categoria,
            "lote": lote,
            "cantidad": cantidad,
            "vence": fecha,
            "estado": resultado["estado"],
            "motivo": resultado["motivo"],
            "registrado": date.today().isoformat(),
        })
        guardar_registros(registros)

        seguir = input("Registrar otro lote? (s/n): ").strip().lower()
        print()

    # Paso 5: resumen final con el paquete externo tabulate
    mostrar_tabla(registros)


def mostrar_tabla(registros):
    """Muestra el inventario ordenado por fecha de vencimiento con tabulate."""
    if not registros:
        print("Todavia no hay lotes registrados.")
        return

    ordenados = sorted(registros, key=lambda r: r["vence"])

    filas = []
    rojos = 0
    for r in ordenados:
        # Se reclasifica con la fecha de HOY en vez de usar el estado guardado:
        # un lote que era verde el dia que se registro puede ser rojo hoy.
        resultado = clasificar_insumo(r["categoria"], r["cantidad"], r["vence"])
        dias = resultado["dias"]

        if resultado["estado"] == "ROJO":
            rojos = rojos + 1

        filas.append([
            r["nombre"],
            r["categoria"],
            r["lote"],
            r["cantidad"],
            r["vence"],
            "sin fecha" if dias is None else dias,
            resultado["estado"],
        ])

    encabezados = ["Insumo", "Categoria", "Lote", "Cant.", "Vence", "Dias", "Estado"]
    print(tabulate(filas, headers=encabezados, tablefmt="grid"))
    print(f"\nLotes en rojo (merma): {rojos} de {len(registros)}")


if __name__ == "__main__":
    main()
