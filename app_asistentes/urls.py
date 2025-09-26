from django.urls import path
from . import views


urlpatterns = [
    path('dashboard-asistente/', views.dashboard_asistente, name='dashboard_asistente'),
    path('evento/<int:eve_id>/detalle/', views.detalle_evento_asistente, name='detalle_evento_asistente'),
    path('evento/<int:eve_id>/compartir/', views.compartir_evento, name='compartir_evento'),
    path('descargar-programacion-asistente/<int:evento_id>/', views.descargar_programacion, name='descargar_programacion_asistente'),
    path('descargar-memorias-asistente/<int:evento_id>/', views.descargar_memorias_asistente, name='descargar_memorias_asistente'),
    path("manual/", views.manual_asistente, name="manual_asistente"),
]