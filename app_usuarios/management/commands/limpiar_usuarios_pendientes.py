from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from app_usuarios.models import Usuario, RolUsuario
from app_asistentes.models import Asistente, AsistenteEvento
from app_participantes.models import Participante, ParticipanteEvento
from app_evaluadores.models import Evaluador, EvaluadorEvento

class Command(BaseCommand):
    help = 'Elimina usuarios inactivos y sus relaciones después de X horas (expiración de links)'

    def handle(self, *args, **kwargs):
        expiracion = timezone.now() - timedelta(minutes=2)
        eliminados = 0
        # 1. Limpiar AsistenteEvento
        for asistencia in AsistenteEvento.objects.filter(confirmado=False, asi_eve_fecha_hora__lt=expiracion):
            asistente = asistencia.asistente
            usuario = asistente.usuario
            asistencia.delete()
            # Si el asistente no tiene más eventos, borrar el objeto y su RolUsuario
            if not AsistenteEvento.objects.filter(asistente=asistente).exists():
                asistente.delete()
                RolUsuario.objects.filter(usuario=usuario, rol__nombre__iexact='asistente').delete()
                # Si el usuario no tiene más roles y está inactivo, eliminar usuario
                tiene_participante = hasattr(usuario, 'participante') and ParticipanteEvento.objects.filter(participante=usuario.participante).exists()
                tiene_evaluador = hasattr(usuario, 'evaluador') and EvaluadorEvento.objects.filter(evaluador=usuario.evaluador).exists()
                if not (tiene_participante or tiene_evaluador) and not usuario.is_active:
                    usuario.delete()
                    eliminados += 1

        # 2. Limpiar ParticipanteEvento
        for insc in ParticipanteEvento.objects.filter(confirmado=False, par_eve_fecha_hora__lt=expiracion):
            participante = insc.participante
            usuario = participante.usuario
            insc.delete()
            if not ParticipanteEvento.objects.filter(participante=participante).exists():
                participante.delete()
                RolUsuario.objects.filter(usuario=usuario, rol__nombre__iexact='participante').delete()
                tiene_asistente = hasattr(usuario, 'asistente') and AsistenteEvento.objects.filter(asistente=usuario.asistente).exists()
                tiene_evaluador = hasattr(usuario, 'evaluador') and EvaluadorEvento.objects.filter(evaluador=usuario.evaluador).exists()
                if not (tiene_asistente or tiene_evaluador) and not usuario.is_active:
                    usuario.delete()
                    eliminados += 1

        # 3. Limpiar EvaluadorEvento
        for insc in EvaluadorEvento.objects.filter(confirmado=False, eva_eve_fecha_hora__lt=expiracion):
            evaluador = insc.evaluador
            usuario = evaluador.usuario
            insc.delete()
            if not EvaluadorEvento.objects.filter(evaluador=evaluador).exists():
                evaluador.delete()
                RolUsuario.objects.filter(usuario=usuario, rol__nombre__iexact='evaluador').delete()
                tiene_asistente = hasattr(usuario, 'asistente') and AsistenteEvento.objects.filter(asistente=usuario.asistente).exists()
                tiene_participante = hasattr(usuario, 'participante') and ParticipanteEvento.objects.filter(participante=usuario.participante).exists()
                if not (tiene_asistente or tiene_participante) and not usuario.is_active:
                    usuario.delete()
                    eliminados += 1

        self.stdout.write(self.style.SUCCESS(f'Registros evento-rol no confirmados y usuarios eliminados: {eliminados}'))
