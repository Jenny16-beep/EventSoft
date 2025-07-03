from django.urls import path
from . import views

urlpatterns = [
    path('dashboard-participante/', views.dashboard_participante_general, name='dashboard_participante_general'),
    path('dashboard-participante/evento/<int:evento_id>/', views.dashboard_participante_evento, name='dashboard_participante_evento'),
    path('modificar-preinscripcion/<int:evento_id>', views.modificar_preinscripcion, name='modificar_preinscripcion_participante'),
    path('cancelar-inscripcion-participante/', views.cancelar_inscripcion, name='cancelar_preinscripcion_participante'),
    path('ver-qr-participante/<int:evento_id>/', views.ver_qr_participante, name='ver_qr_participante'),
    path('desacargar-qr-participante/<int:evento_id>/', views.descargar_qr_participante, name='descargar_qr_participante'),
    path('evento-completo-participante/<int:evento_id>/', views.ver_evento_completo, name='ver_evento_completo_participante'),
    path('instrumentos-participante/<int:evento_id>/', views.instrumento_evaluacion, name='instrumento_evaluacion_participante'),
    path('calificaciones-participante/<int:evento_id>/', views.ver_calificaciones_participante, name='calificaciones_participante'),
    
    
]