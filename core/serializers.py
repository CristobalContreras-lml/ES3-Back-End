"""Serializadores de la API.

El serializer es el equivalente del ModelForm de la ES2, pero para JSON.
La validación es la misma: no se reescribe la regla, se reutiliza la
clasificación de solucion.py igual que hace forms.py.

Decisión central, heredada de la ES2: el estado NO lo manda el cliente.
Lo decide clasificar_insumo() con la fecha de hoy. Por eso todos los
campos de estado van en read_only_fields: si fueran editables, cualquiera
podría mandar {"estado_registro": "VERDE"} y declarar vigente un lote
vencido. Es exactamente lo que este sistema existe para evitar.
"""

from rest_framework import serializers

from .models import Lote


class LoteSerializer(serializers.ModelSerializer):
    """Traduce un Lote a JSON y valida el JSON que llega."""

    # Propiedades del modelo, no columnas. Se calculan con la fecha de hoy
    # en cada lectura, así que son de solo lectura por naturaleza.
    estado_actual = serializers.CharField(read_only=True)
    dias_restantes = serializers.IntegerField(read_only=True)
    motivo_actual = serializers.CharField(read_only=True)
    cambio_de_estado = serializers.BooleanField(read_only=True)

    class Meta:
        model = Lote
        # Los campos se enumeran a mano. Nunca "__all__": eso expone
        # cualquier campo que se agregue en el futuro sin decidirlo.
        fields = [
            "id",
            "nombre",
            "categoria",
            "numero_lote",
            "cantidad",
            "vence",
            # calculados hoy
            "estado_actual",
            "dias_restantes",
            "motivo_actual",
            "cambio_de_estado",
            # foto del registro
            "estado_registro",
            "motivo_registro",
            "fecha_registro",
            # trazabilidad
            "eliminado",
            "fecha_eliminacion",
        ]
        read_only_fields = [
            "estado_registro",
            "motivo_registro",
            "fecha_registro",
            "eliminado",
            "fecha_eliminacion",
        ]

    # ------------------------------------------------------------------
    # Validación campo por campo. Es el mismo clean_<campo> de la ES2
    # con otro nombre: validate_<campo>.
    # ------------------------------------------------------------------

    def validate_nombre(self, valor):
        valor = valor.strip()
        if len(valor) < 3:
            raise serializers.ValidationError("El nombre debe tener al menos 3 caracteres.")
        return valor

    def validate_numero_lote(self, valor):
        return valor.strip().upper()

    def validate_cantidad(self, valor):
        if valor <= 0:
            raise serializers.ValidationError("La cantidad debe ser mayor que 0.")
        if valor > 100000:
            raise serializers.ValidationError(
                "Esa cantidad parece un error de tipeo (máximo 100.000)."
            )
        return valor

    def validate_vence(self, valor):
        from django.utils import timezone

        if valor.year > timezone.now().year + 10:
            raise serializers.ValidationError("Revisa el año: la fecha está demasiado lejos.")
        return valor

    def validate(self, datos):
        """Regla de negocio: no se RECIBE en bodega un lote ya vencido.

        Se apoya en la misma clasificación en vez de volver a comparar
        fechas, igual que forms.py.

        Solo se aplica al crear. Recibir es un acto de ingreso; editar no.
        Si se aplicara también al editar, un lote vencido quedaría
        congelado: el jefe no podría corregirle ni el nombre ni la
        cantidad para registrar la merma, que es justo lo que necesita
        hacer con un lote vencido. Esto salió probando con curl, no
        estaba previsto.
        """
        if self.instance is not None:
            return datos

        categoria = datos.get("categoria")
        cantidad = datos.get("cantidad")
        vence = datos.get("vence")

        if categoria and cantidad and vence:
            tentativo = Lote(categoria=categoria, cantidad=cantidad, vence=vence)
            if tentativo.estado_actual == "ROJO":
                raise serializers.ValidationError(
                    {
                        "vence": [
                            "El lote ya está vencido: no se puede recibir en bodega. "
                            "Si llegó igual, regístralo como merma desde el administrador."
                        ]
                    }
                )
        return datos
