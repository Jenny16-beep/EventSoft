from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse
from django.contrib import messages
from app_eventos.models import Evento
from app_areas.models import Categoria, Area
from app_administradores.models import AdministradorEvento, CodigoInvitacionAdminEvento
from django.core.mail import EmailMessage
from django.utils import timezone
import uuid
from app_usuarios.models import Rol, RolUsuario
from collections import defaultdict
from django.contrib.auth.decorators import login_required, user_passes_test
from app_usuarios.models import Usuario
from app_usuarios.permisos import es_superadmin
from django.template.loader import render_to_string
from django.db import transaction
from app_asistentes.models import Asistente, AsistenteEvento
from app_participantes.models import Participante, ParticipanteEvento
from app_evaluadores.models import Evaluador, EvaluadorEvento
from app_administradores.models import CodigoInvitacionEvento
from app_eventos.models import ConfiguracionCertificado
from app_eventos.models import EventoCategoria




def _eliminar_informacion_evento_cerrado(evento):
    """
    Función auxiliar para eliminar toda la información relacionada con un evento cerrado.
    Elimina participantes, asistentes, evaluadores y administradores del evento,
    y también usuarios si no tienen más roles.
    """
    with transaction.atomic():
        # 1. Eliminar AsistenteEvento del evento
        asistentes_evento = AsistenteEvento.objects.filter(evento=evento)
        asistentes_ids = list(asistentes_evento.values_list('asistente_id', flat=True))
        asistentes_evento.delete()
        
        # Verificar si los asistentes están en otros eventos
        for asistente_id in asistentes_ids:
            try:
                asistente = Asistente.objects.get(id=asistente_id)
                # Si no tiene más eventos asociados, eliminar asistente y su rol
                if not AsistenteEvento.objects.filter(asistente=asistente).exists():
                    usuario = asistente.usuario
                    # Eliminar rol de asistente
                    RolUsuario.objects.filter(usuario=usuario, rol__nombre='asistente').delete()
                    asistente.delete()
                    # Si el usuario no tiene más roles, eliminarlo
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
                # Si no tiene más eventos asociados, eliminar participante y su rol
                if not ParticipanteEvento.objects.filter(participante=participante).exists():
                    usuario = participante.usuario
                    # Eliminar rol de participante
                    RolUsuario.objects.filter(usuario=usuario, rol__nombre='participante').delete()
                    participante.delete()
                    # Si el usuario no tiene más roles, eliminarlo
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
                # Si no tiene más eventos asociados, eliminar evaluador y su rol
                if not EvaluadorEvento.objects.filter(evaluador=evaluador).exists():
                    usuario = evaluador.usuario
                    # Eliminar rol de evaluador
                    RolUsuario.objects.filter(usuario=usuario, rol__nombre='evaluador').delete()
                    evaluador.delete()
                    # Si el usuario no tiene más roles, eliminarlo
                    if not RolUsuario.objects.filter(usuario=usuario).exists():
                        usuario.delete()
            except Evaluador.DoesNotExist:
                continue
        
        # 4. Manejar el administrador del evento
        administrador = evento.eve_administrador_fk
        if administrador:
            usuario_admin = administrador.usuario
            
            # Verificar si el usuario administrador tiene MÁS EVENTOS (excluyendo el actual)
            otros_eventos_admin = Evento.objects.filter(eve_administrador_fk=administrador).exclude(eve_id=evento.eve_id).exists()
            
            # NO ELIMINAR el registro AdministradorEvento - solo verificar si debe eliminar el usuario
            if not otros_eventos_admin:
                # No tiene más eventos, ahora verificar códigos de invitación
                codigos_admin = CodigoInvitacionAdminEvento.objects.filter(usuario_asignado=usuario_admin)
                tiene_limite_positivo = codigos_admin.filter(limite_eventos__gt=0).exists()
                
                if not tiene_limite_positivo:
                    # No tiene códigos con límite > 0, eliminar todos sus códigos
                    codigos_admin.delete()
                    
                    # Eliminar rol de administrador
                    RolUsuario.objects.filter(usuario=usuario_admin, rol__nombre='administrador_evento').delete()
                    
                    # Eliminar el registro AdministradorEvento
                    administrador.delete()
                    
                    # Si no tiene más roles, eliminar usuario
                    if not RolUsuario.objects.filter(usuario=usuario_admin).exists():
                        usuario_admin.delete()
            # Si tiene más eventos, NO hacer nada (preservar todo)
        
        # 5. Eliminar códigos de invitación específicos del evento
        
        CodigoInvitacionEvento.objects.filter(evento=evento).delete()
        
        # 6. Eliminar configuraciones de certificados del evento
        
        ConfiguracionCertificado.objects.filter(evento=evento).delete()
        
        # 7. Eliminar relaciones EventoCategoria
        
        EventoCategoria.objects.filter(evento=evento).delete()
        
        # 8. Finalmente, eliminar el evento (esto también eliminará criterios por CASCADE)
        evento.delete()


@login_required
@user_passes_test(es_superadmin, login_url='ver_eventos')
def dashboard(request):
    estados_objetivo = ['pendiente', 'inscripciones cerradas', 'finalizado', 'cerrado']
    eventos = Evento.objects.filter(eve_estado__in=estados_objetivo)    
    mapa_estados = {
        'pendiente': 'Pendiente',
        'inscripciones cerradas': 'Inscripciones Cerradas',
        'finalizado': 'Finalizado',
        'cerrado': 'Cerrado',
    }
    nuevos_por_estado = {v: [] for v in mapa_estados.values()}
    for evento in eventos:
        estado_raw = evento.eve_estado.lower()
        estado_formateado = mapa_estados.get(estado_raw, estado_raw.title())
        if estado_formateado in nuevos_por_estado:
            nuevos_por_estado[estado_formateado].append(evento.eve_id)
    vistos = request.session.get('eventos_vistos', {})
    notificaciones = {}
    total_nuevos = 0
    for estado, eventos_ids in nuevos_por_estado.items():
        vistos_estado = vistos.get(estado, [])
        nuevos = [eid for eid in eventos_ids if eid not in vistos_estado]
        notificaciones[estado] = len(nuevos)
        total_nuevos += len(nuevos)
    if total_nuevos > 0:
        mensajes_estados = []
        for estado, cantidad in notificaciones.items():
            if cantidad > 0:
                mensajes_estados.append(f"{cantidad} nuevo(s) en '{estado}'")
        mensaje_notificacion = " | ".join(mensajes_estados)
        messages.info(request, f"Tienes {total_nuevos} evento(s) nuevo(s): {mensaje_notificacion}")
    estados_tarjetas = [
        ('Aprobado', 'success', '✔️'),
        ('Pendiente', 'warning', '⏳'),
        ('Rechazado', 'danger', '❌'),
        ('Inscripciones Cerradas', 'info', '📋'),
        ('Finalizado', 'secondary', '🏁'),
        ('Cerrado', 'dark', '🔒'),
    ]    
    return render(request, 'dashboard.html', {
        'notificaciones': notificaciones,
        'estados_tarjetas': estados_tarjetas
    })

@login_required
@user_passes_test(es_superadmin, login_url='ver_eventos')
def crear_codigo_invitacion_admin(request):
    if request.method == 'POST':
        email_destino = request.POST.get('email_destino', '').strip()
        limite_eventos = request.POST.get('limite_eventos', '').strip()
        fecha_expiracion = request.POST.get('fecha_expiracion', '').strip()
        tiempo_limite_creacion = request.POST.get('tiempo_limite_creacion', '').strip()

        errores = []
        if not email_destino:
            errores.append('El correo de destino es obligatorio.')
        if not limite_eventos or not limite_eventos.isdigit() or int(limite_eventos) < 1:
            errores.append('El límite de eventos debe ser un número mayor a 0.')
        if not fecha_expiracion:
            errores.append('La fecha de expiración es obligatoria.')
        if errores:
            for e in errores:
                messages.error(request, e)
            return render(request, 'crear_codigo_invitacion_admin.html')

        # Validar que no exista un código activo para ese correo
        if CodigoInvitacionAdminEvento.objects.filter(email_destino=email_destino, estado='activo').exists():
            messages.error(request, 'Ya existe un código activo para ese correo.')
            return render(request, 'crear_codigo_invitacion_admin.html')

        # Generar código único
        codigo = str(uuid.uuid4()).replace('-', '')[:32]
        try:
            fecha_exp = timezone.datetime.fromisoformat(fecha_expiracion)
        except Exception:
            messages.error(request, 'Formato de fecha de expiración inválido.')
            return render(request, 'crear_codigo_invitacion_admin.html')

        tiempo_limite = None
        if tiempo_limite_creacion:
            try:
                tiempo_limite = timezone.datetime.fromisoformat(tiempo_limite_creacion)
            except Exception:
                messages.error(request, 'Formato de fecha/hora para el tiempo límite de creación inválido.')
                return render(request, 'crear_codigo_invitacion_admin.html')

        codigo_obj = CodigoInvitacionAdminEvento.objects.create(
            codigo=codigo,
            email_destino=email_destino,
            limite_eventos=int(limite_eventos),
            fecha_expiracion=fecha_exp,
            tiempo_limite_creacion=tiempo_limite
        )

        # Enviar correo
        url_registro = request.build_absolute_uri(f"/evento/registro_admin_evento/?codigo={codigo}")
        asunto = 'Invitación para ser Administrador de Evento'
        mensaje = f"""
        Has sido invitado a ser Administrador de Evento en Eventsoft.<br><br>
        Usa el siguiente código de invitación: <b>{codigo}</b><br>
        O haz clic en el siguiente enlace para registrarte:<br>
        <a href='{url_registro}'>{url_registro}</a><br><br>
        Este código permite crear hasta {limite_eventos} evento(s) y expira el {fecha_exp.strftime('%d/%m/%Y %H:%M')}.<br>
        """
        email = EmailMessage(asunto, mensaje, to=[email_destino])
        email.content_subtype = 'html'
        try:
            email.send()
            messages.success(request, 'Código de invitación generado y enviado exitosamente.')
        except Exception as e:
            messages.error(request, f'Error al enviar el correo: {e}')
        return redirect('crear_codigo_invitacion_admin')
    return render(request, 'crear_codigo_invitacion_admin.html')

@login_required
@user_passes_test(es_superadmin, login_url='ver_eventos')
def listar_eventos_estado(request, estado):
    eventos = Evento.objects.filter(eve_estado=estado.lower()).select_related('eve_administrador_fk')
    eventos_por_admin = defaultdict(list)
    for evento in eventos:
        admin = evento.eve_administrador_fk
        eventos_por_admin[admin].append(evento)
    vistos = request.session.get('eventos_vistos', {})
    vistos[estado] = [e.eve_id for e in eventos]
    request.session['eventos_vistos'] = vistos
    return render(request, 'listado_eventos.html', {
        'eventos_por_admin': eventos_por_admin.items(), 
    })


@login_required
@user_passes_test(es_superadmin, login_url='ver_eventos')
def detalle_evento_admin(request, eve_id):
    evento = get_object_or_404(Evento, pk=eve_id)

    if request.method == 'POST':
        nuevo_estado = request.POST.get('nuevo_estado')
        
        # Si el evento está finalizado y se cambia a cerrado, eliminar toda la información
        if evento.eve_estado.lower() == 'finalizado' and nuevo_estado.lower() == 'cerrado':
            try:
                _eliminar_informacion_evento_cerrado(evento)
                messages.success(request, 'Evento cerrado y toda la información ha sido eliminada correctamente.')
                return redirect('dashboard_superadmin')
            except Exception as e:
                messages.error(request, f'Error al cerrar el evento: {str(e)}')
                return redirect('detalle_evento_admin', eve_id=eve_id)
        else:
            evento.eve_estado = nuevo_estado
            evento.save()

            admin_evento = evento.eve_administrador_fk
            admin_usuario = admin_evento.usuario if admin_evento else None
            if admin_usuario and admin_usuario.email:
                cuerpo_html = render_to_string('correo_estado_evento_admin.html', {
                    'evento': evento,
                    'nuevo_estado': nuevo_estado,
                    'admin': admin_usuario,
                })
                email = EmailMessage(
                    subject=f'Actualización de estado de tu evento: {evento.eve_nombre}',
                    body=cuerpo_html,
                    to=[admin_usuario.email],
                )
                email.content_subtype = 'html'
                email.send(fail_silently=True)

            messages.success(request, 'Estado actualizado exitosamente')
            return redirect('dashboard_superadmin')
    
    administrador = get_object_or_404(AdministradorEvento, pk=evento.eve_administrador_fk_id)
    
    # Determinar estados disponibles según el estado actual
    if evento.eve_estado.lower() == 'finalizado':
        estados = ['Cerrado']  # Solo puede cambiar a cerrado
    else:
        estados = ['Pendiente', 'Aprobado', 'Rechazado', 'Inscripciónes Cerradas']
    categorias = Categoria.objects.filter(eventocategoria__evento=evento).select_related('cat_area_fk')
    areas_con_categorias = {}
    for categoria in categorias:
        area = categoria.cat_area_fk
        if area.are_nombre not in areas_con_categorias:
            areas_con_categorias[area.are_nombre] = []
        areas_con_categorias[area.are_nombre].append(categoria)

    # Calcular estadísticas si el evento está aprobado
    estadisticas = None
    if evento.eve_estado.lower() == 'aprobado':
        from app_asistentes.models import AsistenteEvento
        from app_participantes.models import ParticipanteEvento
        from app_evaluadores.models import EvaluadorEvento, Criterio, Calificacion
        
        # Estadísticas de asistentes
        asistentes_total = AsistenteEvento.objects.filter(evento=evento).count()
        asistentes_aprobados = AsistenteEvento.objects.filter(evento=evento, asi_eve_estado='Aprobado').count()
        asistentes_pendientes = AsistenteEvento.objects.filter(evento=evento, asi_eve_estado='Pendiente').count()
        asistentes_confirmados = AsistenteEvento.objects.filter(evento=evento, confirmado=True).count()
        
        # Estadísticas de participantes
        participantes_total = ParticipanteEvento.objects.filter(evento=evento).count()
        participantes_aprobados = ParticipanteEvento.objects.filter(evento=evento, par_eve_estado='Aprobado').count()
        participantes_pendientes = ParticipanteEvento.objects.filter(evento=evento, par_eve_estado='Pendiente').count()
        participantes_confirmados = ParticipanteEvento.objects.filter(evento=evento, confirmado=True).count()
        participantes_calificados = ParticipanteEvento.objects.filter(evento=evento, par_eve_valor__isnull=False).count()
        
        # Estadísticas de evaluadores
        evaluadores_total = EvaluadorEvento.objects.filter(evento=evento).count()
        evaluadores_aprobados = EvaluadorEvento.objects.filter(evento=evento, eva_eve_estado='Aprobado').count()
        evaluadores_pendientes = EvaluadorEvento.objects.filter(evento=evento, eva_eve_estado='Pendiente').count()
        evaluadores_confirmados = EvaluadorEvento.objects.filter(evento=evento, confirmado=True).count()
        
        # Estadísticas de evaluación
        criterios_total = Criterio.objects.filter(cri_evento_fk=evento).count()
        calificaciones_total = Calificacion.objects.filter(criterio__cri_evento_fk=evento).count()
        
        # Calcular capacidad utilizada (solo asistentes ocupan cupos)
        inscritos_totales = asistentes_total  # Solo asistentes ocupan capacidad
        porcentaje_ocupacion = round((inscritos_totales / evento.eve_capacidad) * 100, 1) if evento.eve_capacidad > 0 else 0
        
        # Estadísticas de archivos
        archivos_disponibles = {
            'programacion': bool(evento.eve_programacion),
            'memorias': bool(evento.eve_memorias),
            'informacion_tecnica': bool(evento.eve_informacion_tecnica),
        }
        
        estadisticas = {
            'asistentes': {
                'total': asistentes_total,
                'aprobados': asistentes_aprobados,
                'pendientes': asistentes_pendientes,
                'confirmados': asistentes_confirmados,
            },
            'participantes': {
                'total': participantes_total,
                'aprobados': participantes_aprobados,
                'pendientes': participantes_pendientes,
                'confirmados': participantes_confirmados,
                'calificados': participantes_calificados,
            },
            'evaluadores': {
                'total': evaluadores_total,
                'aprobados': evaluadores_aprobados,
                'pendientes': evaluadores_pendientes,
                'confirmados': evaluadores_confirmados,
            },
            'evaluacion': {
                'criterios': criterios_total,
                'calificaciones': calificaciones_total,
            },
            'capacidad': {
                'total': evento.eve_capacidad,
                'inscritos': inscritos_totales,
                'disponibles': evento.eve_capacidad - inscritos_totales,
                'porcentaje_ocupacion': porcentaje_ocupacion,
            },
            'archivos': archivos_disponibles,
        }

    return render(request, 'app_admin/detalle_evento_admin.html', {
        'evento': evento,
        'administrador': administrador,
        'estados': estados,
        'areas_con_categorias': areas_con_categorias,
        'estadisticas': estadisticas,
    })


@login_required
@user_passes_test(es_superadmin, login_url='ver_eventos')
def descargar_programacion(request, eve_id):
    evento = get_object_or_404(Evento, pk=eve_id)
    if evento.eve_programacion and evento.eve_programacion.name:
        try:
            return FileResponse(
                evento.eve_programacion.open('rb'),
                content_type='application/pdf',
                as_attachment=False,
                filename=f'programacion_evento_{eve_id}.pdf'
            )
        except FileNotFoundError:
            messages.error(request, "El archivo de programación no se encuentra en el servidor.")
            return redirect('detalle_evento_admin', eve_id=eve_id)
    else:
        messages.error(request, "Este evento no tiene un archivo de programación.")
        return redirect('detalle_evento_admin', eve_id=eve_id)
    

@login_required
@user_passes_test(es_superadmin, login_url='ver_eventos')
def crear_administrador_evento(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        telefono = request.POST.get('telefono')
        documento = request.POST.get('documento')

        if Usuario.objects.filter(email=email).exists():
            messages.error(request, 'Ya existe un usuario con ese correo.')
        elif Usuario.objects.filter(documento=documento).exists():
            messages.error(request, 'Ya existe un usuario con ese documento.')
        else:
            user = Usuario.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                telefono=telefono,
                documento=documento
            )
            # Asignar el rol correctamente usando Rol y RolUsuario
            
            rol_admin, _ = Rol.objects.get_or_create(nombre='administrador_evento')
            RolUsuario.objects.create(usuario=user, rol=rol_admin)
            AdministradorEvento.objects.create(usuario=user)
            messages.success(request, 'Administrador de evento creado exitosamente.')
            return redirect('dashboard_superadmin')

    return render(request, 'crear_administrador_evento.html')

@login_required
@user_passes_test(es_superadmin, login_url='ver_eventos')
def listar_administradores_evento(request):
    administradores = AdministradorEvento.objects.select_related('usuario').all()
    return render(request, 'listar_administradores.html', {'administradores': administradores})

@login_required
@user_passes_test(es_superadmin, login_url='ver_eventos')
def eliminar_administrador(request, admin_id):
    admin = get_object_or_404(AdministradorEvento, pk=admin_id)
    nombre = admin.usuario.get_full_name()
    admin.usuario.delete()
    messages.success(request, f"Administrador '{nombre}' eliminado correctamente.")
    return redirect('listar_administradores_evento')


@login_required
@user_passes_test(es_superadmin, login_url='ver_eventos')
def crear_area_categoria(request):
    mensaje = ''
    mensaje_categoria = ''
    areas = Area.objects.all()
    if request.method == 'POST':
        if 'crear_area' in request.POST:
            nombre_area = request.POST.get('nombre_area', '').strip()
            descripcion_area = request.POST.get('descripcion_area', '').strip()
            if not nombre_area:
                mensaje = 'El nombre del área es obligatorio.'
            elif Area.objects.filter(are_nombre__iexact=nombre_area).exists():
                mensaje = 'Ya existe un área con ese nombre.'
            else:
                Area.objects.create(are_nombre=nombre_area, are_descripcion=descripcion_area)
                mensaje = 'Área creada exitosamente.'
                areas = Area.objects.all()
        elif 'crear_categoria' in request.POST:
            nombre_categoria = request.POST.get('nombre_categoria', '').strip()
            descripcion_categoria = request.POST.get('descripcion_categoria', '').strip()
            area_id = request.POST.get('area_id')
            if not nombre_categoria or not area_id:
                mensaje_categoria = 'El nombre de la categoría y el área son obligatorios.'
            elif Categoria.objects.filter(cat_nombre__iexact=nombre_categoria, cat_area_fk_id=area_id).exists():
                mensaje_categoria = 'Ya existe una categoría con ese nombre en el área seleccionada.'
            else:
                Categoria.objects.create(cat_nombre=nombre_categoria, cat_descripcion=descripcion_categoria, cat_area_fk_id=area_id)
                mensaje_categoria = 'Categoría creada exitosamente.'
    return render(request, 'crear_area_categoria.html', {
        'areas': areas,
        'mensaje': mensaje,
        'mensaje_categoria': mensaje_categoria
    })

@login_required
@user_passes_test(es_superadmin, login_url='ver_eventos')
def listar_codigos_invitacion_admin(request):
    codigos = CodigoInvitacionAdminEvento.objects.all().order_by('-fecha_creacion')
    return render(request, 'listar_codigos_invitacion_admin.html', {'codigos': codigos})

@login_required
@user_passes_test(es_superadmin, login_url='ver_eventos')
def accion_codigo_invitacion_admin(request, codigo, accion):
    invitacion = get_object_or_404(CodigoInvitacionAdminEvento, codigo=codigo)
    if accion == 'suspender' and invitacion.estado == 'activo':
        invitacion.estado = 'suspendido'
        invitacion.save()
        messages.success(request, 'Código suspendido correctamente.')
    elif accion == 'activar' and invitacion.estado == 'suspendido':
        invitacion.estado = 'activo'
        invitacion.save()
        messages.success(request, 'Código activado correctamente.')
    elif accion == 'cancelar':
        invitacion.delete()
        messages.success(request, 'Código cancelado y eliminado correctamente.')
    else:
        messages.error(request, 'Acción no permitida para el estado actual del código.')
    return redirect('listar_codigos_invitacion_admin')