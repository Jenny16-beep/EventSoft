from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('cambiar-contrasena/', views.cambiar_contrasena, name='cambiar_contrasena'),
]

