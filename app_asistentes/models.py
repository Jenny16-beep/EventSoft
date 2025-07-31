from django.db import models
from app_eventos.models import Evento
from app_usuarios.models import Usuario

class Asistente(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='asistente')

    def __str__(self):
        return f"{self.usuario.username}"

class AsistenteEvento(models.Model):
    asistente = models.ForeignKey(Asistente, on_delete=models.CASCADE)
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE)
    asi_eve_fecha_hora = models.DateTimeField()
    asi_eve_estado = models.CharField(max_length=45)
    asi_eve_soporte = models.FileField(upload_to='asistentes/soportes/', null=True, blank=True)
    asi_eve_qr = models.ImageField(upload_to='asistentes/qr/', null=True, blank=True)
    confirmado = models.BooleanField(default=False)

    class Meta:
        unique_together = (('asistente', 'evento'),)
