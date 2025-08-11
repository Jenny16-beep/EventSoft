from django.urls import path


from . import views


urlpatterns = [
    path('dashboard/', views.dashboard_adminevento, name='dashboard_adminevento'),
    path('listar-eventos/', views.listar_eventos, name='listar_eventos'),
    path('crear-evento/', views.crear_evento, name='crear_evento'),
    path('obtener-categorias-por-area/<int:area_id>/', views.obtener_categorias_por_area, name='obtener_categorias_por_area'),
    path('modificar-evento/<int:eve_id>/', views.modificar_evento, name='modificar_evento'),
    path('eliminar-evento/<int:eve_id>/', views.eliminar_evento, name='eliminar_evento'),
    path('cerrar-inscripciones/<int:eve_id>/', views.cerrar_inscripciones, name='cerrar_inscripcion_evento'),
    path('reabrir-inscripciones/<int:eve_id>/', views.reabrir_inscripciones, name='reabrir_inscripcion_evento'),
    path('ver-inscripciones/<int:eve_id>/', views.ver_inscripciones, name='ver_inscripciones_evento'),
    path('ver-asistentes/<int:eve_id>/', views.gestion_asistentes, name='ver_asistentes_evento'),
    path('detalle-asistente/<int:eve_id>/<int:asistente_id>/', views.detalle_asistente, name='detalle_asistente_evento'),
    path('ver-participantes/<int:eve_id>/', views.gestion_participantes, name='ver_participantes_evento'),
    path('detalle-participante/<int:eve_id>/<int:participante_id>/', views.detalle_participante, name='detalle_participante_evento'),
    path('descargar-documento-participante/<int:eve_id>/<int:participante_id>/', views.descargar_documento_participante, name='descargar_documento_participante_evento'),
    path('estadisticas-evento/<int:eve_id>/', views.estadisticas_evento, name='estadisticas_evento'),
    path('estaditicas-generales/', views.estadisticas_generales, name='estadisticas_generales'),
    path('dashboard-evaluacion/<int:eve_id>/', views.dashboard_evaluacion, name='dashboard_evaluacion_administrador'),
    path('gestion-item-administrador/<int:eve_id>/', views.gestion_item_administrador, name='gestion_item_administrador_evento'),
    path('agregar-item-administrador/<int:eve_id>/', views.agregar_item_administrador, name='agregar_item_administrador_evento'),
    path('editar-item-administrador/<int:criterio_id>/', views.editar_item_administrador, name='editar_item_administrador_evento'),
    path('eliminar-item-administrador/<int:criterio_id>/', views.eliminar_item_administrador, name='eliminar_item_administrador_evento'),
    path('tabla-posiciones-administrador/<int:eve_id>/', views.ver_tabla_posiciones, name='tabla_posiciones_administrador'),
    path('informacion-detallada-administrador/<int:eve_id>/', views.info_detallada_admin, name='informacion_detallada_administrador_evento'),
    
    # Códigos de invitación para eventos
    path('crear-codigo-invitacion/', views.crear_codigo_invitacion, name='crear_codigo_invitacion'),
    path('listar-codigos-invitacion/', views.listar_codigos_invitacion, name='listar_codigos_invitacion'),
    path('cancelar-codigo-invitacion/<int:codigo_id>/', views.cancelar_codigo_invitacion, name='cancelar_codigo_invitacion'),
    
    path('gestionar-evaluadores/<int:eve_id>/', views.gestion_evaluadores, name='gestion_evaluadores'),
    path('detalle-evaluador/<int:eve_id>/<int:evaluador_id>/', views.detalle_evaluador, name='detalle_evaluador_evento'),
    path('descargar-documento-evaluador/<int:eve_id>/<int:evaluador_id>/', views.descargar_documento_evaluador, name='descargar_documento_evaluador_evento'),
    path('gestionar-notificaciones/', views.gestionar_notificaciones, name='gestionar_notificaciones'),
    
    # URLs para gestión de archivos del evento
    path('gestionar-archivos/<int:eve_id>/', views.gestionar_archivos_evento, name='gestionar_archivos_evento'),
    path('eliminar-archivo/<int:eve_id>/', views.eliminar_archivo_evento, name='eliminar_archivo_evento'),
    
    # URLs para gestión de certificados
    path('gestionar-certificados/', views.gestionar_certificados, name='gestionar_certificados'),
    path('certificados/<int:eve_id>/tipo/', views.seleccionar_tipo_certificado, name='seleccionar_tipo_certificado'),
    path('certificados/<int:eve_id>/<str:tipo>/configurar/', views.configurar_certificado, name='configurar_certificado'),
    path('certificados/<int:eve_id>/<str:tipo>/previsualizar/', views.previsualizar_certificado, name='previsualizar_certificado'),
    # URL específica para premiación debe ir antes que la URL general
    path('certificados/<int:eve_id>/premiacion/enviar/', views.enviar_certificados_premiacion, name='enviar_certificados_premiacion'),
    path('certificados/<int:eve_id>/<str:tipo>/enviar/', views.enviar_certificados, name='enviar_certificados'),
]