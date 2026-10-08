"""Formulario del lote.

La validación vive acá y no repartida dentro de la vista: así el mismo
formulario sirve para crear y para editar, y la vista queda corta.
"""

from django import forms
from django.utils import timezone

from .models import Lote


class LoteForm(forms.ModelForm):
    class Meta:
        model = Lote
        fields = ["nombre", "categoria", "numero_lote", "cantidad", "vence"]
        widgets = {
            "nombre": forms.TextInput(attrs={"placeholder": "Queso mantecoso"}),
            "numero_lote": forms.TextInput(attrs={"placeholder": "L-1180"}),
            "cantidad": forms.NumberInput(attrs={"min": 1}),
            "vence": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }
        error_messages = {
            "cantidad": {"invalid": "La cantidad debe ser un número entero."},
            "vence": {"invalid": "La fecha va en formato AAAA-MM-DD."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # El input date del navegador solo entiende AAAA-MM-DD.
        self.fields["vence"].input_formats = ["%Y-%m-%d"]
        for campo in self.fields.values():
            css = campo.widget.attrs.get("class", "")
            campo.widget.attrs["class"] = (css + " campo").strip()

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip()
        if len(nombre) < 3:
            raise forms.ValidationError("El nombre debe tener al menos 3 caracteres.")
        return nombre

    def clean_numero_lote(self):
        return self.cleaned_data["numero_lote"].strip().upper()

    def clean_cantidad(self):
        cantidad = self.cleaned_data["cantidad"]
        if cantidad <= 0:
            raise forms.ValidationError("La cantidad debe ser mayor que 0.")
        if cantidad > 100000:
            raise forms.ValidationError("Esa cantidad parece un error de tipeo (máximo 100.000).")
        return cantidad

    def clean_vence(self):
        vence = self.cleaned_data["vence"]
        # Un lote que vence en 2050 casi siempre es un año mal escrito.
        if vence.year > timezone.now().year + 10:
            raise forms.ValidationError("Revisa el año: la fecha está demasiado lejos.")
        return vence

    def clean(self):
        """Regla de negocio: no se RECIBE en bodega un lote ya vencido.

        Se apoya en la misma clasificación de solucion.py en vez de volver
        a comparar fechas aquí.

        Solo al crear. Si se aplicara también al editar, un lote vencido
        quedaría congelado y el jefe no podría corregir la cantidad para
        registrar la merma. Se detectó probando la API con curl en la ES3
        y se corrigió en las dos interfaces, para que la pantalla HTML y
        el endpoint se comporten igual.
        """
        datos = super().clean()
        if self.instance is not None and self.instance.pk is not None:
            return datos
        categoria = datos.get("categoria")
        cantidad = datos.get("cantidad")
        vence = datos.get("vence")

        if categoria and cantidad and vence:
            lote = Lote(categoria=categoria, cantidad=cantidad, vence=vence)
            if lote.estado_actual == "ROJO":
                self.add_error(
                    "vence",
                    "El lote ya está vencido: no se puede recibir en bodega. "
                    "Si llegó igual, regístralo como merma desde el administrador.",
                )
        return datos
