import uuid
from django.utils import timezone
from django.db import models
from app_usuarios.models import Usuario
class AdministradorEvento(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, null=True, blank=True, related_name='administrador')

    def __str__(self):
        return f"{self.usuario.username}"
    
class CodigoInvitacionAdminEvento(models.Model):
    ESTADOS = [
        ('activo', 'Activo'),
        ('usado', 'Usado'),
        ('expirado', 'Expirado'),
        ('suspendido', 'Suspendido'),
        ('cancelado', 'Cancelado'),
    ]
    codigo = models.CharField(max_length=32, unique=True, default=uuid.uuid4, editable=False)
    email_destino = models.EmailField()
    limite_eventos = models.PositiveIntegerField(default=1)
    fecha_creacion = models.DateTimeField(default=timezone.now)
    fecha_expiracion = models.DateTimeField()
    fecha_uso = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=12, choices=ESTADOS, default='activo')
    tiempo_limite_creacion = models.DateTimeField(null=True, blank=True)
    usuario_asignado = models.ForeignKey(Usuario, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"Código {self.codigo} para {self.email_destino} ({self.estado})"

class CodigoInvitacionEvento(models.Model):
    """Modelo para códigos de invitación de evaluadores y participantes a eventos específicos"""
    ESTADOS = [
        ('activo', 'Activo'),
        ('usado', 'Usado'),
        ('expirado', 'Expirado'),
        ('cancelado', 'Cancelado'),
    ]
    
    TIPOS = [
        ('evaluador', 'Evaluador'),
        ('participante', 'Participante'),
    ]
    
    codigo = models.CharField(max_length=32, unique=True, editable=False)
    email_destino = models.EmailField()
    evento = models.ForeignKey('app_eventos.Evento', on_delete=models.CASCADE, related_name='codigos_invitacion')
    tipo = models.CharField(max_length=12, choices=TIPOS)
    estado = models.CharField(max_length=12, choices=ESTADOS, default='activo')
    fecha_creacion = models.DateTimeField(default=timezone.now)
    fecha_uso = models.DateTimeField(null=True, blank=True)
    administrador_creador = models.ForeignKey(AdministradorEvento, on_delete=models.CASCADE, related_name='codigos_creados')
    
    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = str(uuid.uuid4()).replace('-', '')[:16]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Código {self.codigo} - {self.evento.eve_nombre} ({self.get_tipo_display()}) - {self.email_destino}"
    
    class Meta:
        verbose_name = "Código de Invitación a Evento"
        verbose_name_plural = "Códigos de Invitación a Eventos"