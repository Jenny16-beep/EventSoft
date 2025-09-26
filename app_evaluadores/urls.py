from django.urls import path
from . import views

urlpatterns = [
    path('dashboard-evaluador/', views.dashboard_evaluador, name='dashboard_evaluador'),
    path('gestionar-items/<int:eve_id>/', views.gestionar_items, name='gestionar_items_evaluador'),
    path('agregar-item/<int:eve_id>/', views.agregar_item, name='agregar_item_evaluador'),
    path('editar-item/<int:criterio_id>/', views.editar_item, name='editar_item_evaluador'),
    path('eliminar-item/<int:criterio_id>/', views.eliminar_item, name='eliminar_item_evaluador'),
    path('lista-participantes-evaluador/<int:eve_id>/', views.lista_participantes, name='lista_participantes_evaluador'),
    path('calificar-participante/<int:eve_id>/<int:participante_id>/', views.calificar_participante, name='calificar_participante_evaluador'),
    path('tabla-posiciones/<int:eve_id>/', views.ver_tabla_posiciones, name='tabla_posiciones_evaluador'),
    path('descargar-tabla-posiciones-pdf/<int:eve_id>/', views.descargar_tabla_posiciones_pdf, name='descargar_tabla_posiciones_pdf'),
    path('informacion-detallada/<int:eve_id>/', views.informacion_detallada, name='informacion_detallada_evaluador'),
    path('evento-cancelar-evaluador/<int:evento_id>/', views.cancelar_inscripcion_evaluador, name='cancelar_inscripcion_evaluador'),
    path('modificar-perfil-evaluador/<int:evento_id>', views.modificar_inscripcion_evaluador, name='modificar_inscripcion_evaluador'),
    path('descargar-memorias-evaluador/<int:evento_id>/', views.descargar_memorias_evaluador, name='descargar_memorias_evaluador'),
    path('descargar-informacion-tecnica-evaluador/<int:evento_id>/', views.descargar_informacion_tecnica_evaluador, name='descargar_informacion_tecnica_evaluador'),
    path('evento/<int:evento_id>/perfil-evaluador/', views.ver_perfil_evaluador, name='perfil_evaluador'),
    path('evento/<int:evento_id>/cargar-programacion-tecnica/', views.cargar_programacion_tecnica, name='cargar_programacion_tecnica'),
    path("manual/", views.manual_evaluador, name="manual_evaluador"),
]