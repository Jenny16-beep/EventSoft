# 🧠 Contexto del Backend Django - Sistema de Eventos

Este documento contiene el modelo de datos completo del sistema, distribuido por apps, incluyendo clases, relaciones, llaves foráneas, y la configuración del panel de administración en Django.

---

## 📦 App: `areas/models.py`

```python
from django.db import models

class Area(models.Model):
    are_codigo = models.AutoField(primary_key=True)
    are_nombre = models.CharField(max_length=45)
    are_descripcion = models.CharField(max_length=400)

class Categoria(models.Model):
    cat_codigo = models.AutoField(primary_key=True)
    cat_nombre = models.CharField(max_length=45)
    cat_descripcion = models.CharField(max_length=400)
    cat_area_fk = models.ForeignKey(Area, on_delete=models.CASCADE, related_name='categorias')


📦 App: administradores/models.py

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

    

📦 App: eventos/models.py

from django.db import models
from administradores.models import AdministradorEvento
from areas.models import Categoria

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
    eve_informacion_tecnica = models.FileField(upload_to='eventos/informacion_tecnica/', null=True, blank=True)

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
        ('premiacion', 'Premiacion'),
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


📦 App: asistentes/models.py

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


📦 App: participantes/models.py

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


📦 App: evaluadores/models.py

from django.db import models
from app_eventos.models import Evento
from app_participantes.models import Participante
from app_usuarios.models import Usuario

class Evaluador(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='evaluador')

    def __str__(self):
        return f"{self.usuario.username}"

class EvaluadorEvento(models.Model):
    evaluador = models.ForeignKey(Evaluador, on_delete=models.CASCADE)
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE)
    eva_eve_documentos = models.FileField(upload_to='evaluadores/documentos/', null=True, blank=True)
    eva_eve_fecha_hora = models.DateTimeField()
    eva_eve_estado = models.CharField(max_length=45)
    eva_eve_qr = models.ImageField(upload_to='evaluadores/qr/', null=True, blank=True)
    confirmado = models.BooleanField(default=False)

    class Meta:
        unique_together = (('evaluador', 'evento'),)

    def __str__(self):
        return f"{self.evaluador.get_full_name()} - {self.evento.eve_nombre}"

class Criterio(models.Model):
    cri_id = models.AutoField(primary_key=True)
    cri_descripcion = models.CharField(max_length=100)
    cri_peso = models.FloatField()
    cri_evento_fk = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name='criterios')

class Calificacion(models.Model):
    evaluador = models.ForeignKey(Evaluador, on_delete=models.CASCADE)
    criterio = models.ForeignKey(Criterio, on_delete=models.CASCADE)
    participante = models.ForeignKey(Participante, on_delete=models.CASCADE)
    cal_valor = models.IntegerField()
    cal_observacion = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        unique_together = (('evaluador', 'criterio', 'participante'),)


📦 App: usuarios/models.py

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


⚙️ Configuración del Admin (usuarios/admin.py)

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, Rol, RolUsuario

class RolUsuarioInline(admin.TabularInline):
    model = RolUsuario
    extra = 1

class UsuarioAdmin(UserAdmin):
    list_display = ('username', 'email', 'documento', 'telefono', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active', 'is_superuser')
    search_fields = ('username', 'email', 'documento', 'telefono')
    list_editable = ('is_active',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Información personal', {'fields': ('first_name', 'last_name', 'email', 'telefono', 'documento')}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Fechas importantes', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'documento', 'telefono', 'is_active', 'is_staff', 'is_superuser')}
        ),
    )

    inlines = [RolUsuarioInline]
    ordering = ('username',)

admin.site.register(Usuario, UsuarioAdmin)
admin.site.register(Rol)
