"""Pasa los lotes de datos.json a la base de datos.

Se corre una sola vez, despues de migrate:
    python manage.py cargar_datos

Los registros que la base ya no acepta (categoria fuera de la lista o
cantidad <= 0) se informan y no se cargan: antes el JSON los dejaba
entrar y quedaban guardados como INVALIDO.
"""

import json
from datetime import date
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand

from core.models import Lote


class Command(BaseCommand):
    help = "Carga los lotes de datos.json en la base de datos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--archivo", default="datos.json", help="Ruta del JSON (por defecto datos.json)."
        )

    def handle(self, *args, **opciones):
        ruta = Path(opciones["archivo"])
        if not ruta.exists():
            self.stdout.write(self.style.ERROR(f"No se encontro {ruta}."))
            return

        registros = json.loads(ruta.read_text(encoding="utf-8"))
        cargados = rechazados = repetidos = 0

        for r in registros:
            lote = Lote(
                nombre=r["nombre"],
                categoria=r["categoria"],
                numero_lote=r["lote"],
                cantidad=r["cantidad"],
                vence=date.fromisoformat(r["vence"]),
            )

            # No duplicar si el comando se corre dos veces.
            if Lote.objects.filter(numero_lote=lote.numero_lote, nombre=lote.nombre).exists():
                repetidos += 1
                continue

            try:
                lote.full_clean(exclude=["estado_registro", "motivo_registro"])
            except ValidationError as error:
                rechazados += 1
                detalle = "; ".join(f"{c}: {m[0]}" for c, m in error.message_dict.items())
                self.stdout.write(
                    self.style.WARNING(f"  Rechazado '{r['nombre']}' ({r['lote']}): {detalle}")
                )
                continue

            lote.guardar_clasificado()
            cargados += 1

        self.stdout.write(self.style.SUCCESS(f"\nCargados: {cargados}"))
        if repetidos:
            self.stdout.write(f"Ya existian: {repetidos}")
        if rechazados:
            self.stdout.write(
                f"Rechazados por validacion: {rechazados} "
                "(la base ya no acepta esos datos; antes entraban como INVALIDO)"
            )
