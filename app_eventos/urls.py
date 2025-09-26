from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

urlpatterns = [
    path('', views.ver_eventos, name='ver_eventos'),
    path("manual/", views.manual_visitante, name="manual_visitante"),
    path('detalle-evento/<int:eve_id>/', views.detalle_evento, name='detalle_evento_visitante'),
    path('<int:eve_id>/compartir/', views.compartir_evento_visitante, name='compartir_evento_visitante'),
    path('inscripcion-asistente/<int:eve_id>/', views.inscripcion_asistente, name='inscripcion_asistente'),
    path('inscripcion-participante/<int:eve_id>/', views.inscribirse_participante, name='inscripcion_participante'),
    path('inscripcion-evaluador/<int:eve_id>/', views.inscribirse_evaluador, name='inscripcion_evaluador'),
    path('registro-con-codigo/<str:codigo>/', views.registro_con_codigo, name='registro_con_codigo'),
    path('logout/', LogoutView.as_view(next_page='ver_eventos'), name='logout'),
    path('confirmar-registro/<str:token>/', views.confirmar_registro, name='confirmar_registro'),
    path('registro_admin_evento/', views.registrarse_admin_evento, name='registro_admin_evento'),
    path('inscribir-otro-expositor/<int:eve_id>/<str:codigo>/', views.inscribir_otro_expositor, name='inscribir_otro_expositor'),
]