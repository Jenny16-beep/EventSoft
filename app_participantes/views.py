from django.shortcuts import render , redirect, get_object_or_404
from django.contrib import messages
from app_participantes.models import ParticipanteEvento , Participante, Proyecto
from app_eventos.models import EventoCategoria, Evento
from app_evaluadores.models import Criterio, Calificacion
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib.auth.decorators import login_required, user_passes_test
from app_usuarios.permisos import es_participante
from django.urls import reverse
from django.http import Http404, HttpResponse, FileResponse
from django.conf import settings
import os


@login_required
@user_passes_test(es_participante, login_url='login')
def dashboard_participante_general(request):
    participante = request.user.participante
    inscripciones = ParticipanteEvento.objects.filter(participante=participante)

    if not inscripciones.exists():
        messages.warning(request, "No tienes inscripciones registradas.")
        return redirect('ingreso_participante')

    eventos = []
    estadisticas = {
        'total': 0,
        'pendientes': 0,
        'aprobados': 0,
        'rechazados': 0,
        'cancelados': 0
    }

    for inscripcion in inscripciones:
        evento_data = {
            'eve_id': inscripcion.evento.eve_id,
            'eve_nombre': inscripcion.evento.eve_nombre,
            'eve_fecha_inicio': inscripcion.evento.eve_fecha_inicio,
            'eve_fecha_fin': inscripcion.evento.eve_fecha_fin,
            'par_eve_estado': inscripcion.par_eve_estado,
        }
        eventos.append(evento_data)
        
        # Contar estadísticas
        estadisticas['total'] += 1
        if inscripcion.par_eve_estado == 'Pendiente':
            estadisticas['pendientes'] += 1
        elif inscripcion.par_eve_estado == 'Aprobado':
            estadisticas['aprobados'] += 1
        elif inscripcion.par_eve_estado == 'Rechazado':
            estadisticas['rechazados'] += 1
        elif inscripcion.par_eve_estado == 'Cancelado':
            estadisticas['cancelados'] += 1

    return render(request, 'dashboard_participante_general.html', {
        'eventos': eventos,
        'estadisticas': estadisticas
    })

@login_required
@user_passes_test(es_participante, login_url='login')
def dashboard_participante_evento(request, evento_id):
    participante = request.user.participante
    inscripcion = get_object_or_404(
        ParticipanteEvento, participante=participante, evento__pk=evento_id
    )

    datos = {
        'par_nombre': participante.usuario.first_name,
        'par_correo': participante.usuario.email,
        'par_telefono': participante.usuario.telefono,
        'eve_nombre': inscripcion.evento.eve_nombre,
        'eve_programacion': inscripcion.evento.eve_programacion,
        'eve_informacion_tecnica': inscripcion.evento.eve_informacion_tecnica,
        'eve_memorias': inscripcion.evento.eve_memorias,
        'par_eve_estado': inscripcion.par_eve_estado,
        'par_id': participante.id,
        'eve_id': inscripcion.evento.eve_id
    }
    return render(request, 'dashboard_participante.html', {'datos': datos})

@login_required
@user_passes_test(es_participante, login_url='login')
@require_http_methods(["GET", "POST"])
def modificar_preinscripcion(request, evento_id):
    participante = get_object_or_404(Participante, usuario=request.user)
    evento = get_object_or_404(Evento, pk=evento_id)
    inscripcion = get_object_or_404(
        ParticipanteEvento,
        participante=participante,
        evento=evento
    )
    if inscripcion.par_eve_estado != 'Pendiente':
        messages.warning(request, "No puedes modificar esta inscripción.")
        return redirect('dashboard_participante_evento', evento_id=evento_id)
    if request.method == 'POST':
        participante.par_nombre = request.POST.get('nombre')
        participante.par_correo = request.POST.get('correo')
        participante.par_telefono = request.POST.get('telefono')
        documento = request.FILES.get('documento')
        if documento:
            inscripcion.par_eve_documentos = documento
        participante.save()
        inscripcion.save()
        messages.success(request, "Datos actualizados correctamente")
        return redirect('dashboard_participante_evento', evento_id=evento_id)
    return render(request, 'modificar_preinscripcion_participante.html', {
        'participante': participante,
        'inscripcion': inscripcion,
        'evento': evento,
    })

@login_required
@user_passes_test(es_participante, login_url='login')
@require_POST
def cancelar_inscripcion(request):
    participante = get_object_or_404(Participante, usuario=request.user)
    inscripcion = ParticipanteEvento.objects.filter(participante=participante).order_by('-id').first()
    if inscripcion:
        evento = inscripcion.evento
        inscripcion.delete()
        if not ParticipanteEvento.objects.filter(participante=participante).exists():
            participante.delete()
        messages.info(request, "Has cancelado tu inscripción exitosamente.")
    else:
        messages.warning(request, "No se encontró inscripción activa.")  
    return render(request, 'preinscripcion_cancelada.html')

@login_required
@user_passes_test(es_participante, login_url='login')
def ver_qr_participante(request, evento_id):
    try:
        participante = request.user.participante
        relacion = ParticipanteEvento.objects.select_related('evento').get(
            participante=participante,
            evento_id=evento_id
        )
        evento = relacion.evento
        datos = {
            'qr_url': relacion.par_eve_qr.url if relacion.par_eve_qr else None,
            'eve_nombre': evento.eve_nombre,
            'eve_lugar': evento.eve_lugar,
            'eve_descripcion': evento.eve_descripcion,
        }
        return render(request, 'ver_qr_participante.html', {
            'datos': datos,
            'evento_id': evento_id
        })

    except ParticipanteEvento.DoesNotExist:
        messages.error(request, "QR no encontrado para esta inscripción.")
        return redirect('dashboard_participante')

@login_required
@user_passes_test(es_participante, login_url='login')
def descargar_qr_participante(request, evento_id):
    try:
        participante = request.user.participante
        inscripcion = ParticipanteEvento.objects.get(
            participante=participante,
            evento__eve_id=evento_id
        )
        if inscripcion.par_eve_qr and os.path.exists(inscripcion.par_eve_qr.path):
            with open(inscripcion.par_eve_qr.path, 'rb') as f:
                response = HttpResponse(f.read(), content_type='image/png')
                filename = f'qr_evento_{evento_id}_participante_{participante.id}.png'
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response
        raise Http404("QR no disponible o archivo no encontrado")
    except ParticipanteEvento.DoesNotExist:
        raise Http404("QR no encontrado para esta inscripción")
    
@login_required
@user_passes_test(es_participante, login_url='login')
def ver_evento_completo(request, evento_id):
    participante = request.user.participante
    evento = get_object_or_404(Evento, pk=evento_id)
    administrador = evento.eve_administrador_fk.usuario 
    evento_categorias = EventoCategoria.objects.filter(evento=evento).select_related('categoria__cat_area_fk')
    categorias_data = []
    for ec in evento_categorias:
        categoria = ec.categoria
        area = categoria.cat_area_fk
        categorias_data.append({
            'cat_nombre': categoria.cat_nombre,
            'cat_descripcion': categoria.cat_descripcion,
            'are_nombre': area.are_nombre,
            'are_descripcion': area.are_descripcion
        })
    evento_data = {
        'eve_id': evento.eve_id,
        'eve_nombre': evento.eve_nombre,
        'eve_descripcion': evento.eve_descripcion,
        'eve_ciudad': evento.eve_ciudad,
        'eve_lugar': evento.eve_lugar,
        'eve_fecha_inicio': evento.eve_fecha_inicio,
        'eve_fecha_fin': evento.eve_fecha_fin,
        'eve_estado': evento.eve_estado,
        'eve_capacidad': evento.eve_capacidad,
        'eve_tienecosto': evento.eve_tienecosto,
        'tiene_costo_legible': 'Sí' if evento.eve_tienecosto.upper() == 'SI' else 'No',
        'eve_programacion': evento.eve_programacion,
        'adm_nombre': administrador.get_full_name(),
        'adm_correo': administrador.email,
        'categorias': categorias_data,
    }

    return render(request, 'evento_completo_participante.html', {'evento': evento_data})

@login_required
@user_passes_test(es_participante, login_url='login')
def instrumento_evaluacion(request, evento_id):
    participante = request.user.participante
    evento = get_object_or_404(Evento, pk=evento_id)
    inscrito = ParticipanteEvento.objects.filter(participante=participante, evento=evento).exists()
    if not inscrito:
        messages.warning(request, "No estás inscrito en este evento.")
        return redirect('dashboard_participante', evento_id=evento_id)
    criterios = Criterio.objects.filter(cri_evento_fk=evento)
    return render(request, 'instrumento_evaluacion_participante.html', {
        'evento': evento,
        'criterios': criterios,
    })

@login_required
@user_passes_test(es_participante, login_url='login')
def ver_calificaciones_participante(request, evento_id):
    participante = request.user.participante
    evento = get_object_or_404(Evento, pk=evento_id)
    inscrito = ParticipanteEvento.objects.filter(participante=participante, evento=evento).exists()
    if not inscrito:
        messages.warning(request, "No estás inscrito en este evento.")
        return redirect('dashboard_participante', evento_id=evento_id)

    calificaciones = Calificacion.objects.select_related('evaluador', 'criterio').filter(
        participante=participante,
        criterio__cri_evento_fk=evento
    )
    return render(request, 'ver_calificaciones_participante.html', {
        'calificaciones': calificaciones,
        'evento': evento,
    })

@login_required
@user_passes_test(es_participante, login_url='login')
def descargar_informacion_tecnica(request, evento_id):
    participante = request.user.participante
    evento = get_object_or_404(Evento, pk=evento_id)
    
    # Verificar que el participante esté inscrito y aprobado
    inscripcion = get_object_or_404(
        ParticipanteEvento, 
        participante=participante, 
        evento=evento,
        par_eve_estado='Aprobado'
    )
    
    if not evento.eve_informacion_tecnica:
        messages.error(request, "Este evento no tiene información técnica disponible.")
        return redirect('dashboard_participante_evento', evento_id=evento_id)
    
    try:
        response = HttpResponse(
            evento.eve_informacion_tecnica.read(),
            content_type='application/pdf'
        )
        filename = f'informacion_tecnica_{evento.eve_nombre.replace(" ", "_")}.pdf'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except FileNotFoundError:
        messages.error(request, "El archivo de información técnica no se encuentra disponible.")
        return redirect('dashboard_participante_evento', evento_id=evento_id)

@login_required
@user_passes_test(es_participante, login_url='login')
def descargar_memorias(request, evento_id):
    participante = request.user.participante
    evento = get_object_or_404(Evento, pk=evento_id)
    
    # Verificar que el participante esté inscrito y aprobado
    inscripcion = get_object_or_404(
        ParticipanteEvento, 
        participante=participante, 
        evento=evento,
        par_eve_estado='Aprobado'
    )
    
    if not evento.eve_memorias:
        messages.error(request, "Este evento no tiene memorias disponibles.")
        return redirect('dashboard_participante_evento', evento_id=evento_id)
    
    try:
        response = HttpResponse(
            evento.eve_memorias.read(),
            content_type='application/pdf'
        )
        filename = f'memorias_{evento.eve_nombre.replace(" ", "_")}.pdf'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except FileNotFoundError:
        messages.error(request, "El archivo de memorias no se encuentra disponible.")
        return redirect('dashboard_participante_evento', evento_id=evento_id)
    
# Agregar estas funciones actualizadas a tu views.py de app_participantes

@login_required
def mis_proyectos(request):
    """Lista de proyectos en los que participa el usuario logueado"""
    participante = getattr(request.user, 'participante', None)
    if not participante:
        return render(request, "mis_proyectos.html", {"proyectos": []})

    # Obtener proyectos a través de ParticipanteEvento
    inscripciones = ParticipanteEvento.objects.filter(
        participante=participante,
        proyecto__isnull=False
    ).select_related('proyecto', 'evento').distinct()
    
    proyectos_data = []
    for inscripcion in inscripciones:
        proyecto = inscripcion.proyecto
        proyectos_data.append({
            'proyecto': proyecto,
            'evento': inscripcion.evento,
            'estado_inscripcion': inscripcion.par_eve_estado,
        })

    return render(request, "mis_proyectos.html", {"proyectos_data": proyectos_data})

@login_required
def detalle_proyecto(request, proyecto_id):
    """Detalle de un proyecto del usuario"""
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    
    # Verificar que el usuario tenga acceso a este proyecto
    participante = getattr(request.user, 'participante', None)
    if not participante:
        messages.error(request, "No tienes acceso a este proyecto.")
        return redirect('mis_proyectos')
    
    # Verificar que el participante esté asociado a este proyecto
    tiene_acceso = ParticipanteEvento.objects.filter(
        participante=participante,
        proyecto=proyecto
    ).exists()
    
    if not tiene_acceso:
        messages.error(request, "No tienes acceso a este proyecto.")
        return redirect('mis_proyectos')

    # Obtener todos los integrantes del proyecto
    integrantes = ParticipanteEvento.objects.filter(
        proyecto=proyecto
    ).select_related("participante__usuario", "evento")

    return render(request, "detalle_proyecto.html", {
        "proyecto": proyecto,
        "integrantes": integrantes
    })

def manual_participante(request):
    """
    Sirve el manual del Participante en formato PDF.
    """
    ruta_manual = os.path.join(settings.MEDIA_ROOT, "manuales", "MANUAL_EXPOSITOR_SISTEMA_EVENTSOFT.pdf")
    if os.path.exists(ruta_manual):
        return FileResponse(open(ruta_manual, "rb"), content_type="application/pdf")
    raise Http404("Manual no encontrado")