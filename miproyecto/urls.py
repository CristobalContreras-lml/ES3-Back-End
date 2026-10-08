"""Direcciones del proyecto.

Dos interfaces sobre el mismo modelo:

    /          pantallas HTML de la ES2 (sesión con cookie)
    /api/      API REST de la ES3 (token en la cabecera)

Ninguna ruta de la ES2 se eliminó. La API vive aparte, bajo /api/.
"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from core import views
from core.api_views import LoteViewSet

# El router genera las cinco rutas del ViewSet. No se escribe ninguna a
# mano: así no aparecen URLs con verbos como /api/crearLote/, que es lo
# que rompe el criterio RESTful.
router = DefaultRouter()
router.register(r"lotes", LoteViewSet, basename="lote")

urlpatterns = [
    path("admin/", admin.site.urls),
    # --- Sesión (ES2) ---
    path("login/", views.vista_login, name="login"),
    path("logout/", views.vista_logout, name="logout"),
    # --- API (ES3) ---
    path("api/", include(router.urls)),
    # Credenciales: token simple del guion, y JWT con expiración y refresco
    path("api/token/", obtain_auth_token, name="api_token"),
    path("api/jwt/", TokenObtainPairView.as_view(), name="jwt_obtener"),
    path("api/jwt/refresh/", TokenRefreshView.as_view(), name="jwt_refrescar"),
    # Documentación generada desde el propio código
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger",
    ),
    # --- CRUD HTML (ES2) ---
    path("", views.lista, name="lista"),
    path("lotes/crear/", views.crear, name="crear"),
    path("lotes/<int:pk>/", views.detalle, name="detalle"),
    path("lotes/<int:pk>/editar/", views.editar, name="editar"),
    path("lotes/<int:pk>/eliminar/", views.eliminar, name="eliminar"),
]
