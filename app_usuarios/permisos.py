def es_superadmin(user):
    return user.is_authenticated and user.rol == 'superadmin'

def es_administrador_evento(user):
    return user.is_authenticated and user.rol == 'administrador_evento'

def es_evaluador(user):
    return user.is_authenticated and user.rol == 'evaluador'

def es_participante(user):
    return user.is_authenticated and user.rol == 'participante'

def es_asistente(user):
    return user.is_authenticated and user.rol == 'asistente'
