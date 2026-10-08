"""Modelo de la Eva 2.

Cada lote que antes era un diccionario dentro de datos.json ahora es una
fila en SQLite. La regla de decisión NO se reescribe aquí: se importa
desde solucion.py, igual que hacía la vista de la ES1.
"""

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from solucion import UMBRALES, clasificar_insumo


class Lote(models.Model):
    """Un lote de insumo que entra a bodega.

    Los campos salen de las claves que ya tenía cada registro en
    datos.json: nombre, categoria, lote, cantidad y vence.
    """

    # Las categorías válidas son las mismas de solucion.py. Se generan
    # desde UMBRALES para no tener la lista escrita en dos lugares: si
    # mañana se agrega "Congelados" al diccionario, el choices lo toma solo.
    CATEGORIA_CHOICES = [(c, c) for c in UMBRALES]

    nombre = models.CharField(max_length=100)
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES)
    numero_lote = models.CharField("número de lote", max_length=30)
    cantidad = models.IntegerField(validators=[MinValueValidator(1)])
    vence = models.DateField("fecha de vencimiento")

    # Foto del estado al momento de registrar el lote. NO es el estado de
    # hoy: para eso están las propiedades de más abajo.
    estado_registro = models.CharField(max_length=20)
    motivo_registro = models.CharField(max_length=300)
    fecha_registro = models.DateTimeField(default=timezone.now)

    # Borrado lógico: el lote se oculta pero la merma queda registrada.
    eliminado = models.BooleanField(default=False)
    fecha_eliminacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["vence"]  # lo que vence antes va primero (FIFO)
        verbose_name = "lote"
        verbose_name_plural = "lotes"

    def __str__(self):
        return f"{self.nombre} ({self.numero_lote}) - {self.estado_actual}"

    # -----------------------------------------------------------------
    # Estado de HOY. Un lote registrado como VERDE puede ser ROJO mañana,
    # así que el semáforo se recalcula en cada consulta en vez de confiar
    # en lo guardado. Es el mismo criterio de la vista de la ES1.
    # -----------------------------------------------------------------

    @property
    def clasificacion(self):
        return clasificar_insumo(self.categoria, self.cantidad, self.vence.isoformat())

    @property
    def estado_actual(self):
        return self.clasificacion["estado"]

    @property
    def color_actual(self):
        return self.clasificacion["color"]

    @property
    def dias_restantes(self):
        return self.clasificacion["dias"]

    @property
    def motivo_actual(self):
        return self.clasificacion["motivo"]

    @property
    def cambio_de_estado(self):
        """True si el lote ya no está en el estado con el que se registró."""
        return self.estado_registro != self.estado_actual

    # -----------------------------------------------------------------
    # Escritura
    # -----------------------------------------------------------------

    def guardar_clasificado(self):
        """Recalcula la foto del estado y guarda.

        Se llama al crear y al editar. Si se edita la cantidad o la fecha
        y no se recalcula, la ficha queda mintiendo.
        """
        resultado = self.clasificacion
        self.estado_registro = resultado["estado"]
        self.motivo_registro = resultado["motivo"]
        self.save()

    def soft_delete(self):
        """Marca el lote como eliminado sin borrar la fila."""
        self.eliminado = True
        self.fecha_eliminacion = timezone.now()
        self.save(update_fields=["eliminado", "fecha_eliminacion"])

    def restaurar(self):
        self.eliminado = False
        self.fecha_eliminacion = None
        self.save(update_fields=["eliminado", "fecha_eliminacion"])
