from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.http import HttpResponse, FileResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
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

    return render(request, 'dashboard_asistente.html', {
        'relaciones': relaciones
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

    return render(request, 'detalle_evento_asistente.html', {
        'evento': evento,
        'relacion': relacion,
    })



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
    
    
