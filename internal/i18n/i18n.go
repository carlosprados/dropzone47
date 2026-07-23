// Package i18n provides user-facing message translation for the bot.
// Templates use fmt positional verbs; callers pass arguments in the documented order.
package i18n

import (
	"fmt"
	"strings"
)

// Lang is a supported language code.
type Lang string

const (
	EN Lang = "en"
	ES Lang = "es"
)

// messages maps a language to its catalog. All languages MUST share the same keys
// (enforced by a test). Logs and errors stay in English; only these reach users.
var messages = map[Lang]map[string]string{
	EN: {
		"welcome":           "Hi! I can download YouTube content for you. Send me a URL and choose audio or video.",
		"invalid_url":       "⚠️ Please send a valid http(s) URL.",
		"fetching_info":     "🔍 Fetching video info…",
		"info_failed":       "⚠️ Failed to fetch video info.",
		"choose":            "Title: %s\nDuration: %s\nWhat would you like to download?", // title, duration
		"btn_audio":         "🎵 Audio",
		"btn_video":         "🎬 Video",
		"rate_limited":      "⚠️ Rate limit reached. Try again in about %d min.", // minutes
		"session_not_found": "⚠️ Session not found. Please send the URL again.",
		"already_running":   "⚠️ A download is already in progress. Use /cancel to stop it.",
		"queued":            "⏳ Queued: '%s' as %s…",           // title, choice
		"downloading":       "🔽 Downloading '%s' as %s…",       // title, choice
		"video_too_large":   "⚠️ Video too large; trying %dp…", // height
		"audio_too_large":   "⚠️ Audio too large; trying lower bitrate…",
		"processing":        "📦 Processing %s…",              // label
		"progress":          "⬇️ %s: %d%%",                   // label, percent
		"completed":         "✅ Download completed for '%s'", // title
		"canceled":          "⛔ Download canceled by user",
		"error":             "⚠️ Error: %s",             // error
		"send_failed":       "⚠️ Could not send %s: %s", // name, error
		"no_downloads":      "You have no recorded downloads.",
		"downloads_status":  "Your downloads:\n- %s [%s] → %s\nCreated: %s\nUpdated: %s", // title, choice, status, created, updated
		"nothing_to_cancel": "There are no active downloads to cancel.",
		"cancel_requested":  "Cancellation requested. ⏹️",
		"nothing_to_clear":  "There are no downloads to clear.",
		"cleared":           "Cleanup complete. Files removed: %d", // removed
	},
	ES: {
		"welcome":           "¡Hola! Puedo descargar contenido de YouTube. Envíame una URL y elige audio o vídeo.",
		"invalid_url":       "⚠️ Envía una URL http(s) válida.",
		"fetching_info":     "🔍 Obteniendo información del vídeo…",
		"info_failed":       "⚠️ No se pudo obtener la información del vídeo.",
		"choose":            "Título: %s\nDuración: %s\n¿Qué quieres descargar?",
		"btn_audio":         "🎵 Audio",
		"btn_video":         "🎬 Vídeo",
		"rate_limited":      "⚠️ Has alcanzado el límite. Inténtalo de nuevo en unos %d min.",
		"session_not_found": "⚠️ Sesión no encontrada. Envía la URL de nuevo.",
		"already_running":   "⚠️ Ya hay una descarga en curso. Usa /cancel para detenerla.",
		"queued":            "⏳ En cola: '%s' como %s…",
		"downloading":       "🔽 Descargando '%s' como %s…",
		"video_too_large":   "⚠️ Vídeo demasiado grande; probando %dp…",
		"audio_too_large":   "⚠️ Audio demasiado grande; probando menor bitrate…",
		"processing":        "📦 Procesando %s…",
		"progress":          "⬇️ %s: %d%%",
		"completed":         "✅ Descarga completada de '%s'",
		"canceled":          "⛔ Descarga cancelada por el usuario",
		"error":             "⚠️ Error: %s",
		"send_failed":       "⚠️ No se pudo enviar %s: %s",
		"no_downloads":      "No tienes descargas registradas.",
		"downloads_status":  "Tus descargas:\n- %s [%s] → %s\nCreada: %s\nActualizada: %s",
		"nothing_to_cancel": "No hay descargas activas que cancelar.",
		"cancel_requested":  "Cancelación solicitada. ⏹️",
		"nothing_to_clear":  "No hay descargas que limpiar.",
		"cleared":           "Limpieza completada. Ficheros eliminados: %d",
	},
}

// Translator renders messages for a fixed language.
type Translator struct{ lang Lang }

// New returns a Translator for lang, falling back to English for unknown languages.
func New(lang string) *Translator {
	l := Lang(strings.ToLower(strings.TrimSpace(lang)))
	if _, ok := messages[l]; !ok {
		l = EN
	}
	return &Translator{lang: l}
}

// Lang returns the resolved language code.
func (t *Translator) Lang() Lang { return t.lang }

// T renders key with the given args, falling back to English then to the raw key.
func (t *Translator) T(key string, args ...any) string {
	tmpl, ok := messages[t.lang][key]
	if !ok {
		tmpl, ok = messages[EN][key]
	}
	if !ok {
		return key
	}
	if len(args) == 0 {
		return tmpl
	}
	return fmt.Sprintf(tmpl, args...)
}

// Languages returns the supported language codes.
func Languages() []Lang { return []Lang{EN, ES} }

// catalog exposes the raw maps for tests.
func catalog() map[Lang]map[string]string { return messages }
