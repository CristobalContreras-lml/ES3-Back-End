# Monitoreo de vencimiento de insumos · Eva 3

**TI3V41 · Programación Back End · Unidad 3 · INACAP**
**Estudiante:** Cristóbal Contreras
**Docente:** Juan Pablo Díaz S.

Sistema de control de vencimientos para la bodega de una cocina central.
Cada lote que entra se clasifica con un semáforo de 4 resultados y queda
guardado en base de datos, con control de acceso por rol.

Esta entrega continúa la ES1 y la ES2. La regla de decisión
(`solucion.py`) es la misma desde la primera unidad y no se reescribió
nunca. Cada unidad cambió una capa distinta:

| Unidad | Dónde viven los datos | Quién consume |
|---|---|---|
| ES1 | `datos.json` | consola |
| ES2 | SQLite | una persona, por pantallas HTML |
| ES3 | SQLite *(la misma)* | **otro programa, por JSON** |

**La ES3 suma, no reemplaza.** Las pantallas HTML de la ES2 siguen
funcionando en `/`; la API vive aparte en `/api/`. Son dos interfaces
sobre el mismo modelo, la misma base y la misma regla.

---

## 1. Puesta en marcha desde cero

Probado con Python 3.14 y Django 6.1 (la suite también se verificó con Python 3.13).

```bash
# 1. Entorno virtual
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate      # Linux / macOS

# 2. Dependencias
pip install -r requirements.txt

# 3. Variables de entorno
copy .env.example .env          # Windows
# cp .env.example .env           # Linux / macOS
```

Abre el `.env` y completa los valores. La `SECRET_KEY` se genera con:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Define también las tres contraseñas de prueba (`PASS_ADMIN`,
`PASS_NORMAL`, `PASS_VIEWER`). **No hay ninguna contraseña escrita en el
código**: si falta la variable, el usuario no se crea.

```bash
# 4. Crear las tablas
python manage.py migrate

# 5. Crear los grupos y los usuarios de prueba
python manage.py crear_roles

# 6. Pasar los datos de la ES1 a la base (opcional)
python manage.py cargar_datos

# 7. Superusuario para el administrador de Django
python manage.py createsuperuser

# 8. Levantar
python manage.py runserver
```

Quedan dos interfaces andando sobre la misma base:

| Dirección | Qué es |
|---|---|
| `http://127.0.0.1:8000/` | Las pantallas HTML de la ES2 |
| `http://127.0.0.1:8000/api/lotes/` | La API REST de la ES3 |
| `http://127.0.0.1:8000/api/docs/` | La documentación navegable |
| `http://127.0.0.1:8000/admin/` | El administrador de Django |

| Dirección | Para qué |
|---|---|
| `http://127.0.0.1:8000/` | Inventario (requiere sesión) |
| `http://127.0.0.1:8000/login/` | Entrar |
| `http://127.0.0.1:8000/admin/` | Administrador de Django |

### Verificación

```bash
python manage.py check                        # sin issues
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py test                         # 29 tests OK
```

---

---

## 2. API REST

### 2.1 Endpoints

El recurso es `lotes`: sustantivo, en plural. Ninguna URL lleva un verbo
—no existe `/api/crearLote/`— porque el verbo lo pone HTTP. Las cinco
rutas del CRUD las genera el `DefaultRouter`, no están escritas a mano.

| Método | Endpoint | Qué hace | Éxito | Quién puede |
|---|---|---|---|---|
| `GET` | `/api/lotes/` | Lista paginada, 10 por página | `200` | los tres roles |
| `POST` | `/api/lotes/` | Registra un lote nuevo | `201` | jefe, bodeguero |
| `GET` | `/api/lotes/{id}/` | Ficha de un lote | `200` | los tres roles |
| `PUT` | `/api/lotes/{id}/` | Reemplaza el registro completo | `200` | solo jefe |
| `PATCH` | `/api/lotes/{id}/` | Cambia un campo suelto | `200` | solo jefe |
| `DELETE` | `/api/lotes/{id}/` | Da de baja (borrado lógico) | `204` | solo jefe |
| `GET` | `/api/lotes/vencidos/` | Los que hay que sacar como merma | `200` | autenticado |
| `GET` | `/api/lotes/resumen/` | Contadores del semáforo | `200` | autenticado |
| `POST` | `/api/token/` | Entrega un token simple | `200` | cualquiera con clave |
| `POST` | `/api/jwt/` | Entrega `access` + `refresh` | `200` | cualquiera con clave |
| `POST` | `/api/jwt/refresh/` | Renueva el `access` | `200` | con `refresh` válido |
| `GET` | `/api/docs/` | Documentación navegable (Swagger) | `200` | autenticado |
| `GET` | `/api/schema/` | Esquema OpenAPI en YAML | `200` | autenticado |

Filtros sobre la lista, los mismos de la pantalla HTML:
`/api/lotes/?q=queso` busca por nombre o número de lote, y
`/api/lotes/?estado=ROJO` filtra por el semáforo de hoy.

### 2.2 Códigos de estado

| Código | Cuándo |
|---|---|
| `200 OK` | La lectura o la edición salió bien |
| `201 Created` | Se creó el lote |
| `204 No Content` | Se dio de baja, no hay nada que devolver |
| `400 Bad Request` | El JSON no pasó la validación |
| `401 Unauthorized` | No mandaste token, o el token no sirve |
| `403 Forbidden` | Mandaste token válido, pero tu rol no alcanza |
| `404 Not Found` | Ese id no existe, o el lote ya está dado de baja |

La diferencia entre `401` y `403` importa: `401` es "no sé quién eres",
`403` es "sé quién eres y no puedes". Un lector autenticado que intenta
`POST` recibe `403`, no `401`.

### 2.3 Cómo consumirla

```bash
# 1. Pedir el token
curl -X POST -d "username=jefe&password=TU_CLAVE" \
     http://127.0.0.1:8000/api/token/
# respuesta: {"token":"084fcbe9..."}

# 2. Usarlo en la cabecera de todas las demás peticiones
curl -H "Authorization: Token 084fcbe9..." \
     http://127.0.0.1:8000/api/lotes/

# 3. Crear un lote
curl -X POST -H "Authorization: Token 084fcbe9..." \
     -H "Content-Type: application/json" \
     -d '{"nombre":"Queso gauda","categoria":"Lacteos",
          "numero_lote":"L-4040","cantidad":15,"vence":"2027-06-30"}' \
     http://127.0.0.1:8000/api/lotes/
```

El token va **en la cabecera `Authorization`**, nunca en la URL ni escrito
dentro del código: la URL queda registrada en el historial del navegador y
en los logs del servidor. En este README y en `pruebas/` los tokens
aparecen truncados a propósito.

Si prefieres no usar `curl`, `/api/docs/` abre una página donde se prueba
cada endpoint desde el navegador.

### 2.4 Por qué está configurada así

El bloque `REST_FRAMEWORK` de `settings.py` es el default de todo el
proyecto. Cuatro decisiones y su razón:

**Token y no sesión.** La sesión de la ES2 vive en una cookie, y una
cookie supone un navegador que la guarda y la reenvía sola. Un programa
cliente no tiene navegador: se identifica mandando su credencial en cada
petición. `SessionAuthentication` se dejó además de token, pero solo para
que la interfaz navegable de DRF funcione mientras se desarrolla; el
cliente real usa token.

**Dos esquemas de token, no uno.** `/api/token/` entrega el token simple
de DRF, que no expira. `/api/jwt/` entrega un JWT que caduca a los 30
minutos y trae un `refresh` para renovarlo. El token simple es más fácil
de explicar y es el que pide el guion; el JWT es el que de verdad
conviene, porque si alguien copia un token de una cabecera, con JWT deja
de servir solo en media hora. Están los dos y el cliente elige.

**`IsAuthenticated` como default.** El default seguro es que todo pida
autenticación y que una vista tenga que abrirse a propósito, no al revés.
Si el default fuera `AllowAny`, bastaría olvidar una línea en un endpoint
nuevo para dejarlo abierto a internet sin que nadie lo note.

**`PAGE_SIZE = 10`.** La bodega puede llegar a tener cientos de lotes y el
cliente típico es una pantalla de inventario o un lector de código de
barras. Diez filas es lo que se alcanza a mostrar sin pedir más, y evita
que una sola petición arrastre la tabla completa.

### 2.5 El estado no lo manda el cliente

Es la decisión de diseño que viene desde la ES2 y acá se vuelve un asunto
de seguridad, no solo de correctitud.

`estado_registro`, `motivo_registro`, `fecha_registro`, `estado_actual`,
`dias_restantes` y `cambio_de_estado` están en `read_only_fields`. El
estado lo calcula `clasificar_insumo()` dentro de `perform_create()`.

Si fueran editables, un cliente podría mandar:

```json
{"nombre": "Queso", "vence": "2026-01-01", "estado_registro": "VERDE"}
```

y declarar vigente un lote podrido. Es exactamente lo que este sistema
existe para evitar. Hay un test que lo comprueba:
`SerializadorTest.test_el_cliente_no_puede_declarar_el_estado`.

Por la misma razón `fields` enumera los campos uno por uno en vez de usar
`"__all__"`: con `__all__`, cualquier campo que se agregue mañana al
modelo queda expuesto sin que nadie lo haya decidido.

### 2.6 Permisos por rol

Los tres grupos de la ES2 (`admin`, `normal`, `viewer`) valen igual en la
API. `core/permissions.py` no inventa roles nuevos: llama a la misma
función `tiene_rol()` que usan los decoradores de las vistas HTML.

| Rol | Usuario | `GET` | `POST` | `PUT`/`PATCH` | `DELETE` |
|---|---|---|---|---|---|
| admin | `jefe` | sí | sí | sí | sí |
| normal | `bodeguero` | sí | sí | — | — |
| viewer | `lector` | sí | — | — | — |

Es deliberado que la fuente de autorización sea una sola. Si la API
tuviera su propia tabla de permisos, bastaría un descuido para que el
bodeguero pudiera borrar por `/api/` lo que no puede borrar por la
pantalla.

### 2.7 Borrado lógico y `204`

`DELETE` devuelve `204 No Content`, que es lo que REST espera, pero por
dentro llama a `soft_delete()`: marca la fila y no la borra. La merma
tiene que quedar registrada. El lote deja de aparecer en `GET /api/lotes/`
y un segundo `DELETE` sobre el mismo id devuelve `404`, porque para la API
ya no existe.

---

## 3. Conexión a la base de datos

La conexión no está escrita a mano en `settings.py`: se arma con
variables de entorno leídas con `python-decouple`.

```python
DB_ENGINE = config("DB_ENGINE", default="django.db.backends.sqlite3")

if DB_ENGINE.endswith("sqlite3"):
    DATABASES = {"default": {"ENGINE": DB_ENGINE,
                             "NAME": BASE_DIR / config("DB_NAME", default="db.sqlite3")}}
else:
    DATABASES = {"default": {"ENGINE": DB_ENGINE,
                             "NAME": config("DB_NAME"),
                             "USER": config("DB_USER"),
                             "PASSWORD": config("DB_PASSWORD"), ...}}
```

Por defecto es SQLite, que es lo que pide la unidad y no necesita
credenciales. La rama de PostgreSQL queda escrita para que el día que se
cambie de motor sólo se edite el `.env`: **en el código no hay ni un
usuario ni una contraseña de base de datos.**

También salen del `.env` la `SECRET_KEY`, el `DEBUG` y los
`ALLOWED_HOSTS`.

---

## 4. Modelo de datos

Cada clave del antiguo `datos.json` pasó a ser un campo:

| `datos.json` | Modelo `Lote` | Tipo |
|---|---|---|
| `nombre` | `nombre` | `CharField(100)` |
| `categoria` | `categoria` | `CharField` con `choices` |
| `lote` | `numero_lote` | `CharField(30)` |
| `cantidad` | `cantidad` | `IntegerField` ≥ 1 |
| `vence` | `vence` | `DateField` |
| `estado` | `estado_registro` | `CharField` (foto al registrar) |
| `motivo` | `motivo_registro` | `CharField(300)` |
| `registrado` | `fecha_registro` | `DateTimeField` |
| — | `eliminado`, `fecha_eliminacion` | borrado lógico |

Las categorías válidas **no están escritas dos veces**: el `choices` se
genera desde el diccionario `UMBRALES` de `solucion.py`.

```python
CATEGORIA_CHOICES = [(c, c) for c in UMBRALES]
```

### Por qué hay dos estados y no uno

El guion de la unidad guarda el resultado en un campo y lo muestra. Acá
eso no sirve: **el estado de este proyecto cambia solo con el paso de los
días.** Un lote registrado como VERDE es ROJO dos semanas después aunque
nadie toque la ficha.

La solución son dos cosas distintas:

- `estado_registro`: la foto del día en que entró el lote. Es un campo
  guardado y sirve de trazabilidad.
- `estado_actual`: una `@property` que llama a `clasificar_insumo()` con
  la fecha de hoy. Es lo que se muestra en el inventario.

Cuando los dos no coinciden, la lista lo avisa («registrado como VERDE»).
Es la misma decisión que ya había tomado la vista de la ES1.

---

## 5. Administrador de Django

`LoteAdmin` incluye:

- `list_display` con 8 columnas, incluido un semáforo con color.
- `list_filter` por categoría, estado de baja y fecha de vencimiento.
- `search_fields` por nombre y número de lote, y `date_hierarchy`.
- `readonly_fields` sobre los campos calculados: el estado de registro y
  las fechas no se editan a mano, porque si se pudieran escribir la ficha
  podría mentir.
- `fieldsets` que separan datos del lote, clasificación y trazabilidad.
- Dos acciones masivas: dar de baja (borrado lógico) y restaurar.
- `save_model` reclasifica al guardar, igual que el CRUD web.
- `has_delete_permission` reserva el **borrado físico** al superusuario:
  la merma tiene que quedar registrada.

Los permisos de cada grupo (`view_lote`, `add_lote`, `change_lote`) se
asignan en `crear_roles`, así que el administrador respeta los mismos
roles que la aplicación.

---

## 6. CRUD y roles

| Vista | URL | Quién puede |
|---|---|---|
| Listar (READ) | `/` | admin, normal, viewer |
| Crear (CREATE) | `/lotes/crear/` | admin, normal |
| Ver ficha | `/lotes/<pk>/` | admin |
| Editar (UPDATE) | `/lotes/<pk>/editar/` | admin |
| Dar de baja (DELETE lógico) | `/lotes/<pk>/eliminar/` | admin |

El permiso se aplica con el decorador `@requiere_rol(...)` de
`core/permisos.py`, **en el servidor**. La plantilla también esconde los
botones que no corresponden, pero eso es sólo comodidad: el
`{% if es_admin %}` va *además* del decorador, nunca en su lugar.

Comprobado escribiendo las direcciones a mano con cada usuario:

```
lector      /lotes/crear/ -> BLOQUEADO   /lotes/1/editar/ -> BLOQUEADO
bodeguero   /lotes/crear/ -> permitido   /lotes/1/editar/ -> BLOQUEADO
jefe        /lotes/crear/ -> permitido   /lotes/1/editar/ -> permitido
sin sesión  /lotes/crear/ -> /login/?next=/lotes/crear/
```

### Validación y mensajes

La validación vive en `LoteForm` (`core/forms.py`), no repartida dentro
de la vista, así el mismo formulario sirve para crear y para editar:

- nombre de al menos 3 caracteres, número de lote normalizado a mayúsculas;
- cantidad entera entre 1 y 100.000 (`"diez"` devuelve el formulario con
  el error, no un error 500);
- año de vencimiento razonable;
- regla de negocio en `clean()`: **no se recibe en bodega un lote ya
  vencido**, usando la misma clasificación de `solucion.py`.

Cada acción deja un mensaje con `django.contrib.messages`.

---

## 7. Seguridad

| Medida | Dónde |
|---|---|
| Contraseñas cifradas (PBKDF2) | `User` de Django, nunca un modelo propio |
| CSRF | `{% csrf_token %}` en los 4 formularios POST, incluido el logout |
| Permisos por rol | decorador en el servidor |
| Secretos fuera del código | `.env` + `python-decouple` |
| Cookie de sesión | `HttpOnly`, expira en 8 h o al cerrar el navegador |
| `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE` | activas cuando `DEBUG=False` |
| Clickjacking y sniffing | `X_FRAME_OPTIONS=DENY`, `nosniff` |
| Mensaje de login genérico | no revela si falló el usuario o la contraseña |

El logout es POST, no un enlace GET: así no se puede cerrar la sesión de
alguien desde una imagen o un link externo.

---

## 8. Pruebas

**57 tests en verde**: los 29 de la ES2 en `core/tests.py`, que siguen
pasando sin tocarse, más 28 de la API en `core/tests_api.py`.

### Pantallas HTML · `core/tests.py`

| Clase | Qué cubre |
|---|---|
| `ReglaDeDecisionTest` | los 4 resultados y que cada categoría use su propio umbral |
| `ModeloTest` | borrado lógico y que el estado guardado envejezca mientras el actual no |
| `CrudTest` | crear, editar (reclasifica), dar de baja, 404, buscador, datos inválidos |
| `PermisosTest` | cada rol contra cada URL, incluido POST directo sin pasar por el botón |
| `SesionTest` | login, logout, mensaje genérico, contraseña nunca en texto plano |
| `CsrfTest` | POST sin token devuelve 403 |

### API REST · `core/tests_api.py`

| Clase | Criterio | Qué cubre |
|---|---|---|
| `AutenticacionTest` | 3.1.2 | sin token es 401, con token 200, token inventado 401, JWT trae access y refresh |
| `PermisosApiTest` | 3.1.2 | cada rol contra cada verbo: el lector no crea, el bodeguero crea pero no borra |
| `CodigosDeEstadoTest` | 3.1.3 | 200, 201, 204, 400, 404 y que la lista venga paginada |
| `SerializadorTest` | 3.1.3 | el cliente no puede declarar el estado, y no se exponen campos sensibles |
| `RestfulTest` | 3.1.4 | la URL es sustantivo plural, un GET no modifica nada, el DELETE es lógico |

```
python manage.py test
Ran 57 tests
OK
```

### Evidencia en cliente HTTP · `pruebas/`

| Archivo | Qué es | Quién lo generó |
|---|---|---|
| `salida_local.txt` | 16 peticiones contra el servidor, con el código de estado de cada una | el estudiante, con `pruebas/correr_pruebas.py` en su computador |
| `salida_curl.txt` | las mismas pruebas con `curl`, en otra corrida | el asistente de IA, en su propio entorno |
| `LEEME.md` | cómo repetir las pruebas a mano con `curl` | — |

Las dos transcripciones incluyen los casos malos, que valen tanto como los
buenos: sin token (`401`), con datos inválidos (`400`), con un id inexistente
(`404`) y con un rol sin permiso (`403`). Los tokens aparecen truncados y las
contraseñas nunca se escriben.

Para repetirlas, con el servidor andando en otra terminal:

```
python pruebas\correr_pruebas.py
```

---

## 9. Estructura

```
miproyecto/
├── solucion.py            # regla de decision de la ES1, intacta
├── datos.json             # datos de la ES1, ya migrados
├── manage.py
├── .env.example           # plantilla, sin valores
├── requirements.txt
├── plan.md  ia.md  README.md
├── pruebas/               # evidencia curl de cada endpoint
├── miproyecto/
│   ├── settings.py        # BD y secretos por variables de entorno
│   └── urls.py
└── core/
    ├── models.py          # Lote
    ├── forms.py           # LoteForm con validaciones
    ├── views.py           # CRUD HTML + login/logout   (ES2, intacto)
    ├── serializers.py     # LoteSerializer             (ES3)
    ├── api_views.py       # LoteViewSet                (ES3)
    ├── permissions.py     # PermisoLote por rol        (ES3)
    ├── admin.py           # LoteAdmin
    ├── permisos.py        # requiere_rol (lo usan las dos interfaces)
    ├── context_processors.py
    ├── tests.py           # 29 pruebas de la ES2
    ├── tests_api.py       # 28 pruebas de la API
    ├── migrations/0001_initial.py
    ├── management/commands/
    │   ├── crear_roles.py
    │   └── cargar_datos.py
    └── templates/         # base, lista, form, confirmar, detalle, login
```

---

## 10. Nota sobre los datos migrados

De los 8 registros de `datos.json` se cargaron 6. Los otros dos tenían
categorías fuera de la lista (`Abarrotes`, `Conservas y salsas`) y la base
los rechaza:

```
Rechazado 'Harina sin cernir' (H-0104): categoria: Valor 'Abarrotes' no es una opción válida.
Rechazado 'Tomate triturado' (TM-8834A): categoria: Valor 'Conservas y salsas' no es una opción válida.
```

No es un error del script: es la diferencia entre el JSON y una base de
datos. Antes el dato malo entraba y quedaba guardado como `INVALIDO`;
ahora el `choices` lo frena en la puerta. El resultado `INVALIDO` sigue
existiendo en la regla y sigue probado, porque los datos antiguos que ya
están en la base pueden quedar en ese estado.
