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