# plan.md · Monitoreo de vencimiento de insumos

**Asignatura:** TI3V41 · Programación Back End · **Unidad 2 · Eva 2**
**Estudiante:** Cristóbal Contreras
**Docente:** Juan Pablo Díaz S.

> Actualizado para la Eva 2. En la ES1 este documento decía «sin base de
> datos» y dejaba el login en *Won't*. Las dos cosas cambiaron: ahora hay
> SQLite, CRUD completo, roles y borrado lógico. Lo que **no** cambió es
> la regla de decisión del apartado técnico.

---

## 1. Apartado de negocio

### Problema

En la bodega de una cocina central (banquetería / cadena de restaurantes
chicos) se manejan cientos de insumos con vidas útiles distintas. Cada
semana se botan cajas de productos caros —quesos, carnes, salsas
preparadas— porque quedaron al fondo del estante o debajo de lotes más
nuevos y nadie vio que se estaban venciendo. Se rompe la regla básica de
rotación FIFO (*First In, First Out*). A quien le molesta: al jefe de
cocina, que descubre la pérdida cuando ya no hay nada que hacer, y al
dueño, que paga esa merma.

A eso se suma un problema que la ES1 dejó a la vista: cuando los datos
viven en un archivo JSON, **cualquiera que abra la carpeta puede editar o
borrar un registro sin dejar rastro**, y no hay forma de saber quién lo
hizo. En una bodega donde el bodeguero, el jefe de cocina y el dueño usan
el mismo sistema, eso no sirve.

### Solución

El programa recibe los datos de un lote que entra a bodega y responde de
inmediato con un semáforo: rojo si está vencido, amarillo si vence dentro
del plazo de alerta de su categoría, verde si está vigente, y un cuarto
resultado cuando el dato ingresado no tiene sentido.

En esta entrega los lotes se guardan en una base de datos, se consultan
desde una aplicación web con sesión iniciada, y **cada persona puede
hacer sólo lo que le corresponde**: el bodeguero registra lo que llega,
el jefe de cocina corrige y da de baja, y el dueño mira. Un lote dado de
baja no se borra: queda registrado para poder medir la merma.

### Alcance

**Entra:**

- Base de datos SQLite con el modelo `Lote` y migraciones versionadas.
- CRUD web completo: listar, crear, editar y dar de baja.
- Borrado lógico, con fecha de baja.
- Login y tres roles (admin, normal, viewer) aplicados en el servidor.
- Administrador de Django personalizado para la gestión de la colección.
- Buscador por insumo o número de lote y filtro por estado del semáforo.
- Recálculo del semáforo con la fecha de hoy en cada consulta.
- Ingreso por consola (`solucion.py`), que se conserva de la ES1.

**No entra:** API REST, envío de correos, lectura de códigos de barra,
exportación a CSV o PDF, recuperación de contraseña por correo,
despliegue en un servidor real.

### Priorización MoSCoW

**Must · imprescindible (esto es lo que se entrega)**

1. Modelo `Lote` en base de datos, con las categorías validadas contra la
   lista de `solucion.py`.
2. Migraciones creadas y aplicadas, con `makemigrations --check` limpio.
3. CRUD completo con validación, manejo de errores y mensajes al usuario.
4. Borrado lógico: la ficha se oculta, la merma queda registrada.
5. Login, logout y tres roles aplicados con decorador en el servidor.
6. Administrador de Django con columnas, filtros, buscador y permisos.
7. Credenciales y secretos fuera del código, en `.env`.
8. Batería de pruebas que cubra la regla, el CRUD, los permisos y el CSRF.

*(Los puntos 5 y 8 estaban en Won't en la ES1. El login se movió a Must
porque sin sesión no se puede distinguir quién hace cada cosa, que es
justamente el problema nuevo que apareció al dejar el JSON.)*

**Should · importante (queda escrito, no programado)**

- Historial de cambios por lote: quién editó qué y cuándo.
- Pantalla de mermas con el total perdido en el mes.
- Avisar en la portada cuántos lotes pasarán a rojo esta semana.

**Could · deseable**

- Exportar el listado de vencidos a CSV o PDF.
- Aviso por correo cuando un lote pasa a rojo.
- Carga masiva de lotes desde una planilla.

**Won't · fuera por ahora**

- API REST para que otro sistema consulte el inventario.
- Escaneo de códigos de barra con la cámara.
- Pronósticos automáticos de compra o integración con proveedores.
- Varias bodegas o sucursales.

---

## 2. Apartado técnico

### Datos de entrada

| Dato | Campo del modelo | Tipo | Validación |
|---|---|---|---|
| Nombre del insumo | `nombre` | `CharField(100)` | mínimo 3 caracteres |
| Categoría | `categoria` | `CharField` con `choices` | debe estar en `UMBRALES` |
| Número de lote | `numero_lote` | `CharField(30)` | se normaliza a mayúsculas |
| Cantidad | `cantidad` | `IntegerField` | entero entre 1 y 100.000 |
| Fecha de vencimiento | `vence` | `DateField` | no se recibe un lote ya vencido |

Dato calculado: **días restantes** = fecha de vencimiento − fecha de hoy.

Cada categoría tiene su propio plazo de alerta: Verduras 3 días, Carnes
5, Lácteos 7, Salsas 10, Empaques 30.

### Regla de decisión · 4 resultados

**No cambió respecto de la ES1.** Vive en `solucion.py` y se importa
desde el modelo; no está copiada en ningún otro archivo.

| # | Resultado | Cuándo ocurre |
|---|---|---|
| 1 | **INVÁLIDO** | fecha ilegible **o** cantidad ≤ 0 **o** categoría fuera de la lista |
| 2 | **ROJO** | los días restantes son 0 o menos |
| 3 | **AMARILLO** | los días restantes ≤ el plazo de alerta de su categoría |
| 4 | **VERDE** | los días restantes superan ese plazo |

El caso inválido va **primero** en el `if`: una fecha ilegible no se
puede comparar con nada.

### Estado guardado vs. estado de hoy

Es la decisión de diseño principal de esta entrega. El modelo guarda
`estado_registro` (la foto del día en que entró el lote) y calcula
`estado_actual` con una `@property` que vuelve a llamar a la regla con la
fecha de hoy.

Si sólo se guardara el estado, un lote registrado como VERDE seguiría
apareciendo verde para siempre, que es exactamente el error que este
sistema debe evitar. Si sólo se calculara, se perdería la trazabilidad de
cómo entró el lote. Por eso están los dos, y la lista avisa cuando no
coinciden.

### Base de datos

SQLite, configurada con variables de entorno (`DB_ENGINE`, `DB_NAME`).
`settings.py` deja escrita también la rama de PostgreSQL para que cambiar
de motor sea editar el `.env` y no el código.

### Roles y permisos

| Rol | Grupo | Listar | Crear | Editar | Dar de baja |
|---|---|---|---|---|---|
| Dueño / auditor | `viewer` | sí | no | no | no |
| Bodeguero | `normal` | sí | sí | no | no |
| Jefe de cocina | `admin` | sí | sí | sí | sí |

El permiso se aplica con el decorador `@requiere_rol(...)` en el
servidor. Los mismos grupos tienen asignados los permisos de Django
(`view_lote`, `add_lote`, `change_lote`), así que el administrador
respeta las mismas reglas.

### Paquetes externos

- `tabulate` — resumen en consola, se conserva de la ES1.
- `python-decouple` — lee el `.env` para no tener secretos en el código.
