"""Corre las pruebas de la API contra el servidor y guarda la evidencia.

Uso (con el servidor andando en otra terminal):

    python manage.py runserver          <- terminal 1
    python pruebas\\correr_pruebas.py     <- terminal 2, dentro del venv

Las contrasenas se leen del .env (PASS_ADMIN, PASS_VIEWER). No se escriben
en ningun archivo y los tokens se guardan truncados.

El resultado queda en pruebas/salida_local.txt: cada peticion con el codigo
de estado que devolvio y si coincide con el esperado.
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

from decouple import config

BASE = "http://127.0.0.1:8000"
SALIDA = Path(__file__).resolve().parent / "salida_local.txt"

lineas = []
fallos = []


def escribir(texto=""):
    print(texto)
    lineas.append(texto)


def peticion(metodo, ruta, datos=None, cabecera=None, formulario=False):
    """Devuelve (codigo, texto_del_cuerpo). Un 4xx no es excepcion aqui."""
    cuerpo = None
    cabeceras = {}
    if datos is not None:
        if formulario:
            cuerpo = urllib.parse.urlencode(datos).encode()
            cabeceras["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            cuerpo = json.dumps(datos).encode()
            cabeceras["Content-Type"] = "application/json"
    if cabecera:
        cabeceras["Authorization"] = cabecera
    req = urllib.request.Request(BASE + ruta, data=cuerpo, method=metodo, headers=cabeceras)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def paso(numero, titulo, esperado, metodo, ruta, datos=None, cabecera=None, formulario=False):
    escribir("")
    escribir("=" * 60)
    escribir(f"{numero} - {titulo}  ·  se espera {esperado}")
    escribir("=" * 60)
    escribir(f"$ {metodo} {ruta}")
    if datos is not None and not formulario:
        escribir(f"  cuerpo: {json.dumps(datos, ensure_ascii=False)}")
    if cabecera:
        escribir(f"  Authorization: {cabecera[:14]}...  (truncado)")
    codigo, cuerpo = peticion(metodo, ruta, datos, cabecera, formulario)
    ok = "OK" if codigo == esperado else f"NO COINCIDE (esperado {esperado})"
    escribir(f"--> HTTP {codigo}   [{ok}]")
    if codigo != esperado:
        fallos.append(numero)
    return codigo, cuerpo


def mostrar(cuerpo, limite=500):
    escribir(cuerpo[:limite] + (" ..." if len(cuerpo) > limite else ""))


def main():
    clave_jefe = config("PASS_ADMIN", default="")
    clave_lector = config("PASS_VIEWER", default="")
    if not clave_jefe or not clave_lector:
        sys.exit("Falta PASS_ADMIN o PASS_VIEWER en el .env. "
                 "Corre antes: python manage.py crear_roles")

    escribir(f"Evidencia de pruebas de la API · {datetime.now():%d-%m-%Y %H:%M}")
    escribir(f"Servidor: {BASE}")
    escribir("Corrido por el estudiante en su computador.")

    try:
        peticion("GET", "/api/lotes/")
    except OSError:
        sys.exit("No se pudo conectar. Levanta el servidor con: python manage.py runserver")

    paso(1, "SIN TOKEN", 401, "GET", "/api/lotes/")

    # La contrasena real se manda, pero nunca se imprime ni se guarda.
    escribir("")
    escribir("=" * 60)
    escribir("2 - PEDIR TOKEN (jefe)  ·  se espera 200")
    escribir("=" * 60)
    escribir('$ POST /api/token/   cuerpo: username=jefe&password=***')
    codigo, cuerpo = peticion("POST", "/api/token/",
                              {"username": "jefe", "password": clave_jefe}, formulario=True)
    if codigo != 200:
        fallos.append(2)
        escribir(f"--> HTTP {codigo}   [NO COINCIDE (esperado 200)]")
        sys.exit(guardar())
    token = json.loads(cuerpo)["token"]
    auth = f"Token {token}"
    escribir("--> HTTP 200   [OK]")
    escribir(f'{{"token": "{token[:10]}..."}}   (truncado: nunca se publica entero)')

    paso(3, "LISTAR CON TOKEN (paginado)", 200, "GET", "/api/lotes/", cabecera=auth)

    en_un_ano = (date.today() + timedelta(days=365)).isoformat()
    numero = f"T-{datetime.now():%H%M%S}"
    nuevo = {"nombre": "Queso de prueba", "categoria": "Lacteos",
             "numero_lote": numero, "cantidad": 15, "vence": en_un_ano}
    codigo, cuerpo = paso(4, "CREAR", 201, "POST", "/api/lotes/", nuevo, auth)
    if codigo != 201:
        sys.exit(guardar())
    lote_id = json.loads(cuerpo)["id"]
    mostrar(cuerpo)

    malo = {"nombre": "X", "categoria": "Abarrotes", "numero_lote": "H-1",
            "cantidad": -3, "vence": en_un_ano}
    _, cuerpo = paso(5, "CREAR CON DATOS MALOS", 400, "POST", "/api/lotes/", malo, auth)
    mostrar(cuerpo)

    paso(6, "VER UNO", 200, "GET", f"/api/lotes/{lote_id}/", cabecera=auth)
    paso(7, "ID QUE NO EXISTE", 404, "GET", "/api/lotes/99999/", cabecera=auth)
    paso(8, "EDITAR UN CAMPO (PATCH)", 200, "PATCH", f"/api/lotes/{lote_id}/",
         {"cantidad": 44}, auth)
    paso(9, "FILTRAR POR ESTADO", 200, "GET", "/api/lotes/?estado=ROJO", cabecera=auth)
    _, cuerpo = paso(10, "RESUMEN DEL SEMAFORO", 200, "GET", "/api/lotes/resumen/", cabecera=auth)
    mostrar(cuerpo)

    # --- el lector: autenticado pero sin permiso ---
    escribir("")
    escribir("=" * 60)
    escribir("11 - TOKEN DEL LECTOR  ·  se espera 403 al crear")
    escribir("=" * 60)
    codigo, cuerpo = peticion("POST", "/api/token/",
                              {"username": "lector", "password": clave_lector}, formulario=True)
    token_lector = json.loads(cuerpo)["token"] if codigo == 200 else ""
    auth_lector = f"Token {token_lector}"
    escribir(f"Token del lector: {token_lector[:10]}...  (truncado)")
    paso("11b", "LECTOR INTENTA CREAR", 403, "POST", "/api/lotes/", nuevo, auth_lector)
    paso(12, "LECTOR INTENTA BORRAR", 403, "DELETE", f"/api/lotes/{lote_id}/",
         cabecera=auth_lector)

    paso(13, "JEFE DA DE BAJA", 204, "DELETE", f"/api/lotes/{lote_id}/", cabecera=auth)
    paso(14, "BORRAR DE NUEVO (ya no existe para la API)", 404, "DELETE",
         f"/api/lotes/{lote_id}/", cabecera=auth)

    escribir("")
    escribir("=" * 60)
    escribir("15 - JWT CON EXPIRACION  ·  se espera 200 con access y refresh")
    escribir("=" * 60)
    escribir('$ POST /api/jwt/   cuerpo: {"username": "jefe", "password": "***"}')
    codigo, cuerpo = peticion("POST", "/api/jwt/",
                              {"username": "jefe", "password": clave_jefe})
    if codigo == 200:
        d = json.loads(cuerpo)
        escribir("--> HTTP 200   [OK]")
        escribir(f'{{"access": "{d["access"][:16]}...", "refresh": "{d["refresh"][:16]}..."}}')
        escribir("(truncados) El access caduca a los 30 minutos; el refresh lo renueva.")
    else:
        fallos.append(15)
        escribir(f"--> HTTP {codigo}   [NO COINCIDE (esperado 200)]")

    paso(16, "TOKEN INVENTADO", 401, "GET", "/api/lotes/",
         cabecera="Token 00000000000000000000000000000000")

    sys.exit(guardar())


def guardar():
    escribir("")
    escribir("=" * 60)
    if fallos:
        escribir(f"RESULTADO: {len(fallos)} peticion(es) no dieron el codigo esperado: {fallos}")
    else:
        escribir("RESULTADO: todas las peticiones dieron el codigo esperado.")
    escribir("=" * 60)
    SALIDA.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"\nEvidencia guardada en: {SALIDA}")
    return 1 if fallos else 0


if __name__ == "__main__":
    main()
