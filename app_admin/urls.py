from django.urls import path
from . import views

urlpatterns = [
    path('dashboard-superadmin' , views.dashboard, name='dashboard_superadmin'),
    path('listar-eventos/<str:estado>/', views.listar_eventos_estado, name='listar_eventos_estado'),
    path('detalle-evento-admin/<int:eve_id>/', views.detalle_evento_admin, name='detalle_evento_admin'),
    path('descargar-programacion/<int:eve_id>/', views.descargar_programacion, name='descargar_programacion_admin'),
    path('crear/', views.crear_administrador_evento, name='crear_administrador_evento'),
    path('listar-administradores/', views.listar_administradores_evento, name='listar_administradores_evento'),
    path('eliminar-administrador/<int:admin_id>/', views.eliminar_administrador, name='eliminar_administrador'),

]