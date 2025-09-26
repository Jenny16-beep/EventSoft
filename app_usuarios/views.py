from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.hashers import check_password
from django.contrib import messages
from app_participantes.models import ParticipanteEvento
from app_asistentes.models import AsistenteEvento
from app_evaluadores.models import EvaluadorEvento

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        rol = request.POST.get('rol')
        user = authenticate(request, email=email, password=password)
        if user is not None:
            # Verificar si el usuario tiene el rol seleccionado
            if not user.roles.filter(rol__nombre=rol).exists():
                messages.error(request, f"No tienes asignado el rol seleccionado.")
                return redirect('login')
            # Validar confirmación según el rol
            if rol == 'asistente':
                if not hasattr(user, 'asistente'):
                    messages.error(request, "Tu cuenta no está registrada como asistente.")
                    return redirect('login')
                if not AsistenteEvento.objects.filter(asistente=user.asistente, confirmado=True).exists():
                    messages.error(request, "Aún no has confirmado tu inscripción como asistente.")
                    return redirect('login')
            elif rol == 'participante':
                if not hasattr(user, 'participante'):
                    messages.error(request, "Tu cuenta no está registrada como participante.")
                    return redirect('login')
                if not ParticipanteEvento.objects.filter(participante=user.participante, confirmado=True).exists():
                    messages.error(request, "Aún no has confirmado tu inscripción como participante.")
                    return redirect('login')
            elif rol == 'evaluador':
                if not hasattr(user, 'evaluador'):
                    messages.error(request, "Tu cuenta no está registrada como evaluador.")
                    return redirect('login')
                if not EvaluadorEvento.objects.filter(evaluador=user.evaluador, confirmado=True).exists():
                    messages.error(request, "Aún no has confirmado tu inscripción como evaluador.")
                    return redirect('login')
            # Guardar el rol elegido en la sesión
            request.session['rol_sesion'] = rol
            login(request, user)
            return redirect_por_rol(rol)
        else:
            messages.error(request, "Correo o contraseña incorrectos.")
            return redirect('login')
    return render(request, 'login.html', {})

def redirect_por_rol(rol):
    if rol == 'superadmin':
        return redirect('dashboard_superadmin')
    elif rol == 'administrador_evento':
        return redirect('dashboard_adminevento')
    elif rol == 'evaluador':
        return redirect('dashboard_evaluador')
    elif rol == 'participante':
        return redirect('dashboard_participante_general' )
    elif rol == 'asistente':
        return redirect('dashboard_asistente')
    else:
        return redirect('login')

@login_required
def cambiar_contrasena(request):
    if request.method == 'POST':
        actual = request.POST.get('actual')
        nueva = request.POST.get('nueva')
        confirmar = request.POST.get('confirmar')
        user = request.user
        rol_usuario = user.roles.first()
        rol = rol_usuario.rol.nombre if rol_usuario else None
        if not check_password(actual, user.password):
            messages.error(request, 'La contraseña actual no es correcta.')
        elif nueva != confirmar:
            messages.error(request, 'Las nuevas contraseñas no coinciden.')
        else:
            user.set_password(nueva)
            user.save()
            update_session_auth_hash(request, user)
            if rol == 'asistente':
                from app_asistentes.models import AsistenteEvento
                AsistenteEvento.objects.filter(asistente__usuario=user).update(asi_eve_clave=nueva)
            elif rol == 'participante':
                from app_participantes.models import ParticipanteEvento
                ParticipanteEvento.objects.filter(participante__usuario=user).update(par_eve_clave=nueva)
            elif rol == 'evaluador':
                from app_evaluadores.models import EvaluadorEvento
                EvaluadorEvento.objects.filter(evaluador=user).update(eva_eve_clave=nueva)
            messages.success(request, 'La contraseña ha sido actualizada correctamente.')
            return redirect('ver_eventos')
    return render(request, 'cambiar_contrasena.html')