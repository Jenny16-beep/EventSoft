from django.db import models
from app_administradores.models import AdministradorEvento
from app_areas.models import Categoria

class Evento(models.Model):
    eve_id = models.AutoField(primary_key=True)
    eve_nombre = models.CharField(max_length=100)
    eve_descripcion = models.CharField(max_length=400)
    eve_ciudad = models.CharField(max_length=45)
    eve_lugar = models.CharField(max_length=45)
    eve_fecha_inicio = models.DateField()
    eve_fecha_fin = models.DateField()
    eve_estado = models.CharField(max_length=45)
    eve_imagen = models.ImageField(upload_to='eventos/imagenes/', null=True, blank=True)
    eve_capacidad = models.IntegerField()
    eve_tienecosto = models.CharField(max_length=2)
    eve_administrador_fk = models.ForeignKey(AdministradorEvento, on_delete=models.CASCADE, related_name='eventos')
    eve_programacion = models.FileField(upload_to='eventos/programaciones/', null=True, blank=True)
    eve_memorias = models.FileField(upload_to='eventos/memorias/', null=True, blank=True)

class EventoCategoria(models.Model):
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE)
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE)

    class Meta:
        unique_together = (('evento', 'categoria'),)


class ConfiguracionCertificado(models.Model):
    TIPO_CHOICES = [
        ('asistencia', 'Asistencia'),
        ('participacion', 'Participación'),
        ('evaluador', 'Evaluador'),
        ('premiacion', 'Premiación'),
    ]
    
    PLANTILLA_CHOICES = [
        ('elegante', 'Elegante'),
        ('moderno', 'Moderno'),
        ('clasico', 'Clásico'),
    ]
    
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name='configuraciones_certificado')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    plantilla = models.CharField(max_length=20, choices=PLANTILLA_CHOICES, default='elegante')
    titulo = models.CharField(max_length=200, default='Certificado')
    cuerpo = models.TextField(help_text='Puedes usar {nombre}, {evento}, {fecha}, etc.')
    firma = models.ImageField(upload_to='certificados/firmas/', null=True, blank=True)
    logo = models.ImageField(upload_to='certificados/logos/', null=True, blank=True)
    fecha_emision = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = (('evento', 'tipo'),)

    def __str__(self):
        return f"{self.evento.eve_nombre} - {self.get_tipo_display()}"
