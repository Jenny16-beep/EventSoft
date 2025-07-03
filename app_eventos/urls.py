from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views


urlpatterns = [
    path('', views.ver_eventos, name='ver_eventos'),
    path('detalle-evento/<int:eve_id>/', views.detalle_evento, name='detalle_evento_visitante'),
    path('inscripcion-asistente/<int:eve_id>/', views.inscripcion_asistente, name='inscripcion_asistente'),
    path('inscripcion-participante/<int:eve_id>/', views.inscribirse_participante, name='inscripcion_participante'),
    path('inscripcion-evaluador/<int:eve_id>/', views.inscribirse_evaluador, name='inscripcion_evaluador'),
    path('logout/', LogoutView.as_view(next_page='ver_eventos'), name='logout'),
    

    
    
]