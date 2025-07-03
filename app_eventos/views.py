from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Prefetch, Q
from django.core.files.base import ContentFile

from io import BytesIO

from app_participantes.models import Participante, ParticipanteEvento
from app_areas.models import Area, Categoria
from app_asistentes.models import Asistente, AsistenteEvento
from app_evaluadores.models import Evaluador, EvaluadorEvento
from .models import Evento, EventoCategoria
from app_usuarios.models import Usuario

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


@require_http_methods(["GET", "POST"])
def inscripcion_asistente(request, eve_id):
    evento = get_object_or_404(Evento, pk=eve_id)
    if request.method == 'GET':
        return render(request, "inscribirse_asistente.html", {'evento': evento})
    documento = request.POST.get('asi_id')
    nombres = request.POST.get('asi_nombres')
    apellidos = request.POST.get('asi_apellidos')
    correo = request.POST.get('asi_correo')
    telefono = request.POST.get('asi_telefono')
    soporte = request.FILES.get('soporte_pago')
    if evento.eve_capacidad <= 0:
        messages.error(request, "Este evento ya no tiene cupos disponibles.")
        return redirect('ver_eventos')
    usuario = Usuario.objects.filter(Q(email=correo) | Q(documento=documento)).first()
    clave = generar_clave()
    clave_generada = True
    if usuario:
        if usuario.rol != 'asistente':
            messages.error(request, "Este correo o documento ya está registrado con otro rol.")
            return redirect('ver_eventos')
        clave_generada = False
    else:
        usuario = Usuario.objects.create_user(
            username=correo.split('@')[0] if correo else f"user{documento}",
            email=correo,
            telefono=telefono,
            documento=documento,
            first_name=nombres,
            last_name=apellidos,
            rol='asistente',
            password=clave
        )
    asistente, _ = Asistente.objects.get_or_create(usuario=usuario)
    if AsistenteEvento.objects.filter(asistente=asistente, evento=evento).exists():
        messages.warning(request, "Ya estás inscrito en este evento como asistente.")
        return redirect('ver_eventos')
    estado = "Pendiente" if evento.eve_tienecosto == 'SI' else "Aprobado"
    fecha_hora = timezone.now()
    if clave_generada:
        clave_a_guardar = clave
    else:
        ultima_inscripcion = AsistenteEvento.objects.filter(
            asistente=asistente
        ).order_by('-asi_eve_fecha_hora').first()
        clave_a_guardar = ultima_inscripcion.asi_eve_clave if ultima_inscripcion else "NO_DISPONIBLE"
    asistencia = AsistenteEvento(
        asistente=asistente,
        evento=evento,
        asi_eve_fecha_hora=fecha_hora,
        asi_eve_estado=estado,
        asi_eve_clave=clave_a_guardar
    )
    if soporte:
        asistencia.asi_eve_soporte = soporte
    if estado == "Aprobado":
        qr_data = f"asistente:{documento}|evento:{evento.eve_id}|clave:{clave_a_guardar}"
        qr_img = qrcode.make(qr_data)
        buffer = BytesIO()
        qr_img.save(buffer, format='PNG')
        filename = f"qr_asistente_{documento}_{clave_a_guardar}.png"
        asistencia.asi_eve_qr.save(filename, ContentFile(buffer.getvalue()), save=False)
        evento.eve_capacidad -= 1
        evento.save()
    asistencia.save()
    return render(request, "confirmacion_asistente.html", {
        'nombre': usuario.first_name,
        'clave': clave if clave_generada else None,
        'qr_generado': estado == "Aprobado",
        'evento_tiene_costo': evento.eve_tienecosto == 'SI',
        'clave_existente': not clave_generada
    })

    
def inscribirse_participante(request, eve_id):
    evento = Evento.objects.prefetch_related(
        Prefetch('eventocategoria_set', queryset=EventoCategoria.objects.select_related('categoria'))
    ).filter(eve_id=eve_id).first()  
    if not evento:
        messages.error(request, "Evento no encontrado")
        return redirect('ver_eventos')
    if request.method == "POST":
        documento = request.POST.get('par_id')
        nombres = request.POST.get('par_nombres')
        apellidos = request.POST.get('par_apellidos')
        correo = request.POST.get('par_correo')
        telefono = request.POST.get('par_telefono')
        archivo = request.FILES.get('documentos')
        if not (documento and nombres and apellidos and correo):
            messages.error(request, "Por favor completa todos los campos obligatorios.")
            return redirect('inscripcion_participante', eve_id=eve_id)
        usuario = Usuario.objects.filter(Q(email=correo) | Q(documento=documento)).first()
        clave_generada = False
        if usuario:
            datos_iguales = (
                usuario.documento == documento and
                usuario.first_name.strip().lower() == nombres.strip().lower() and
                usuario.last_name.strip().lower() == apellidos.strip().lower() and
                usuario.email.strip().lower() == correo.strip().lower() and
                (usuario.telefono or "").strip() == (telefono or "").strip()
            )
            if not datos_iguales:
                messages.error(request, "La información proporcionada no coincide con registros anteriores.")
                return redirect('inscripcion_participante', eve_id=eve_id)
            if usuario.rol != 'participante':
                messages.error(request, "Ya estás registrado con otro rol y no puedes inscribirte como participante.")
                return redirect('inscripcion_participante', eve_id=eve_id)
            participante, _ = Participante.objects.get_or_create(usuario=usuario)
            if ParticipanteEvento.objects.filter(participante=participante, evento=evento).exists():
                messages.warning(request, "Ya estás inscrito en este evento como participante.")
                return redirect('ver_eventos')
            ultima_inscripcion = ParticipanteEvento.objects.filter(participante=participante)\
                .order_by('-par_eve_fecha_hora').first()

            clave = ultima_inscripcion.par_eve_clave if ultima_inscripcion and ultima_inscripcion.par_eve_clave else generar_clave()
            clave_generada = not (ultima_inscripcion and ultima_inscripcion.par_eve_clave)

        else:
            clave = generar_clave()
            clave_generada = True
            username_generado = correo.split('@')[0] if correo else f"user{documento}"
            usuario = Usuario.objects.create_user(
                username=username_generado,
                email=correo,
                telefono=telefono,
                documento=documento,
                first_name=nombres,
                last_name=apellidos,
                rol='participante',
                password=clave
            )
            participante = Participante.objects.create(usuario=usuario)
        ParticipanteEvento.objects.create(
            participante=participante,
            evento=evento,
            par_eve_fecha_hora=timezone.now(),
            par_eve_documentos=archivo,
            par_eve_estado='Pendiente',
            par_eve_clave=clave
        )
        return render(request, "confirmacion_participante.html", {
            "clave": clave if clave_generada else None,
            "nombre": nombres,
        })
    return render(request, 'inscribirse_participante.html', {'evento': evento})



def inscribirse_evaluador(request, eve_id):
    evento = Evento.objects.prefetch_related(
        Prefetch('eventocategoria_set', queryset=EventoCategoria.objects.select_related('categoria'))
    ).filter(eve_id=eve_id).first()
    if not evento:
        messages.error(request, "Evento no encontrado")
        return redirect('ver_eventos')
    if request.method == "POST":
        documento = request.POST.get('eva_id')
        nombres = request.POST.get('eva_nombres')
        apellidos = request.POST.get('eva_apellidos')
        correo = request.POST.get('eva_correo')
        telefono = request.POST.get('eva_telefono')
        archivo = request.FILES.get('documentacion')
        if not (documento and nombres and apellidos and correo):
            messages.error(request, "Por favor completa todos los campos obligatorios.")
            return redirect('inscripcion_evaluador', eve_id=eve_id)
        usuario = Usuario.objects.filter(Q(documento=documento) | Q(email=correo)).first()
        clave_generada = False
        if usuario:
            datos_iguales = (
                usuario.documento == documento and
                usuario.first_name.strip().lower() == nombres.strip().lower() and
                usuario.last_name.strip().lower() == apellidos.strip().lower() and
                usuario.email.strip().lower() == correo.strip().lower() and
                (usuario.telefono or "").strip() == (telefono or "").strip()
            )
            if not datos_iguales:
                messages.error(request, "La información proporcionada no coincide con registros anteriores.")
                return redirect('inscripcion_evaluador', eve_id=eve_id)
            if usuario.rol != 'evaluador':
                messages.error(request, "Ya estás registrado con otro rol y no puedes inscribirte como evaluador.")
                return redirect('inscripcion_evaluador', eve_id=eve_id)
            evaluador, _ = Evaluador.objects.get_or_create(usuario=usuario)
            if EvaluadorEvento.objects.filter(evaluador=usuario, evento=evento).exists():
                messages.warning(request, "Ya estás inscrito en este evento como evaluador.")
                return redirect('ver_eventos')
            ultima = EvaluadorEvento.objects.filter(evaluador=usuario).order_by('-eva_eve_fecha_hora').first()
            clave = ultima.eva_eve_clave if ultima and ultima.eva_eve_clave else generar_clave()
            clave_generada = not (ultima and ultima.eva_eve_clave)
        else:
            clave = generar_clave()
            clave_generada = True
            username_generado = correo.split('@')[0] if correo else f"user{documento}"
            usuario = Usuario.objects.create_user(
                username=username_generado,
                email=correo,
                telefono=telefono,
                documento=documento,
                first_name=nombres,
                last_name=apellidos,
                rol='evaluador',
                password=clave
            )
            evaluador = Evaluador.objects.create(usuario=usuario)
        EvaluadorEvento.objects.create(
            evaluador=usuario,
            evento=evento,
            eva_eve_estado='Pendiente',
            eva_eve_clave=clave,
            eva_eve_fecha_hora=timezone.now(),
            eva_eve_documentos=archivo
        )
        return render(request, "confirmacion_evaluador.html", {
            "clave": clave if clave_generada else None,
            "nombre": nombres,
            "nueva": clave_generada
        })
    return render(request, 'inscribirse_evaluador.html', {'evento': evento})