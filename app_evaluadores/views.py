from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from app_usuarios.permisos import es_evaluador
from django.contrib import messages
from django.http import HttpResponse, FileResponse, Http404
from .models import Evaluador
from app_eventos.models import Evento, EventoCategoria
from app_evaluadores.models import Criterio, Calificacion, EvaluadorEvento
from app_participantes.models import ParticipanteEvento, Participante
from app_usuarios.models import Usuario
import os
from django.conf import settings
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle


def calcular_y_guardar_nota_general(participante, evento):
    criterios = Criterio.objects.filter(cri_evento_fk=evento)
    peso_total = sum(c.cri_peso for c in criterios) or 1
    
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
        
        participante_evento = ParticipanteEvento.objects.get(
            participante=participante,
            evento=evento
        )
        participante_evento.par_eve_valor = round(puntaje_ponderado, 2)
        participante_evento.save()
        
        return round(puntaje_ponderado, 2)
    
    return 0



def obtener_puesto_participante(participante, evento):
    """
    Obtiene el puesto de un participante en un evento basado en su nota
    """
    # Obtener todas las participaciones del evento ordenadas por nota
    participaciones = ParticipanteEvento.objects.filter(
        evento=evento,
        par_eve_estado='Aprobado',
        par_eve_valor__isnull=False
    ).order_by('-par_eve_valor')
    
    # Encontrar el puesto del participante
    for i, pe in enumerate(participaciones, 1):
        if pe.participante == participante:
            return i
    
    return None  # No encontrado o sin calificación




@login_required
@user_passes_test(es_evaluador, login_url='login')
def dashboard_evaluador(request):
    evaluador = request.user.evaluador
    inscripciones = EvaluadorEvento.objects.select_related('evento').filter(evaluador=evaluador)

    # Agregar información sobre archivos disponibles a cada inscripción
    inscripciones_con_archivos = []
    for inscripcion in inscripciones:
        inscripcion_data = {
            'inscripcion': inscripcion,
            'evento': inscripcion.evento,
            'estado': inscripcion.eva_eve_estado,
            'tiene_memorias': bool(inscripcion.evento.eve_memorias),
            'tiene_info_tecnica': bool(inscripcion.evento.eve_informacion_tecnica),
        }
        inscripciones_con_archivos.append(inscripcion_data)

    return render(request, 'app_evaluadores/dashboard_evaluador.html', {
        'evaluador': evaluador,
        'inscripciones': inscripciones,
        'inscripciones_con_archivos': inscripciones_con_archivos
    })


@login_required
@user_passes_test(es_evaluador, login_url='login')
def gestionar_items(request, eve_id):
    evento = get_object_or_404(Evento, pk=eve_id)
    try:
        evaluador = request.user.evaluador
        inscripcion = EvaluadorEvento.objects.get(evaluador=evaluador, evento=evento)
        
        # Verificar que la inscripción esté aprobada
        if inscripcion.eva_eve_estado != 'Aprobado':
            messages.warning(request, "Tu inscripción como evaluador no ha sido aprobada para este evento.")
            return redirect('dashboard_evaluador')
        
        # Verificar que tenga permiso para gestionar la rúbrica
        if not inscripcion.puede_gestionar_rubrica:
            messages.warning(request, "No tienes permiso para gestionar la rúbrica de este evento.")
            return redirect('dashboard_evaluador')

    except (EvaluadorEvento.DoesNotExist, Evaluador.DoesNotExist):
        messages.error(request, "No estás inscrito como evaluador en este evento.")
        return redirect('dashboard_evaluador')

    # Obtener criterios del evento
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

    # Obtener todos los participantes aprobados
    participantes_evento = ParticipanteEvento.objects.filter(
        evento=evento,
        par_eve_estado='Aprobado'
    ).select_related('participante__usuario', 'proyecto')

    # Obtener todos los participantes que ya fueron calificados por este evaluador
    calificaciones = Calificacion.objects.filter(
        evaluador=evaluador,
        criterio__cri_evento_fk=evento
    ).values_list('participante_id', flat=True).distinct()

    calificados_ids = set(calificaciones)

    # Agrupar participantes por proyecto
    proyectos = {}
    for pe in participantes_evento:
        proyecto = pe.proyecto
        if proyecto not in proyectos:
            proyectos[proyecto] = []
        proyectos[proyecto].append(pe)

    # Determinar si cada proyecto ya fue calificado (si al menos un miembro fue calificado)
    proyectos_calificados = set()
    for proyecto, participantes in proyectos.items():
        if any(p.participante.id in calificados_ids for p in participantes):
            proyectos_calificados.add(proyecto)

    context = {
        'participantes': participantes_evento,
        'evento': evento,
        'proyectos_calificados': proyectos_calificados,
    }
    return render(request, 'lista_participantes_evaluador.html', context)


@login_required
@user_passes_test(es_evaluador, login_url='login')
def calificar_participante(request, eve_id, participante_id):
    evento = get_object_or_404(Evento, pk=eve_id)
    try:
        evaluador = request.user.evaluador
        inscripcion = EvaluadorEvento.objects.get(evaluador=evaluador, evento=evento)
        if inscripcion.eva_eve_estado != 'Aprobado':
            messages.warning(request, "Tu inscripción como evaluador aún no ha sido aprobada para este evento.")
            return redirect('dashboard_evaluador')
    except (EvaluadorEvento.DoesNotExist, Evaluador.DoesNotExist):
        messages.error(request, "No estás inscrito como evaluador en este evento.")
        return redirect('dashboard_evaluador')
    participante = get_object_or_404(Participante, pk=participante_id)
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
    
        # Calcular nota general para este participante
        nota = calcular_y_guardar_nota_general(participante, evento)

        # Propagar calificación al proyecto y demás integrantes si es grupal
        if participacion.proyecto:
            proyecto = participacion.proyecto
            proyecto.pro_valor = nota
            proyecto.save()
        
            # Actualizar todos los integrantes del proyecto
            integrantes = ParticipanteEvento.objects.filter(
                proyecto=proyecto,
                par_eve_estado='Aprobado'
            )
            for integrante in integrantes:
                integrante.par_eve_valor = nota
                integrante.save()
    
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
        evaluador = request.user.evaluador
        inscripcion = EvaluadorEvento.objects.get(evaluador=evaluador, evento=evento)
        if inscripcion.eva_eve_estado != 'Aprobado':
            messages.warning(request, "Tu inscripción a este evento aún no ha sido aprobada.")
            return redirect('dashboard_evaluador')
    except (EvaluadorEvento.DoesNotExist, Evaluador.DoesNotExist):
        messages.error(request, "No estás inscrito en este evento.")
        return redirect('dashboard_evaluador')

    criterios = Criterio.objects.filter(cri_evento_fk=evento)
    peso_total = sum(c.cri_peso for c in criterios) or 1

    # Incluir el proyecto en el select_related
    participantes_evento = ParticipanteEvento.objects.filter(
        evento=evento,
        par_eve_estado='Aprobado'
    ).select_related('participante', 'proyecto')  # 👈 Clave: agregar 'proyecto'

    posiciones = []
    for pe in participantes_evento:
        participante = pe.participante
        
        # Si ya tenemos la nota guardada, la usamos; si no, la calculamos
        if pe.par_eve_valor is not None:
            puntaje_ponderado = pe.par_eve_valor
        else:
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
                puntaje_ponderado = round(puntaje_ponderado, 2)
                pe.par_eve_valor = puntaje_ponderado
                pe.save()
            else:
                puntaje_ponderado = 0

        # Guardar también el proyecto
        posiciones.append({
            'participante': participante,
            'puntaje': puntaje_ponderado,
            'proyecto': pe.proyecto  # 👈 Aquí está el dato clave
        })

    posiciones.sort(key=lambda x: x['puntaje'], reverse=True)

    return render(request, 'tabla_posiciones_evaluador.html', {
        'evento': evento,
        'posiciones': posiciones
    })

@login_required
@user_passes_test(es_evaluador, login_url='login')
def descargar_tabla_posiciones_pdf(request, eve_id):
    evento = get_object_or_404(Evento, pk=eve_id)
    try:
        evaluador = request.user.evaluador
        inscripcion = EvaluadorEvento.objects.get(evaluador=evaluador, evento=evento)
        if inscripcion.eva_eve_estado != 'Aprobado':
            messages.warning(request, "No tienes acceso a este evento porque tu inscripción no está aprobada.")
            return redirect('dashboard_evaluador')
    except (EvaluadorEvento.DoesNotExist, Evaluador.DoesNotExist):
        messages.error(request, "No estás inscrito en este evento.")
        return redirect('dashboard_evaluador')

    # Obtener participantes calificados y ordenados
    participantes_evento = ParticipanteEvento.objects.filter(
        evento=evento,
        par_eve_estado='Aprobado',
        par_eve_valor__isnull=False
    ).select_related('participante__usuario', 'proyecto').order_by('-par_eve_valor')

    # Crear la respuesta HTTP con el contenido PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="tabla_posiciones_{evento.eve_nombre}.pdf"'

    # Crear el documento PDF
    doc = SimpleDocTemplate(response, pagesize=letter)
    elements = []

    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=1,  # Centrado
    )
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=20,
        alignment=1,
    )

    # Título
    elements.append(Paragraph(f"Tabla de Posiciones", title_style))
    elements.append(Paragraph(f"Evento: {evento.eve_nombre}", subtitle_style))
    elements.append(Spacer(1, 20))

    # Preparar datos para la tabla
    data = [["Posición", "Nombre del Participante", "Correo", "Proyecto Grupal / Individual", "Puntaje"]]

    for i, pe in enumerate(participantes_evento, start=1):
        nombre = f"{pe.participante.usuario.first_name} {pe.participante.usuario.last_name}"
        correo = pe.participante.usuario.email
        proyecto = pe.proyecto.titulo if pe.proyecto else "Individual"
        puntaje = f"{pe.par_eve_valor:.2f}"

        # Usar Paragraph para permitir saltos de línea si es necesario
        data.append([str(i), nombre, correo, Paragraph(proyecto, styles['Normal']), puntaje])

    # Ajustar anchos de columna para evitar desbordamiento
    col_widths = [
        0.8*inch,  # Posición
        2.2*inch,  # Nombre
        2.0*inch,  # Correo
        2.5*inch,  # Tipo de Proyecto (más ancho)
        0.8*inch,  # Puntaje
    ]

    # Crear la tabla
    table = Table(data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
    ]))

    elements.append(table)

    # Generar el PDF
    doc.build(elements)

    return response

@login_required
@user_passes_test(es_evaluador, login_url='login')
def informacion_detallada(request, eve_id):   
    evaluador = request.user.evaluador
    evento = get_object_or_404(Evento, pk=eve_id)
    try:
        evaluador = request.user.evaluador
        inscripcion = EvaluadorEvento.objects.get(evaluador=evaluador, evento=evento)
        if inscripcion.eva_eve_estado != 'Aprobado':
            messages.warning(request, "No tienes acceso a este evento porque tu inscripción no está aprobada.")
            return redirect('dashboard_evaluador')
    except (EvaluadorEvento.DoesNotExist, Evaluador.DoesNotExist):
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
    evaluador = evaluador_usuario.evaluador
    inscripcion = get_object_or_404(EvaluadorEvento, evaluador=evaluador, evento=evento)
    if inscripcion.eva_eve_estado != "Pendiente":
        messages.error(request, "No puedes cancelar la inscripción porque ya fue aprobada.")
        return redirect('dashboard_evaluador')
    if request.method == 'POST':
        inscripcion.delete()
        otros_eventos = EvaluadorEvento.objects.filter(evaluador=evaluador).count()
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
    evaluador = usuario.evaluador
    inscripcion = get_object_or_404(EvaluadorEvento, evaluador=evaluador, evento=evento)
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


@login_required
@user_passes_test(es_evaluador, login_url='login')
def descargar_memorias_evaluador(request, evento_id):
    """Vista para descargar las memorias de un evento como evaluador"""
    evento = get_object_or_404(Evento, eve_id=evento_id)
    evaluador = request.user.evaluador
    
    # Verificar que el evaluador esté inscrito en el evento
    inscripcion = get_object_or_404(EvaluadorEvento, evaluador=evaluador, evento=evento)
    
    # Solo permitir si el estado no es "Pendiente"
    if inscripcion.eva_eve_estado == 'Pendiente':
        messages.error(request, "No puedes descargar memorias mientras tu inscripción esté pendiente.")
        return redirect('dashboard_evaluador')
    
    # Verificar que el archivo de memorias exista
    if not evento.eve_memorias:
        messages.error(request, "Este evento no tiene memorias disponibles para descargar.")
        return redirect('dashboard_evaluador')
    
    # Verificar que el archivo físico exista
    if not os.path.exists(evento.eve_memorias.path):
        messages.error(request, "El archivo de memorias no se encuentra disponible.")
        return redirect('dashboard_evaluador')
    
    try:
        response = FileResponse(
            open(evento.eve_memorias.path, 'rb'),
            as_attachment=True,
            filename=f"Memorias_{evento.eve_nombre}_{evento.eve_memorias.name.split('/')[-1]}"
        )
        return response
    except Exception as e:
        messages.error(request, "Error al descargar el archivo de memorias.")
        return redirect('dashboard_evaluador')


@login_required
@user_passes_test(es_evaluador, login_url='login')
def descargar_informacion_tecnica_evaluador(request, evento_id):
    """Vista para descargar la información técnica de un evento como evaluador"""
    evento = get_object_or_404(Evento, eve_id=evento_id)
    evaluador = request.user.evaluador
    
    # Verificar que el evaluador esté inscrito en el evento
    inscripcion = get_object_or_404(EvaluadorEvento, evaluador=evaluador, evento=evento)
    
    # Solo permitir si el estado no es "Pendiente"
    if inscripcion.eva_eve_estado == 'Pendiente':
        messages.error(request, "No puedes descargar información técnica mientras tu inscripción esté pendiente.")
        return redirect('dashboard_evaluador')
    
    # Verificar que el archivo de información técnica exista
    if not evento.eve_informacion_tecnica:
        messages.error(request, "Este evento no tiene información técnica disponible para descargar.")
        return redirect('dashboard_evaluador')
    
    # Verificar que el archivo físico exista
    if not os.path.exists(evento.eve_informacion_tecnica.path):
        messages.error(request, "El archivo de información técnica no se encuentra disponible.")
        return redirect('dashboard_evaluador')
    
    try:
        response = FileResponse(
            open(evento.eve_informacion_tecnica.path, 'rb'),
            as_attachment=True,
            filename=f"InfoTecnica_{evento.eve_nombre}_{evento.eve_informacion_tecnica.name.split('/')[-1]}"
        )
        return response
    except Exception as e:
        messages.error(request, "Error al descargar el archivo de información técnica.")
        return redirect('dashboard_evaluador')
    
@login_required
@user_passes_test(es_evaluador, login_url='login')
@login_required
@user_passes_test(es_evaluador, login_url='login')
def ver_perfil_evaluador(request, evento_id):
    evaluador = request.user.evaluador  # Obtener el Evaluador asociado al usuario actual
    evaluador_evento = get_object_or_404(EvaluadorEvento, evento_id=evento_id, evaluador=evaluador)
    
    # Acceder al usuario asociado al evaluador
    usuario = evaluador.usuario
    
    return render(request, 'perfil_evaluador.html', {
        'evento': evaluador_evento.evento,
        'evaluador': evaluador_evento,
        'usuario': usuario,  # Agregar el usuario al contexto
        'qr_url': evaluador_evento.eva_eve_qr.url if evaluador_evento.eva_eve_qr else None,
    })

@login_required
@user_passes_test(es_evaluador, login_url='login')
def cargar_programacion_tecnica(request, evento_id):
    evento = get_object_or_404(Evento, pk=evento_id)
    if request.method == 'POST':
        archivo = request.FILES.get('programacion_tecnica')
        if archivo:
            evento.eve_programacion_tecnica = archivo
            evento.save()
            messages.success(request, "Programación técnica cargada correctamente.")
        else:
            messages.error(request, "Debes seleccionar un archivo.")
        return redirect('dashboard_evaluador')
    return render(request, 'cargar_programacion_tecnica.html', {'evento': evento})

def manual_evaluador(request):
    """
    Sirve el manual del Evaluador en formato PDF.
    """
    ruta_manual = os.path.join(settings.MEDIA_ROOT, "manuales", "MANUAL_EVALUADOR_SISTEMA_EVENTSOFT.pdf")
    if os.path.exists(ruta_manual):
        return FileResponse(open(ruta_manual, "rb"), content_type="application/pdf")
    raise Http404("Manual no encontrado")