# dropzone47

Bot de Telegram para descargar contenido de YouTube y enviar el audio/vídeo al chat con controles de tamaño, carpeta de descargas configurable, persistencia básica de sesión y progreso visible en el mensaje (porcentaje, velocidad y ETA), además de cancelación.

## Requisitos
- Python 3.11+
- FFmpeg instalado y disponible en `PATH` (necesario para fusionar vídeo y extraer audio)

## Configuración (.env)
Este proyecto carga variables desde un fichero `.env` usando `python-dotenv`.

1) Copia el ejemplo y edítalo:

```
cp .env.example .env
```

2) Completa al menos `TELEGRAM_BOT_TOKEN`.

Variables disponibles:
- `TELEGRAM_BOT_TOKEN`: token del bot de Telegram (obligatorio).
- `DOWNLOAD_DIR`: carpeta donde se guardan las descargas. Por defecto `./downloads`.
- `TELEGRAM_MAX_MB`: tamaño máximo de archivo a enviar en MB. Por defecto `1900`.
- `MAX_HEIGHT`: resolución máxima de vídeo (p. ej. `720`). Por defecto `720`.
- `AUDIO_KBITRATE`: bitrate de audio MP3 (kbps). Por defecto `128`.
- `SOCKET_TIMEOUT`: timeout de red para `yt-dlp` (s). Por defecto `30`.
- `YTDLP_RETRIES`: reintentos de descarga de `yt-dlp`. Por defecto `3`.
- `CLEANUP_AFTER_SEND`: si elimina los archivos tras enviarlos (`true`/`false`). En `.env.example` está en `false` para conservarlos.
- `SESSIONS_DB`: ruta base del fichero `shelve` para sesiones. Por defecto `./downloads/sessions`.

## Instalación y uso
1) Crea el bot con BotFather y copia el token.
2) Prepara el entorno:
- Con `uv` (recomendado si ya lo usas):
  - `uv sync`
- Con `pip`:
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -e .`

3) Configura el `.env` (ver sección anterior).
4) Ejecuta el bot:

```
python main.py
```

5) En Telegram, envía al bot una URL de YouTube. Verás título, duración y botones para elegir `audio`, `video` o `ambos`. El bot sube los ficheros al chat (no solo rutas) y usa nombres de archivo amigables.

### Comandos
- `/downloads`: muestra el estado de tu descarga actual/reciente.
- `/cancel`: cancela la descarga en curso (si la hay).
- `/clear_downloads`: elimina archivos descargados asociados a tu última descarga.

Durante la descarga verás actualizaciones periódicas del progreso en la leyenda del mensaje original (aprox. cada 5% o 2s, lo que ocurra antes).

## Notas
- El bot intenta mantener los archivos dentro del límite de tamaño configurado. Si un vídeo supera el límite, reintenta con menor resolución (p. ej. 480p). Para audio, reduce el bitrate si es necesario.
- Las sesiones se guardan de forma ligera en disco, lo que permite continuar tras reinicios simples. No está pensado para alta concurrencia/multiproceso.
- Para conservar los archivos localmente, usa `CLEANUP_AFTER_SEND=false`.

## Desarrollo
- Librerías principales: `python-telegram-bot 22.x`, `yt-dlp`, `python-dotenv`.
- Subida de ficheros: se abren en binario y se pasan como file handle a `send_audio`/`send_video`/`send_document` con `filename` explícito para forzar upload real y un nombre visible.
- Se usan `effective_message` y guards para evitar advertencias de Pyright con posibles `None` en `update.message`/`callback_query`.
