Este documento da el contexto para trabajar el envio de notificaciones a travez de correo electronico

📩 Envío de Correos Electrónicos con Adjuntos en Django (HTML + Archivos)
🔧 1. Configuración en settings.py
Para habilitar el envío de correos mediante Gmail (u otro proveedor SMTP), configura los siguientes parámetros:

python
Copiar
Editar
# settings.py

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'daviladani888@gmail.com'
EMAIL_HOST_PASSWORD = 'hbqp ctml okwd wueg'
DEFAULT_FROM_EMAIL = 'daviladani888@gmail.com'

⚠️ Importante: EMAIL_HOST_PASSWORD es una App Password, generada desde la cuenta de Gmail (no es la contraseña real del correo).

💬 2. Plantilla de Formulario: enviar_correo.html
Formulario HTML para capturar los datos del destinatario, asunto, mensaje y archivo adjunto:

html
Copiar
Editar
<!-- templates/enviar_correo.html -->

<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Enviar correo con adjunto</title>
</head>
<body>
    <h2>Enviar correo con archivo adjunto</h2>

    {% if enviado %}
        <p style="color:green;">¡Correo enviado con éxito!</p>
    {% endif %}

    <form method="post" enctype="multipart/form-data">
        {% csrf_token %}
        <label>Para:</label><br>
        <input type="email" name="destinatario" required><br><br>

        <label>Asunto:</label><br>
        <input type="text" name="asunto" required><br><br>

        <label>Mensaje:</label><br>
        <textarea name="mensaje" rows="5" cols="40" required></textarea><br><br>

        <label>Archivo adjunto:</label><br>
        <input type="file" name="archivo" required><br><br>

        <button type="submit">Enviar</button>
    </form>
</body>
</html>
🧾 3. Plantilla HTML del correo: plantilla_email.html
Este archivo será renderizado como cuerpo del correo, usando variables:

html
Copiar
Editar
<!-- templates/plantilla_email.html -->

<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body>
    <h2>{{ asunto }}</h2>
    <p>{{ mensaje }}</p>
</body>
</html>
🧠 4. Lógica en la Vista: views.py
python
Copiar
Editar
# views.py

from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.shortcuts import render

def enviar_correo(request):
    if request.method == 'POST':
        destinatario = request.POST['destinatario']
        asunto = request.POST['asunto']
        mensaje = request.POST['mensaje']
        archivo = request.FILES.get('archivo')  # None si no hay archivo

        # Cuerpo HTML del correo, usando plantilla
        cuerpo_html = render_to_string('plantilla_email.html', {
            'asunto': asunto,
            'mensaje': mensaje,
        })

        # Construcción del correo
        email = EmailMessage(
            subject=asunto,
            body=cuerpo_html,
            from_email=None,  # Usará DEFAULT_FROM_EMAIL
            to=[destinatario],
        )
        email.content_subtype = 'html'  # Especifica que es HTML

        # Adjunta el archivo, si fue enviado
        if archivo:
            email.attach(archivo.name, archivo.read(), archivo.content_type)

        email.send()

        return render(request, 'enviar_correo.html', {'enviado': True})

    return render(request, 'enviar_correo.html')

# Todo lo mostrado en este documento es ejemplo para informar de como es que se busca trabajar, obviamente esto es base para el proyecto y se debe adecuar a las necesidades