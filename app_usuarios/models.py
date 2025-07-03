from django.contrib.auth.models import AbstractUser
from django.db import models

class Usuario(AbstractUser):
    ROL_CHOICES = [
        ('superadmin', 'SuperAdmin'),
        ('administrador_evento', 'Administrador Evento'),
        ('evaluador', 'Evaluador'),
        ('participante', 'Participante'),
        ('asistente', 'Asistente'),
    ]

    rol = models.CharField(max_length=30, choices=ROL_CHOICES)
    email = models.EmailField(unique=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    documento = models.CharField(max_length=20)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS= ['username']

    def __str__(self):
        return f"{self.username} ({self.rol})"