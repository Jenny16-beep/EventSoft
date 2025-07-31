from django.utils.deprecation import MiddlewareMixin

class RolSesionMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.user.is_authenticated:
            rol_sesion = request.session.get('rol_sesion')
            if rol_sesion:
                request.user.rol_actual = rol_sesion
            else:
                # fallback: primer rol
                rol_usuario = getattr(request.user, 'roles', None)
                if rol_usuario and rol_usuario.first():
                    request.user.rol_actual = rol_usuario.first().rol.nombre
                else:
                    request.user.rol_actual = None
