"""Deja los roles disponibles en todas las plantillas.

Sirve solo para mostrar u ocultar botones. El permiso de verdad lo da el
decorador de permisos.py, nunca esta variable.
"""

from .permisos import ROL_ADMIN, ROL_NORMAL, tiene_rol


def roles(request):
    user = request.user
    return {
        "es_admin": tiene_rol(user, ROL_ADMIN),
        "puede_crear": tiene_rol(user, ROL_ADMIN, ROL_NORMAL),
    }
