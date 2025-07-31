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