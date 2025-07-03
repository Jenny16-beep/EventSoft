
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from django.contrib import admin



urlpatterns = [
    path('admin-django/', admin.site.urls),
    path('admin/', include('app_admin.urls')),
    path('participante/', include('app_participantes.urls')),
    path('evaluador/', include('app_evaluadores.urls')),
    path('asistente/', include('app_asistentes.urls')),
    path('admin-evento/', include('app_administradores.urls')),
    path('evento/', include('app_eventos.urls')),
    path('usuario/', include('app_usuarios.urls')),
    
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)