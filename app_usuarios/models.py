from django.contrib.auth.models import AbstractUser
from django.db import models

class Usuario(AbstractUser):
    email = models.EmailField(unique=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    documento = models.CharField(max_length=20)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return f"{self.username}"

    @property
    def rol_principal(self):
        rol_usuario = self.roles.first()
        if rol_usuario:
            return rol_usuario.rol.nombre
        return "Sin rol"

    @property
    def rol_descripcion(self):
        rol_usuario = self.roles.first()
        if rol_usuario:
            return rol_usuario.rol.descripcion
        return "Sin descripción"
    
class Rol(models.Model):
    nombre = models.CharField(max_length=30, unique=True)
    descripcion = models.TextField(blank=True)

    def __str__(self):
        return self.nombre

class RolUsuario(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='roles')
    rol = models.ForeignKey(Rol, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = (('usuario', 'rol'),)

    def __str__(self):
        return f"{self.usuario.username} - {self.rol.nombre}"