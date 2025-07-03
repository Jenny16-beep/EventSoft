from django.db import models
from app_usuarios.models import Usuario

class AdministradorEvento(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, null=True, blank=True, related_name='administrador')

    def __str__(self):
        return f"{self.usuario.username}"
    