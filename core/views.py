"""Vistas de la Eva 2.

Los datos ya no salen de datos.json sino de SQLite. La regla de decisión
sigue siendo la misma de la ES1: se importa, no se copia.
"""

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import LoteForm
from .models import Lote
from .permisos import ROL_ADMIN, ROL_NORMAL, ROL_VIEWER, requiere_rol

# ---------------------------------------------------------------
# Sesión
# ---------------------------------------------------------------


def vista_login(request):
    if request.user.is_authenticated:
        return redirect("lista")

    if request.method == "POST":
        usuario = authenticate(
            request,
            username=request.POST.get("username", "").strip(),
            password=request.POST.get("password", ""),
        )
        if usuario is not None:
            login(request, usuario)
            messages.success(request, f"Bienvenido, {usuario.username}.")
            return redirect("lista")
        # Mensaje genérico: no se dice cuál de los dos datos falló.
        messages.error(request, "Usuario o contraseña incorrectos.")

    return render(request, "login.html")


@login_required(login_url="login")
def vista_logout(request):
    logout(request)
    messages.info(request, "Sesión cerrada.")
    return redirect("login")


# ---------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------


@login_required(login_url="login")
def lista(request):
    """READ. Todos los usuarios autenticados pueden mirar."""
    lotes = Lote.objects.filter(eliminado=False)

    # Buscador por nombre o número de lote (era un Should de la ES1).
    busqueda = request.GET.get("q", "").strip()
    if busqueda:
        lotes = lotes.filter(Q(nombre__icontains=busqueda) | Q(numero_lote__icontains=busqueda))

    # Filtro por estado. Se resuelve en Python y no en la base porque el
    # estado de hoy es calculado, no una columna.
    filtro = request.GET.get("estado", "").upper()
    lotes = list(lotes)
    if filtro in ("ROJO", "AMARILLO", "VERDE", "INVALIDO"):
        lotes = [l for l in lotes if l.estado_actual == filtro]

    contadores = {"ROJO": 0, "AMARILLO": 0, "VERDE": 0, "INVALIDO": 0}
    for lote in Lote.objects.filter(eliminado=False):
        contadores[lote.estado_actual] = contadores.get(lote.estado_actual, 0) + 1

    contexto = {
        "lotes": lotes,
        "hoy": timezone.localdate().strftime("%d-%m-%Y"),
        "busqueda": busqueda,
        "filtro": filtro,
        "rojos": contadores["ROJO"],
        "amarillos": contadores["AMARILLO"],
        "verdes": contadores["VERDE"],
        "invalidos": contadores["INVALIDO"],
        "total": sum(contadores.values()),
        "unidades_en_riesgo": sum(
            l.cantidad for l in Lote.objects.filter(eliminado=False) if l.estado_actual == "ROJO"
        ),
    }
    return render(request, "lista.html", contexto)


@requiere_rol(ROL_ADMIN, ROL_NORMAL)
def crear(request):
    """CREATE. El bodeguero (normal) y el admin pueden recibir lotes."""
    if request.method == "POST":
        form = LoteForm(request.POST)
        if form.is_valid():
            lote = form.save(commit=False)
            lote.guardar_clasificado()  # clasifica antes de guardar
            messages.success(
                request, f"Lote {lote.numero_lote} registrado como {lote.estado_registro}."
            )
            return redirect("lista")
        messages.error(request, "Revisa los datos marcados en rojo.")
    else:
        form = LoteForm()

    return render(request, "form.html", {"form": form, "accion": "Registrar"})


@requiere_rol(ROL_ADMIN)
def editar(request, pk):
    """UPDATE. Solo el admin corrige una ficha ya registrada."""
    lote = get_object_or_404(Lote, pk=pk, eliminado=False)

    if request.method == "POST":
        form = LoteForm(request.POST, instance=lote)
        if form.is_valid():
            lote = form.save(commit=False)
            # Se vuelve a clasificar: si cambió la cantidad o la fecha, el
            # estado guardado ya no corresponde.
            lote.guardar_clasificado()
            messages.success(request, f"Lote {lote.numero_lote} actualizado.")
            return redirect("lista")
        messages.error(request, "Revisa los datos marcados en rojo.")
    else:
        form = LoteForm(instance=lote)

    return render(request, "form.html", {"form": form, "accion": "Editar", "lote": lote})


@requiere_rol(ROL_ADMIN)
def eliminar(request, pk):
    """DELETE lógico. La merma no se borra, se oculta."""
    lote = get_object_or_404(Lote, pk=pk, eliminado=False)

    if request.method == "POST":
        lote.soft_delete()
        messages.success(request, f"Lote {lote.numero_lote} dado de baja.")
        return redirect("lista")

    return render(request, "confirmar.html", {"lote": lote})


@requiere_rol(ROL_ADMIN)
def detalle(request, pk):
    """Ficha completa, incluidos los lotes dados de baja."""
    lote = get_object_or_404(Lote, pk=pk)
    return render(request, "detalle.html", {"lote": lote})
