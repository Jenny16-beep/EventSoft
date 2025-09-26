from django.urls import path
from . import views
from django.urls import path

urlpatterns = [
    path('dashboard-superadmin' , views.dashboard, name='dashboard_superadmin'),
    path("manual/superadmin/", views.manual_super_admin, name="manual_super_admin"),
    path("manual/tecnico/", views.manual_tecnico_operacion, name="manual_tecnico_operacion"),
    path('listar-eventos/<str:estado>/', views.listar_eventos_estado, name='listar_eventos_estado'),
    path('detalle-evento-admin/<int:eve_id>/', views.detalle_evento_admin, name='detalle_evento_admin'),
    path('descargar-programacion/<int:eve_id>/', views.descargar_programacion, name='descargar_programacion_admin'),
    path('crear-administrador-evento/', views.crear_administrador_evento, name='crear_administrador_evento'),
    path('listar-administradores/', views.listar_administradores_evento, name='listar_administradores_evento'),
    path('eliminar-administrador/<int:admin_id>/', views.eliminar_administrador, name='eliminar_administrador'),
    path('crear-area-categoria/', views.crear_area_categoria, name='crear_area_categoria'),
    path('crear-codigo-invitacion-admin/', views.crear_codigo_invitacion_admin, name='crear_codigo_invitacion_admin'),
    path('listar-codigos-invitacion-admin/', views.listar_codigos_invitacion_admin, name='listar_codigos_invitacion_admin'),
    path('accion-codigo-invitacion-admin/<str:codigo>/<str:accion>/', views.accion_codigo_invitacion_admin, name='accion_codigo_invitacion_admin'),
]