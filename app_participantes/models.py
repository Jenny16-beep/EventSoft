from django.db import models
from app_eventos.models import Evento
from app_usuarios.models import Usuario

class Participante(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='participante')

    def __str__(self):
        return f"{self.usuario.username}"

class Proyecto(models.Model):
    evento = models.ForeignKey('app_eventos.Evento', on_delete=models.CASCADE, related_name="proyectos")
    titulo = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True, null=True)
    archivo = models.FileField(upload_to="proyectos/", blank=True, null=True)
    fecha_subida = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=[("Pendiente", "Pendiente"), ("Aprobado", "Aprobado"), ("Rechazado", "Rechazado")], default="Pendiente")
    pro_valor = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.titulo} ({self.evento.eve_nombre})"
    
class ParticipanteEvento(models.Model):
    participante = models.ForeignKey(Participante, on_delete=models.CASCADE)
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE)
    par_eve_fecha_hora = models.DateTimeField()
    par_eve_documentos = models.FileField(upload_to='participantes/documentos/', null=True, blank=True)
    par_eve_estado = models.CharField(max_length=45)
    par_eve_qr = models.ImageField(upload_to='participantes/qr/', null=True, blank=True)
    par_eve_valor = models.FloatField(null=True, blank=True)
    confirmado = models.BooleanField(default=False)
    codigo = models.CharField(max_length=20, blank=True, null=True, help_text="Código de proyecto grupal")
    proyecto = models.ForeignKey('Proyecto', on_delete=models.SET_NULL, null=True, blank=True, related_name="participantes")

    class Meta:
        unique_together = (('participante', 'evento'),)