"""Permisos de la API, por rol.

No se inventan roles nuevos para la API. Se reutilizan los tres grupos
que ya existen desde la ES2 (admin, normal, viewer) a través de la misma
función tiene_rol() de permisos.py.

Esa decisión es deliberada: si la API tuviera su propia tabla de permisos,
un día el bodeguero podría borrar por /api/ lo que no puede borrar por la
pantalla HTML. Una sola fuente de autorización para las dos interfaces.
"""

from rest_framework import permissions

from .permisos import ROL_ADMIN, ROL_NORMAL, ROL_VIEWER, tiene_rol


class PermisoLote(permissions.BasePermission):
    """Traduce los roles de la ES2 a verbos HTTP.

        GET, HEAD, OPTIONS  -> los tres roles (viewer incluido)
        POST                -> admin y normal (el bodeguero recibe lotes)
        PUT, PATCH, DELETE  -> solo admin (corregir y dar de baja)

    Es el mismo reparto de los decoradores @requiere_rol de views.py:
    crear lo pueden ambos, editar y eliminar solo el jefe.
    """

    message = "Tu rol no permite esta operación sobre los lotes."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in permissions.SAFE_METHODS:
            return tiene_rol(request.user, ROL_ADMIN, ROL_NORMAL, ROL_VIEWER)

        if request.method == "POST":
            return tiene_rol(request.user, ROL_ADMIN, ROL_NORMAL)

        # PUT, PATCH y DELETE modifican o retiran una ficha ya registrada.
        return tiene_rol(request.user, ROL_ADMIN)


class SoloLectura(permissions.BasePermission):
    """Permiso auxiliar para endpoints de consulta (resumen, vencidos)."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.method in permissions.SAFE_METHODS
        )
