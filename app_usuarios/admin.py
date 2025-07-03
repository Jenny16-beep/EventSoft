# app_usuarios/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario

class UsuarioAdmin(UserAdmin):
    
    list_display = ('username', 'email', 'rol', 'documento', 'telefono', 'is_staff', 'is_active')
    list_filter = ('rol', 'is_staff', 'is_active', 'is_superuser')
    search_fields = ('username', 'email', 'documento', 'telefono')

   
    list_editable = ('rol', 'is_active')

    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Información personal', {'fields': ('first_name', 'last_name', 'email', 'telefono', 'documento', 'rol')}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Fechas importantes', {'fields': ('last_login', 'date_joined')}),
    )

    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'rol', 'documento', 'telefono', 'is_active', 'is_staff', 'is_superuser')}
        ),
    )

    ordering = ('username',)

admin.site.register(Usuario, UsuarioAdmin)