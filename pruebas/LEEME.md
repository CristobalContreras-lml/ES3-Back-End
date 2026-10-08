# Evidencia de pruebas en cliente HTTP

Criterios **3.1.3** (códigos de estado) y **3.1.4** (API verificada con
pruebas en cliente HTTP).

## Qué hay aquí

`salida_curl.txt` — transcripción de 15 peticiones reales contra
`runserver`, cada una con el código de estado que devolvió.

Los tokens aparecen **truncados** a propósito. Un token completo en un
archivo que se entrega es una credencial publicada.

## Resumen de las 15 peticiones

| # | Petición | Esperado | Qué demuestra |
|---|---|---|---|
| 1 | `GET /api/lotes/` sin token | `401` | La API está cerrada por defecto |
| 2 | `POST /api/token/` | `200` | El endpoint entrega credenciales |
| 3 | `GET /api/lotes/` con token | `200` | Respuesta paginada |
| 4 | `POST /api/lotes/` válido | `201` | Created |
| 5 | `POST` con cantidad negativa y categoría inválida | `400` | La validación corta |
| 6 | `GET /api/lotes/1/` | `200` | Ficha individual |
| 7 | `GET /api/lotes/99999/` | `404` | Id que no existe |
| 8 | `PATCH /api/lotes/1/` | `200` | Edición parcial |
| 9 | `GET /api/lotes/?estado=ROJO` | `200` | Filtro por semáforo |
| 10 | `GET /api/lotes/resumen/` | `200` | Endpoint propio |
| 11 | `POST` con token del lector | `403` | El rol no alcanza |
| 12 | `DELETE` con token del lector | `403` | Forbidden, no 401 |
| 13 | `DELETE` con token del jefe | `204` | No Content |
| 14 | `POST /api/jwt/` | `200` | Access + refresh |
| 15 | `GET` con token inventado | `401` | Credencial falsa rechazada |

Los casos malos (1, 5, 7, 11, 12, 15) importan tanto como los buenos: un
`400` y un `404` bien devueltos valen lo mismo que un `201`.

La diferencia entre **11-12** y **15** es la que se suele confundir:
`403` es "sé quién eres y no puedes", `401` es "no sé quién eres".

## Cómo regenerar esta evidencia

Con el servidor andando (`python manage.py runserver`), en otra terminal.
Estos comandos son para **cmd de Windows**, donde las comillas dentro del
JSON van escapadas con `\`.

```bat
set API=http://127.0.0.1:8000

:: 1. Sin token  -> 401
curl -i %API%/api/lotes/

:: 2. Pedir el token  -> 200
curl -X POST -d "username=jefe&password=TU_CLAVE" %API%/api/token/

:: Copia el token de la respuesta y guardalo:
set TOKEN=Authorization: Token PEGA_AQUI_EL_TOKEN

:: 3. Listar  -> 200
curl -i -H "%TOKEN%" %API%/api/lotes/

:: 4. Crear  -> 201
curl -i -X POST -H "%TOKEN%" -H "Content-Type: application/json" ^
  -d "{\"nombre\":\"Queso gauda\",\"categoria\":\"Lacteos\",\"numero_lote\":\"L-4040\",\"cantidad\":15,\"vence\":\"2027-06-30\"}" ^
  %API%/api/lotes/

:: 5. Datos malos  -> 400
curl -i -X POST -H "%TOKEN%" -H "Content-Type: application/json" ^
  -d "{\"nombre\":\"X\",\"categoria\":\"Abarrotes\",\"numero_lote\":\"H-1\",\"cantidad\":-3,\"vence\":\"2027-06-30\"}" ^
  %API%/api/lotes/

:: 7. Id inexistente  -> 404
curl -i -H "%TOKEN%" %API%/api/lotes/99999/

:: 8. Editar un campo  -> 200
curl -i -X PATCH -H "%TOKEN%" -H "Content-Type: application/json" ^
  -d "{\"cantidad\":44}" %API%/api/lotes/1/

:: 10. Resumen  -> 200
curl -i -H "%TOKEN%" %API%/api/lotes/resumen/

:: 13. Dar de baja  -> 204
curl -i -X DELETE -H "%TOKEN%" %API%/api/lotes/1/

:: 15. Token inventado  -> 401
curl -i -H "Authorization: Token 0000000000" %API%/api/lotes/
```

Para el `403`, repite los pasos 2 y 4 con `username=lector` en vez de
`jefe`.

## Sin curl

`http://127.0.0.1:8000/api/docs/` abre la documentación navegable, donde
se prueba cada endpoint desde el navegador con botones.
