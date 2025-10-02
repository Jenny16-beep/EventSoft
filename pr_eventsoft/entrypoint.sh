#!/bin/bash
set -e

# Puerto (Render inyecta PORT automáticamente)
PORT=${PORT:-10000}

echo "▶️ Ejecutando migraciones..."
MAX_RETRIES=12
i=0
until python manage.py migrate --noinput; do
  i=$((i+1))
  echo "⏳ Intento $i/$MAX_RETRIES: la BD aún no está lista. Esperando 3s..."
  sleep 3
  if [ $i -ge $MAX_RETRIES ]; then
    echo "❌ ERROR: No se pudo conectar a la base de datos después de $MAX_RETRIES intentos."
    exit 1
  fi
done

echo "▶️ Ejecutando collectstatic..."
python manage.py collectstatic --noinput || echo "⚠️ collectstatic falló, pero seguimos."

echo "🚀 Arrancando Gunicorn..."
exec gunicorn pr_eventsoft.wsgi:application --bind 0.0.0.0:${PORT} --workers 3
