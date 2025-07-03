from datetime import date
from django.utils.deprecation import MiddlewareMixin
from app_eventos.models import Evento

class ActualizarEventosFinalizadosMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if not hasattr(request, '_eventos_actualizados'):
            hoy = date.today()
            eventos = Evento.objects.filter(
                eve_fecha_fin__lt=hoy,
                eve_estado__in=['Aprobado', 'Inscripciones Cerradas', 'Pendiente']
            )

            if eventos.exists():
                eventos.update(eve_estado='Finalizado')

            request._eventos_actualizados = True
