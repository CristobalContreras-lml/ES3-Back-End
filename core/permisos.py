"""Control de acceso por rol.

La restricción va en el servidor. Esconder un botón en la plantilla no
sirve de nada: cualquiera puede escribir la direccion a mano.
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

ROL_ADMIN = "admin"
ROL_NORMAL = "normal"
ROL_VIEWER = "viewer"
ROLES = (ROL_ADMIN, ROL_NORMAL, ROL_VIEWER)


def tiene_rol(user, *roles):
    """True si el usuario pertenece a alguno de los grupos pedidos."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=roles).exists()


def requiere_rol(*roles):
    """Decorador que corta la vista si el rol no corresponde."""

    def decorador(view_func):
        @wraps(view_func)
        @login_required(login_url="login")
        def wrapper(request, *args, **kwargs):
            if tiene_rol(request.user, *roles):
                return view_func(request, *args, **kwargs)
            messages.error(request, "No tienes permiso para esta acción.")
            return redirect("lista")

        return wrapper

    return decorador
