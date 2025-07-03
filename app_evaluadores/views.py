from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from app_usuarios.permisos import es_evaluador
from django.contrib import messages
from .models import Evaluador
from app_eventos.models import Evento
from app_evaluadores.models import Criterio, Calificacion, EvaluadorEvento
from app_participantes.models import ParticipanteEvento, Participante
from app_usuarios.models import Usuario




@login_required
@user_passes_test(es_evaluador, login_url='login')
def dashboard_evaluador(request):
    evaluador = request.user.evaluador
    inscripciones = EvaluadorEvento.objects.select_related('evento').filter(evaluador=request.user)

    return render(request, 'dashboard_evaluador.html', {
        'evaluador': evaluador,
        'inscripciones': inscripciones
    })


@login_required
@user_passes_test(es_evaluador, login_url='login')
def gestionar_items(request, eve_id):
    evento = get_object_or_404(Evento, pk=eve_id)
    try:
        inscripcion = EvaluadorEvento.objects.get(evaluador=request.user, evento=evento)
        if inscripcion.eva_eve_estado != 'Aprobado':
            messages.warning(request, "Tu inscripción como evaluador no ha sido aprobada para este evento.")
            return redirect('dashboard_evaluador')
    except EvaluadorEvento.DoesNotExist:
        messages.error(request, "No estás inscrito como evaluador en este evento.")
        return redirect('dashboard_evaluador')
    criterios = evento.criterios.all()
    peso_total_actual = sum(c.cri_peso for c in criterios if c.cri_peso is not None)
    return render(request, 'gestion_items_evaluador.html', {
        'evento': evento,
        'criterios': criterios,
        'peso_total_actual': peso_total_actual
    })


@login_required
@user_passes_test(es_evaluador, login_url='login')
def agregar_item(request, eve_id):
    evento = get_object_or_404(Evento, pk=eve_id)    
    if request.method == 'POST':
        descripcion = request.POST.get('descripcion')
        peso = float(request.POST.get('peso', 0))
        peso_total_actual = sum(c.cri_peso for c in Criterio.objects.filter(cri_evento_fk=eve_id))        
        if peso_total_actual + peso > 100:
            messages.error(request, 'El peso total no puede exceder el 100%.')
            return redirect('gestionar_items_evaluador', eve_id=eve_id)
        Criterio.objects.create(
            cri_descripcion=descripcion,
            cri_peso=peso,
            cri_evento_fk=evento
        )
        messages.success(request, 'Ítem agregado correctamente.')
        return redirect('gestionar_items_evaluador', eve_id=eve_id)
    peso_total_actual = sum(c.cri_peso for c in Criterio.objects.filter(cri_evento_fk=eve_id))
    peso_restante = 100 - peso_total_actual
    return render(request, 'agregar_item_evaluador.html', {
        'evento': evento,
        'peso_total_actual': peso_total_actual,
        'peso_restante': peso_restante
    })

@login_required
@user_passes_test(es_evaluador, login_url='login')
def editar_item(request, criterio_id):
    criterio = get_object_or_404(Criterio, pk=criterio_id)
    peso_total_actual = sum(
        c.cri_peso for c in Criterio.objects.filter(cri_evento_fk=criterio.cri_evento_fk).exclude(pk=criterio.pk)
    )
    peso_restante = 100 - peso_total_actual
    if request.method == 'POST':
        descripcion = request.POST.get('descripcion')
        peso = float(request.POST.get('peso', 0))
        if peso_total_actual + peso > 100:
            messages.error(request, 'El peso total no puede exceder el 100%.')
            return redirect('gestionar_items_evaluador', eve_id=criterio.cri_evento_fk.pk)
        criterio.cri_descripcion = descripcion
        criterio.cri_peso = peso
        criterio.save()
        messages.success(request, 'Ítem editado correctamente.')
        return redirect('gestionar_items_evaluador', eve_id=criterio.cri_evento_fk.pk)
    return render(request, 'editar_item_evaluador.html', {
        'criterio': criterio,
        'peso_total_actual': peso_total_actual,
        'peso_restante': peso_restante,
    })

@login_required
@user_passes_test(es_evaluador, login_url='login')
def eliminar_item(request, criterio_id):
    criterio = get_object_or_404(Criterio, pk=criterio_id)
    evento_id = criterio.cri_evento_fk.pk
    criterio.delete()
    messages.success(request, 'Ítem eliminado correctamente.')
    return redirect('gestionar_items_evaluador', eve_id=evento_id)


@login_required
@user_passes_test(es_evaluador, login_url='login')
def lista_participantes(request, eve_id):
    evento = get_object_or_404(Evento, pk=eve_id)
    try:
        evaluador = request.user.evaluador
    except Evaluador.DoesNotExist:
        messages.warning(request, "No estás registrado como evaluador.")
        return redirect('login_evaluador')
    if not evento.criterios.exists():
        messages.warning(request, "Este evento aún no tiene criterios definidos.")
        return redirect('gestionar_items_evaluador', eve_id=eve_id)
    participantes_evento = ParticipanteEvento.objects.filter(
        evento=evento,
        par_eve_estado='Aprobado'
    )
    calificaciones = Calificacion.objects.filter(
        evaluador=evaluador,
        criterio__cri_evento_fk=evento
    ).values_list('participante_id', flat=True).distinct()
    calificados = set(calificaciones)
    context = {
        'participantes': participantes_evento,
        'evento': evento,
        'calificados': calificados,
    }
    return render(request, 'lista_participantes_evaluador.html', context)


@login_required
@user_passes_test(es_evaluador, login_url='login')
def calificar_participante(request, eve_id, participante_id):
    evento = get_object_or_404(Evento, pk=eve_id)
    try:
        inscripcion = EvaluadorEvento.objects.get(evaluador=request.user, evento=evento)
        if inscripcion.eva_eve_estado != 'Aprobado':
            messages.warning(request, "Tu inscripción como evaluador aún no ha sido aprobada para este evento.")
            return redirect('dashboard_evaluador')
    except EvaluadorEvento.DoesNotExist:
        messages.error(request, "No estás inscrito como evaluador en este evento.")
        return redirect('dashboard_evaluador')
    usuario = get_object_or_404(Usuario, pk=participante_id)
    participante = get_object_or_404(Participante, usuario=usuario)
    participacion = ParticipanteEvento.objects.filter(
        evento=evento,
        participante=participante,
        par_eve_estado='Aprobado'
    ).first()
    if not participacion:
        messages.error(request, "Este participante no está aprobado para ser calificado en este evento.")
        return redirect('lista_participantes_evaluador', eve_id=eve_id)
    criterios = Criterio.objects.filter(cri_evento_fk=evento)
    evaluador = request.user.evaluador
    if request.method == 'POST':
        for criterio in criterios:
            valor = request.POST.get(f'criterio_{criterio.cri_id}')
            if valor:
                try:
                    valor_int = int(valor)
                    if 1 <= valor_int <= 5:
                        calificacion, created = Calificacion.objects.get_or_create(
                            evaluador=evaluador,
                            criterio=criterio,
                            participante=participante,
                            defaults={'cal_valor': valor_int}
                        )
                        if not created:
                            calificacion.cal_valor = valor_int
                            calificacion.save()
                    else:
                        messages.error(request, f"El valor de '{criterio.cri_descripcion}' debe estar entre 1 y 5.")
                        return redirect(request.path)
                except ValueError:
                    messages.error(request, f"Valor inválido para '{criterio.cri_descripcion}'.")
                    return redirect(request.path)
        messages.success(request, "Calificaciones guardadas exitosamente.")
        return redirect('lista_participantes_evaluador', eve_id=eve_id)

    return render(request, 'formulario_calificacion.html', {
        'criterios': criterios,
        'participante': participante,
        'evento': evento,
    })


@login_required
@user_passes_test(es_evaluador, login_url='login')
def ver_tabla_posiciones(request, eve_id):
    evento = get_object_or_404(Evento, pk=eve_id)
    try:
        inscripcion = EvaluadorEvento.objects.get(evaluador=request.user, evento=evento)
        if inscripcion.eva_eve_estado != 'Aprobado':
            messages.warning(request, "Tu inscripción a este evento aún no ha sido aprobada.")
            return redirect('dashboard_evaluador')
    except EvaluadorEvento.DoesNotExist:
        messages.error(request, "No estás inscrito en este evento.")
        return redirect('dashboard_evaluador')
    criterios = Criterio.objects.filter(cri_evento_fk=evento)
    peso_total = sum(c.cri_peso for c in criterios) or 1
    participantes_evento = ParticipanteEvento.objects.filter(
        evento=evento,
        par_eve_estado='Aprobado'
    ).select_related('participante')
    posiciones = []
    for pe in participantes_evento:
        participante = pe.participante
        calificaciones = Calificacion.objects.filter(
            participante=participante,
            criterio__cri_evento_fk=evento
        ).select_related('criterio')
        evaluadores_ids = set(c.evaluador_id for c in calificaciones)
        num_evaluadores = len(evaluadores_ids)
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
    return render(request, 'tabla_posiciones_evaluador.html', {
        'evento': evento,
        'posiciones': posiciones
    })


@login_required
@user_passes_test(es_evaluador, login_url='login')
def informacion_detallada(request, eve_id):   
    evaluador = request.user.evaluador
    evento = get_object_or_404(Evento, pk=eve_id)
    try:
        inscripcion = EvaluadorEvento.objects.get(evaluador=request.user, evento=evento)
        if inscripcion.eva_eve_estado != 'Aprobado':
            messages.warning(request, "No tienes acceso a este evento porque tu inscripción no está aprobada.")
            return redirect('dashboard_evaluador')
    except EvaluadorEvento.DoesNotExist:
        messages.error(request, "No estás inscrito en este evento.")
        return redirect('dashboard_evaluador')
    criterios = Criterio.objects.filter(cri_evento_fk=evento)
    total_criterios = criterios.count()
    participantes_evento = ParticipanteEvento.objects.filter(
        evento=evento,
        par_eve_estado='Aprobado'
    ).select_related('participante__usuario')
    participantes_info = []
    for pe in participantes_evento:
        participante = pe.participante
        calificaciones_actual = Calificacion.objects.filter(
            evaluador=evaluador,
            participante=participante,
            criterio__cri_evento_fk=evento
        ).select_related('criterio')
        total_aporte = 0
        calificaciones_lista = []
        for c in calificaciones_actual:
            aporte = (c.cal_valor * c.criterio.cri_peso) / 100
            total_aporte += aporte
            calificaciones_lista.append({
                'criterio': c.criterio,
                'cal_valor': c.cal_valor,
                'aporte': round(aporte, 2)
            })
        evaluado = len(calificaciones_lista) == total_criterios
        promedio_ponderado = round(total_aporte, 2) if calificaciones_lista else None
        participantes_info.append({
            'participante': participante,
            'evaluado': evaluado,
            'promedio_ponderado': promedio_ponderado,
            'calificaciones': calificaciones_lista,
            'evaluados': len(calificaciones_lista),
            'total_criterios': total_criterios
        })
    context = {
        'evaluador': evaluador,
        'evento': evento,
        'criterios': criterios,
        'participantes_info': participantes_info
    }
    return render(request, 'info_detallada_evaluador.html', context)


@login_required
@user_passes_test(es_evaluador, login_url='login')
def cancelar_inscripcion_evaluador(request, evento_id):
    evaluador_usuario = request.user
    evento = get_object_or_404(Evento, pk=evento_id)
    inscripcion = get_object_or_404(EvaluadorEvento, evaluador=evaluador_usuario, evento=evento)
    if inscripcion.eva_eve_estado != "Pendiente":
        messages.error(request, "No puedes cancelar la inscripción porque ya fue aprobada.")
        return redirect('dashboard_evaluador')
    if request.method == 'POST':
        inscripcion.delete()
        otros_eventos = EvaluadorEvento.objects.filter(evaluador=evaluador_usuario).count()
        if otros_eventos == 0:
            Evaluador.objects.filter(usuario=evaluador_usuario).delete()
            usuario_username = evaluador_usuario.username
            evaluador_usuario.delete()
            messages.success(request, f"Se canceló tu inscripción y se eliminó el usuario '{usuario_username}' porque no estaba en otros eventos.")
            return redirect('login')
        messages.success(request, "Inscripción cancelada con éxito.")
        return redirect('dashboard_evaluador')
    return render(request, 'confirmar_cancelacion.html', {
        'evento': evento
    })

@login_required
@user_passes_test(es_evaluador, login_url='login')
def modificar_inscripcion_evaluador(request, evento_id):
    usuario = request.user
    evento = get_object_or_404(Evento, pk=evento_id)
    inscripcion = get_object_or_404(EvaluadorEvento, evaluador=usuario, evento=evento)
    if inscripcion.eva_eve_estado != "Pendiente":
        messages.error(request, "Solo puedes modificar la inscripción si está en estado Pendiente.")
        return redirect('dashboard_evaluador')
    if request.method == "POST":
        usuario.first_name = request.POST.get("eva_nombres")
        usuario.last_name = request.POST.get("eva_apellidos")
        usuario.email = request.POST.get("eva_correo")
        usuario.telefono = request.POST.get("eva_telefono")
        usuario.documento = request.POST.get("eva_id")
        usuario.save()
        archivo = request.FILES.get('documentacion')
        if archivo:
            inscripcion.eva_eve_qr = archivo
            inscripcion.save()
        messages.success(request, "Información actualizada correctamente.")
        return redirect('dashboard_evaluador')
    return render(request, 'modificar_inscripcion.html', {
        'evento': evento,
        'usuario': usuario,
        'inscripcion': inscripcion
    })