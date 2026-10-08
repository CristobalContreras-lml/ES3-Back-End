"""Crea los tres grupos, sus permisos y los usuarios de prueba.

Se corre con:  python manage.py crear_roles

Las contrasenas salen del .env. No hay ninguna escrita en este archivo:
si estuvieran aca, cualquiera que clone el repositorio entraria como
administrador.
"""

from decouple import config
from django.contrib.auth.models import Group, Permission, User
from django.core.management.base import BaseCommand

from core.permisos import ROL_ADMIN, ROL_NORMAL, ROL_VIEWER

# Que puede hacer cada grupo dentro del administrador de Django.
# El viewer solo mira; el normal registra; el admin ademas corrige.
PERMISOS_POR_ROL = {
    ROL_ADMIN: ["view_lote", "add_lote", "change_lote"],
    ROL_NORMAL: ["view_lote", "add_lote"],
    ROL_VIEWER: ["view_lote"],
}

# Usuario de prueba de cada rol y el nombre de la variable del .env.
USUARIOS = [
    ("jefe", ROL_ADMIN, "PASS_ADMIN"),
    ("bodeguero", ROL_NORMAL, "PASS_NORMAL"),
    ("lector", ROL_VIEWER, "PASS_VIEWER"),
]


class Command(BaseCommand):
    help = "Crea los grupos admin, normal y viewer con sus permisos y usuarios de prueba."

    def handle(self, *args, **opciones):
        for rol, codigos in PERMISOS_POR_ROL.items():
            grupo, creado = Group.objects.get_or_create(name=rol)
            permisos = Permission.objects.filter(
                codename__in=codigos, content_type__app_label="core"
            )
            grupo.permissions.set(permisos)
            estado = "creado" if creado else "actualizado"
            self.stdout.write(f"Grupo '{rol}' {estado} con {permisos.count()} permiso(s).")

        for username, rol, variable in USUARIOS:
            clave = config(variable, default="")
            if not clave:
                self.stdout.write(
                    self.style.WARNING(
                        f"Falta {variable} en el .env: no se creo el usuario '{username}'."
                    )
                )
                continue

            usuario, creado = User.objects.get_or_create(username=username)
            # set_password cifra con PBKDF2. Nunca se guarda el texto plano.
            usuario.set_password(clave)
            usuario.is_staff = True  # puede entrar al administrador
            usuario.save()
            usuario.groups.set([Group.objects.get(name=rol)])
            estado = "creado" if creado else "actualizado"
            self.stdout.write(self.style.SUCCESS(f"Usuario '{username}' ({rol}) {estado}."))

        self.stdout.write(self.style.SUCCESS("Listo."))
