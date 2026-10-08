"""Vistas de la API (DRF).

Archivo nuevo. views.py NO se toca: son dos interfaces distintas sobre el
mismo modelo. Las pantallas HTML de la ES2 siguen funcionando igual.

Las cuatro vistas de la ES2 (lista, crear, editar, eliminar) se juntan en
un solo ModelViewSet, y el router genera las rutas. Se eligió ViewSet y no
APIView ni generics: el recurso es uno solo y las cinco operaciones son
las estándar, así que escribir cinco clases sería repetir lo que el
ViewSet ya resuelve. Mezclar los tres estilos en un mismo proyecto es lo
que vuelve imposible justificarlo después.
"""

from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Lote
from .permissions import PermisoLote
from .serializers import LoteSerializer

ESTADOS = ("ROJO", "AMARILLO", "VERDE", "INVALIDO")


class LoteViewSet(viewsets.ModelViewSet):
    """CRUD completo sobre los lotes de insumos.

    list     GET    /api/lotes/        200
    create   POST   /api/lotes/        201
    retrieve GET    /api/lotes/{id}/   200
    update   PUT    /api/lotes/{id}/   200
    partial  PATCH  /api/lotes/{id}/   200
    destroy  DELETE /api/lotes/{id}/   204  (borrado lógico)
    """

    serializer_class = LoteSerializer
    permission_classes = [PermisoLote]

    def get_queryset(self):
        """Los lotes dados de baja no se listan: el borrado es lógico.

        Acepta dos filtros por query string, los mismos de la pantalla
        HTML: ?q= busca por nombre o número de lote, y ?estado= filtra por
        el semáforo de hoy.
        """
        qs = Lote.objects.filter(eliminado=False)

        busqueda = self.request.query_params.get("q", "").strip()
        if busqueda:
            qs = qs.filter(
                Q(nombre__icontains=busqueda) | Q(numero_lote__icontains=busqueda)
            )

        estado = self.request.query_params.get("estado", "").upper()
        if estado in ESTADOS:
            # El estado de hoy es calculado, no una columna: no se puede
            # filtrar en SQL. Se resuelven los ids en Python y se vuelve a
            # un queryset para que la paginación siga funcionando.
            ids = [lote.pk for lote in qs if lote.estado_actual == estado]
            qs = qs.filter(pk__in=ids)

        return qs

    # ------------------------------------------------------------------
    # Escritura. El estado nunca viene del cliente: lo calcula la regla.
    # ------------------------------------------------------------------

    def perform_create(self, serializer):
        lote = serializer.save()
        lote.guardar_clasificado()

    def perform_update(self, serializer):
        """Al editar se vuelve a clasificar.

        Si cambió la cantidad o la fecha y no se recalculara, la ficha
        guardada quedaría mintiendo.
        """
        lote = serializer.save()
        lote.guardar_clasificado()

    def perform_destroy(self, instance):
        """DELETE hace borrado lógico, no borra la fila.

        La merma tiene que quedar registrada. El cliente igual recibe
        204 No Content, que es lo que REST espera de un DELETE.
        """
        instance.soft_delete()

    # ------------------------------------------------------------------
    # Endpoints propios de consulta
    # ------------------------------------------------------------------

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def vencidos(self, request):
        """GET /api/lotes/vencidos/ — los que hay que sacar como merma."""
        lotes = [l for l in Lote.objects.filter(eliminado=False) if l.estado_actual == "ROJO"]
        datos = self.get_serializer(lotes, many=True).data
        return Response(datos, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def resumen(self, request):
        """GET /api/lotes/resumen/ — el contador del semáforo."""
        contadores = dict.fromkeys(ESTADOS, 0)
        unidades_en_riesgo = 0

        for lote in Lote.objects.filter(eliminado=False):
            contadores[lote.estado_actual] = contadores.get(lote.estado_actual, 0) + 1
            if lote.estado_actual == "ROJO":
                unidades_en_riesgo += lote.cantidad

        return Response(
            {
                "hoy": timezone.localdate().isoformat(),
                "total": sum(contadores.values()),
                "por_estado": contadores,
                "unidades_en_riesgo": unidades_en_riesgo,
            },
            status=status.HTTP_200_OK,
        )
