"""Casos de prueba de la Eva 2.

Se corren con:  python manage.py test
Cubren las tres cosas que se pueden romper sin que se note:
la regla de decisión, el CRUD y los permisos por rol.
"""

from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.permisos import ROL_ADMIN, ROL_NORMAL, ROL_VIEWER
from core.models import Lote


def fecha_en(dias):
    return timezone.localdate() + timedelta(days=dias)


class ReglaDeDecisionTest(TestCase):
    """La regla de la ES1 debe seguir dando los mismos 4 resultados."""

    def crear(self, categoria="Lacteos", cantidad=10, dias=30):
        return Lote(categoria=categoria, cantidad=cantidad, vence=fecha_en(dias))

    def test_lote_vigente_es_verde(self):
        self.assertEqual(self.crear(dias=60).estado_actual, "VERDE")

    def test_lote_dentro_del_umbral_es_amarillo(self):
        # Lacteos avisa con 7 dias
        self.assertEqual(self.crear(dias=5).estado_actual, "AMARILLO")

    def test_lote_vencido_es_rojo(self):
        self.assertEqual(self.crear(dias=-1).estado_actual, "ROJO")

    def test_lote_que_vence_hoy_es_rojo(self):
        self.assertEqual(self.crear(dias=0).estado_actual, "ROJO")

    def test_cantidad_cero_es_invalido(self):
        self.assertEqual(self.crear(cantidad=0).estado_actual, "INVALIDO")

    def test_categoria_fuera_de_lista_es_invalido(self):
        self.assertEqual(self.crear(categoria="Abarrotes").estado_actual, "INVALIDO")

    def test_cada_categoria_usa_su_propio_umbral(self):
        # Verduras avisa con 3 dias: a 5 dias todavia esta verde...
        self.assertEqual(self.crear(categoria="Verduras", dias=5).estado_actual, "VERDE")
        # ...pero Lacteos, que avisa con 7, ya esta amarillo.
        self.assertEqual(self.crear(categoria="Lacteos", dias=5).estado_actual, "AMARILLO")


class ModeloTest(TestCase):
    def test_borrado_logico_no_borra_la_fila(self):
        lote = Lote(nombre="Queso", categoria="Lacteos", numero_lote="L-1",
                    cantidad=5, vence=fecha_en(20))
        lote.guardar_clasificado()

        lote.soft_delete()

        self.assertTrue(Lote.objects.filter(pk=lote.pk).exists())
        self.assertTrue(lote.eliminado)
        self.assertIsNotNone(lote.fecha_eliminacion)
        self.assertEqual(Lote.objects.filter(eliminado=False).count(), 0)

    def test_el_estado_guardado_envejece_y_el_actual_no(self):
        """Un lote registrado como VERDE debe verse ROJO cuando le pasa la fecha."""
        lote = Lote(nombre="Pollo", categoria="Carnes", numero_lote="C-1",
                    cantidad=5, vence=fecha_en(30))
        lote.guardar_clasificado()
        self.assertEqual(lote.estado_registro, "VERDE")

        # Pasa el tiempo: la fecha de vencimiento queda atras.
        lote.vence = fecha_en(-2)
        self.assertEqual(lote.estado_registro, "VERDE")  # la foto no cambia
        self.assertEqual(lote.estado_actual, "ROJO")  # el semaforo si
        self.assertTrue(lote.cambio_de_estado)


class CrudTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("jefe", password="clave-de-prueba-1")
        self.admin.groups.add(Group.objects.create(name=ROL_ADMIN))
        self.client.login(username="jefe", password="clave-de-prueba-1")

    def datos(self, **cambios):
        base = {
            "nombre": "Queso mantecoso",
            "categoria": "Lacteos",
            "numero_lote": "L-1180",
            "cantidad": 12,
            "vence": fecha_en(40).isoformat(),
        }
        base.update(cambios)
        return base

    def test_crear_guarda_y_clasifica(self):
        respuesta = self.client.post(reverse("crear"), self.datos(), follow=True)

        self.assertEqual(Lote.objects.count(), 1)
        lote = Lote.objects.first()
        self.assertEqual(lote.estado_registro, "VERDE")
        self.assertContains(respuesta, "registrado como VERDE")

    def test_crear_con_cantidad_invalida_no_guarda_nada(self):
        respuesta = self.client.post(reverse("crear"), self.datos(cantidad="diez"))

        self.assertEqual(Lote.objects.count(), 0)
        self.assertEqual(respuesta.status_code, 200)  # vuelve al formulario, no 500
        self.assertContains(respuesta, "número entero")

    def test_crear_con_cantidad_cero_muestra_error(self):
        self.client.post(reverse("crear"), self.datos(cantidad=0))
        self.assertEqual(Lote.objects.count(), 0)

    def test_no_se_puede_recibir_un_lote_ya_vencido(self):
        respuesta = self.client.post(reverse("crear"), self.datos(vence=fecha_en(-5).isoformat()))

        self.assertEqual(Lote.objects.count(), 0)
        self.assertContains(respuesta, "ya está vencido")

    def test_editar_recalcula_el_estado(self):
        self.client.post(reverse("crear"), self.datos())
        lote = Lote.objects.first()
        self.assertEqual(lote.estado_registro, "VERDE")

        # Se corrige la fecha a una dentro del umbral de Lacteos (7 dias).
        self.client.post(
            reverse("editar", args=[lote.pk]), self.datos(vence=fecha_en(3).isoformat())
        )

        lote.refresh_from_db()
        self.assertEqual(lote.estado_registro, "AMARILLO")  # no quedo el VERDE viejo

    def test_eliminar_es_logico(self):
        self.client.post(reverse("crear"), self.datos())
        lote = Lote.objects.first()

        self.client.post(reverse("eliminar", args=[lote.pk]))

        lote.refresh_from_db()
        self.assertTrue(lote.eliminado)
        self.assertTrue(Lote.objects.filter(pk=lote.pk).exists())  # la fila sigue
        # Ya no aparece en el inventario. Se mira la lista del contexto y no el
        # HTML completo, porque el mensaje de exito tambien nombra el lote.
        self.assertEqual(len(self.client.get(reverse("lista")).context["lotes"]), 0)

    def test_lote_inexistente_devuelve_404(self):
        self.assertEqual(self.client.get(reverse("editar", args=[9999])).status_code, 404)

    def test_buscador_filtra_por_nombre(self):
        self.client.post(reverse("crear"), self.datos())
        self.client.post(reverse("crear"), self.datos(nombre="Lechuga", numero_lote="V-220",
                                                      categoria="Verduras"))

        respuesta = self.client.get(reverse("lista"), {"q": "lechuga"})

        self.assertContains(respuesta, "Lechuga")
        self.assertNotContains(respuesta, "Queso mantecoso")


class PermisosTest(TestCase):
    """Lo que mas se evalua: que el permiso este en el servidor.

    Cada prueba entra escribiendo la direccion a mano, que es justamente
    lo que haria alguien para saltarse un boton escondido.
    """

    def setUp(self):
        for rol in (ROL_ADMIN, ROL_NORMAL, ROL_VIEWER):
            Group.objects.create(name=rol)

        self.lote = Lote(nombre="Queso", categoria="Lacteos", numero_lote="L-1",
                         cantidad=5, vence=fecha_en(30))
        self.lote.guardar_clasificado()

    def entrar_como(self, rol):
        usuario = User.objects.create_user(f"u_{rol}", password="clave-de-prueba-1")
        usuario.groups.add(Group.objects.get(name=rol))
        self.client.login(username=f"u_{rol}", password="clave-de-prueba-1")
        return usuario

    def test_sin_sesion_la_lista_redirige_al_login(self):
        respuesta = self.client.get(reverse("lista"))
        self.assertRedirects(respuesta, f"{reverse('login')}?next={reverse('lista')}")

    def test_viewer_puede_mirar(self):
        self.entrar_como(ROL_VIEWER)
        self.assertEqual(self.client.get(reverse("lista")).status_code, 200)

    def test_viewer_no_puede_crear_aunque_escriba_la_direccion(self):
        self.entrar_como(ROL_VIEWER)

        respuesta = self.client.get(reverse("crear"), follow=True)

        self.assertContains(respuesta, "No tienes permiso")
        self.assertEqual(Lote.objects.count(), 1)  # no se creo nada

    def test_normal_puede_crear_pero_no_editar(self):
        self.entrar_como(ROL_NORMAL)

        self.assertEqual(self.client.get(reverse("crear")).status_code, 200)

        respuesta = self.client.get(reverse("editar", args=[self.lote.pk]), follow=True)
        self.assertContains(respuesta, "No tienes permiso")

    def test_normal_no_puede_eliminar_por_post_directo(self):
        """El POST a mano tambien tiene que cortarse, no solo el GET."""
        self.entrar_como(ROL_NORMAL)

        self.client.post(reverse("eliminar", args=[self.lote.pk]))

        self.lote.refresh_from_db()
        self.assertFalse(self.lote.eliminado)

    def test_admin_puede_todo(self):
        self.entrar_como(ROL_ADMIN)

        self.assertEqual(self.client.get(reverse("crear")).status_code, 200)
        self.assertEqual(self.client.get(reverse("editar", args=[self.lote.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("eliminar", args=[self.lote.pk])).status_code, 200)

    def test_superusuario_pasa_sin_grupo(self):
        User.objects.create_superuser("root", password="clave-de-prueba-1")
        self.client.login(username="root", password="clave-de-prueba-1")

        self.assertEqual(self.client.get(reverse("editar", args=[self.lote.pk])).status_code, 200)


class SesionTest(TestCase):
    def setUp(self):
        Group.objects.create(name=ROL_VIEWER)
        self.usuario = User.objects.create_user("lector", password="clave-de-prueba-1")
        self.usuario.groups.add(Group.objects.get(name=ROL_VIEWER))

    def test_login_correcto_entra_al_inventario(self):
        respuesta = self.client.post(
            reverse("login"), {"username": "lector", "password": "clave-de-prueba-1"}, follow=True
        )
        self.assertContains(respuesta, "Inventario de lotes")

    def test_login_incorrecto_muestra_mensaje_generico(self):
        respuesta = self.client.post(
            reverse("login"), {"username": "lector", "password": "equivocada"}
        )
        self.assertContains(respuesta, "Usuario o contraseña incorrectos")

    def test_la_contrasena_no_se_guarda_en_texto_plano(self):
        self.assertNotEqual(self.usuario.password, "clave-de-prueba-1")
        self.assertTrue(self.usuario.password.startswith("pbkdf2_"))
        self.assertTrue(self.usuario.check_password("clave-de-prueba-1"))

    def test_logout_cierra_la_sesion(self):
        self.client.login(username="lector", password="clave-de-prueba-1")

        self.client.post(reverse("logout"))

        respuesta = self.client.get(reverse("lista"))
        self.assertEqual(respuesta.status_code, 302)  # vuelve al login


class CsrfTest(TestCase):
    """Django rechaza el POST sin token. Se prueba con enforce_csrf_checks."""

    def test_post_sin_token_csrf_es_rechazado(self):
        from django.test import Client

        Group.objects.create(name=ROL_ADMIN)
        usuario = User.objects.create_user("jefe", password="clave-de-prueba-1")
        usuario.groups.add(Group.objects.get(name=ROL_ADMIN))

        cliente = Client(enforce_csrf_checks=True)
        cliente.login(username="jefe", password="clave-de-prueba-1")

        respuesta = cliente.post(reverse("crear"), {
            "nombre": "Queso mantecoso", "categoria": "Lacteos", "numero_lote": "L-9",
            "cantidad": 5, "vence": fecha_en(30).isoformat(),
        })

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(Lote.objects.count(), 0)
