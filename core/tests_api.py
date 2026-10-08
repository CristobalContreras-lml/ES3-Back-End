"""Pruebas de la API REST (ES3).

Los 29 tests de la ES2 siguen en tests.py y siguen pasando: las pantallas
HTML no se tocaron. Estos se suman, no los reemplazan.

Cada clase cubre un criterio de la rúbrica:

    AutenticacionTest   3.1.2  sin token es 401, con token es 200
    PermisosApiTest     3.1.2  403 segun el rol, no 404 ni 200
    CodigosDeEstadoTest 3.1.3  200, 201, 204, 400, 404
    SerializadorTest    3.1.3  el cliente no puede escribir el estado
    RestfulTest         3.1.4  las URL son sustantivos y GET no modifica
"""

from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from core.models import Lote
from core.permisos import ROL_ADMIN, ROL_NORMAL, ROL_VIEWER

HOY = date.today()
EN_UN_ANO = HOY + timedelta(days=365)
LISTA = "/api/lotes/"


def crear_usuario(nombre, rol):
    usuario = User.objects.create_user(username=nombre, password="ClaveDePrueba123")
    grupo, _ = Group.objects.get_or_create(name=rol)
    usuario.groups.add(grupo)
    return usuario


def lote_de_ejemplo(**extra):
    datos = {
        "nombre": "Queso mantecoso",
        "categoria": "Lacteos",
        "numero_lote": "L-1180",
        "cantidad": 20,
        "vence": EN_UN_ANO,
    }
    datos.update(extra)
    lote = Lote(**datos)
    lote.guardar_clasificado()
    return lote


class AutenticacionTest(APITestCase):
    """3.1.2 · La API esta cerrada por defecto."""

    def setUp(self):
        self.jefe = crear_usuario("jefe", ROL_ADMIN)

    def test_sin_token_responde_401(self):
        """El error clasico es dejar AllowAny 'para poder probar'."""
        respuesta = self.client.get(LISTA)
        self.assertEqual(respuesta.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_con_token_responde_200(self):
        token = Token.objects.create(user=self.jefe)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        respuesta = self.client.get(LISTA)
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)

    def test_el_endpoint_de_token_entrega_un_token(self):
        respuesta = self.client.post(
            "/api/token/", {"username": "jefe", "password": "ClaveDePrueba123"}
        )
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertIn("token", respuesta.data)

    def test_el_jwt_entrega_acceso_y_refresco(self):
        """El JWT expira; por eso trae un refresh ademas del access."""
        respuesta = self.client.post(
            "/api/jwt/", {"username": "jefe", "password": "ClaveDePrueba123"}
        )
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertIn("access", respuesta.data)
        self.assertIn("refresh", respuesta.data)

    def test_un_token_inventado_no_sirve(self):
        self.client.credentials(HTTP_AUTHORIZATION="Token 0000000000000000")
        respuesta = self.client.get(LISTA)
        self.assertEqual(respuesta.status_code, status.HTTP_401_UNAUTHORIZED)


class PermisosApiTest(APITestCase):
    """3.1.2 · Los tres roles de la ES2 valen igual en la API."""

    def setUp(self):
        self.lote = lote_de_ejemplo()
        self.usuarios = {
            ROL_ADMIN: crear_usuario("jefe", ROL_ADMIN),
            ROL_NORMAL: crear_usuario("bodeguero", ROL_NORMAL),
            ROL_VIEWER: crear_usuario("lector", ROL_VIEWER),
        }

    def autenticar(self, rol):
        token, _ = Token.objects.get_or_create(user=self.usuarios[rol])
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_los_tres_roles_pueden_leer(self):
        for rol in self.usuarios:
            with self.subTest(rol=rol):
                self.autenticar(rol)
                self.assertEqual(self.client.get(LISTA).status_code, status.HTTP_200_OK)

    def test_el_lector_no_puede_crear(self):
        self.autenticar(ROL_VIEWER)
        respuesta = self.client.post(
            LISTA,
            {
                "nombre": "Leche entera",
                "categoria": "Lacteos",
                "numero_lote": "L-9000",
                "cantidad": 5,
                "vence": EN_UN_ANO.isoformat(),
            },
        )
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_el_bodeguero_crea_pero_no_borra(self):
        """Es el mismo reparto que los decoradores de views.py."""
        self.autenticar(ROL_NORMAL)
        creacion = self.client.post(
            LISTA,
            {
                "nombre": "Leche entera",
                "categoria": "Lacteos",
                "numero_lote": "L-9001",
                "cantidad": 5,
                "vence": EN_UN_ANO.isoformat(),
            },
        )
        self.assertEqual(creacion.status_code, status.HTTP_201_CREATED)

        borrado = self.client.delete(f"{LISTA}{self.lote.pk}/")
        self.assertEqual(borrado.status_code, status.HTTP_403_FORBIDDEN)

    def test_el_bodeguero_tampoco_puede_editar(self):
        self.autenticar(ROL_NORMAL)
        respuesta = self.client.patch(f"{LISTA}{self.lote.pk}/", {"cantidad": 99})
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_el_jefe_puede_todo(self):
        self.autenticar(ROL_ADMIN)
        edicion = self.client.patch(f"{LISTA}{self.lote.pk}/", {"cantidad": 99})
        self.assertEqual(edicion.status_code, status.HTTP_200_OK)
        borrado = self.client.delete(f"{LISTA}{self.lote.pk}/")
        self.assertEqual(borrado.status_code, status.HTTP_204_NO_CONTENT)


class CodigosDeEstadoTest(APITestCase):
    """3.1.3 · Cada situacion devuelve el numero que le corresponde."""

    def setUp(self):
        self.lote = lote_de_ejemplo()
        self.jefe = crear_usuario("jefe", ROL_ADMIN)
        token = Token.objects.create(user=self.jefe)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_get_lista_devuelve_200(self):
        self.assertEqual(self.client.get(LISTA).status_code, status.HTTP_200_OK)

    def test_post_valido_devuelve_201(self):
        respuesta = self.client.post(
            LISTA,
            {
                "nombre": "Pollo entero",
                "categoria": "Carnes",
                "numero_lote": "C-5050",
                "cantidad": 12,
                "vence": EN_UN_ANO.isoformat(),
            },
        )
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED)

    def test_delete_devuelve_204(self):
        respuesta = self.client.delete(f"{LISTA}{self.lote.pk}/")
        self.assertEqual(respuesta.status_code, status.HTTP_204_NO_CONTENT)

    def test_post_con_cantidad_negativa_devuelve_400(self):
        respuesta = self.client.post(
            LISTA,
            {
                "nombre": "Pollo entero",
                "categoria": "Carnes",
                "numero_lote": "C-5051",
                "cantidad": -5,
                "vence": EN_UN_ANO.isoformat(),
            },
        )
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cantidad", respuesta.data)

    def test_post_con_categoria_inexistente_devuelve_400(self):
        """Las mismas categorias que rechazo la migracion de datos.json."""
        respuesta = self.client.post(
            LISTA,
            {
                "nombre": "Harina sin cernir",
                "categoria": "Abarrotes",
                "numero_lote": "H-0104",
                "cantidad": 10,
                "vence": EN_UN_ANO.isoformat(),
            },
        )
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("categoria", respuesta.data)

    def test_no_se_puede_recibir_un_lote_ya_vencido(self):
        respuesta = self.client.post(
            LISTA,
            {
                "nombre": "Yogurt natural",
                "categoria": "Lacteos",
                "numero_lote": "L-0001",
                "cantidad": 3,
                "vence": (HOY - timedelta(days=5)).isoformat(),
            },
        )
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_se_puede_editar_un_lote_ya_vencido(self):
        """La regla del vencido aplica al RECIBIR, no al corregir.

        Salio probando con curl: el PATCH devolvia 400 sobre un lote
        vencido, asi que un lote vencido quedaba congelado y el jefe no
        podia ajustar la cantidad para registrar la merma. Es justo lo
        que necesita hacer con un lote vencido.
        """
        vencido = lote_de_ejemplo(
            numero_lote="L-VENCIDO", vence=HOY - timedelta(days=30)
        )
        self.assertEqual(vencido.estado_actual, "ROJO")

        respuesta = self.client.patch(f"{LISTA}{vencido.pk}/", {"cantidad": 2})
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        vencido.refresh_from_db()
        self.assertEqual(vencido.cantidad, 2)

    def test_crear_un_lote_vencido_sigue_bloqueado(self):
        """La correccion anterior no debe abrir la puerta al crear."""
        respuesta = self.client.post(
            LISTA,
            {
                "nombre": "Queso viejo",
                "categoria": "Lacteos",
                "numero_lote": "L-0002",
                "cantidad": 3,
                "vence": (HOY - timedelta(days=10)).isoformat(),
            },
        )
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_un_id_que_no_existe_devuelve_404(self):
        respuesta = self.client.get(f"{LISTA}99999/")
        self.assertEqual(respuesta.status_code, status.HTTP_404_NOT_FOUND)

    def test_la_lista_viene_paginada(self):
        """PAGE_SIZE 10: la respuesta trae count, next, previous y results."""
        respuesta = self.client.get(LISTA)
        for clave in ("count", "next", "previous", "results"):
            self.assertIn(clave, respuesta.data)


class SerializadorTest(APITestCase):
    """3.1.3 · El estado lo decide la regla, no el cliente."""

    def setUp(self):
        self.jefe = crear_usuario("jefe", ROL_ADMIN)
        token = Token.objects.create(user=self.jefe)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_el_cliente_no_puede_declarar_el_estado(self):
        """Mandar estado_registro VERDE en el JSON no debe tener efecto."""
        respuesta = self.client.post(
            LISTA,
            {
                "nombre": "Crema de leche",
                "categoria": "Lacteos",
                "numero_lote": "L-7777",
                "cantidad": 4,
                "vence": (HOY + timedelta(days=2)).isoformat(),
                "estado_registro": "VERDE",
                "motivo_registro": "lo digo yo",
            },
        )
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED)
        lote = Lote.objects.get(numero_lote="L-7777")
        # Vence en 2 dias: la regla lo clasifica AMARILLO, no VERDE.
        self.assertEqual(lote.estado_registro, "AMARILLO")
        self.assertNotEqual(lote.motivo_registro, "lo digo yo")

    def test_la_respuesta_trae_el_estado_calculado_hoy(self):
        lote_de_ejemplo(numero_lote="L-2222")
        respuesta = self.client.get(LISTA)
        fila = respuesta.data["results"][0]
        for campo in ("id", "estado_actual", "dias_restantes", "cambio_de_estado"):
            self.assertIn(campo, fila)

    def test_no_se_exponen_campos_sensibles(self):
        lote_de_ejemplo(numero_lote="L-3333")
        fila = self.client.get(LISTA).data["results"][0]
        for prohibido in ("password", "token", "user"):
            self.assertNotIn(prohibido, fila)


class RestfulTest(APITestCase):
    """3.1.4 · Convenciones REST."""

    def setUp(self):
        self.lote = lote_de_ejemplo()
        self.jefe = crear_usuario("jefe", ROL_ADMIN)
        token = Token.objects.create(user=self.jefe)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_la_url_es_un_sustantivo_en_plural(self):
        self.assertEqual(reverse("lote-list"), "/api/lotes/")

    def test_un_get_no_modifica_nada(self):
        """Si un GET borrara o guardara algo, no seria REST."""
        antes = Lote.objects.filter(eliminado=False).count()
        self.client.get(LISTA)
        self.client.get(f"{LISTA}{self.lote.pk}/")
        self.client.get(f"{LISTA}resumen/")
        self.assertEqual(Lote.objects.filter(eliminado=False).count(), antes)

    def test_el_delete_es_logico_la_fila_no_desaparece(self):
        total_filas = Lote.objects.count()
        self.client.delete(f"{LISTA}{self.lote.pk}/")
        self.assertEqual(Lote.objects.count(), total_filas)
        self.lote.refresh_from_db()
        self.assertTrue(self.lote.eliminado)

    def test_el_endpoint_resumen_responde_200(self):
        respuesta = self.client.get(f"{LISTA}resumen/")
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertIn("por_estado", respuesta.data)

    def test_el_esquema_openapi_se_genera(self):
        """3.1.4 · la documentacion sale del propio codigo."""
        respuesta = self.client.get("/api/schema/")
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
