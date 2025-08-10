from django.db import models
from app_eventos.models import Evento
from app_usuarios.models import Usuario

class Participante(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='participante')

    def __str__(self):
        return f"{self.usuario.username}"
    

class ParticipanteEvento(models.Model):
    participante = models.ForeignKey(Participante, on_delete=models.CASCADE)
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE)
    par_eve_fecha_hora = models.DateTimeField()
    par_eve_documentos = models.FileField(upload_to='participantes/documentos/', null=True, blank=True)
    par_eve_estado = models.CharField(max_length=45)
    par_eve_qr = models.ImageField(upload_to='participantes/qr/', null=True, blank=True)
    par_eve_valor = models.FloatField(null=True, blank=True)
    confirmado = models.BooleanField(default=False)

    class Meta:
        unique_together = (('participante', 'evento'),)
