# Imagen base de Python
FROM python:3.11-slim

# Variables de entorno para Django
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Carpeta de trabajo dentro del contenedor
WORKDIR /app

# Instalar dependencias de sistema (necesarias para MySQL)
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalarlas
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del proyecto
COPY . .

# Dar permisos al entrypoint
RUN chmod +x ./entrypoint.sh

# Exponer puerto (Render usa $PORT)
EXPOSE 8000

# Comando de arranque
CMD ["./entrypoint.sh"]
