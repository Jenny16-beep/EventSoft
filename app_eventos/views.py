from app_administradores.models import CodigoInvitacionAdminEvento, AdministradorEvento, CodigoInvitacionEvento
from django.db import transaction

from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from app_participantes.models import Participante, ParticipanteEvento
from app_areas.models import Area, Categoria
from app_asistentes.models import Asistente, AsistenteEvento
from app_evaluadores.models import Evaluador, EvaluadorEvento
from .models import Evento, EventoCategoria
from app_usuarios.models import Usuario, Rol, RolUsuario
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from io import BytesIO
from django.core.files.base import ContentFile
from django.urls import reverse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import random
import string
import qrcode

def generar_clave():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10))

def ver_eventos(request):
    area = request.GET.get('area')
    categoria = request.GET.get('categoria')
    ciudad = request.GET.get('ciudad')
    fecha = request.GET.get('fecha')
    nombre = request.GET.get('nombre')
    eventos = Evento.objects.filter(eve_estado__in=['Aprobado', 'Inscripciones Cerradas'])
    if ciudad:
        eventos = eventos.filter(eve_ciudad__icontains=ciudad)
    if fecha:
        eventos = eventos.filter(eve_fecha_inicio__lte=fecha, eve_fecha_fin__gte=fecha)
    if nombre:
        eventos = eventos.filter(eve_nombre__icontains=nombre)
    if categoria:
        eventos = eventos.filter(eventocategoria__categoria__cat_codigo=categoria)
    if area:
        eventos = eventos.filter(eventocategoria__categoria__cat_area_fk__are_codigo=area)
    areas = Area.objects.all()
    categorias = Categoria.objects.filter(cat_area_fk__are_codigo=area) if area else Categoria.objects.all()
    context = {
        'eventos': eventos.distinct(),
        'areas': areas,
        'categorias': categorias,
    }
    return render(request, 'eventos.html', context)


def detalle_evento(request, eve_id):
    evento = get_object_or_404(Evento.objects.select_related('eve_administrador_fk'), pk=eve_id)
    categorias = EventoCategoria.objects.select_related('categoria__cat_area_fk').filter(evento=evento)
    return render(request, 'detalle_evento.html', {
        'evento': evento,
        'categorias': categorias,
    })

@csrf_exempt
def compartir_evento_visitante(request, eve_id):
    """Vista para generar contenido compartible del evento para visitantes web"""
    evento = get_object_or_404(Evento, pk=eve_id)
    
    # Verificar que el evento esté disponible públicamente
    if evento.eve_estado.lower() not in ['aprobado', 'inscripciones cerradas']:
        return JsonResponse({
            'success': False,
            'error': 'Este evento no está disponible públicamente.'
        }, status=403)
    
    if request.method == 'POST' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Generar URL absoluta del evento
        url_evento = request.build_absolute_uri(reverse('detalle_evento_visitante', args=[eve_id]))
        
        # Obtener categorías
        categorias = [ec.categoria.cat_nombre for ec in evento.eventocategoria_set.all()]
        
        # Crear mensaje genérico para visitantes
        mensaje_compartir = f"🎉 ¡Descubre este increíble evento!\n\n"
        mensaje_compartir += f"📅 {evento.eve_nombre}\n\n"
        mensaje_compartir += f"📅 Fechas: {evento.eve_fecha_inicio.strftime('%d/%m/%Y')}"
        
        if evento.eve_fecha_inicio != evento.eve_fecha_fin:
            mensaje_compartir += f" - {evento.eve_fecha_fin.strftime('%d/%m/%Y')}"
        
        mensaje_compartir += f"\n📍 Lugar: {evento.eve_lugar}, {evento.eve_ciudad}\n"
        mensaje_compartir += f"📝 {evento.eve_descripcion}\n\n"
        
        if categorias:
            mensaje_compartir += f"🏷️ Categorías: {', '.join(categorias)}\n\n"
        
        # Información sobre registro
        if evento.eve_tienecosto == "SI":
            mensaje_compartir += "💳 Evento con costo - Consulta detalles de inscripción\n\n"
        else:
            mensaje_compartir += "🆓 ¡Evento gratuito!\n\n"
        
        mensaje_compartir += f"ℹ️ Más información y registro: {url_evento}"
        
        response_data = {
            'success': True,
            'mensaje': mensaje_compartir,
            'titulo': f"Evento: {evento.eve_nombre}",
            'url': url_evento,
            'evento_nombre': evento.eve_nombre
        }
        
        return JsonResponse(response_data)
    
    # Para peticiones GET (por si acaso)
    return JsonResponse({
        'success': False,
        'error': 'Método no permitido.'
    }, status=405)

def inscripcion_asistente(request, eve_id):
    return registro_evento(request, eve_id, 'asistente')

def inscribirse_participante(request, eve_id):
    messages.error(request, "El registro de participantes solo está disponible mediante código de invitación.")
    return redirect('ver_eventos')

def inscribirse_evaluador(request, eve_id):
    messages.error(request, "El registro de evaluadores solo está disponible mediante código de invitación.")
    return redirect('ver_eventos')


def registro_con_codigo(request, codigo):
    """Vista para manejar registro con código de invitación"""
    # Buscar el código de invitación
    codigo_invitacion = get_object_or_404(
        CodigoInvitacionEvento,
        codigo=codigo,
        estado='activo'
    )
    
    evento = codigo_invitacion.evento
    tipo = codigo_invitacion.tipo
    
    # Verificar que el evento esté activo
    if evento.eve_estado.lower() not in ['aprobado', 'inscripciones cerradas']:
        messages.error(request, "Este evento no está disponible para inscripciones.")
        return redirect('ver_eventos')
    
    if request.method == "POST":
        # Marcar el código como usado
        codigo_invitacion.estado = 'usado'
        codigo_invitacion.fecha_uso = timezone.now()
        codigo_invitacion.save()
        
        # Procesar el registro normalmente pero con email prefijado
        return procesar_registro_con_codigo(request, evento.eve_id, tipo, codigo_invitacion.email_destino)
    
    return render(request, f'inscribirse_{tipo}.html', {
        'evento': evento,
        'codigo_invitacion': codigo_invitacion,
        'email_prefijado': codigo_invitacion.email_destino
    })


def procesar_registro_con_codigo(request, eve_id, tipo, email_prefijado):
    """Función que procesa el registro con código, solo para evaluadores y participantes"""
    evento = Evento.objects.filter(eve_id=eve_id).first()
    if not evento:
        messages.error(request, "Evento no encontrado")
        return redirect('ver_eventos')
    
    # Campos por tipo (solo participante y evaluador)
    if tipo == 'participante':
        documento = request.POST.get('par_id')
        nombres = request.POST.get('par_nombres')
        apellidos = request.POST.get('par_apellidos')
        correo = email_prefijado  # Email prefijado del código
        telefono = request.POST.get('par_telefono')
        archivo = request.FILES.get('documentos')
    elif tipo == 'evaluador':
        documento = request.POST.get('eva_id')
        nombres = request.POST.get('eva_nombres')
        apellidos = request.POST.get('eva_apellidos')
        correo = email_prefijado  # Email prefijado del código
        telefono = request.POST.get('eva_telefono')
        archivo = request.FILES.get('documentacion')
    else:
        messages.error(request, "Tipo de registro inválido para códigos de invitación.")
        return redirect('ver_eventos')
    
    # Validación básica
    if not (documento and nombres and apellidos):
        messages.error(request, "Por favor completa todos los campos obligatorios.")
        return redirect('registro_con_codigo', codigo=request.POST.get('codigo', ''))
    
    # Continuar con el proceso normal de registro usando el sistema existente
    # Pero con el correo prefijado del código de invitación
    
    # Validar consistencia de datos si el usuario ya existe
    usuario = Usuario.objects.filter(Q(email=correo) | Q(documento=documento)).first()
    if usuario:
        if (usuario.email != correo or usuario.documento != documento or 
            usuario.first_name != nombres or usuario.last_name != apellidos):
            messages.error(request, 
                "Los datos no coinciden con un usuario existente. "
                "Si ya tienes cuenta, verifica que los datos sean exactamente iguales."
            )
            return redirect('registro_con_codigo', codigo=request.POST.get('codigo', ''))
    
    # Validar que no esté inscrito en el mismo evento (en cualquier rol)
    ya_inscrito = False
    pendiente_confirmacion = False
    rol_inscrito = ""
    if usuario:
        # Verificar si está como participante
        participante = getattr(usuario, 'participante', None)
        if participante:
            participacion = ParticipanteEvento.objects.filter(participante=participante, evento=evento).first()
            if participacion:
                ya_inscrito = True
                pendiente_confirmacion = not participacion.confirmado
                rol_inscrito = "participante"
        
        # Verificar si está como evaluador
        if not ya_inscrito:
            evaluador = getattr(usuario, 'evaluador', None)
            if evaluador:
                evaluacion = EvaluadorEvento.objects.filter(evaluador=evaluador, evento=evento).first()
                if evaluacion:
                    ya_inscrito = True
                    pendiente_confirmacion = not evaluacion.confirmado
                    rol_inscrito = "evaluador"
        
        # Verificar si está como asistente
        if not ya_inscrito:
            asistente = getattr(usuario, 'asistente', None)
            if asistente:
                asistencia = AsistenteEvento.objects.filter(asistente=asistente, evento=evento).first()
                if asistencia:
                    ya_inscrito = True
                    pendiente_confirmacion = not asistencia.confirmado
                    rol_inscrito = "asistente"
    
    if ya_inscrito:
        if pendiente_confirmacion:
            messages.warning(request, f"Ya tienes una inscripción como {rol_inscrito} en este evento pendiente de confirmación.")
        else:
            messages.info(request, f"Ya estás inscrito como {rol_inscrito} en este evento.")
        return redirect('ver_eventos')
    
    # Si usuario existe y está activo, asignar rol si no lo tiene y crear relación evento-rol
    if usuario and usuario.is_active:
        # Asignar rol si no lo tiene
        rol = Rol.objects.filter(nombre__iexact=tipo).first()
        if rol and not RolUsuario.objects.filter(usuario=usuario, rol=rol).exists():
            RolUsuario.objects.create(usuario=usuario, rol=rol)
        
        # Crear relación evento-rol si no existe (solo participante y evaluador)
        if tipo == 'participante':
            participante, _ = Participante.objects.get_or_create(usuario=usuario)
            ParticipanteEvento.objects.get_or_create(
                participante=participante,
                evento=evento,
                defaults={
                    'par_eve_fecha_hora': timezone.now(),
                    'par_eve_estado': 'Pendiente',
                    'par_eve_documentos': archivo,
                    'confirmado': True
                }
            )
        elif tipo == 'evaluador':
            evaluador, _ = Evaluador.objects.get_or_create(usuario=usuario)
            EvaluadorEvento.objects.get_or_create(
                evaluador=evaluador,
                evento=evento,
                defaults={
                    'eva_eve_fecha_hora': timezone.now(),
                    'eva_eve_estado': 'Pendiente',
                    'eva_eve_documentos': archivo,
                    'confirmado': True
                }
            )
        
        messages.success(request, f"Te has registrado exitosamente como {tipo} en el evento {evento.eve_nombre}.")
        return redirect('ver_eventos')
    
    # Si usuario existe y está inactivo, activarlo y crear relaciones
    if usuario and not usuario.is_active:
        usuario.is_active = True
        usuario.save()
        
        # Asignar rol si no lo tiene
        rol = Rol.objects.filter(nombre__iexact=tipo).first()
        if rol and not RolUsuario.objects.filter(usuario=usuario, rol=rol).exists():
            RolUsuario.objects.create(usuario=usuario, rol=rol)
        
        # Crear relación evento-rol si no existe
        if tipo == 'participante':
            participante, _ = Participante.objects.get_or_create(usuario=usuario)
            ParticipanteEvento.objects.get_or_create(
                participante=participante,
                evento=evento,
                defaults={
                    'par_eve_fecha_hora': timezone.now(),
                    'par_eve_estado': 'Pendiente',
                    'par_eve_documentos': archivo,
                    'confirmado': True
                }
            )
        elif tipo == 'evaluador':
            evaluador, _ = Evaluador.objects.get_or_create(usuario=usuario)
            EvaluadorEvento.objects.get_or_create(
                evaluador=evaluador,
                evento=evento,
                defaults={
                    'eva_eve_fecha_hora': timezone.now(),
                    'eva_eve_estado': 'Pendiente',
                    'eva_eve_documentos': archivo,
                    'confirmado': True
                }
            )
        
        messages.success(request, f"Tu cuenta ha sido activada y te has registrado como {tipo} en el evento {evento.eve_nombre}.")
        return redirect('ver_eventos')
    
    # Crear usuario si no existe
    if not usuario:
        usuario = Usuario.objects.create_user(
            username=correo.split('@')[0] if correo else f"user{documento}",
            email=correo,
            telefono=telefono,
            documento=documento,
            first_name=nombres,
            last_name=apellidos,
            password='temporal',
            is_active=True  # Activar directamente ya que viene por invitación
        )
        
        # Asignar rol y crear objeto evento-rol
        rol_obj = Rol.objects.filter(nombre__iexact=tipo).first()
        if rol_obj:
            RolUsuario.objects.create(usuario=usuario, rol=rol_obj)
        
        # Crear objetos evento-rol para nuevo usuario (solo participante y evaluador)
        if tipo == 'participante':
            participante = Participante.objects.create(usuario=usuario)
            ParticipanteEvento.objects.create(
                participante=participante,
                evento=evento,
                par_eve_fecha_hora=timezone.now(),
                par_eve_estado='Pendiente',
                par_eve_documentos=archivo,
                confirmado=True
            )
        elif tipo == 'evaluador':
            evaluador = Evaluador.objects.create(usuario=usuario)
            EvaluadorEvento.objects.create(
                evaluador=evaluador,
                evento=evento,
                eva_eve_fecha_hora=timezone.now(),
                eva_eve_estado='Pendiente',
                eva_eve_documentos=archivo,
                confirmado=True
            )
        
        # Enviar correo con credenciales
        clave = generar_clave()
        usuario.set_password(clave)
        usuario.save()
        
        cuerpo_html = render_to_string('correo_registro_completado.html', {
            'nombre': usuario.first_name,
            'evento': evento.eve_nombre,
            'tipo': tipo.title(),
            'clave': clave,
            'email': usuario.email,
        })
        
        email = EmailMessage(
            subject=f'Registro completado - {evento.eve_nombre}',
            body=cuerpo_html,
            to=[usuario.email],
        )
        email.content_subtype = 'html'
        email.send()
        
        messages.success(request, f"¡Registro completado! Se ha enviado un correo con tus credenciales de acceso.")
        return redirect('ver_eventos')


def registro_evento(request, eve_id, tipo):
    evento = Evento.objects.filter(eve_id=eve_id).first()
    if not evento:
        messages.error(request, "Evento no encontrado")
        return redirect('ver_eventos')
    if request.method == "POST":
        # Solo asistentes permitidos en este flujo
        if tipo == 'asistente':
            documento = request.POST.get('asi_id')
            nombres = request.POST.get('asi_nombres')
            apellidos = request.POST.get('asi_apellidos')
            correo = request.POST.get('asi_correo')
            telefono = request.POST.get('asi_telefono')
            archivo = request.FILES.get('soporte_pago')
        else:
            return HttpResponse('Tipo de registro inválido para este flujo.')
        # Validación básica
        if not (documento and nombres and apellidos and correo):
            messages.error(request, "Por favor completa todos los campos obligatorios.")
            return redirect(f'inscripcion_{tipo}', eve_id=eve_id)
        # Validar consistencia de datos si el usuario ya existe
        usuario = Usuario.objects.filter(Q(email=correo) | Q(documento=documento)).first()
        if usuario:
            if (usuario.email != correo or usuario.documento != documento or usuario.first_name != nombres or usuario.last_name != apellidos):
                messages.error(request, "Los datos ingresados no coinciden con los registrados para este usuario. Por favor, verifica tu información.")
                return redirect(f'inscripcion_{tipo}', eve_id=eve_id)
        # Validar que no esté inscrito en el mismo evento (en cualquier rol)
        ya_inscrito = False
        pendiente_confirmacion = False
        rol_inscrito = ""
        if usuario:
            # Verificar si está como asistente
            asistente = getattr(usuario, 'asistente', None)
            if asistente:
                rel = AsistenteEvento.objects.filter(asistente=asistente, evento=evento).first()
                if rel:
                    ya_inscrito = True
                    pendiente_confirmacion = not rel.confirmado
                    rol_inscrito = "asistente"
            
            # Verificar si está como participante
            if not ya_inscrito:
                participante = getattr(usuario, 'participante', None)
                if participante:
                    participacion = ParticipanteEvento.objects.filter(participante=participante, evento=evento).first()
                    if participacion:
                        ya_inscrito = True
                        pendiente_confirmacion = not participacion.confirmado
                        rol_inscrito = "participante"
            
            # Verificar si está como evaluador
            if not ya_inscrito:
                evaluador = getattr(usuario, 'evaluador', None)
                if evaluador:
                    evaluacion = EvaluadorEvento.objects.filter(evaluador=evaluador, evento=evento).first()
                    if evaluacion:
                        ya_inscrito = True
                        pendiente_confirmacion = not evaluacion.confirmado
                        rol_inscrito = "evaluador"
        
        if ya_inscrito:
            if pendiente_confirmacion:
                messages.error(request, f"Ya tienes una inscripción como {rol_inscrito} pendiente de confirmación para este evento. Revisa tu correo (y la carpeta de spam) para confirmar tu registro.")
            else:
                messages.error(request, f"Ya tienes una inscripción como {rol_inscrito} para este evento. No puedes inscribirte nuevamente.")
            return redirect('ver_eventos')
        # Si usuario existe y está activo, asignar rol asistente y crear relación evento-asistente
        if usuario and usuario.is_active:
            # Asignar rol asistente si no lo tiene
            rol = Rol.objects.filter(nombre__iexact=tipo).first()
            if rol and not RolUsuario.objects.filter(usuario=usuario, rol=rol).exists():
                RolUsuario.objects.create(usuario=usuario, rol=rol)
            # Crear relación evento-asistente si no existe
            asistente, _ = Asistente.objects.get_or_create(usuario=usuario)
            if not AsistenteEvento.objects.filter(asistente=asistente, evento=evento).exists():
                estado = "Pendiente" if evento.eve_tienecosto == 'SI' else "Aprobado"
                # Solo guardar soporte si el evento tiene costo
                asistencia = AsistenteEvento(
                    asistente=asistente,
                    evento=evento,
                    asi_eve_fecha_hora=timezone.now(),
                    asi_eve_estado=estado,
                    confirmado= True
                )
                if evento.eve_tienecosto == 'SI' and archivo:
                    asistencia.asi_eve_soporte = archivo
                
                qr_img_bytes = None
                if estado == "Aprobado":
                    qr_data = f"asistente:{usuario.documento}|evento:{evento.eve_id}|clave:{usuario.password}"
                    buffer = BytesIO()
                    qr_img = qrcode.make(qr_data)
                    qr_img.save(buffer, format='PNG')
                    filename = f"qr_asistente_{usuario.documento}_{evento.eve_id}.png"
                    asistencia.asi_eve_qr.save(filename, ContentFile(buffer.getvalue()), save=False)
                    qr_img_bytes = buffer.getvalue()
                    
                    # Descontar capacidad del evento cuando es gratuito y aprobado
                    evento.eve_capacidad -= 1
                    evento.save()
                
                asistencia.save()
                
                # Enviar correo con QR si es gratuito y aprobado
                if estado == "Aprobado":
                    cuerpo_html = render_to_string('correo_clave.html', {
                        'nombre': usuario.first_name,
                        'evento': evento.eve_nombre,
                        'clave': None,  # No mostrar clave porque ya está activo
                        'qr_url': asistencia.asi_eve_qr.url if asistencia.asi_eve_qr else None,
                    })
                    email = EmailMessage(
                        subject=f'Registro aprobado - {evento.eve_nombre}',
                        body=cuerpo_html,
                        to=[usuario.email],
                    )
                    email.content_subtype = 'html'
                    if qr_img_bytes:
                        email.attach('qr_acceso.png', qr_img_bytes, 'image/png')
                    email.send()
                    
            return render(request, "ya_registrado.html", {
                'nombre': usuario.first_name,
                'correo': usuario.email,
                'evento': evento.eve_nombre,
                'preinscripcion': True,
            })
        # Si usuario existe y está inactivo, crear objeto asistente-evento con archivo y estado 'Pendiente', mostrar proceso pendiente
        if usuario and not usuario.is_active:
            # Crear RolUsuario si no existe
            rol_obj = Rol.objects.filter(nombre__iexact=tipo).first()
            if rol_obj and not RolUsuario.objects.filter(usuario=usuario, rol=rol_obj).exists():
                RolUsuario.objects.create(usuario=usuario, rol=rol_obj)
            asistente, _ = Asistente.objects.get_or_create(usuario=usuario)
            if not AsistenteEvento.objects.filter(asistente=asistente, evento=evento).exists():
                asistencia = AsistenteEvento(
                    asistente=asistente,
                    evento=evento,
                    asi_eve_fecha_hora=timezone.now(),
                    asi_eve_estado='Pendiente',
                    confirmado=False
                )
                if evento.eve_tienecosto == 'SI' and archivo:
                    asistencia.asi_eve_soporte = archivo
                asistencia.save()
            # Generar token y URL de reenvío para el proceso actual
            serializer = URLSafeTimedSerializer(settings.SECRET_KEY)
            token = serializer.dumps({'email': usuario.email, 'evento': evento.eve_id, 'rol': tipo})
            confirm_url = request.build_absolute_uri(reverse('confirmar_registro', args=[token]))
            cuerpo_html = render_to_string('correo_confirmacion.html', {
                'nombre': usuario.first_name,
                'evento': evento.eve_nombre,
                'confirm_url': confirm_url,
            })
            email = EmailMessage(
                subject=f'Confirma tu registro como {tipo} en {evento.eve_nombre}',
                body=cuerpo_html,
                to=[usuario.email],
            )
            email.content_subtype = 'html'
            email.send()
            return render(request, "registro_pendiente.html", {
                'nombre': usuario.first_name,
                'correo': usuario.email,
                'evento': evento.eve_nombre,
            })
        # Crear usuario si no existe
        if not usuario:
            usuario = Usuario.objects.create_user(
                username=correo.split('@')[0] if correo else f"user{documento}",
                email=correo,
                telefono=telefono,
                documento=documento,
                first_name=nombres,
                last_name=apellidos,
                password='temporal',
                is_active=False
            )
        # Asignar rol asistente y crear objeto asistente-evento, luego enviar correo de confirmación
        rol_obj = Rol.objects.filter(nombre__iexact=tipo).first()
        if rol_obj and not RolUsuario.objects.filter(usuario=usuario, rol=rol_obj).exists():
            RolUsuario.objects.create(usuario=usuario, rol=rol_obj)
        asistente, _ = Asistente.objects.get_or_create(usuario=usuario)
        if not AsistenteEvento.objects.filter(asistente=asistente, evento=evento).exists():
            asistencia = AsistenteEvento(
                asistente=asistente,
                evento=evento,
                asi_eve_fecha_hora=timezone.now(),
                asi_eve_estado='Pendiente',
                confirmado=False
            )
            if evento.eve_tienecosto == 'SI' and archivo:
                asistencia.asi_eve_soporte = archivo
            asistencia.save()
        serializer = URLSafeTimedSerializer(settings.SECRET_KEY)
        token = serializer.dumps({'email': usuario.email, 'evento': evento.eve_id, 'rol': tipo})
        confirm_url = request.build_absolute_uri(reverse('confirmar_registro', args=[token]))
        cuerpo_html = render_to_string('correo_confirmacion.html', {
            'nombre': usuario.first_name,
            'evento': evento.eve_nombre,
            'confirm_url': confirm_url,
        })
        email = EmailMessage(
            subject=f'Confirma tu registro como {tipo} en {evento.eve_nombre}',
            body=cuerpo_html,
            to=[usuario.email],
        )
        email.content_subtype = 'html'
        email.send()
        return render(request, "registro_pendiente.html", {
            'nombre': usuario.first_name,
            'correo': usuario.email,
            'evento': evento.eve_nombre,
        })
    return render(request, f'inscribirse_{tipo}.html', {'evento': evento})


def confirmar_registro(request, token):   
    serializer = URLSafeTimedSerializer(settings.SECRET_KEY)
    try:
        data = serializer.loads(token, max_age=60)  # 1 minuto
        email = data.get('email')
        evento_id = data.get('evento')
        rol = data.get('rol')
    except (BadSignature, SignatureExpired):
        # Si el usuario no está activo, eliminar solo la relación evento-rol no confirmada, el objeto de rol si no tiene más relaciones, y el usuario si no tiene más roles
        try:
            data = serializer.loads(token, max_age=60*60*24)  # Intentar decodificar para obtener email
            email = data.get('email')
            evento_id = data.get('evento')
            rol = data.get('rol')
            usuario = Usuario.objects.filter(email=email).first()
            evento = Evento.objects.filter(eve_id=evento_id).first()
            print(f"[DEBUG] Usuario antes de limpieza: {usuario}")
            if usuario and evento:
                rol_obj = Rol.objects.filter(nombre__iexact=rol).first()
                rol_usuario = None
                if rol_obj:
                    rol_usuario = RolUsuario.objects.filter(usuario=usuario, rol=rol_obj).first()
                # --- Limpieza por rol ---
                if rol == 'asistente':
                    asistente = getattr(usuario, 'asistente', None)
                    print(f"[DEBUG] Asistente antes: {asistente}")
                    if asistente:
                        rel = AsistenteEvento.objects.filter(asistente=asistente, evento=evento, confirmado=False).first()
                        print(f"[DEBUG] AsistenteEvento a eliminar: {rel}")
                        if rel:
                            rel.delete()
                        print(f"[DEBUG] AsistenteEvento restantes: {AsistenteEvento.objects.filter(asistente=asistente).count()}")
                        # Recargar usuario y relaciones tras posible borrado
                        if not AsistenteEvento.objects.filter(asistente=asistente).exists():
                            print(f"[DEBUG] Eliminando Asistente: {asistente}")
                            asistente.delete()
                            usuario = Usuario.objects.get(pk=usuario.pk)
                            if rol_usuario:
                                print(f"[DEBUG] Eliminando RolUsuario: {rol_usuario}")
                                rol_usuario.delete()
                                usuario = Usuario.objects.get(pk=usuario.pk)
                elif rol == 'participante':
                    participante = getattr(usuario, 'participante', None)
                    print(f"[DEBUG] Participante antes: {participante}")
                    if participante:
                        rel = ParticipanteEvento.objects.filter(participante=participante, evento=evento, confirmado=False).first()
                        print(f"[DEBUG] ParticipanteEvento a eliminar: {rel}")
                        if rel:
                            rel.delete()
                        print(f"[DEBUG] ParticipanteEvento restantes: {ParticipanteEvento.objects.filter(participante=participante).count()}")
                        if not ParticipanteEvento.objects.filter(participante=participante).exists():
                            print(f"[DEBUG] Eliminando Participante: {participante}")
                            participante.delete()
                            usuario = Usuario.objects.get(pk=usuario.pk)
                            if rol_usuario:
                                print(f"[DEBUG] Eliminando RolUsuario: {rol_usuario}")
                                rol_usuario.delete()
                                usuario = Usuario.objects.get(pk=usuario.pk)
                elif rol == 'evaluador':
                    evaluador = getattr(usuario, 'evaluador', None)
                    print(f"[DEBUG] Evaluador antes: {evaluador}")
                    if evaluador:
                        rel = EvaluadorEvento.objects.filter(evaluador=evaluador, evento=evento, confirmado=False).first()
                        print(f"[DEBUG] EvaluadorEvento a eliminar: {rel}")
                        if rel:
                            rel.delete()
                        print(f"[DEBUG] EvaluadorEvento restantes: {EvaluadorEvento.objects.filter(evaluador=evaluador).count()}")
                        if not EvaluadorEvento.objects.filter(evaluador=evaluador).exists():
                            print(f"[DEBUG] Eliminando Evaluador: {evaluador}")
                            evaluador.delete()
                            usuario = Usuario.objects.get(pk=usuario.pk)
                            if rol_usuario:
                                print(f"[DEBUG] Eliminando RolUsuario: {rol_usuario}")
                                rol_usuario.delete()
                                usuario = Usuario.objects.get(pk=usuario.pk)

                # --- Limpieza de huérfanos (por si quedaron) ---
                asistente = getattr(usuario, 'asistente', None)
                if asistente and not AsistenteEvento.objects.filter(asistente=asistente).exists():
                    print(f"[DEBUG] Eliminando Asistente huérfano: {asistente}")
                    asistente.delete()
                    usuario = Usuario.objects.get(pk=usuario.pk)
                participante = getattr(usuario, 'participante', None)
                if participante and not ParticipanteEvento.objects.filter(participante=participante).exists():
                    print(f"[DEBUG] Eliminando Participante huérfano: {participante}")
                    participante.delete()
                    usuario = Usuario.objects.get(pk=usuario.pk)
                evaluador = getattr(usuario, 'evaluador', None)
                if evaluador and not EvaluadorEvento.objects.filter(evaluador=evaluador).exists():
                    print(f"[DEBUG] Eliminando Evaluador huérfano: {evaluador}")
                    evaluador.delete()
                    usuario = Usuario.objects.get(pk=usuario.pk)

                # --- Validación final y borrado de usuario si corresponde ---
                tiene_asistente = hasattr(usuario, 'asistente')
                tiene_participante = hasattr(usuario, 'participante')
                tiene_evaluador = hasattr(usuario, 'evaluador')
                tiene_rolusuario = RolUsuario.objects.filter(usuario=usuario).exists()
                print(f"[DEBUG] Estado final usuario: asistente={tiene_asistente}, participante={tiene_participante}, evaluador={tiene_evaluador}, rolusuario={tiene_rolusuario}")
                if not (tiene_asistente or tiene_participante or tiene_evaluador or tiene_rolusuario):
                    print(f"[DEBUG] Eliminando usuario: {usuario}")
                    usuario.delete()
                else:
                    print(f"[DEBUG] Usuario NO eliminado: {usuario}")
        except Exception as e:
            print(f"[DEBUG] Excepción en cleanup: {e}")
        return render(request, 'enlace_expirado.html')
    usuario = Usuario.objects.filter(email=email).first()
    evento = Evento.objects.filter(eve_id=evento_id).first()
    if not usuario or not evento:
        return HttpResponse('Usuario o evento no encontrado.')
    if usuario.is_active:
        # Si ya está activo, procesar la confirmación sin generar nueva clave
        # Asignar el rol confirmado solo si no lo tiene ya (solo asistente permitido)
        rol_obj = Rol.objects.filter(nombre__iexact=rol).first()
        if rol_obj and not RolUsuario.objects.filter(usuario=usuario, rol=rol_obj).exists():
            RolUsuario.objects.create(usuario=usuario, rol=rol_obj)
        
        qr_url = None
        qr_img_bytes = None
        
        # Solo procesar asistentes en este flujo
        if rol == 'asistente':
            asistente, _ = Asistente.objects.get_or_create(usuario=usuario)
            asistencia = AsistenteEvento.objects.filter(asistente=asistente, evento=evento).first()
            if asistencia:
                asistencia.confirmado = True
                # Si es gratuito: aprobado, QR y descontar capacidad
                if evento.eve_tienecosto == 'NO':
                    asistencia.asi_eve_estado = 'Aprobado'
                    qr_data = f"asistente:{usuario.documento}|evento:{evento.eve_id}|clave:{usuario.password}"
                    buffer = BytesIO()
                    qr_img = qrcode.make(qr_data)
                    qr_img.save(buffer, format='PNG')
                    filename = f"qr_asistente_{usuario.documento}_{evento.eve_id}.png"
                    asistencia.asi_eve_qr.save(filename, ContentFile(buffer.getvalue()), save=False)
                    qr_url = asistencia.asi_eve_qr.url
                    qr_img_bytes = buffer.getvalue()
                    evento.eve_capacidad -= 1
                    evento.save()
                else:
                    # Si tiene costo: mantener en Pendiente
                    asistencia.asi_eve_estado = 'Pendiente'
                asistencia.save()
                
                # Enviar correo con QR si corresponde
                if evento.eve_tienecosto == 'NO':
                    cuerpo_html = render_to_string('correo_clave.html', {
                        'nombre': usuario.first_name,
                        'evento': evento.eve_nombre,
                        'clave': None,  # No mostrar clave porque ya está activo
                        'qr_url': qr_url,
                    })
                    email = EmailMessage(
                        subject=f'Confirmación de registro - {evento.eve_nombre}',
                        body=cuerpo_html,
                        to=[usuario.email],
                    )
                    email.content_subtype = 'html'
                    if qr_img_bytes:
                        email.attach('qr_acceso.png', qr_img_bytes, 'image/png')
                    email.send()
        else:
            return HttpResponse('Tipo de registro inválido para este flujo.')
        
        return render(request, "ya_registrado.html", {
            'nombre': usuario.first_name,
            'correo': usuario.email,
            'evento': evento.eve_nombre,
        })
    
    clave = generar_clave()
    usuario.set_password(clave)
    usuario.is_active = True
    usuario.save()
    # Asignar el rol confirmado solo si no lo tiene ya (solo asistente permitido)
    rol_obj = Rol.objects.filter(nombre__iexact=rol).first()
    if rol_obj and not RolUsuario.objects.filter(usuario=usuario, rol=rol_obj).exists():
        RolUsuario.objects.create(usuario=usuario, rol=rol_obj)
    qr_url = None
    qr_img_bytes = None
    
    # Solo procesar asistentes en este flujo
    if rol == 'asistente':
        asistente, _ = Asistente.objects.get_or_create(usuario=usuario)
        asistencia = AsistenteEvento.objects.filter(asistente=asistente, evento=evento).first()
        if asistencia:
            asistencia.confirmado = True
            # Solo asistentes gratuitos quedan aprobados y reciben QR
            if evento.eve_tienecosto == 'NO':
                asistencia.asi_eve_estado = 'Aprobado'
                qr_data = f"asistente:{usuario.documento}|evento:{evento.eve_id}|clave:{clave}"
                buffer = BytesIO()
                qr_img = qrcode.make(qr_data)
                qr_img.save(buffer, format='PNG')
                filename = f"qr_asistente_{usuario.documento}_{clave}.png"
                asistencia.asi_eve_qr.save(filename, ContentFile(buffer.getvalue()), save=False)
                qr_url = asistencia.asi_eve_qr.url
                qr_img_bytes = buffer.getvalue()
                evento.eve_capacidad -= 1
                evento.save()
            asistencia.save()
    else:
        return HttpResponse('Tipo de registro inválido para este flujo.')
    cuerpo_html = render_to_string('correo_clave.html', {
        'nombre': usuario.first_name,
        'evento': evento.eve_nombre,
        'clave': clave,
        'qr_url': qr_url,
    })
    email = EmailMessage(
        subject=f'Tu clave de acceso para el evento {evento.eve_nombre}',
        body=cuerpo_html,
        to=[usuario.email],
    )
    email.content_subtype = 'html'
    if qr_img_bytes:
        email.attach('qr_acceso.png', qr_img_bytes, 'image/png')
    email.send()
    return render(request, 'registro_confirmado.html', {
        'nombre': usuario.first_name,
        'evento': evento.eve_nombre,
        'correo': usuario.email,
    })


def registrarse_admin_evento(request):
    codigo = request.GET.get('codigo', '').strip()
    invitacion = CodigoInvitacionAdminEvento.objects.filter(codigo=codigo).first()
    if not invitacion or invitacion.estado != 'activo' or invitacion.fecha_expiracion < timezone.now():
        return render(request, 'registro_admin_evento_invalido.html', {'razon': 'El código es inválido, expirado o ya fue usado.'})

    if request.method == 'POST':
        nombre = request.POST.get('first_name', '').strip()
        apellido = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        documento = request.POST.get('documento', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        errores = []
        if not nombre or not apellido or not email or not documento or not username or not password:
            errores.append('Todos los campos son obligatorios.')
        if Usuario.objects.filter(email=email).exists():
            errores.append('Ya existe un usuario con ese correo.')
        if Usuario.objects.filter(documento=documento).exists():
            errores.append('Ya existe un usuario con ese documento.')
        if Usuario.objects.filter(username=username).exists():
            errores.append('Ya existe un usuario con ese nombre de usuario.')
        if errores:
            for e in errores:
                messages.error(request, e)
            return render(request, 'registro_admin_evento.html', {'codigo': codigo, 'email': invitacion.email_destino})

        with transaction.atomic():
            user = Usuario.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=nombre,
                last_name=apellido,
                telefono=telefono,
                documento=documento
            )
            rol_admin, _ = Rol.objects.get_or_create(nombre='administrador_evento')
            RolUsuario.objects.create(usuario=user, rol=rol_admin)
            AdministradorEvento.objects.create(usuario=user)
            invitacion.estado = 'usado'
            invitacion.fecha_uso = timezone.now()
            invitacion.usuario_asignado = user
            invitacion.save()
        return render(request, 'registro_admin_evento_exito.html', {'usuario': user})

    # GET: mostrar formulario
    return render(request, 'registro_admin_evento.html', {'codigo': codigo, 'email': invitacion.email_destino})
