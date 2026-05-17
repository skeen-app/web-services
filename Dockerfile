FROM python:3.11-slim

# Evita que Python genere archivos .pyc y asegura salida de logs limpia
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED True

# Seteamos el PATH de Python a la raíz de la app
ENV PYTHONPATH=/app

WORKDIR /app

# Primero instalamos dependencias para optimizar caché
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos todo el proyecto
COPY . .

# --- EL TRUCO MAESTRO ---
# Creamos archivos __init__.py en src y todas sus subcarpetas 
# para forzar a Python a reconocerlos como paquetes.
RUN find src -type d -exec touch {}/__init__.py \;

# Exponemos el puerto de Cloud Run
EXPOSE 8080

# Ejecutamos uvicorn como módulo para que resuelva mejor los paths internos
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]