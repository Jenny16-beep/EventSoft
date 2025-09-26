from django.http import HttpResponse
from weasyprint import HTML
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, FileResponse
from django.core.files.base import ContentFile
from django.utils.crypto import get_random_string
from django.conf import settings
from django.db import transaction
import base64
import os
import mimetypes
from io import BytesIO
from django.http import HttpResponse, Http404
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.contrib import messages
from django.shortcuts import redirect
from .models import AdministradorEvento, CodigoInvitacionAdminEvento, CodigoInvitacionEvento
from app_eventos.models import Evento
from app_eventos.models import EventoCategoria
from app_areas.models import Area, Categoria
from app_participantes.models import ParticipanteEvento, Participante
from app_asistentes.models import AsistenteEvento
from app_evaluadores.models import Criterio, Calificacion
from app_evaluadores.models import EvaluadorEvento, Evaluador
from app_usuarios.models import Usuario
from app_asistentes.models import Asistente, AsistenteEvento
from app_participantes.models import Participante, ParticipanteEvento
from app_evaluadores.models import Evaluador, EvaluadorEvento
from app_administradores.models import CodigoInvitacionEvento
from app_eventos.models import ConfiguracionCertificado, EventoCategoria
from app_usuarios.models import RolUsuario
from django.contrib.auth.decorators import login_required, user_passes_test
from app_usuarios.permisos import es_administrador_evento
import qrcode
import io
import mimetypes
import os
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from app_usuarios.models import Rol, RolUsuario
from django.template import Context, Template
from app_eventos.models import ConfiguracionCertificado
from django.contrib import messages
from django.core.files.images import get_image_dimensions
from django.conf import settings
from django.utils import timezone
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle


@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def dashboard_adminevento(request):
    return render(request, 'app_administradores/dashboard_adminevento.html')


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
            administrador = request.user.administrador
        except AdministradorEvento.DoesNotExist:
            messages.error(request, "Tu cuenta no está asociada como Administrador de Evento.")
            return redirect('ver_eventos')

        # Validar código de invitación
        invitacion = CodigoInvitacionAdminEvento.objects.filter(usuario_asignado=request.user).order_by('-fecha_creacion').first()
        if not invitacion:
            messages.error(request, "No tienes un código de invitación válido asociado a tu cuenta.")
            return redirect('dashboard_adminevento')

        # Validar tiempo límite de creación (si existe)
        if invitacion.tiempo_limite_creacion:
            
            if timezone.now() > invitacion.tiempo_limite_creacion:
                messages.error(request, "El tiempo límite para crear eventos con tu código de invitación ha expirado.")
                return redirect('dashboard_adminevento')

        # Validar cupos disponibles
        if invitacion.limite_eventos < 1:
            messages.error(request, "Ya has alcanzado el límite de eventos permitidos por tu código de invitación.")
            return redirect('dashboard_adminevento')

        # Crear evento y descontar cupo
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
        invitacion.limite_eventos -= 1
        invitacion.save()
        categoria_ids = request.POST.getlist('categoria_id[]')
        for cat_id in categoria_ids:
            EventoCategoria.objects.create(evento=evento, categoria_id=cat_id)
        # Enviar correo a los superadmin       
        try:
            rol_superadmin = Rol.objects.get(nombre__iexact='superadmin')
            usuarios_superadmin = RolUsuario.objects.filter(rol=rol_superadmin).select_related('usuario')
            correos_superadmin = [ru.usuario.email for ru in usuarios_superadmin if ru.usuario.email]
        except Rol.DoesNotExist:
            correos_superadmin = []

        if correos_superadmin:
            cuerpo_html = render_to_string('correo_nuevo_evento_superadmin.html', {
                'evento': evento,
                'creador': request.user,
            })
            email = EmailMessage(
                subject=f'Nuevo evento creado: {evento.eve_nombre}',
                body=cuerpo_html,
                to=correos_superadmin,
            )
            email.content_subtype = 'html'
            email.send(fail_silently=True)

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
    administrador = request.user.administrador
    
    # Verificar que el evento pertenece al administrador logueado
    if evento.eve_administrador_fk != administrador:
        messages.error(request, "No tienes permisos para eliminar este evento.")
        return redirect('listar_eventos')
    
    # Verificar si será el último evento del administrador
    otros_eventos = Evento.objects.filter(eve_administrador_fk=administrador).exclude(eve_id=evento.eve_id).exists()
    
    advertencia_eliminacion_usuario = False
    if not otros_eventos:
        # No tiene más eventos, verificar códigos de invitación
        codigos_admin = CodigoInvitacionAdminEvento.objects.filter(usuario_asignado=request.user)
        tiene_limite_positivo = codigos_admin.filter(limite_eventos__gt=0).exists()
        
        if not tiene_limite_positivo:
            # Su usuario será eliminado
            advertencia_eliminacion_usuario = True
    
    if request.method == 'POST':
        confirmacion = request.POST.get('confirmacion_eliminacion')
        if confirmacion == 'confirmar':
            try:
                with transaction.atomic():
                    # Usar la misma lógica de eliminación que en app_admin
                    _eliminar_informacion_evento_completo(evento)
                    
                    if advertencia_eliminacion_usuario:
                        messages.warning(request, 'Evento eliminado. Tu cuenta de usuario también ha sido eliminada del sistema.')
                        # Cerrar sesión ya que el usuario será eliminado
                        from django.contrib.auth import logout
                        logout(request)
                        return redirect('login')
                    else:
                        messages.success(request, "Evento eliminado correctamente.")
                        return redirect('listar_eventos')
            except Exception as e:
                messages.error(request, f"Error al eliminar el evento: {str(e)}")
                return redirect('listar_eventos')
        else:
            messages.error(request, "Debes confirmar la eliminación.")
    
    return render(request, 'confirmar_eliminacion_evento.html', {
        'evento': evento,
        'advertencia_eliminacion_usuario': advertencia_eliminacion_usuario,
        'otros_eventos': otros_eventos
    })


def _eliminar_informacion_evento_completo(evento):
    """
    Función auxiliar para eliminar toda la información relacionada con un evento.
    Versión para administradores - misma lógica que app_admin
    """
    
    # 1. Eliminar AsistenteEvento del evento
    asistentes_evento = AsistenteEvento.objects.filter(evento=evento)
    asistentes_ids = list(asistentes_evento.values_list('asistente_id', flat=True))
    asistentes_evento.delete()
    
    # Verificar si los asistentes están en otros eventos
    for asistente_id in asistentes_ids:
        try:
            asistente = Asistente.objects.get(id=asistente_id)
            if not AsistenteEvento.objects.filter(asistente=asistente).exists():
                usuario = asistente.usuario
                RolUsuario.objects.filter(usuario=usuario, rol__nombre='asistente').delete()
                asistente.delete()
                if not RolUsuario.objects.filter(usuario=usuario).exists():
                    usuario.delete()
        except Asistente.DoesNotExist:
            continue
    
    # 2. Eliminar ParticipanteEvento del evento
    participantes_evento = ParticipanteEvento.objects.filter(evento=evento)
    participantes_ids = list(participantes_evento.values_list('participante_id', flat=True))
    participantes_evento.delete()
    
    # Verificar si los participantes están en otros eventos
    for participante_id in participantes_ids:
        try:
            participante = Participante.objects.get(id=participante_id)
            if not ParticipanteEvento.objects.filter(participante=participante).exists():
                usuario = participante.usuario
                RolUsuario.objects.filter(usuario=usuario, rol__nombre='participante').delete()
                participante.delete()
                if not RolUsuario.objects.filter(usuario=usuario).exists():
                    usuario.delete()
        except Participante.DoesNotExist:
            continue
    
    # 3. Eliminar EvaluadorEvento del evento
    evaluadores_evento = EvaluadorEvento.objects.filter(evento=evento)
    evaluadores_ids = list(evaluadores_evento.values_list('evaluador_id', flat=True))
    evaluadores_evento.delete()
    
    # Verificar si los evaluadores están en otros eventos
    for evaluador_id in evaluadores_ids:
        try:
            evaluador = Evaluador.objects.get(id=evaluador_id)
            if not EvaluadorEvento.objects.filter(evaluador=evaluador).exists():
                usuario = evaluador.usuario
                RolUsuario.objects.filter(usuario=usuario, rol__nombre='evaluador').delete()
                evaluador.delete()
                if not RolUsuario.objects.filter(usuario=usuario).exists():
                    usuario.delete()
        except Evaluador.DoesNotExist:
            continue
    
    # 4. Manejar el administrador del evento
    administrador = evento.eve_administrador_fk
    if administrador:
        usuario_admin = administrador.usuario
        
        # Verificar si tiene más eventos (excluyendo el actual)
        otros_eventos_admin = Evento.objects.filter(eve_administrador_fk=administrador).exclude(eve_id=evento.eve_id).exists()
        
        if not otros_eventos_admin:
            # No tiene más eventos, verificar códigos de invitación
            codigos_admin = CodigoInvitacionAdminEvento.objects.filter(usuario_asignado=usuario_admin)
            tiene_limite_positivo = codigos_admin.filter(limite_eventos__gt=0).exists()
            
            if not tiene_limite_positivo:
                # Eliminar códigos, rol y usuario
                codigos_admin.delete()
                RolUsuario.objects.filter(usuario=usuario_admin, rol__nombre='administrador_evento').delete()
                administrador.delete()
                if not RolUsuario.objects.filter(usuario=usuario_admin).exists():
                    usuario_admin.delete()
    
    # 5. Eliminar relaciones y configuraciones del evento
    CodigoInvitacionEvento.objects.filter(evento=evento).delete()
    ConfiguracionCertificado.objects.filter(evento=evento).delete()
    EventoCategoria.objects.filter(evento=evento).delete()
    
    # 6. Finalmente, eliminar el evento
    evento.delete()

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
    asistentes = AsistenteEvento.objects.select_related('asistente').filter(evento__eve_id=eve_id, confirmado=True)
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
        enviar_qr = False
        qr_buffer = None

        if nuevo_estado == "Aprobado":
            if estado_actual == "Pendiente":
                evento.eve_capacidad = max(evento.eve_capacidad - 1, 0)

            if not asistente_evento.asi_eve_qr:
                
                data_qr = f"Asistente: {asistente_evento.asistente.usuario.get_full_name()} - Evento: {evento.eve_nombre}"
                img = qrcode.make(data_qr)
                qr_buffer = io.BytesIO()
                img.save(qr_buffer, format='PNG')
                filename = f"qr_asistente_{asistente_id}_evento_{evento.eve_id}.png"
                asistente_evento.asi_eve_qr.save(filename, ContentFile(qr_buffer.getvalue()), save=False)
                enviar_qr = True
            else:
                enviar_qr = True

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

        # Enviar correo al asistente
        usuario_asistente = asistente_evento.asistente.usuario
        if usuario_asistente and usuario_asistente.email:
            
            cuerpo_html = render_to_string('correo_estado_asistente.html', {
                'evento': evento,
                'asistente': usuario_asistente,
                'nuevo_estado': nuevo_estado,
            })
            email = EmailMessage(
                subject=f'Actualización de estado de tu inscripción como asistente en {evento.eve_nombre}',
                body=cuerpo_html,
                to=[usuario_asistente.email],
            )
            email.content_subtype = 'html'
            if nuevo_estado == "Aprobado" and asistente_evento.asi_eve_qr:
                # Adjuntar QR
                qr_path = asistente_evento.asi_eve_qr.path
                email.attach_file(qr_path)
            email.send(fail_silently=True)

        return redirect('ver_asistentes_evento', eve_id=eve_id)

    return render(request, 'detalle_asistente.html', {
        'asistente': asistente_evento,
        'evento': evento
    })

@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def gestion_participantes(request, eve_id):
    evento = get_object_or_404(Evento, pk=eve_id)
    participantes = ParticipanteEvento.objects.filter(evento=evento, confirmado=True).select_related('participante')
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
    participante_evento = ParticipanteEvento.objects.select_related(
        'participante__usuario', 'evento'
    ).filter(evento=evento, participante=participante).first()

    if not participante_evento:
        messages.error(request, "Participante no encontrado en este evento")
        return redirect('ver_participantes_evento', eve_id=eve_id)

    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        if nuevo_estado:
            usuario = participante.usuario
            enviar_qr = False

            if nuevo_estado == 'Aprobado':
                if not participante_evento.par_eve_qr:
                    data_qr = f"Participante: {usuario.first_name} {usuario.last_name} - Evento: {evento.eve_nombre}"
                    img = qrcode.make(data_qr)
                    buffer = io.BytesIO()
                    img.save(buffer, format='PNG')
                    file_name = f"qr_{get_random_string(8)}.png"
                    participante_evento.par_eve_qr.save(file_name, ContentFile(buffer.getvalue()), save=False)
                    enviar_qr = True
                else:
                    enviar_qr = True

                participante_evento.par_eve_estado = nuevo_estado
                participante_evento.save()

                # 🔹 Actualizar estado del proyecto asociado
                if participante_evento.proyecto:
                    participante_evento.proyecto.estado = nuevo_estado
                    participante_evento.proyecto.save()

                # 🔹 NUEVO: Actualizar estado de todos los integrantes del proyecto grupal
                if participante_evento.codigo:  # Si tiene código, es proyecto grupal
                    # Buscar todos los participantes con el mismo código (mismo proyecto)
                    integrantes_grupo = ParticipanteEvento.objects.filter(
                        evento=evento,
                        codigo=participante_evento.codigo
                    ).exclude(participante=participante)  # Excluir el actual
                    
                    for integrante in integrantes_grupo:
                        if integrante.par_eve_estado != 'Aprobado':  # Solo actualizar si no está ya aprobado
                            # Generar QR para cada integrante
                            if not integrante.par_eve_qr:
                                data_qr_int = f"Participante: {integrante.participante.usuario.first_name} {integrante.participante.usuario.last_name} - Evento: {evento.eve_nombre}"
                                img_int = qrcode.make(data_qr_int)
                                buffer_int = io.BytesIO()
                                img_int.save(buffer_int, format='PNG')
                                file_name_int = f"qr_{get_random_string(8)}.png"
                                integrante.par_eve_qr.save(file_name_int, ContentFile(buffer_int.getvalue()), save=False)
                            
                            integrante.par_eve_estado = nuevo_estado
                            integrante.save()
                            
                            # Enviar correo a cada integrante
                            if integrante.participante.usuario.email:
                                cuerpo_html = render_to_string('correo_estado_participante.html', {
                                    'evento': evento,
                                    'participante': integrante.participante.usuario,
                                    'nuevo_estado': nuevo_estado,
                                })
                                email = EmailMessage(
                                    subject=f'Actualización de estado de tu inscripción como participante en {evento.eve_nombre}',
                                    body=cuerpo_html,
                                    to=[integrante.participante.usuario.email],
                                )
                                email.content_subtype = 'html'
                                if integrante.par_eve_qr:
                                    qr_path = integrante.par_eve_qr.path
                                    email.attach_file(qr_path)
                                email.send(fail_silently=True)
                    
                    messages.success(request, f"Inscripción aprobada junto con {integrantes_grupo.count()} integrantes más del proyecto grupal")
                else:
                    messages.success(request, "Inscripción aprobada")

            elif nuevo_estado == 'Pendiente':
                if participante_evento.par_eve_qr:
                    participante_evento.par_eve_qr.delete(save=False)
                    participante_evento.par_eve_qr = None
                participante_evento.par_eve_estado = nuevo_estado
                participante_evento.save()

                # 🔹 Actualizar proyecto también a pendiente
                if participante_evento.proyecto:
                    participante_evento.proyecto.estado = nuevo_estado
                    participante_evento.proyecto.save()

                # 🔹 NUEVO: Actualizar estado de todos los integrantes del proyecto grupal
                if participante_evento.codigo:  # Si tiene código, es proyecto grupal
                    integrantes_grupo = ParticipanteEvento.objects.filter(
                        evento=evento,
                        codigo=participante_evento.codigo
                    ).exclude(participante=participante)
                    
                    for integrante in integrantes_grupo:
                        if integrante.par_eve_qr:
                            integrante.par_eve_qr.delete(save=False)
                            integrante.par_eve_qr = None
                        integrante.par_eve_estado = nuevo_estado
                        integrante.save()
                        
                        # Enviar correo a cada integrante
                        if integrante.participante.usuario.email:
                            cuerpo_html = render_to_string('correo_estado_participante.html', {
                                'evento': evento,
                                'participante': integrante.participante.usuario,
                                'nuevo_estado': nuevo_estado,
                            })
                            email = EmailMessage(
                                subject=f'Actualización de estado de tu inscripción como participante en {evento.eve_nombre}',
                                body=cuerpo_html,
                                to=[integrante.participante.usuario.email],
                            )
                            email.content_subtype = 'html'
                            email.send(fail_silently=True)
                    
                    messages.info(request, f"Estado restablecido a pendiente junto con {integrantes_grupo.count()} integrantes más del proyecto grupal")
                else:
                    messages.info(request, "Estado restablecido a pendiente y QR eliminado")

            elif nuevo_estado == 'Rechazado':
                # 🔹 Actualizar estado del proyecto antes de eliminar
                if participante_evento.proyecto:
                    participante_evento.proyecto.estado = nuevo_estado
                    participante_evento.proyecto.save()

                # 🔹 NUEVO: Actualizar/eliminar todos los integrantes del proyecto grupal
                if participante_evento.codigo:  # Si tiene código, es proyecto grupal
                    integrantes_grupo = ParticipanteEvento.objects.filter(
                        evento=evento,
                        codigo=participante_evento.codigo
                    ).exclude(participante=participante)
                    
                    # Enviar correos y eliminar integrantes
                    integrantes_eliminados = 0
                    for integrante in integrantes_grupo:
                        # Enviar correo antes de eliminar
                        if integrante.participante.usuario.email:
                            cuerpo_html = render_to_string('correo_estado_participante.html', {
                                'evento': evento,
                                'participante': integrante.participante.usuario,
                                'nuevo_estado': nuevo_estado,
                            })
                            email = EmailMessage(
                                subject=f'Actualización de estado de tu inscripción como participante en {evento.eve_nombre}',
                                body=cuerpo_html,
                                to=[integrante.participante.usuario.email],
                            )
                            email.content_subtype = 'html'
                            email.send(fail_silently=True)
                        
                        # Eliminar inscripción del integrante
                        participante_int = integrante.participante
                        integrante.delete()
                        
                        # Eliminar participante si no tiene otras inscripciones
                        otros_eventos = ParticipanteEvento.objects.filter(participante=participante_int).exists()
                        if not otros_eventos:
                            participante_int.delete()
                        
                        integrantes_eliminados += 1
                    
                    messages.warning(request, f"Inscripción rechazada junto con {integrantes_eliminados} integrantes más del proyecto grupal")
                else:
                    messages.warning(request, "Inscripción rechazada")

                # Eliminar la inscripción principal
                participante_evento.delete()
                otros_eventos = ParticipanteEvento.objects.filter(participante=participante).exists()
                if not otros_eventos:
                    participante.delete()
                    messages.warning(request, "Participante eliminado completamente")
                    return redirect('ver_participantes_evento', eve_id=eve_id)
                else:
                    messages.warning(request, "Participante eliminado del evento")
                    return redirect('ver_participantes_evento', eve_id=eve_id)

            # Enviar correo al participante principal
            usuario_participante = participante.usuario
            if usuario_participante and usuario_participante.email:
                cuerpo_html = render_to_string('correo_estado_participante.html', {
                    'evento': evento,
                    'participante': usuario_participante,
                    'nuevo_estado': nuevo_estado,
                })
                email = EmailMessage(
                    subject=f'Actualización de estado de tu inscripción como participante en {evento.eve_nombre}',
                    body=cuerpo_html,
                    to=[usuario_participante.email],
                )
                email.content_subtype = 'html'
                if nuevo_estado == 'Aprobado' and participante_evento.par_eve_qr:
                    qr_path = participante_evento.par_eve_qr.path
                    email.attach_file(qr_path)
                email.send(fail_silently=True)

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
    evaluadores = EvaluadorEvento.objects.filter(evento=evento, confirmado=True).select_related('evaluador__usuario')
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
    usuario = evaluador_evento.evaluador.usuario
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        if nuevo_estado:
            enviar_qr = False
            if nuevo_estado == 'Aprobado':
                if not evaluador_evento.eva_eve_qr:
                    data_qr = f"Evaluador: {usuario.first_name} {usuario.last_name} - Evento: {evento.eve_nombre}"
                    img = qrcode.make(data_qr)
                    buffer = io.BytesIO()
                    img.save(buffer, format='PNG')
                    file_name = f"qr_{get_random_string(8)}.png"
                    evaluador_evento.eva_eve_qr.save(file_name, ContentFile(buffer.getvalue()), save=False)
                    enviar_qr = True
                else:
                    enviar_qr = True
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

            # Enviar correo al evaluador
            usuario_evaluador = usuario
            if usuario_evaluador and usuario_evaluador.email:
                cuerpo_html = render_to_string('correo_estado_evaluador.html', {
                    'evento': evento,
                    'evaluador': usuario_evaluador,
                    'nuevo_estado': nuevo_estado,
                })
                email = EmailMessage(
                    subject=f'Actualización de estado de tu inscripción como evaluador en {evento.eve_nombre}',
                    body=cuerpo_html,
                    to=[usuario_evaluador.email],
                )
                email.content_subtype = 'html'
                if nuevo_estado == 'Aprobado' and evaluador_evento.eva_eve_qr:
                    qr_path = evaluador_evento.eva_eve_qr.path
                    email.attach_file(qr_path)
                email.send(fail_silently=True)

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
    if evento.eve_estado.lower() != 'aprobado':
        messages.error(request, "Solo puedes ver estadísticas de eventos aprobados.")
        return redirect('listar_eventos')
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
    if evento.eve_estado.lower() != 'aprobado':
        messages.error(request, "Solo puedes acceder a esta función si el evento está aprobado.")
        return redirect('listar_eventos')
    context = {
        'evento': evento,
    }
    return render(request, 'dashboard_evaluacion.html', context)


@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def gestion_item_administrador(request, eve_id):
    evento = get_object_or_404(Evento, pk=eve_id)
    if evento.eve_estado.lower() != 'aprobado':
        messages.error(request, "Solo puedes acceder a esta función si el evento está aprobado.")
        return redirect('listar_eventos')
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
    if evento.eve_estado.lower() != 'aprobado':
        messages.error(request, "Solo puedes acceder a esta función si el evento está aprobado.")
        return redirect('listar_eventos')
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
    evento = criterio.cri_evento_fk
    if evento.eve_estado.lower() != 'aprobado':
        messages.error(request, "Solo puedes acceder a esta función si el evento está aprobado.")
        return redirect('listar_eventos')
    criterios_evento = Criterio.objects.filter(cri_evento_fk=evento)
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
@user_passes_test(es_administrador_evento, login_url='login')
def restriccion_rubrica(request, eve_id):
    evento = get_object_or_404(Evento, pk=eve_id)
    if evento.eve_estado.lower() not in ['aprobado', 'inscripciones cerradas']:
        messages.warning(request, "Solo se puede gestionar rúbricas en eventos aprobados o con inscripciones cerradas.")
        return redirect('listar_eventos')

    evaluadores = EvaluadorEvento.objects.filter(evento=evento)
    
    if request.method == 'POST':
        eval_id = request.POST.get('evaluador_id')
        accion = request.POST.get('accion')
        evaluador_evento = get_object_or_404(EvaluadorEvento, pk=eval_id)
        if accion == 'autorizar':
            evaluador_evento.puede_gestionar_rubrica = True
        else:
            evaluador_evento.puede_gestionar_rubrica = False
        evaluador_evento.save()
        messages.success(request, "Permiso de gestión de rúbrica actualizado correctamente.")
        return redirect('restriccion_rubrica', eve_id=eve_id)

    return render(request, 'restriccion_rubrica.html', {
        'evento': evento,
        'evaluadores': evaluadores
    })

@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def ver_tabla_posiciones(request, eve_id):
    evento = get_object_or_404(Evento, pk=eve_id)
    if evento.eve_estado.lower() != 'aprobado':
        messages.error(request, "Solo puedes acceder a esta función si el evento está aprobado.")
        return redirect('listar_eventos')

    criterios = Criterio.objects.filter(cri_evento_fk=evento)
    peso_total = sum(c.cri_peso for c in criterios) or 1

    # Obtener participantes aprobados y cargar proyecto
    participantes_evento = ParticipanteEvento.objects.filter(
        evento=evento,
        par_eve_estado='Aprobado'
    ).select_related('participante', 'proyecto')  # 👈 Agregar 'proyecto'

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

        posiciones.append({
            'participante': participante,
            'puntaje': puntaje_ponderado,
            'proyecto': pe.proyecto  # 👈 Guardar el proyecto
        })

    posiciones.sort(key=lambda x: x['puntaje'], reverse=True)

    return render(request, 'tabla_posiciones.html', {
        'evento': evento,
        'posiciones': posiciones
    })

@login_required
@user_passes_test(es_administrador_evento, login_url='login')
def descargar_tabla_posiciones_pdf_admin(request, eve_id):
    evento = get_object_or_404(Evento, pk=eve_id)
    if evento.eve_administrador_fk.usuario != request.user:
        messages.error(request, "No tienes permiso para acceder a este evento.")
        return redirect('dashboard_adminevento')

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

        data.append([str(i), nombre, correo, Paragraph(proyecto, styles['Normal']), puntaje])

    # Ajustar anchos de columna
    col_widths = [
        0.8*inch,  # Posición
        2.2*inch,  # Nombre
        2.0*inch,  # Correo
        2.5*inch,  # Proyecto Grupal / Individual (más ancho)
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
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def descargar_tabla_posiciones_pdf(request, eve_id):
    evento = get_object_or_404(Evento, pk=eve_id)

    criterios = Criterio.objects.filter(cri_evento_fk=evento)
    peso_total = sum(c.cri_peso for c in criterios) or 1

    participantes_evento = ParticipanteEvento.objects.filter(
        evento=evento, par_eve_estado='Aprobado'
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
        puntaje_ponderado = (
            sum(c.cal_valor * c.criterio.cri_peso for c in calificaciones) /
            (peso_total * num_evaluadores)
        ) if num_evaluadores > 0 else 0
        posiciones.append({
            'participante': participante,
            'puntaje': round(puntaje_ponderado, 2)
        })

    posiciones.sort(key=lambda x: x['puntaje'], reverse=True)

    # Validar si hay datos
    if not posiciones:
        messages.warning(request, "No se puede descargar porque no hay información en la tabla.")
        return redirect('tabla_posiciones_administrador', eve_id=eve_id)

    # Renderizar PDF
    template_path = 'tabla_posiciones_pdf.html'
    context = {'evento': evento, 'posiciones': posiciones}
    template = get_template(template_path)
    html = template.render(context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="tabla_posiciones_{evento.eve_id}.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Error al generar el PDF', status=500)
    return response

@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def info_detallada_admin(request, eve_id):
    administrador = request.user.administrador
    evento = get_object_or_404(Evento, pk=eve_id)
    if evento.eve_administrador_fk != administrador:
        messages.error(request, "No tienes permisos para acceder a este evento.")
        return redirect('listar_eventos')
    if evento.eve_estado.lower() != 'aprobado':
        messages.error(request, "Solo puedes acceder a esta función si el evento está aprobado.")
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

@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def gestionar_notificaciones(request):
    administrador = request.user.administrador
    eventos = Evento.objects.filter(eve_administrador_fk=administrador, eve_estado__iexact='Aprobado')
    tipo = request.GET.get('tipo', 'asistentes')
    evento_id = request.GET.get('evento')
    filtro_nombre = request.GET.get('nombre', '').strip()
    filtro_documento = request.GET.get('documento', '').strip()
    filtro_correo = request.GET.get('correo', '').strip()
    filtro_estado = request.GET.get('estado', '')
    filtro_confirmado = request.GET.get('confirmado', '')
    destinatarios = []
    evento_seleccionado = None
    estados = ['Pendiente', 'Aprobado', 'Rechazado']
    if evento_id:
        evento_seleccionado = get_object_or_404(Evento, pk=evento_id, eve_administrador_fk=administrador)
        if tipo == 'asistentes':
            qs = AsistenteEvento.objects.select_related('asistente__usuario').filter(evento=evento_seleccionado)
            if filtro_nombre:
                qs = qs.filter(Q(asistente__usuario__first_name__icontains=filtro_nombre) | Q(asistente__usuario__last_name__icontains=filtro_nombre))
            if filtro_documento:
                qs = qs.filter(asistente__usuario__documento__icontains=filtro_documento)
            if filtro_correo:
                qs = qs.filter(asistente__usuario__email__icontains=filtro_correo)
            if filtro_estado:
                qs = qs.filter(asi_eve_estado__iexact=filtro_estado)
            if filtro_confirmado:
                qs = qs.filter(confirmado=(filtro_confirmado == 'true'))
            destinatarios = list(qs)
        elif tipo == 'participantes':
            qs = ParticipanteEvento.objects.select_related('participante__usuario').filter(evento=evento_seleccionado)
            if filtro_nombre:
                qs = qs.filter(Q(participante__usuario__first_name__icontains=filtro_nombre) | Q(participante__usuario__last_name__icontains=filtro_nombre))
            if filtro_documento:
                qs = qs.filter(participante__usuario__documento__icontains=filtro_documento)
            if filtro_correo:
                qs = qs.filter(participante__usuario__email__icontains=filtro_correo)
            if filtro_estado:
                qs = qs.filter(par_eve_estado__iexact=filtro_estado)
            if filtro_confirmado:
                qs = qs.filter(confirmado=(filtro_confirmado == 'true'))
            destinatarios = list(qs)
        elif tipo == 'evaluadores':
            qs = EvaluadorEvento.objects.select_related('evaluador__usuario').filter(evento=evento_seleccionado)
            if filtro_nombre:
                qs = qs.filter(Q(evaluador__usuario__first_name__icontains=filtro_nombre) | Q(evaluador__usuario__last_name__icontains=filtro_nombre))
            if filtro_documento:
                qs = qs.filter(evaluador__usuario__documento__icontains=filtro_documento)
            if filtro_correo:
                qs = qs.filter(evaluador__usuario__email__icontains=filtro_correo)
            if filtro_estado:
                qs = qs.filter(eva_eve_estado__iexact=filtro_estado)
            if filtro_confirmado:
                qs = qs.filter(confirmado=(filtro_confirmado == 'true'))
            destinatarios = list(qs)

    if request.method == 'POST':
        tipo = request.POST.get('tipo')
        evento_id = request.POST.get('evento')
        asunto = request.POST.get('asunto', '').strip()
        mensaje = request.POST.get('mensaje', '').strip()
        seleccionados = request.POST.getlist('seleccionados')
        if not asunto or not mensaje or not seleccionados:
            messages.error(request, 'Debes completar el asunto, mensaje y seleccionar al menos un destinatario.')
        else:
            enviados = 0
            if tipo == 'asistentes':
                qs = AsistenteEvento.objects.select_related('asistente__usuario').filter(pk__in=seleccionados)
                for ae in qs:
                    usuario = ae.asistente.usuario
                    if usuario.email:
                        email = EmailMessage(
                            subject=asunto,
                            body=mensaje,
                            to=[usuario.email],
                        )
                        email.content_subtype = 'html'
                        email.send(fail_silently=True)
                        enviados += 1
            elif tipo == 'participantes':
                qs = ParticipanteEvento.objects.select_related('participante__usuario').filter(pk__in=seleccionados)
                for pe in qs:
                    usuario = pe.participante.usuario
                    if usuario.email:
                        email = EmailMessage(
                            subject=asunto,
                            body=mensaje,
                            to=[usuario.email],
                        )
                        email.content_subtype = 'html'
                        email.send(fail_silently=True)
                        enviados += 1
            elif tipo == 'evaluadores':
                qs = EvaluadorEvento.objects.select_related('evaluador__usuario').filter(pk__in=seleccionados)
                for ee in qs:
                    usuario = ee.evaluador.usuario
                    if usuario.email:
                        email = EmailMessage(
                            subject=asunto,
                            body=mensaje,
                            to=[usuario.email],
                        )
                        email.content_subtype = 'html'
                        email.send(fail_silently=True)
                        enviados += 1
            messages.success(request, f'Notificaciones enviadas a {enviados} destinatario(s).')
            return redirect('gestionar_notificaciones')

    return render(request, 'gestionar_notificaciones.html', {
        'eventos': eventos,
        'tipo': tipo,
        'evento_id': evento_id,
        'destinatarios': destinatarios,
        'estados': estados,
        'filtro_nombre': filtro_nombre,
        'filtro_documento': filtro_documento,
        'filtro_correo': filtro_correo,
        'filtro_estado': filtro_estado,
        'filtro_confirmado': filtro_confirmado,
        'evento_seleccionado': evento_seleccionado,
    })


@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def gestionar_archivos_evento(request, eve_id):
    evento = get_object_or_404(Evento, eve_id=eve_id)
    
    # Verificar que el administrador sea el propietario del evento
    if evento.eve_administrador_fk != request.user.administrador:
        messages.error(request, "No tienes permisos para gestionar este evento.")
        return redirect('listar_eventos')
    
    if request.method == 'POST':
        archivo_tipo = request.POST.get('archivo_tipo')
        archivo = request.FILES.get('archivo')
        
        if archivo:
            # Validar tipos de archivo permitidos
            nombre_archivo = archivo.name.lower()
            extensiones_permitidas = ['.pdf', '.doc', '.docx', '.ppt', '.pptx', '.zip']
            
            if not any(nombre_archivo.endswith(ext) for ext in extensiones_permitidas):
                messages.error(request, "Formato de archivo no permitido. Solo se aceptan: PDF, DOC, DOCX, PPT, PPTX, ZIP")
                return redirect('gestionar_archivos_evento', eve_id=eve_id)
            
            # Validar tamaño del archivo (máximo 50MB)
            if archivo.size > 50 * 1024 * 1024:  # 50MB en bytes
                messages.error(request, "El archivo es demasiado grande. El tamaño máximo permitido es 50MB.")
                return redirect('gestionar_archivos_evento', eve_id=eve_id)
            
            if archivo_tipo == 'memorias':
                evento.eve_memorias = archivo
                messages.success(request, "Memorias del evento actualizadas correctamente.")
            elif archivo_tipo == 'informacion_tecnica':
                evento.eve_informacion_tecnica = archivo
                messages.success(request, "Información técnica del evento actualizada correctamente.")
            else:
                messages.error(request, "Tipo de archivo no válido.")
                return redirect('gestionar_archivos_evento', eve_id=eve_id)
            
            evento.save()
        else:
            messages.error(request, "Por favor selecciona un archivo.")
    
    return render(request, 'app_administradores/gestionar_archivos_evento.html', {
        'evento': evento
    })


@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def eliminar_archivo_evento(request, eve_id):
    evento = get_object_or_404(Evento, eve_id=eve_id)
    
    # Verificar que el administrador sea el propietario del evento
    if evento.eve_administrador_fk != request.user.administrador:
        messages.error(request, "No tienes permisos para gestionar este evento.")
        return redirect('listar_eventos')
    
    if request.method == 'POST':
        archivo_tipo = request.POST.get('archivo_tipo')
        
        if archivo_tipo == 'memorias' and evento.eve_memorias:
            evento.eve_memorias.delete(save=False)
            evento.eve_memorias = None
            evento.save()
            messages.success(request, "Memorias del evento eliminadas correctamente.")
        elif archivo_tipo == 'informacion_tecnica' and evento.eve_informacion_tecnica:
            evento.eve_informacion_tecnica.delete(save=False)
            evento.eve_informacion_tecnica = None
            evento.save()
            messages.success(request, "Información técnica del evento eliminada correctamente.")
        else:
            messages.error(request, "No se encontró el archivo a eliminar.")
    
    return redirect('gestionar_archivos_evento', eve_id=eve_id)


# ===============================
# FUNCIONES HELPER
# ===============================

def imagen_to_base64(imagen_field):
    """Convierte un campo de imagen de Django a base64 para usar en PDFs"""
    if imagen_field and hasattr(imagen_field, 'path'):
        try:
            with open(imagen_field.path, 'rb') as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                # Detectar el formato de la imagen
                mime_type, _ = mimetypes.guess_type(imagen_field.path)
                if mime_type:
                    format_name = mime_type.split('/')[1]
                else:
                    # Fallback basado en la extensión
                    ext = os.path.splitext(imagen_field.path)[1].lower()
                    if ext in ['.jpg', '.jpeg']:
                        format_name = 'jpeg'
                    elif ext == '.png':
                        format_name = 'png'
                    elif ext == '.gif':
                        format_name = 'gif'
                    else:
                        format_name = 'jpeg'  # default
                
                return encoded_string, format_name
        except Exception as e:
            print(f"Error al convertir imagen a base64: {e}")
            return None, None
    return None, None


# ===============================
# GESTIÓN DE CERTIFICADOS
# ===============================

@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def gestionar_certificados(request):
    """Vista principal para gestionar certificados"""
    administrador = request.user.administrador
    eventos = Evento.objects.filter(eve_administrador_fk=administrador)
    return render(request, 'app_administradores/gestionar_certificados.html', {
        'eventos': eventos
    })


@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def seleccionar_tipo_certificado(request, eve_id):
    """Vista para seleccionar el tipo de certificado (asistencia, participación, evaluador)"""
    evento = get_object_or_404(Evento, eve_id=eve_id)
    
    # Verificar que el usuario sea el administrador del evento
    if evento.eve_administrador_fk != request.user.administrador:
        messages.error(request, "No tienes permisos para gestionar certificados de este evento.")
        return redirect('gestionar_certificados')
    
    return render(request, 'app_administradores/seleccionar_tipo_certificado.html', {
        'evento': evento
    })

@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def configurar_certificado(request, eve_id, tipo):
    """Vista para configurar el certificado según el tipo"""
    evento = get_object_or_404(Evento, eve_id=eve_id)
    
    # Verificar que el usuario sea el administrador del evento
    if evento.eve_administrador_fk != request.user.administrador:
        messages.error(request, "No tienes permisos para gestionar certificados de este evento.")
        return redirect('gestionar_certificados')
    
    # Verificar que el tipo sea válido
    tipos_validos = ['asistencia', 'participacion', 'evaluador', 'premiacion']
    if tipo not in tipos_validos:
        messages.error(request, "Tipo de certificado no válido.")
        return redirect('seleccionar_tipo_certificado', eve_id=eve_id)
    
    # Mensajes por defecto según el tipo
    if tipo == 'asistencia':
        mensaje_defecto = 'Certificamos que **NOMBRE** identificado(a) con documento **DOCUMENTO** ha asistido al evento **EVENTO** realizado el **FECHA** en **CIUDAD**.'
    elif tipo == 'participacion':
        mensaje_defecto = 'Certificamos que **NOMBRE** identificado(a) con documento **DOCUMENTO** ha participado activamente en el evento **EVENTO** realizado el **FECHA** en **CIUDAD**.'
    elif tipo == 'evaluador':
        mensaje_defecto = 'Certificamos que **NOMBRE** identificado(a) con documento **DOCUMENTO** se ha desempeñado como evaluador en el evento **EVENTO** realizado el **FECHA** en **CIUDAD**.'
    elif tipo == 'premiacion':
        mensaje_defecto = '¡Felicitaciones! Certificamos que **NOMBRE** identificado(a) con documento **DOCUMENTO** obtuvo un destacado desempeño y calificación en el evento **EVENTO** realizado el **FECHA** en **CIUDAD**, alcanzando el **PUESTO** lugar con una puntuación sobresaliente.'
    else:
        mensaje_defecto = 'Certificamos que **NOMBRE** identificado(a) con documento **DOCUMENTO** ha participado en el evento **EVENTO** realizado el **FECHA** en **CIUDAD**.'
    
    # Buscar configuración existente o crear una nueva
    configuracion, created = ConfiguracionCertificado.objects.get_or_create(
        evento=evento,
        tipo=tipo,
        defaults={
            'titulo': f'Certificado de {tipo.title()}',
            'cuerpo': mensaje_defecto,
            'plantilla': 'elegante'
        }
    )
    
    if request.method == 'POST':
        # Actualizar configuración
        configuracion.titulo = request.POST.get('titulo', configuracion.titulo)
        configuracion.cuerpo = request.POST.get('cuerpo', configuracion.cuerpo)
        configuracion.plantilla = request.POST.get('plantilla', configuracion.plantilla)
        
        # Manejar logo
        if 'logo' in request.FILES:
            configuracion.logo = request.FILES['logo']
        
        # Manejar firma
        if 'firma' in request.FILES:
            configuracion.firma = request.FILES['firma']
        
        configuracion.save()
        messages.success(request, f"Configuración del certificado de {tipo} guardada correctamente.")
        return redirect('previsualizar_certificado', eve_id=eve_id, tipo=tipo)
    
    return render(request, 'configurar_certificado.html', {
        'evento': evento,
        'tipo': tipo,
        'configuracion': configuracion,
        'plantillas': ConfiguracionCertificado.PLANTILLA_CHOICES
    })


@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def previsualizar_certificado(request, eve_id, tipo):
    """Vista para previsualizar el certificado"""
    evento = get_object_or_404(Evento, eve_id=eve_id)
    
    # Verificar que el usuario sea el administrador del evento
    if evento.eve_administrador_fk != request.user.administrador:
        messages.error(request, "No tienes permisos para gestionar certificados de este evento.")
        return redirect('gestionar_certificados')
    
    try:
        configuracion = ConfiguracionCertificado.objects.get(evento=evento, tipo=tipo)
    except ConfiguracionCertificado.DoesNotExist:
        messages.error(request, "No has guardado una configuración para este tipo de certificado. Primero debes configurar y guardar el certificado.")
        return redirect('configurar_certificado', eve_id=eve_id, tipo=tipo)
    
    # Verificar que la configuración tenga contenido guardado (no sea solo la configuración por defecto)
    # Validamos que tenga al menos título y cuerpo personalizados
    if not configuracion.titulo or not configuracion.cuerpo:
        messages.error(request, "La configuración del certificado está incompleta. Debes guardar una configuración válida primero.")
        return redirect('configurar_certificado', eve_id=eve_id, tipo=tipo)
    
    # Verificar que no sea la configuración por defecto (comparamos con los mensajes por defecto)
    mensajes_defecto = {
        'asistencia': 'Certificamos que **NOMBRE** identificado(a) con documento **DOCUMENTO** ha asistido al evento **EVENTO** realizado el **FECHA** en **CIUDAD**.',
        'participacion': 'Certificamos que **NOMBRE** identificado(a) con documento **DOCUMENTO** ha participado activamente en el evento **EVENTO** realizado el **FECHA** en **CIUDAD**.',
        'evaluador': 'Certificamos que **NOMBRE** identificado(a) con documento **DOCUMENTO** se ha desempeñado como evaluador en el evento **EVENTO** realizado el **FECHA** en **CIUDAD**.',
        'premiacion': '¡Felicitaciones! Certificamos que **NOMBRE** identificado(a) con documento **DOCUMENTO** obtuvo un destacado desempeño y calificación en el evento **EVENTO** realizado el **FECHA** en **CIUDAD**, alcanzando el **PUESTO** lugar con una puntuación sobresaliente.'
    }
    
    # Si el cuerpo es exactamente igual al mensaje por defecto y el título es genérico, 
    # consideramos que no ha sido realmente configurado
    titulo_defecto = f'Certificado de {tipo.title()}'
    if (configuracion.cuerpo == mensajes_defecto.get(tipo, '') and 
        configuracion.titulo == titulo_defecto):
        messages.warning(request, "Debes personalizar la configuración del certificado antes de poder previsualizarlo. Los valores actuales son solo plantillas por defecto.")
        return redirect('configurar_certificado', eve_id=eve_id, tipo=tipo)
    
    # Datos de ejemplo para la previsualización usando datos reales del evento
    datos_ejemplo = {
        'NOMBRE': 'Ana García López',
        'DOCUMENTO': '1023456789',
        'EVENTO': evento.eve_nombre,
        'FECHA': evento.eve_fecha_inicio.strftime('%d de %B de %Y'),
        'CIUDAD': evento.eve_ciudad,
        'LUGAR': evento.eve_lugar,
    }
    
    # Agregar datos específicos para premiación
    if tipo == 'premiacion':
        datos_ejemplo['PUESTO'] = '1°'
        datos_ejemplo['PUNTUACION'] = '95'
    
    # Renderizar el cuerpo con datos de ejemplo
    cuerpo_con_datos = configuracion.cuerpo
    for clave, valor in datos_ejemplo.items():
        cuerpo_con_datos = cuerpo_con_datos.replace(f'**{clave}**', valor)
    
    if request.GET.get('formato') == 'pdf':
        # Convertir imágenes a base64 para el PDF
        logo_base64, logo_format = imagen_to_base64(configuracion.logo)
        firma_base64, firma_format = imagen_to_base64(configuracion.firma)
        
        # Generar PDF de previsualización
        html_content = render_to_string('certificado_plantilla.html', {
            'configuracion': configuracion,
            'cuerpo_renderizado': cuerpo_con_datos,
            'datos': datos_ejemplo,
            'es_preview': True,
            'logo_base64': logo_base64,
            'logo_format': logo_format,
            'firma_base64': firma_base64,
            'firma_format': firma_format,
        })
        
        pdf_file = HTML(string=html_content, base_url=request.build_absolute_uri()).write_pdf()
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="preview_certificado_{tipo}.pdf"'
        return response
    
    return render(request, 'previsualizar_certificado.html', {
        'evento': evento,
        'tipo': tipo,
        'configuracion': configuracion,
        'cuerpo_renderizado': cuerpo_con_datos,
        'datos_ejemplo': datos_ejemplo
    })

@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def enviar_certificados(request, eve_id, tipo):
    """Vista para enviar certificados a destinatarios"""
    evento = get_object_or_404(Evento, eve_id=eve_id)
    
    # Verificar que el usuario sea el administrador del evento
    if evento.eve_administrador_fk != request.user.administrador:
        messages.error(request, "No tienes permisos para gestionar certificados de este evento.")
        return redirect('gestionar_certificados')
    
    try:
        configuracion = ConfiguracionCertificado.objects.get(evento=evento, tipo=tipo)
    except ConfiguracionCertificado.DoesNotExist:
        messages.error(request, "Debe configurar el certificado primero.")
        return redirect('configurar_certificado', eve_id=eve_id, tipo=tipo)
    
    # Obtener destinatarios según el tipo
    destinatarios = []
    if tipo == 'asistencia':
        destinatarios = AsistenteEvento.objects.filter(
            evento=evento, 
            confirmado=True,
            asi_eve_estado='Aprobado'
        ).select_related('asistente__usuario')
    elif tipo == 'participacion':
        destinatarios = ParticipanteEvento.objects.filter(
            evento=evento, 
            confirmado=True,
            par_eve_estado='Aprobado'
        ).select_related('participante__usuario')
    elif tipo == 'evaluador':
        destinatarios = EvaluadorEvento.objects.filter(
            evento=evento, 
            confirmado=True,
            eva_eve_estado='Aprobado'
        ).select_related('evaluador__usuario')
    
    if request.method == 'POST':
        
        destinatarios_seleccionados = request.POST.getlist('destinatarios')

        if not destinatarios_seleccionados:
            messages.error(request, "Debe seleccionar al menos un destinatario.")
        else:
            # Procesar envío de certificados
            enviados = 0
            errores = []
            
            for dest_id in destinatarios_seleccionados:
                try:
                    # Buscar destinatario según el tipo
                    if tipo == 'asistencia':
                        dest_obj = AsistenteEvento.objects.get(id=dest_id)
                        usuario = dest_obj.asistente.usuario
                    elif tipo == 'participacion':
                        dest_obj = ParticipanteEvento.objects.get(id=dest_id)
                        usuario = dest_obj.participante.usuario
                    elif tipo == 'evaluador':
                        dest_obj = EvaluadorEvento.objects.get(id=dest_id)
                        usuario = dest_obj.evaluador.usuario
                    
                    # Preparar datos del certificado
                    datos_certificado = {
                        'NOMBRE': f'{usuario.first_name} {usuario.last_name}',
                        'DOCUMENTO': usuario.documento,
                        'EVENTO': evento.eve_nombre,
                        'FECHA': evento.eve_fecha_inicio.strftime('%d de %B de %Y'),
                        'CIUDAD': evento.eve_ciudad,
                        'LUGAR': evento.eve_lugar,
                    }
                    
                    # Renderizar el cuerpo del certificado
                    cuerpo_con_datos = configuracion.cuerpo
                    for clave, valor in datos_certificado.items():
                        cuerpo_con_datos = cuerpo_con_datos.replace(f'**{clave}**', valor)
                    
                    # Convertir imágenes a base64 para el PDF
                    logo_base64, logo_format = imagen_to_base64(configuracion.logo)
                    firma_base64, firma_format = imagen_to_base64(configuracion.firma)
                    
                    # Generar PDF del certificado
                    html_content = render_to_string('app_administradores/certificado_plantilla.html', {
                        'configuracion': configuracion,
                        'cuerpo_renderizado': cuerpo_con_datos,
                        'datos': datos_certificado,
                        'es_preview': False,
                        'logo_base64': logo_base64,
                        'logo_format': logo_format,
                        'firma_base64': firma_base64,
                        'firma_format': firma_format,
                    })
                    
                    pdf_file = HTML(string=html_content, base_url=request.build_absolute_uri()).write_pdf()
                    
                    # Enviar por correo electrónico
                    email = EmailMessage(
                        subject=f'Certificado de {tipo.title()} - {evento.eve_nombre}',
                        body=f'Estimado/a {datos_certificado["NOMBRE"]},\n\nAdjuntamos su certificado de {tipo} del evento "{evento.eve_nombre}".\n\nSaludos cordiales.',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=[usuario.email],
                    )
                    
                    filename = f'certificado_{tipo}_{usuario.documento}.pdf'
                    email.attach(filename, pdf_file, 'application/pdf')
                    email.send()
                    
                    enviados += 1
                    
                except Exception as e:
                    errores.append(f'{usuario.email}: {str(e)}')
            
            if enviados > 0:
                messages.success(request, f"Se enviaron {enviados} certificados correctamente.")
            
            if errores:
                messages.warning(request, f"Errores en el envío: {', '.join(errores)}")
            
            return redirect('enviar_certificados', eve_id=eve_id, tipo=tipo)
    
    # Verificar advertencias para mostrar en el template
    advertencias = []
    if not configuracion.logo:
        advertencias.append("No has configurado un logo para el certificado")
    if not configuracion.firma:
        advertencias.append("No has configurado una firma para el certificado")
    
    return render(request, 'app_administradores/enviar_certificados.html', {
        'evento': evento,
        'tipo': tipo,
        'configuracion': configuracion,
        'destinatarios': destinatarios,
        'advertencias': advertencias
    })


@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def enviar_certificados_premiacion(request, eve_id):
    """Vista para enviar certificados de premiación con ranking"""
    
    evento = get_object_or_404(Evento, eve_id=eve_id)
    
    # Verificar que el usuario sea el administrador del evento
    if evento.eve_administrador_fk != request.user.administrador:
        messages.error(request, "No tienes permisos para gestionar certificados de este evento.")
        return redirect('gestionar_certificados')
    
    try:
        configuracion = ConfiguracionCertificado.objects.get(evento=evento, tipo='premiacion')
    except ConfiguracionCertificado.DoesNotExist:
        messages.error(request, "Debe configurar el certificado de premiación primero.")
        return redirect('configurar_certificado', eve_id=eve_id, tipo='premiacion')
    
    # Obtener participantes con calificación final usando par_eve_valor
    participantes_con_puntuacion = []
    
    # Obtener todos los participantes confirmados del evento que tienen calificación
    participantes_evento = ParticipanteEvento.objects.filter(
        evento=evento, 
        confirmado=True,
        par_eve_estado='Aprobado',
        par_eve_valor__isnull=False
    ).select_related('participante__usuario').order_by('-par_eve_valor')
    
    for participante_evento in participantes_evento:
        participantes_con_puntuacion.append({
            'id': participante_evento.id,
            'participante_evento': participante_evento,
            'participante': participante_evento.participante,
            'nombre_completo': f'{participante_evento.participante.usuario.first_name} {participante_evento.participante.usuario.last_name}',
            'documento': participante_evento.participante.usuario.documento,
            'email': participante_evento.participante.usuario.email,
            'estado': participante_evento.par_eve_estado,
            'puntuacion_total': participante_evento.par_eve_valor
        })
    
    # Asignar puestos considerando empates basados en par_eve_valor
    participantes_ranking = []
    puesto_actual = 1
    
    for i, participante in enumerate(participantes_con_puntuacion):
        # Si no es el primero y tiene la misma puntuación que el anterior, mantiene el puesto
        if i > 0 and participante['puntuacion_total'] == participantes_con_puntuacion[i-1]['puntuacion_total']:
            participante['puesto'] = participantes_ranking[i-1]['puesto']
        else:
            participante['puesto'] = puesto_actual
        
        participantes_ranking.append(participante)
        puesto_actual = i + 2  # Siguiente puesto disponible
    
    if request.method == 'POST':
        participantes_seleccionados = request.POST.getlist('participantes')  
        if not participantes_seleccionados:
            messages.error(request, "Debe seleccionar al menos un participante.")
        else:
            # Procesar envío de certificados
            enviados = 0
            errores = []
            
            # Crear diccionario para acceso rápido por ID
            participantes_dict = {str(p['id']): p for p in participantes_ranking}
            
            for part_id in participantes_seleccionados:
                try:
                    participante_data = participantes_dict[part_id]
                    participante_evento = participante_data['participante_evento']
                    usuario = participante_data['participante'].usuario
                    
                    # Preparar datos del certificado incluyendo PUESTO
                    datos_certificado = {
                        'NOMBRE': f'{usuario.first_name} {usuario.last_name}',
                        'DOCUMENTO': usuario.documento,
                        'EVENTO': evento.eve_nombre,
                        'FECHA': evento.eve_fecha_inicio.strftime('%d de %B de %Y'),
                        'CIUDAD': evento.eve_ciudad,
                        'LUGAR': evento.eve_lugar,
                        'PUESTO': f"{participante_data['puesto']}°",
                        'PUNTUACION': str(participante_data['puntuacion_total'])
                    }
                    
                    # Renderizar el cuerpo del certificado
                    cuerpo_con_datos = configuracion.cuerpo
                    for clave, valor in datos_certificado.items():
                        cuerpo_con_datos = cuerpo_con_datos.replace(f'**{clave}**', valor)
                    
                    # Convertir imágenes a base64 para el PDF
                    logo_base64, logo_format = imagen_to_base64(configuracion.logo)
                    firma_base64, firma_format = imagen_to_base64(configuracion.firma)
                    
                    # Generar PDF del certificado
                    html_content = render_to_string('app_administradores/certificado_plantilla.html', {
                        'configuracion': configuracion,
                        'cuerpo_renderizado': cuerpo_con_datos,
                        'datos': datos_certificado,
                        'es_preview': False,
                        'logo_base64': logo_base64,
                        'logo_format': logo_format,
                        'firma_base64': firma_base64,
                        'firma_format': firma_format,
                    })
                    
                    pdf_file = HTML(string=html_content, base_url=request.build_absolute_uri()).write_pdf()
                    
                    # Enviar por correo electrónico
                    email = EmailMessage(
                        subject=f'Certificado de Premiación - {evento.eve_nombre}',
                        body=f'Estimado/a {datos_certificado["NOMBRE"]},\n\n¡Felicitaciones! Adjuntamos su certificado de premiación del evento "{evento.eve_nombre}" donde obtuvo el {datos_certificado["PUESTO"]} lugar con una puntuación de {datos_certificado["PUNTUACION"]} puntos.\n\nSaludos cordiales.',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=[usuario.email],
                    )
                    
                    filename = f'certificado_premiacion_{usuario.documento}.pdf'
                    email.attach(filename, pdf_file, 'application/pdf')
                    email.send()
                    
                    enviados += 1
                    
                except Exception as e:
                    errores.append(f'{participante_data["email"]}: {str(e)}')
            
            if enviados > 0:
                messages.success(request, f"Se enviaron {enviados} certificados de premiación correctamente.")
            
            if errores:
                messages.warning(request, f"Errores en el envío: {', '.join(errores)}")
            
            return redirect('enviar_certificados_premiacion', eve_id=eve_id)
    
    # Verificar advertencias para mostrar en el template
    advertencias = []
    if not configuracion.logo:
        advertencias.append("No has configurado un logo para el certificado")
    if not configuracion.firma:
        advertencias.append("No has configurado una firma para el certificado")
    
    return render(request, 'app_administradores/enviar_certificados_premiacion.html', {
        'evento': evento,
        'configuracion': configuracion,
        'participantes_ranking': participantes_ranking,
        'advertencias': advertencias
    })


# ===============================
# GESTIÓN DE CÓDIGOS DE INVITACIÓN
# ===============================

@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def crear_codigo_invitacion(request):
    """Vista para seleccionar evento y crear códigos de invitación para evaluadores/participantes"""
    administrador = request.user.administrador
    
    # Obtener solo eventos aprobados del administrador
    eventos_aprobados = Evento.objects.filter(
        eve_administrador_fk=administrador,
        eve_estado__iexact='Aprobado'
    ).order_by('-eve_fecha_inicio')
    
    if request.method == 'POST':
        evento_id = request.POST.get('evento_id')
        tipo = request.POST.get('tipo')
        emails = request.POST.getlist('emails[]')  # Para manejar múltiples emails
        
        # Validaciones
        if not evento_id or not tipo:
            messages.error(request, "Debe seleccionar un evento y especificar el tipo.")
            return render(request, 'app_administradores/crear_codigo_invitacion.html', {
                'eventos': eventos_aprobados
            })
        
        evento = get_object_or_404(Evento, pk=evento_id, eve_administrador_fk=administrador)
        
        # Filtrar emails válidos
        emails_validos = [email.strip() for email in emails if email.strip()]
        if not emails_validos:
            messages.error(request, "Debe proporcionar al menos un correo electrónico válido.")
            return render(request, 'app_administradores/crear_codigo_invitacion.html', {
                'eventos': eventos_aprobados
            })
        
        # Crear códigos de invitación
        codigos_creados = []
        emails_fallidos = []
        
        for email in emails_validos:
            try:
                # Verificar si ya existe un código activo para este email y evento
                codigo_existente = CodigoInvitacionEvento.objects.filter(
                    email_destino=email,
                    evento=evento,
                    tipo=tipo,
                    estado='activo'
                ).first()
                
                if codigo_existente:
                    emails_fallidos.append(f"{email} (ya tiene código activo)")
                    continue
                
                # Crear nuevo código
                codigo = CodigoInvitacionEvento.objects.create(
                    email_destino=email,
                    evento=evento,
                    tipo=tipo,
                    administrador_creador=administrador
                )
                
                # Enviar correo
                url_registro = request.build_absolute_uri(
                    reverse('registro_con_codigo', args=[codigo.codigo])
                )
                
                asunto = f'Invitación como {tipo.title()} - {evento.eve_nombre}'
                mensaje_html = render_to_string('correo_invitacion_evento.html', {
                    'evento': evento,
                    'tipo': tipo.title(),
                    'codigo': codigo.codigo,
                    'url_registro': url_registro,
                })
                
                email_obj = EmailMessage(
                    subject=asunto,
                    body=mensaje_html,
                    to=[email]
                )
                email_obj.content_subtype = 'html'
                email_obj.send()
                
                codigos_creados.append(codigo)
                
            except Exception as e:
                emails_fallidos.append(f"{email} (error: {str(e)})")
        
        # Mensajes de resultado
        if codigos_creados:
            messages.success(
                request, 
                f"Se crearon {len(codigos_creados)} código(s) de invitación exitosamente."
            )
        
        if emails_fallidos:
            messages.warning(
                request,
                f"Algunos correos no pudieron procesarse: {', '.join(emails_fallidos)}"
            )
        
        return redirect('listar_codigos_invitacion')
    
    return render(request, 'app_administradores/crear_codigo_invitacion.html', {
        'eventos': eventos_aprobados
    })


@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def listar_codigos_invitacion(request):
    """Vista para listar códigos de invitación creados por el administrador"""
    administrador = request.user.administrador
    
    codigos = CodigoInvitacionEvento.objects.filter(
        administrador_creador=administrador
    ).select_related('evento').order_by('-fecha_creacion')
    
    return render(request, 'app_administradores/listar_codigos_invitacion.html', {
        'codigos': codigos
    })


@login_required
@user_passes_test(es_administrador_evento, login_url='ver_eventos')
def cancelar_codigo_invitacion(request, codigo_id):
    """Vista para cancelar un código de invitación"""
    administrador = request.user.administrador
    
    codigo = get_object_or_404(
        CodigoInvitacionEvento,
        pk=codigo_id,
        administrador_creador=administrador,
        estado='activo'
    )
    
    codigo.estado = 'cancelado'
    codigo.save()
    
    messages.success(request, f"Código de invitación para {codigo.email_destino} cancelado exitosamente.")
    return redirect('listar_codigos_invitacion')

def manual_administrador_evento(request):
    """
    Sirve el manual del Administrador de Evento en formato PDF.
    """
    ruta_manual = os.path.join(settings.MEDIA_ROOT, "manuales", "MANUAL_ADMINISTRADOR_DE_EVENTO_SISTEMA_EVENTSOFT.pdf")
    if os.path.exists(ruta_manual):
        return FileResponse(open(ruta_manual, "rb"), content_type="application/pdf")
    raise Http404("Manual no encontrado")