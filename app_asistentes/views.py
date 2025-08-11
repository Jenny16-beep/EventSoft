from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.http import HttpResponse, FileResponse, JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse
from django.template.loader import render_to_string
from app_usuarios.permisos import es_asistente
from app_asistentes.models import AsistenteEvento
from app_eventos.models import EventoCategoria, Evento
import mimetypes
import os

@login_required
@user_passes_test(es_asistente, login_url='ver_eventos')
def dashboard_asistente(request):
    asistente = request.user.asistente
    relaciones = AsistenteEvento.objects.filter(asistente=asistente).select_related('evento')

    # Calcular estadísticas
    estadisticas = {
        'total': relaciones.count(),
        'pendientes': relaciones.filter(asi_eve_estado='Pendiente').count(),
        'aprobados': relaciones.filter(asi_eve_estado='Aprobado').count(),
        'con_qr': relaciones.filter(asi_eve_qr__isnull=False).count(),
    }

    # Agregar información sobre memorias disponibles para cada relación
    relaciones_con_memorias = []
    for relacion in relaciones:
        relacion_data = {
            'relacion': relacion,
            'evento': relacion.evento,
            'estado': relacion.asi_eve_estado,
            'tiene_memorias': bool(relacion.evento.eve_memorias),
        }
        relaciones_con_memorias.append(relacion_data)

    return render(request, 'app_asistentes/dashboard_asistente.html', {
        'relaciones': relaciones,
        'relaciones_con_memorias': relaciones_con_memorias,
        'estadisticas': estadisticas
    })

@login_required
@user_passes_test(es_asistente, login_url='ver_eventos')
def detalle_evento_asistente(request, eve_id):
    evento = get_object_or_404(Evento, pk=eve_id)
    asistente = request.user.asistente
    relacion = get_object_or_404(AsistenteEvento, evento=evento, asistente=asistente)

    if request.method == 'POST':
        if 'cancelar_inscripcion' in request.POST:
            relacion.delete()
            messages.success(request, "Inscripción cancelada correctamente.")
            return redirect('dashboard_asistente')

    # Agregar información sobre memorias disponibles
    tiene_memorias = bool(evento.eve_memorias)

    return render(request, 'app_asistentes/detalle_evento_asistente.html', {
        'evento': evento,
        'relacion': relacion,
        'tiene_memorias': tiene_memorias,
    })



@login_required
@user_passes_test(es_asistente, login_url='ver_eventos')
def compartir_evento(request, eve_id):
    """Vista para generar contenido compartible del evento"""
    evento = get_object_or_404(Evento, pk=eve_id)
    asistente = request.user.asistente
    
    # Verificar que el asistente está inscrito en el evento
    relacion = get_object_or_404(AsistenteEvento, evento=evento, asistente=asistente)
    
    # Generar URL absoluta del evento
    url_evento = request.build_absolute_uri(reverse('detalle_evento_asistente', args=[eve_id]))
    
    # Obtener categorías
    categorias = [ec.categoria.cat_nombre for ec in evento.eventocategoria_set.all()]
    
    if request.method == 'POST' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Crear mensaje para compartir
        asistente_nombre = request.user.get_full_name() or request.user.username
        mensaje_compartir = f"¡Hola! Soy {asistente_nombre} y te invito al evento '{evento.eve_nombre}'! 🎉\n\n"
        mensaje_compartir += f"📅 Fechas: {evento.eve_fecha_inicio.strftime('%d/%m/%Y')}"
        
        if evento.eve_fecha_inicio != evento.eve_fecha_fin:
            mensaje_compartir += f" - {evento.eve_fecha_fin.strftime('%d/%m/%Y')}"
        
        mensaje_compartir += f"\n📍 Lugar: {evento.eve_lugar}, {evento.eve_ciudad}\n"
        mensaje_compartir += f"📝 {evento.eve_descripcion}\n\n"
        
        if categorias:
            mensaje_compartir += f"🏷️ Categorías: {', '.join(categorias)}\n\n"
        
        mensaje_compartir += f"¡No te lo pierdas! Más información aquí: {url_evento}"
        
        response_data = {
            'success': True,
            'mensaje': mensaje_compartir,
            'titulo': f"Evento: {evento.eve_nombre}",
            'url': url_evento,
            'evento_nombre': evento.eve_nombre
        }
        
        return JsonResponse(response_data)
    
    # Para peticiones GET, renderizar template (si lo necesitas)
    contexto_compartir = {
        'evento': evento,
        'asistente_nombre': request.user.get_full_name() or request.user.username,
        'url_evento': url_evento,
        'categorias': categorias,
    }
    
    return render(request, 'app_asistentes/compartir_evento.html', contexto_compartir)


def descargar_programacion(request, evento_id):
    evento = get_object_or_404(Evento, pk=evento_id)
    if evento.eve_programacion:
        try:
            file_path = evento.eve_programacion.path
            tipo_mime, _ = mimetypes.guess_type(file_path)
            tipo_mime = tipo_mime or "application/octet-stream"
            return FileResponse(open(file_path, 'rb'),
                                as_attachment=True,
                                filename=f"programacion_{evento_id}{os.path.splitext(file_path)[1]}",
                                content_type=tipo_mime)
        except FileNotFoundError:
            messages.error(request, "El archivo de programación no se encuentra en el servidor.")
            return redirect('ver_qr_asistente')
    else:
        messages.warning(request, "No hay programación disponible para este evento.")
        return redirect('ver_qr_asistente')


@login_required
@user_passes_test(es_asistente, login_url='ver_eventos')
def descargar_memorias_asistente(request, evento_id):
    """Vista para descargar las memorias de un evento como asistente"""
    evento = get_object_or_404(Evento, eve_id=evento_id)
    asistente = request.user.asistente
    
    # Verificar que el asistente esté inscrito en el evento
    relacion = get_object_or_404(AsistenteEvento, asistente=asistente, evento=evento)
    
    # Solo permitir si el estado es "Aprobado"
    if relacion.asi_eve_estado != 'Aprobado':
        messages.error(request, "Solo puedes descargar memorias si tu inscripción está aprobada.")
        return redirect('dashboard_asistente')
    
    # Verificar que el archivo de memorias exista
    if not evento.eve_memorias:
        messages.error(request, "Este evento no tiene memorias disponibles para descargar.")
        return redirect('dashboard_asistente')
    
    # Verificar que el archivo físico exista
    if not os.path.exists(evento.eve_memorias.path):
        messages.error(request, "El archivo de memorias no se encuentra disponible.")
        return redirect('dashboard_asistente')
    
    try:
        response = FileResponse(
            open(evento.eve_memorias.path, 'rb'),
            as_attachment=True,
            filename=f"Memorias_{evento.eve_nombre}_{evento.eve_memorias.name.split('/')[-1]}"
        )
        return response
    except Exception as e:
        messages.error(request, "Error al descargar el archivo de memorias.")
        return redirect('dashboard_asistente')    
