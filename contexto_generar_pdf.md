# Generación de PDFs en Django con WeasyPrint

## ¿Por qué usar HTML para generar PDFs?

Una de las maneras más eficientes de generar archivos PDF en aplicaciones web es transformar plantillas HTML en archivos PDF. Esto permite reutilizar diseños visuales y aprovechar CSS para formatear el contenido.

---

## WeasyPrint

WeasyPrint es una biblioteca de Python que convierte documentos HTML y CSS en archivos PDF de alta calidad. Usa motores de renderizado similares a los de navegadores web para interpretar el HTML y el CSS.

### Instalación

```bash
pip install weasyprint
```

### Verificación

Después de instalar, puedes verificar la instalación ejecutando:

```bash
python -m weasyprint --info
```

Si ves errores relacionados con librerías faltantes, probablemente debas instalar GTK3 u otras dependencias gráficas.

#### Instalación de GTK en Windows

Puedes descargar el entorno de ejecución GTK desde:

[https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases)

Asegúrate de marcar la opción:

> Set up PATH environment variable to include GTK+

Luego vuelve a verificar:

```bash
python -m weasyprint --info
```

---

## Ejemplos de uso

### 1. Generar PDF desde una URL

```python
from weasyprint import HTML
from django.http import HttpResponse

def pdf_desde_url(request):
    HTML('https://automatizacioncaldas.blogspot.com/').write_pdf('tmp/automatizacion.pdf')
    return HttpResponse("Archivo generado exitosamente")
```

### 2. Generar PDF desde un string HTML (para descarga)

```python
def pdf_desde_string(request):
    html_content = '<h1>Hola, mundo!</h1>'
    pdf_file = HTML(string=html_content).write_pdf()
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="hola_mundo.pdf"'
    return response
```

### 3. Generar PDF desde una plantilla HTML (para previsualización)

**Plantilla: `templates/reglamento.html`**

```html
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reglamento Campeonato de Fútbol</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f2f2f2; color: #333; margin: 0; padding: 0; }
        header { background-color: #007B3A; color: white; padding: 20px 0; text-align: center; }
        main { max-width: 800px; margin: 40px auto; padding: 20px; background-color: white; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        h1, h2 { margin-top: 0; }
        ol { padding-left: 20px; }
        footer { text-align: center; padding: 20px; background-color: #ddd; margin-top: 40px; }
    </style>
</head>
<body>
    <header><h1>Reglamento del Campeonato de Fútbol 2025</h1></header>
    <main>
        <h2>Normas Generales</h2>
        <ol>
            <li>El campeonato se jugará en formato todos contra todos.</li>
            <li>Los partidos tendrán una duración de 2 tiempos de 25 minutos cada uno.</li>
            <li>Cada equipo debe presentar al menos 7 jugadores para iniciar el partido.</li>
            <li>El equipo que no se presente perderá el partido por 3-0.</li>
            <li>No se permiten jugadores no inscritos en la planilla oficial.</li>
            <li>Las tarjetas amarillas acumuladas en 3 partidos generarán una fecha de suspensión.</li>
            <li>La violencia verbal o física será sancionada con la expulsión del torneo.</li>
            <li>El equipo con más puntos al final será el campeón. En caso de empate, se usará diferencia de goles.</li>
        </ol>
    </main>
    <footer>&copy; 2025 Comité Organizador del Campeonato</footer>
</body>
</html>
```

**Vista:**

```python
def pdf_desde_plantilla(request):
    pdf_file = HTML(filename='templates/reglamento.html').write_pdf()
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="reglamento.pdf"'
    return response
```

---

## Crear PDF con datos de un modelo Django

### Modelo `Producto`

```python
from django.db import models

class Producto(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    precio = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.nombre
```

### Plantilla `listado_productos.html`

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Listado de Productos</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { text-align: center; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #ccc; padding: 10px; text-align: left; }
        th { background-color: #f0f0f0; }
    </style>
</head>
<body>
    <h1>Listado de Productos</h1>
    <table>
        <thead>
            <tr>
                <th>Nombre</th>
                <th>Descripción</th>
                <th>Precio</th>
            </tr>
        </thead>
        <tbody>
            {% for producto in productos %}
            <tr>
                <td>{{ producto.nombre }}</td>
                <td>{{ producto.descripcion }}</td>
                <td>${{ producto.precio }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
```

### Vista

```python
from weasyprint import HTML
from django.template.loader import render_to_string
from django.http import HttpResponse
from .models import Producto

def productos(request):
    productos = Producto.objects.all()
    html_string = render_to_string('app_productos/listado_productos.html', {'productos': productos})
    pdf_bytes = HTML(string=html_string).write_pdf()
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="productos.pdf"'
    return response
```
