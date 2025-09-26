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