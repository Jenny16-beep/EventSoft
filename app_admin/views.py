from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse
from django.contrib import messages
from app_eventos.models import Evento
from app_areas.models import Categoria
from app_administradores.models import AdministradorEvento
from collections import defaultdict
from django.contrib.auth.decorators import login_required, user_passes_test
from app_usuarios.models import Usuario
from app_usuarios.permisos import es_superadmin

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
                documento=documento,
                rol='administrador_evento'
            )
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