"""Administrador de Django para la gestión de lotes."""

from django.contrib import admin, messages
from django.utils.html import format_html

from .models import Lote

COLORES = {
    "ROJO": "#c0392b",
    "AMARILLO": "#b7950b",
    "VERDE": "#1e8449",
    "INVALIDO": "#707b7c",
}


@admin.register(Lote)
class LoteAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "categoria",
        "numero_lote",
        "cantidad",
        "vence",
        "dias_restantes",
        "semaforo",
        "eliminado",
    )
    list_filter = ("categoria", "eliminado", "vence")
    search_fields = ("nombre", "numero_lote")
    ordering = ("vence",)
    date_hierarchy = "vence"
    list_per_page = 25

    # La foto del registro y las fechas no se editan a mano: las calcula
    # el sistema. Si se pudieran escribir, la ficha podría mentir.
    readonly_fields = (
        "estado_registro",
        "motivo_registro",
        "fecha_registro",
        "fecha_eliminacion",
        "semaforo",
        "dias_restantes",
    )

    fieldsets = (
        ("Datos del lote", {"fields": ("nombre", "categoria", "numero_lote", "cantidad", "vence")}),
        (
            "Clasificación",
            {
                "fields": ("semaforo", "dias_restantes", "estado_registro", "motivo_registro"),
                "description": "El semáforo se recalcula con la fecha de hoy. "
                "El estado de registro es la foto del día en que entró el lote.",
            },
        ),
        ("Trazabilidad", {"fields": ("fecha_registro", "eliminado", "fecha_eliminacion")}),
    )

    actions = ("dar_de_baja", "restaurar_lotes")

    # ---------------- columnas calculadas ----------------

    @admin.display(description="Estado hoy")
    def semaforo(self, obj):
        estado = obj.estado_actual
        return format_html(
            '<b style="color:{}">{}</b>', COLORES.get(estado, "#000"), estado
        )

    @admin.display(description="Días")
    def dias_restantes(self, obj):
        dias = obj.dias_restantes
        return "sin fecha" if dias is None else dias

    # ---------------- acciones masivas ----------------

    @admin.action(description="Dar de baja los lotes seleccionados (borrado lógico)")
    def dar_de_baja(self, request, queryset):
        contador = 0
        for lote in queryset.filter(eliminado=False):
            lote.soft_delete()
            contador += 1
        self.message_user(request, f"{contador} lote(s) dados de baja.", messages.SUCCESS)

    @admin.action(description="Restaurar los lotes seleccionados")
    def restaurar_lotes(self, request, queryset):
        contador = 0
        for lote in queryset.filter(eliminado=True):
            lote.restaurar()
            contador += 1
        self.message_user(request, f"{contador} lote(s) restaurados.", messages.SUCCESS)

    # ---------------- permisos por usuario ----------------
    # El admin de Django ya respeta los permisos de cada grupo
    # (core.add_lote, core.change_lote, core.delete_lote). Aca solo se
    # agrega una regla propia: el borrado físico queda reservado al
    # superusuario, porque la merma tiene que quedar registrada.

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        """Reclasifica al guardar desde el administrador."""
        obj.guardar_clasificado()
