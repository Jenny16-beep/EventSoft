from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, FileResponse
from django.core.files.base import ContentFile
from django.utils.crypto import get_random_string

from .models import AdministradorEvento
from app_eventos.models import Evento
from app_eventos.models import EventoCategoria
from app_areas.models import Area, Categoria
from app_participantes.models import ParticipanteEvento, Participante
from app_asistentes.models import AsistenteEvento
from app_evaluadores.models import Criterio, Calificacion
from app_evaluadores.models import EvaluadorEvento, Evaluador
from app_usuarios.models import Usuario
from django.contrib.auth.decorators import login_required, user_passes_test
from app_usuarios.permisos import es_administrador_evento
import qrcode
import io

import mimetypes
import os



@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def dashboard_adminevento(request):
    return render(request, 'dashboard_adminevento.html')

@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def crear_evento(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        descripcion = request.POST.get('descripcion')
        ciudad = request.POST.get('ciudad')
        lugar = request.POST.get('lugar')
        fecha_inicio = request.POST.get('fecha_inicio')
        fecha_fin = request.POST.get('fecha_fin')
        capacidad = request.POST.get('capacidad')
        tienecosto = request.POST.get('tienecosto')
        imagen = request.FILES.get('imagen')
        programacion = request.FILES.get('programacion')

        if not (imagen and programacion):
            messages.error(request, "Debes subir la imagen y el archivo de programación.")
            areas = Area.objects.all()
            return render(request, 'crear_evento.html', {'areas': areas})

        estado = 'Pendiente'
        try:
            administrador = request.user.administrador  # ← aquí está el cambio clave
        except AdministradorEvento.DoesNotExist:
            messages.error(request, "Tu cuenta no está asociada como Administrador de Evento.")
            return redirect('ver_eventos')

        evento = Evento.objects.create(
            eve_nombre=nombre,
            eve_descripcion=descripcion,
            eve_ciudad=ciudad,
            eve_lugar=lugar,
            eve_fecha_inicio=fecha_inicio,
            eve_fecha_fin=fecha_fin,
            eve_estado=estado,
            eve_imagen=imagen,
            eve_capacidad=capacidad,
            eve_tienecosto=tienecosto,
            eve_administrador_fk=administrador,
            eve_programacion=programacion
        )

        categoria_ids = request.POST.getlist('categoria_id[]')
        for cat_id in categoria_ids:
            EventoCategoria.objects.create(evento=evento, categoria_id=cat_id)

        messages.success(request, "Evento creado exitosamente.")
        return redirect(reverse('dashboard_adminevento'))
    else:
        areas = Area.objects.all()
        return render(request, 'crear_evento.html', {'areas': areas})
    
@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def obtener_categorias_por_area(request, area_id):
    categorias = Categoria.objects.filter(cat_area_fk_id=area_id)
    categorias_json = [
        {'cat_codigo': cat.cat_codigo, 'cat_nombre': cat.cat_nombre}
        for cat in categorias
    ]
    return JsonResponse(categorias_json, safe=False)

@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def listar_eventos(request):
    administrador = request.user.administrador
    eventos = Evento.objects.filter(eve_administrador_fk=administrador)
    return render(request, 'listar_eventos.html', {'eventos': eventos})


@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def modificar_evento(request, eve_id):
    evento = get_object_or_404(Evento, eve_id=eve_id)

    if request.method == 'POST':
        evento.eve_nombre = request.POST['nombre']
        evento.eve_descripcion = request.POST['descripcion']
        evento.eve_ciudad = request.POST['ciudad']
        evento.eve_lugar = request.POST['lugar']
        evento.eve_fecha_inicio = request.POST['fecha_inicio']
        evento.eve_fecha_fin = request.POST['fecha_fin']
        evento.eve_capacidad = int(request.POST['capacidad'])
        evento.eve_tienecosto = request.POST['tienecosto']

        if 'imagen' in request.FILES:
            evento.eve_imagen = request.FILES['imagen']

        if 'programacion' in request.FILES:
            evento.eve_programacion = request.FILES['programacion']

        EventoCategoria.objects.filter(evento=evento).delete()
        categoria_ids = request.POST.getlist('categoria_id[]')
        for cat_id in categoria_ids:
            EventoCategoria.objects.create(evento=evento, categoria_id=cat_id)

        evento.save()
        messages.success(request, "Evento modificado exitosamente.")
        return redirect(reverse('dashboard_adminevento'))

    else:
        categorias_actuales = EventoCategoria.objects.filter(evento=evento).select_related('categoria__cat_area_fk')
        categorias_info = []
        for ec in categorias_actuales:
            categoria = ec.categoria
            area = categoria.cat_area_fk
            categorias_info.append({
                'categoria_id': categoria.cat_codigo,
                'area_id': area.are_codigo,
            })
        todas_areas = Area.objects.all()
        return render(request, 'modificar_evento.html', {
            'evento': evento,
            'todas_areas': todas_areas,
            'categorias_info': categorias_info
        })
    
@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def eliminar_evento(request, eve_id):
    evento = get_object_or_404(Evento, eve_id=eve_id)
    EventoCategoria.objects.filter(evento=evento).delete()
    evento.delete()
    messages.success(request, "Evento eliminado correctamente.")
    return redirect(reverse('dashboard_adminevento'))

@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def cerrar_inscripciones(request, eve_id):
    evento = Evento.objects.filter(eve_id=eve_id, eve_estado='aprobado').first()
    if evento:
        evento.eve_estado = 'Inscripciones Cerradas'
        evento.save()
        messages.success(request, "Las inscripciones se cerraron correctamente.")
    else:
        messages.error(request, "El evento no está aprobado o no existe.")
    return redirect(reverse('listar_eventos'))

@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def reabrir_inscripciones(request, eve_id):
    evento = Evento.objects.filter(eve_id=eve_id, eve_estado='inscripciones cerradas').first()
    if evento:
        evento.eve_estado = 'Aprobado'
        evento.save()
        messages.success(request, "Las inscripciones fueron reabiertas exitosamente.")
    else:
        messages.error(request, "El evento no está en estado 'inscripciones cerradas' o no existe.")
    return redirect(reverse('listar_eventos'))

@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def ver_inscripciones(request, eve_id):
    evento = get_object_or_404(Evento, eve_id=eve_id)
    return render(request, 'ver_inscripciones.html', {'evento': evento})

@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def gestion_asistentes(request, eve_id):
    evento = get_object_or_404(Evento, eve_id=eve_id)
    asistentes = AsistenteEvento.objects.select_related('asistente').filter(evento__eve_id=eve_id)
    return render(request, 'gestion_asistentes.html', {
        'evento': evento,
        'asistentes': asistentes,
    })

@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
@require_http_methods(["GET", "POST"])
def detalle_asistente(request, eve_id, asistente_id):
    evento = get_object_or_404(Evento, eve_id=eve_id)

    try:
        asistente_evento = AsistenteEvento.objects.select_related('asistente__usuario').get(
            evento__eve_id=eve_id,
            asistente__pk=asistente_id
        )
    except AsistenteEvento.DoesNotExist:
        messages.error(request, "Asistente no encontrado en este evento")
        return redirect('ver_asistentes_evento', eve_id=eve_id)

    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        estado_actual = asistente_evento.asi_eve_estado

        if nuevo_estado == "Aprobado":
            if estado_actual == "Pendiente":
                evento.eve_capacidad = max(evento.eve_capacidad - 1, 0)

            if not asistente_evento.asi_eve_qr:
                data_qr = f"Asistente: {asistente_evento.asistente.usuario.get_full_name()} - Evento: {evento.eve_nombre}"
                img = qrcode.make(data_qr)
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                filename = f"qr_asistente_{asistente_id}_evento_{evento.eve_id}.png"
                asistente_evento.asi_eve_qr.save(filename, ContentFile(buffer.getvalue()), save=False)

            asistente_evento.asi_eve_estado = nuevo_estado
            evento.save()
            asistente_evento.save()
            messages.success(request, "Estado actualizado y QR generado")

        elif nuevo_estado == "Pendiente":
            if estado_actual == "Aprobado":
                evento.eve_capacidad += 1
            asistente_evento.asi_eve_estado = nuevo_estado

            if asistente_evento.asi_eve_qr:
                asistente_evento.asi_eve_qr.delete(save=False)
            asistente_evento.asi_eve_qr = None

            evento.save()
            asistente_evento.save()
            messages.success(request, "Estado actualizado y QR eliminado")

        elif nuevo_estado == "Rechazado":
            if estado_actual == "Aprobado":
                evento.eve_capacidad += 1
                evento.save()

            if asistente_evento.asi_eve_qr:
                asistente_evento.asi_eve_qr.delete(save=False)

            asistente = asistente_evento.asistente
            asistente_evento.delete()

            if not AsistenteEvento.objects.filter(asistente=asistente).exists():
                asistente.delete()
                messages.success(request, "Asistente rechazado y eliminado completamente")
            else:
                messages.success(request, "Asistente rechazado y eliminado del evento")

        return redirect('ver_asistentes_evento', eve_id=eve_id)

    return render(request, 'detalle_asistente.html', {
        'asistente': asistente_evento,
        'evento': evento
    })

@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def gestion_participantes(request, eve_id):
    evento = get_object_or_404(Evento, pk=eve_id)
    participantes = ParticipanteEvento.objects.filter(evento=evento).select_related('participante')
    context = {
        'evento': evento,
        'participantes': participantes,
        'eve_id': eve_id,
    }
    return render(request, 'gestion_participantes.html', context)


@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def detalle_participante(request, eve_id, participante_id):
    evento = get_object_or_404(Evento, pk=eve_id)
    participante = get_object_or_404(Participante, pk=participante_id)
    participante_evento = ParticipanteEvento.objects.select_related('participante__usuario', 'evento')\
        .filter(evento=evento, participante=participante).first()
    if not participante_evento:
        messages.error(request, "Participante no encontrado en este evento")
        return redirect('ver_participantes_evento', eve_id=eve_id)
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        if nuevo_estado:
            usuario = participante.usuario
            if nuevo_estado == 'Aprobado':
                if not participante_evento.par_eve_qr:
                    data_qr = f"Participante: {usuario.first_name} {usuario.last_name} - Evento: {evento.eve_nombre}"
                    img = qrcode.make(data_qr)
                    buffer = io.BytesIO()
                    img.save(buffer, format='PNG')
                    file_name = f"qr_{get_random_string(8)}.png"
                    participante_evento.par_eve_qr.save(file_name, ContentFile(buffer.getvalue()), save=False)
                participante_evento.par_eve_estado = nuevo_estado
                participante_evento.save()
                messages.success(request, "Inscripción aprobada")
            elif nuevo_estado == 'Pendiente':
                if participante_evento.par_eve_qr:
                    participante_evento.par_eve_qr.delete(save=False)
                    participante_evento.par_eve_qr = None
                participante_evento.par_eve_estado = nuevo_estado
                participante_evento.save()
                messages.info(request, "Estado restablecido a pendiente y QR eliminado")
            elif nuevo_estado == 'Rechazado':
                participante_evento.delete()
                otros_eventos = ParticipanteEvento.objects.filter(participante=participante).exists()
                if not otros_eventos:
                    participante.delete()
                    messages.warning(request, "Inscripción rechazada y participante eliminado completamente")
                    return redirect('ver_participantes_evento', eve_id=eve_id)
                else:
                    messages.warning(request, "Inscripción rechazada y eliminado del evento")
                    return redirect('ver_participantes_evento', eve_id=eve_id)
            return redirect('detalle_participante_evento', eve_id=eve_id, participante_id=participante_id)
    return render(request, 'detalle_participante.html', {
        'participante': participante_evento,
        'evento': evento,
        'eve_id': eve_id,
    })


def descargar_documento_participante(request, eve_id, participante_id):
    participante_evento = get_object_or_404(
        ParticipanteEvento,
        evento_id=eve_id,
        participante_id=participante_id
    )
    if not participante_evento.par_eve_documentos:
        messages.error(request, "Documento no disponible para este participante.")
        return redirect('detalle_participante_evento', eve_id=eve_id, participante_id=participante_id)
    documento = participante_evento.par_eve_documentos
    try:
        file_path = documento.path
        tipo_mime, _ = mimetypes.guess_type(file_path)
        tipo_mime = tipo_mime or "application/octet-stream"
        response = FileResponse(open(file_path, 'rb'), content_type=tipo_mime)
        response['Content-Disposition'] = f'attachment; filename=documento_participante_{participante_id}{os.path.splitext(file_path)[1]}'
        return response
    except FileNotFoundError:
        messages.error(request, "El archivo no se encuentra en el servidor.")
        return redirect('detalle_participante_evento', eve_id=eve_id, participante_id=participante_id)


@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def gestion_evaluadores(request, eve_id):
    evento = get_object_or_404(Evento, pk=eve_id)
    evaluadores = EvaluadorEvento.objects.filter(evento=evento).select_related('evaluador')
    context = {
        'evento': evento,
        'evaluadores': evaluadores,
        'eve_id': eve_id,
    }
    return render(request, 'gestion_evaluadores.html', context)


@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def detalle_evaluador(request, eve_id, evaluador_id):
    evento = get_object_or_404(Evento, pk=eve_id)
    evaluador_evento = get_object_or_404(EvaluadorEvento, evento=evento, evaluador__id=evaluador_id)
    usuario = evaluador_evento.evaluador
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        if nuevo_estado:
            if nuevo_estado == 'Aprobado':
                if not evaluador_evento.eva_eve_qr:
                    data_qr = f"Evaluador: {usuario.first_name} {usuario.last_name} - Evento: {evento.eve_nombre}"
                    img = qrcode.make(data_qr)
                    buffer = io.BytesIO()
                    img.save(buffer, format='PNG')
                    file_name = f"qr_{get_random_string(8)}.png"
                    evaluador_evento.eva_eve_qr.save(file_name, ContentFile(buffer.getvalue()), save=False)
                evaluador_evento.eva_eve_estado = nuevo_estado
                evaluador_evento.save()
                messages.success(request, "Inscripción aprobada")
            elif nuevo_estado == 'Pendiente':
                if evaluador_evento.eva_eve_qr:
                    evaluador_evento.eva_eve_qr.delete(save=False)
                    evaluador_evento.eva_eve_qr = None
                evaluador_evento.eva_eve_estado = nuevo_estado
                evaluador_evento.save()
                messages.info(request, "Estado restablecido a pendiente y QR eliminado")
            elif nuevo_estado == 'Rechazado':
                evaluador_evento.delete()
                otros_eventos = EvaluadorEvento.objects.filter(evaluador=usuario).exists()
                if not otros_eventos:
                    Evaluador.objects.filter(usuario=usuario).delete()
                    usuario.delete()
                    messages.warning(request, "Inscripción rechazada y evaluador eliminado completamente")
                    return redirect('ver_evaluadores_evento', eve_id=eve_id)
                else:
                    messages.warning(request, "Inscripción rechazada y eliminado del evento")
                    return redirect('ver_evaluadores_evento', eve_id=eve_id)
            return redirect('detalle_evaluador_evento', eve_id=eve_id, evaluador_id=evaluador_id)
    return render(request, 'detalle_evaluador.html', {
        'evaluador': evaluador_evento,
        'evento': evento,
        'eve_id': eve_id,
    })



def descargar_documento_evaluador(request, eve_id, evaluador_id):
    evaluador_evento = get_object_or_404(
        EvaluadorEvento,
        evento_id=eve_id,
        evaluador_id=evaluador_id
    )
    if not evaluador_evento.eva_eve_documentos:
        messages.error(request, "Documento no disponible para este evaluador.")
        return redirect('detalle_evaluador_evento', eve_id=eve_id, evaluador_id=evaluador_id)

    documento = evaluador_evento.eva_eve_documentos
    try:
        file_path = documento.path
        tipo_mime, _ = mimetypes.guess_type(file_path)
        tipo_mime = tipo_mime or "application/octet-stream"
        response = FileResponse(open(file_path, 'rb'), content_type=tipo_mime)
        extension = os.path.splitext(file_path)[1]
        response['Content-Disposition'] = f'attachment; filename=documento_evaluador_{evaluador_id}{extension}'
        return response
    except FileNotFoundError:
        messages.error(request, "El archivo no se encuentra en el servidor.")
        return redirect('detalle_evaluador_evento', eve_id=eve_id, evaluador_id=evaluador_id)


@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def estadisticas_evento(request, eve_id):
    evento = get_object_or_404(Evento, pk=eve_id)
    asistentes_aprobados = AsistenteEvento.objects.filter(evento=evento, asi_eve_estado='Aprobado').count()
    total_asistentes = AsistenteEvento.objects.filter(evento=evento).count()  
    total_participantes = ParticipanteEvento.objects.filter(evento=evento).count()
    participantes_aprobados = ParticipanteEvento.objects.filter(evento=evento, par_eve_estado='Aprobado').count()
    capacidad_total = evento.eve_capacidad + asistentes_aprobados
    if capacidad_total > 0:
        porcentaje_ocupacion = round((asistentes_aprobados / capacidad_total) * 100, 2)
        porcentaje_disponible = round((evento.eve_capacidad / capacidad_total) * 100, 2)
    else:
        porcentaje_ocupacion = 0
        porcentaje_disponible = 0
    context = {
        'evento': evento,
        'total_asistentes': total_asistentes,
        'asistentes_aprobados': asistentes_aprobados,
        'total_participantes': total_participantes,
        'participantes_aprobados': participantes_aprobados,
        'capacidad_total': capacidad_total,
        'porcentaje_ocupacion': porcentaje_ocupacion,
        'porcentaje_disponible': porcentaje_disponible,
    }
    return render(request, 'estadisticas_evento.html', context)


@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def estadisticas_generales(request):
    administrador = request.user.administrador  
    eventos = Evento.objects.filter(eve_administrador_fk=administrador)
    total_eventos = eventos.count()

    resumen = {
        'Aprobado': 0,
        'Pendiente': 0,
        'Inscripciones Cerradas': 0,
        'Finalizado': 0
    }

    capacidad_total = 0
    capacidad_utilizada = 0
    total_participantes_aprobados = 0
    datos_eventos = []

    for evento in eventos:
        estado = evento.eve_estado
        resumen[estado] = resumen.get(estado, 0) + 1

        asistentes_aprobados = AsistenteEvento.objects.filter(
            evento=evento, asi_eve_estado='Aprobado'
        ).count()

        participantes_aprobados = ParticipanteEvento.objects.filter(
            evento=evento, par_eve_estado='Aprobado'
        ).count()

        total_participantes_aprobados += participantes_aprobados

        capacidad_original = evento.eve_capacidad + asistentes_aprobados
        capacidad_total += capacidad_original
        capacidad_utilizada += asistentes_aprobados

        datos_eventos.append({
            'nombre': evento.eve_nombre,
            'estado': estado,
            'capacidad': capacidad_original,
            'ocupados': asistentes_aprobados,
            'porcentaje': round(asistentes_aprobados / capacidad_original * 100, 2) if capacidad_original else 0,
            'participantes': participantes_aprobados
        })

    ocupacion_global = round(capacidad_utilizada / capacidad_total * 100, 2) if capacidad_total else 0

    context = {
        'total_eventos': total_eventos,
        'resumen': resumen,
        'capacidad_total': capacidad_total,
        'capacidad_utilizada': capacidad_utilizada,
        'ocupacion_global': ocupacion_global,
        'datos_eventos': datos_eventos,
        'etiquetas_estado': list(resumen.keys()),
        'datos_estado': list(resumen.values()),
        'total_participantes_aprobados': total_participantes_aprobados
    }

    return render(request, 'estadisticas_generales.html', context)


@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def dashboard_evaluacion(request, eve_id):
    administrador = request.user.administrador
    evento = get_object_or_404(Evento, pk=eve_id)
    if evento.eve_administrador_fk != administrador:
        messages.error(request, "No tienes permisos para acceder a este evento.")
        return redirect('listar_eventos')
    context = {
        'evento': evento,
    }
    return render(request, 'dashboard_evaluacion.html', context)


@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def gestion_item_administrador(request, eve_id):
    evento = get_object_or_404(Evento, pk=eve_id)
    criterios = Criterio.objects.filter(cri_evento_fk=evento)
    peso_total_actual = sum(c.cri_peso for c in criterios if c.cri_peso is not None)
    context = {
        'evento': evento,
        'criterios': criterios,
        'peso_total_actual': peso_total_actual,
    }
    return render(request, 'gestion_items.html', context)


@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def agregar_item_administrador(request, eve_id):
    evento = get_object_or_404(Evento, pk=eve_id)
    if request.method == 'POST':
        descripcion = request.POST.get('descripcion')
        peso_str = request.POST.get('peso')
        try:
            peso = float(peso_str)
        except (TypeError, ValueError):
            messages.error(request, 'El peso debe ser un número válido.')
            return redirect('agregar_item_administrador_evento', eve_id=eve_id)
        criterios = Criterio.objects.filter(cri_evento_fk=evento)
        peso_total_actual = sum(c.cri_peso for c in criterios if c.cri_peso is not None)
        if peso_total_actual + peso > 100:
            messages.error(request, 'El peso total no puede exceder el 100%.')
            return redirect('agregar_item_administrador_evento', eve_id=eve_id)
        nuevo_criterio = Criterio(
            cri_descripcion=descripcion,
            cri_peso=peso,
            cri_evento_fk=evento
        )
        nuevo_criterio.save()
        messages.success(request, 'Ítem agregado correctamente.')
        return redirect('gestion_item_administrador_evento', eve_id=eve_id)
    criterios = Criterio.objects.filter(cri_evento_fk=evento)
    peso_total_actual = sum(c.cri_peso for c in criterios if c.cri_peso is not None)
    peso_restante = 100 - peso_total_actual
    context = {
        'evento': evento,
        'peso_total_actual': peso_total_actual,
        'peso_restante': peso_restante,
    }
    return render(request, 'agregar_item.html', context)


@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def editar_item_administrador(request, criterio_id):
    criterio = get_object_or_404(Criterio, pk=criterio_id)
    criterios_evento = Criterio.objects.filter(cri_evento_fk=criterio.cri_evento_fk)
    peso_total_actual = sum(c.cri_peso for c in criterios_evento if c.pk != criterio.pk)
    peso_restante = 100 - peso_total_actual
    if request.method == 'POST':
        descripcion = request.POST.get('descripcion')
        peso_str = request.POST.get('peso')
        try:
            peso = float(peso_str)
        except (ValueError, TypeError):
            messages.error(request, 'El peso debe ser un número válido.')
            return redirect('editar_item_administrador_evento', criterio_id=criterio_id)
        if peso_total_actual + peso > 100:
            messages.error(request, 'El peso total no puede exceder el 100%.')
            return redirect('gestion_item_administrador_evento', eve_id=criterio.cri_evento_fk.pk)
        criterio.cri_descripcion = descripcion
        criterio.cri_peso = peso
        criterio.save()
        messages.success(request, 'Ítem editado correctamente.')
        return redirect('gestion_item_administrador_evento', eve_id=criterio.cri_evento_fk.pk)
    context = {
        'criterio': criterio,
        'peso_total_actual': peso_total_actual,
        'peso_restante': peso_restante
    }
    return render(request, 'editar_item.html', context)


@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def eliminar_item_administrador(request, criterio_id):
    criterio = get_object_or_404(Criterio, pk=criterio_id)
    evento_id = criterio.cri_evento_fk.eve_id
    criterio.delete()
    messages.success(request, 'Ítem eliminado correctamente.')
    return redirect('gestion_item_administrador_evento', eve_id=evento_id)


@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def ver_tabla_posiciones(request, eve_id):
    evento = get_object_or_404(Evento, pk=eve_id)
    criterios = Criterio.objects.filter(cri_evento_fk=evento)
    peso_total = sum(c.cri_peso for c in criterios) or 1
    participantes_evento = ParticipanteEvento.objects.filter(
        evento=evento,
        par_eve_estado='Aprobado'
    ).select_related('participante')
    posiciones = []
    for pe in participantes_evento:
        participante = pe.participante
        calificaciones = Calificacion.objects.select_related('criterio').filter(
            participante=participante,
            criterio__cri_evento_fk=evento
        )
        evaluadores = set(c.evaluador_id for c in calificaciones)
        num_evaluadores = len(evaluadores)
        if num_evaluadores > 0:
            puntaje_ponderado = sum(
                c.cal_valor * c.criterio.cri_peso for c in calificaciones
            ) / (peso_total * num_evaluadores)
        else:
            puntaje_ponderado = 0
        posiciones.append({
            'participante': participante,
            'puntaje': round(puntaje_ponderado, 2)
        })
    posiciones.sort(key=lambda x: x['puntaje'], reverse=True)
    return render(request, 'tabla_posiciones.html', {
        'evento': evento,
        'posiciones': posiciones
    })


@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def info_detallada_admin(request, eve_id):
    administrador = request.user.administrador
    evento = get_object_or_404(Evento, pk=eve_id)
    if evento.eve_administrador_fk != administrador:
        messages.error(request, "No tienes permisos para acceder a este evento.")
        return redirect('listar_eventos')
    criterios = Criterio.objects.filter(cri_evento_fk=evento)
    participantes_evento = ParticipanteEvento.objects.filter(
        evento=evento,
        par_eve_estado='Aprobado'
    ).select_related('participante')
    participantes_info = []
    for pe in participantes_evento:
        participante = pe.participante
        calificaciones = Calificacion.objects.select_related('criterio').filter(
            participante=participante,
            criterio__cri_evento_fk=evento
        )
        evaluadores = {c.evaluador_id for c in calificaciones}
        num_evaluadores = len(evaluadores)
        criterios_evaluados = {c.criterio_id for c in calificaciones}
        total_criterios = criterios.count()
        if num_evaluadores > 0:
            total = sum([
                (c.cal_valor * c.criterio.cri_peso) / 100 for c in calificaciones
            ])
            promedio_ponderado = round(total / num_evaluadores, 2)
        else:
            promedio_ponderado = None
        participantes_info.append({
            'participante': participante,
            'evaluados': len(criterios_evaluados),
            'total_criterios': total_criterios,
            'calificaciones': calificaciones,
            'promedio_ponderado': promedio_ponderado,
        })
    context = {
        'evento': evento,
        'criterios': criterios,
        'participantes_info': participantes_info
    }
    return render(request, 'info_detallada_admin.html', context)