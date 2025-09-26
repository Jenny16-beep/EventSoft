def get_rol_usuario(user):
    if not user.is_authenticated:
        return None
    # Usar el rol de la sesión si está presente
    rol_actual = getattr(user, 'rol_actual', None)
    if rol_actual:
        return rol_actual
    rol_usuario = user.roles.first()
    return rol_usuario.rol.nombre if rol_usuario else None

def es_superadmin(user):
    return get_rol_usuario(user) == 'superadmin'

def es_administrador_evento(user):
    return get_rol_usuario(user) == 'administrador_evento'

def es_evaluador(user):
    return get_rol_usuario(user) == 'evaluador'

def es_participante(user):
    return get_rol_usuario(user) == 'participante'

def es_asistente(user):
    return get_rol_usuario(user) == 'asistente'