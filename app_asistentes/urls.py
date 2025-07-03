from django.urls import path
from . import views


urlpatterns = [
    path('dashboard-asistente/', views.dashboard_asistente, name='dashboard_asistente'),
    path('evento/<int:eve_id>/detalle/', views.detalle_evento_asistente, name='detalle_evento_asistente'),
    path('descargar-programacion-asistente/<int:evento_id>/', views.descargar_programacion, name='descargar_programacion_asistente'),
    
]