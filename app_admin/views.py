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



@login_required
@user_passes_test(es_superadmin, login_url='ver_eventos')
def dashboard(request):
    estados_objetivo = ['pendiente', 'inscripciones cerradas', 'finalizado']
    eventos = Evento.objects.filter(eve_estado__in=estados_objetivo)    
    mapa_estados = {
        'pendiente': 'Pendiente',
        'inscripciones cerradas': 'Inscripciones Cerradas',
        'finalizado': 'Finalizado',
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
    estados = ['Pendiente', 'Aprobado', 'Rechazado', 'Inscripciónes Cerradas']
    categorias = Categoria.objects.filter(eventocategoria__evento=evento).select_related('cat_area_fk')
    areas_con_categorias = {}
    for categoria in categorias:
        area = categoria.cat_area_fk
        if area.are_nombre not in areas_con_categorias:
            areas_con_categorias[area.are_nombre] = []
        areas_con_categorias[area.are_nombre].append(categoria)

    return render(request, 'detalle_evento_admin.html', {
        'evento': evento,
        'administrador': administrador,
        'estados': estados,
        'areas_con_categorias': areas_con_categorias,
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