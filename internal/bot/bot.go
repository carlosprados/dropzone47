// Package bot wires the Telegram handlers, the concurrency queue, rate limiting,
// sessions and the download backends together.
package bot

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	tgbot "github.com/go-telegram/bot"
	"github.com/go-telegram/bot/models"

	"github.com/carlosprados/dropzone47/internal/config"
	"github.com/carlosprados/dropzone47/internal/download"
	"github.com/carlosprados/dropzone47/internal/i18n"
	"github.com/carlosprados/dropzone47/internal/ratelimit"
	"github.com/carlosprados/dropzone47/internal/session"
	"github.com/carlosprados/dropzone47/internal/util"
)

type task struct {
	status    string // queued | downloading | sending | done | error | canceled
	choice    string
	title     string
	id        string
	files     []string
	cancel    context.CancelFunc
	createdAt time.Time
	updatedAt time.Time
}

func (t *task) active() bool {
	return t.status == "queued" || t.status == "downloading" || t.status == "sending"
}

// Bot is the running Telegram bot.
type Bot struct {
	cfg     config.Config
	tr      *i18n.Translator
	dl      download.Downloader
	store   *session.Store
	limiter *ratelimit.Limiter
	slots   chan struct{}
	log     *slog.Logger

	mu    sync.Mutex
	tasks map[int64]*task
}

// New builds a Bot from its dependencies.
func New(cfg config.Config, dl download.Downloader, store *session.Store, log *slog.Logger) *Bot {
	return &Bot{
		cfg:     cfg,
		tr:      i18n.New(cfg.Lang),
		dl:      dl,
		store:   store,
		limiter: ratelimit.New(cfg.RateLimitMax, cfg.RateLimitWindow),
		slots:   make(chan struct{}, cfg.MaxConcurrentDownloads),
		log:     log,
		tasks:   make(map[int64]*task),
	}
}

// Run registers handlers and blocks on long polling until ctx is canceled.
func (b *Bot) Run(ctx context.Context) error {
	opts := []tgbot.Option{
		tgbot.WithDefaultHandler(b.onText),
		tgbot.WithCallbackQueryDataHandler("", tgbot.MatchTypePrefix, b.onCallback),
	}
	api, err := tgbot.New(b.cfg.TelegramToken, opts...)
	if err != nil {
		return err
	}
	api.RegisterHandler(tgbot.HandlerTypeMessageText, "/start", tgbot.MatchTypeExact, b.cmdStart)
	api.RegisterHandler(tgbot.HandlerTypeMessageText, "/downloads", tgbot.MatchTypeExact, b.cmdDownloads)
	api.RegisterHandler(tgbot.HandlerTypeMessageText, "/cancel", tgbot.MatchTypeExact, b.cmdCancel)
	api.RegisterHandler(tgbot.HandlerTypeMessageText, "/clear_downloads", tgbot.MatchTypeExact, b.cmdClear)

	b.log.Info("bot started", "downloader", b.dl.Name(), "lang", string(b.tr.Lang()))
	api.Start(ctx)
	return nil
}

func (b *Bot) cmdStart(ctx context.Context, api *tgbot.Bot, update *models.Update) {
	if update.Message == nil {
		return
	}
	b.send(ctx, api, update.Message.Chat.ID, b.tr.T("welcome"))
}

func (b *Bot) onText(ctx context.Context, api *tgbot.Bot, update *models.Update) {
	msg := update.Message
	if msg == nil || msg.From == nil {
		return
	}
	url := strings.TrimSpace(msg.Text)
	if strings.HasPrefix(url, "/") {
		return // unknown command
	}
	userID := msg.From.ID
	chatID := msg.Chat.ID

	if !util.IsValidURL(url) {
		b.send(ctx, api, chatID, b.tr.T("invalid_url"))
		return
	}
	b.send(ctx, api, chatID, b.tr.T("fetching_info"))

	infoCtx, cancel := context.WithTimeout(ctx, 60*time.Second)
	defer cancel()
	info, err := b.dl.FetchInfo(infoCtx, url)
	if err != nil || info.ID == "" {
		b.log.Warn("fetch info failed", "url", url, "err", err)
		b.send(ctx, api, chatID, b.tr.T("info_failed"))
		return
	}

	if err := b.store.Save(userID, session.Data{URL: url, Title: info.Title, ID: info.ID}); err != nil {
		b.log.Warn("save session failed", "user", userID, "err", err)
	}

	caption := b.tr.T("choose", info.Title, util.HumanizeDuration(info.DurationSec))
	kb := &models.InlineKeyboardMarkup{InlineKeyboard: [][]models.InlineKeyboardButton{
		{{Text: b.tr.T("btn_audio"), CallbackData: "audio"}},
		{{Text: b.tr.T("btn_video"), CallbackData: "video"}},
	}}
	if _, err := api.SendMessage(ctx, &tgbot.SendMessageParams{ChatID: chatID, Text: caption, ReplyMarkup: kb}); err != nil {
		b.log.Warn("send choices failed", "err", err)
	}
}

func (b *Bot) onCallback(ctx context.Context, api *tgbot.Bot, update *models.Update) {
	q := update.CallbackQuery
	_, _ = api.AnswerCallbackQuery(ctx, &tgbot.AnswerCallbackQueryParams{CallbackQueryID: q.ID})

	choice := q.Data
	if choice != "audio" && choice != "video" {
		return
	}
	if q.Message.Message == nil {
		return // inaccessible message
	}
	userID := q.From.ID
	chatID := q.Message.Message.Chat.ID
	messageID := q.Message.Message.ID

	sess, err := b.store.Load(userID)
	if err != nil || sess == nil {
		b.edit(ctx, api, chatID, messageID, b.tr.T("session_not_found"))
		return
	}

	b.mu.Lock()
	if t := b.tasks[userID]; t != nil && t.active() {
		b.mu.Unlock()
		b.send(ctx, api, chatID, b.tr.T("already_running"))
		return
	}
	if !b.limiter.Allow(userID) {
		b.mu.Unlock()
		mins := int(b.limiter.RetryAfter(userID).Minutes()) + 1
		b.send(ctx, api, chatID, b.tr.T("rate_limited", mins))
		return
	}
	dlCtx, cancel := context.WithCancel(context.Background())
	t := &task{
		status:    "queued",
		choice:    choice,
		title:     sess.Title,
		id:        sess.ID,
		cancel:    cancel,
		createdAt: time.Now(),
		updatedAt: time.Now(),
	}
	b.tasks[userID] = t
	b.mu.Unlock()

	b.edit(ctx, api, chatID, messageID, b.tr.T("queued", sess.Title, choice))
	go b.runDownload(dlCtx, api, userID, chatID, messageID, choice, *sess, t)
}

func (b *Bot) runDownload(ctx context.Context, api *tgbot.Bot, userID, chatID int64, messageID int, choice string, sess session.Data, t *task) {
	defer t.cancel()
	defer func() {
		if b.cfg.CleanupAfterSend {
			download.ForceRemove(t.files)
		}
		_ = b.store.Delete(userID)
	}()

	// Wait for a global download slot (the queue). Cancellation while waiting aborts.
	select {
	case b.slots <- struct{}{}:
		defer func() { <-b.slots }()
	case <-ctx.Done():
		b.setStatus(t, "canceled")
		b.edit(ctx, api, chatID, messageID, b.tr.T("canceled"))
		return
	}

	b.setStatus(t, "downloading")
	b.edit(ctx, api, chatID, messageID, b.tr.T("downloading", sess.Title, choice))

	destDir, err := util.UserDownloadDir(b.cfg.DownloadDir, userID)
	if err != nil {
		b.fail(ctx, api, t, chatID, messageID, err)
		return
	}

	req := download.Request{
		URL:          sess.URL,
		ID:           sess.ID,
		BaseName:     download.BuildBaseName(sess.Title, sess.ID),
		Format:       download.Format(choice),
		MaxHeight:    b.cfg.MaxHeight,
		AudioKbps:    b.cfg.AudioKbitrate,
		MaxMB:        b.cfg.TelegramMaxMB,
		HeightLadder: b.cfg.VideoHeightLadder,
		DestDir:      destDir,
	}

	res, err := b.dl.Fetch(ctx, req, b.progressFn(ctx, api, chatID, messageID))
	if err != nil {
		if ctx.Err() != nil {
			b.setStatus(t, "canceled")
			b.edit(ctx, api, chatID, messageID, b.tr.T("canceled"))
			return
		}
		b.fail(ctx, api, t, chatID, messageID, err)
		return
	}

	b.mu.Lock()
	t.files = res.Files
	t.status = "sending"
	t.updatedAt = time.Now()
	b.mu.Unlock()

	b.sendFiles(ctx, api, chatID, sess.Title, res.Files)
	b.setStatus(t, "done")
	b.edit(ctx, api, chatID, messageID, b.tr.T("completed", sess.Title))
}

// progressFn returns a throttled progress callback that edits the status message.
func (b *Bot) progressFn(ctx context.Context, api *tgbot.Bot, chatID int64, messageID int) download.ProgressFunc {
	var lastPct = -100
	var lastAt time.Time
	return func(p download.Progress) {
		switch p.Stage {
		case download.StageFallbackVid:
			b.send(ctx, api, chatID, b.tr.T("video_too_large", p.Height))
		case download.StageFallbackAud:
			b.send(ctx, api, chatID, b.tr.T("audio_too_large"))
		case download.StageProcessing:
			b.edit(ctx, api, chatID, messageID, b.tr.T("processing", p.Label))
		case download.StageDownloading:
			now := time.Now()
			if p.Percent < lastPct+5 && now.Sub(lastAt) < 2*time.Second {
				return
			}
			lastPct = p.Percent
			lastAt = now
			parts := []string{b.tr.T("progress", p.Label, p.Percent)}
			if p.SpeedBytes > 0 {
				parts = append(parts, util.SizeofFmt(p.SpeedBytes)+"/s")
			}
			if p.ETASeconds > 0 {
				parts = append(parts, fmt.Sprintf("ETA %ds", p.ETASeconds))
			}
			b.edit(ctx, api, chatID, messageID, strings.Join(parts, " • "))
		}
	}
}

func (b *Bot) sendFiles(ctx context.Context, api *tgbot.Bot, chatID int64, title string, files []string) {
	for _, path := range files {
		if err := b.sendOne(ctx, api, chatID, title, path); err != nil {
			b.log.Warn("send file failed", "path", path, "err", err)
			b.send(ctx, api, chatID, b.tr.T("send_failed", filepath.Base(path), err))
		}
	}
}

func (b *Bot) sendOne(ctx context.Context, api *tgbot.Bot, chatID int64, title, path string) error {
	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()
	name := filepath.Base(path)
	upload := &models.InputFileUpload{Filename: name, Data: f}
	lower := strings.ToLower(path)
	switch {
	case strings.HasSuffix(lower, ".mp3"):
		_, err = api.SendAudio(ctx, &tgbot.SendAudioParams{ChatID: chatID, Audio: upload, Title: title})
	case strings.HasSuffix(lower, ".mp4"), strings.HasSuffix(lower, ".mkv"),
		strings.HasSuffix(lower, ".webm"), strings.HasSuffix(lower, ".mov"):
		_, err = api.SendVideo(ctx, &tgbot.SendVideoParams{ChatID: chatID, Video: upload, SupportsStreaming: true})
	default:
		_, err = api.SendDocument(ctx, &tgbot.SendDocumentParams{ChatID: chatID, Document: upload})
	}
	return err
}

func (b *Bot) cmdDownloads(ctx context.Context, api *tgbot.Bot, update *models.Update) {
	if update.Message == nil {
		return
	}
	userID := update.Message.From.ID
	b.mu.Lock()
	t := b.tasks[userID]
	b.mu.Unlock()
	if t == nil {
		b.send(ctx, api, update.Message.Chat.ID, b.tr.T("no_downloads"))
		return
	}
	b.send(ctx, api, update.Message.Chat.ID, b.tr.T("downloads_status",
		t.title, t.choice, t.status,
		t.createdAt.UTC().Format(time.RFC3339), t.updatedAt.UTC().Format(time.RFC3339)))
}

func (b *Bot) cmdCancel(ctx context.Context, api *tgbot.Bot, update *models.Update) {
	if update.Message == nil {
		return
	}
	userID := update.Message.From.ID
	b.mu.Lock()
	t := b.tasks[userID]
	canCancel := t != nil && t.active()
	if canCancel {
		t.cancel()
	}
	b.mu.Unlock()
	if !canCancel {
		b.send(ctx, api, update.Message.Chat.ID, b.tr.T("nothing_to_cancel"))
		return
	}
	b.send(ctx, api, update.Message.Chat.ID, b.tr.T("cancel_requested"))
}

func (b *Bot) cmdClear(ctx context.Context, api *tgbot.Bot, update *models.Update) {
	if update.Message == nil {
		return
	}
	userID := update.Message.From.ID
	chatID := update.Message.Chat.ID
	b.mu.Lock()
	t := b.tasks[userID]
	b.mu.Unlock()
	if t == nil {
		b.send(ctx, api, chatID, b.tr.T("nothing_to_clear"))
		return
	}
	destDir, err := util.UserDownloadDir(b.cfg.DownloadDir, userID)
	removed := 0
	if err == nil && t.id != "" {
		for _, p := range download.FindOutputFiles(destDir, t.id) {
			if os.Remove(p) == nil {
				removed++
			}
		}
	}
	b.mu.Lock()
	t.files = nil
	b.mu.Unlock()
	b.send(ctx, api, chatID, b.tr.T("cleared", removed))
}

// --- helpers ---

func (b *Bot) setStatus(t *task, status string) {
	b.mu.Lock()
	t.status = status
	t.updatedAt = time.Now()
	b.mu.Unlock()
}

func (b *Bot) fail(ctx context.Context, api *tgbot.Bot, t *task, chatID int64, messageID int, err error) {
	b.log.Warn("download failed", "err", err)
	b.setStatus(t, "error")
	b.edit(ctx, api, chatID, messageID, b.tr.T("error", err.Error()))
}

func (b *Bot) send(ctx context.Context, api *tgbot.Bot, chatID int64, text string) {
	if _, err := api.SendMessage(ctx, &tgbot.SendMessageParams{ChatID: chatID, Text: text}); err != nil {
		b.log.Debug("send message failed", "err", err)
	}
}

func (b *Bot) edit(ctx context.Context, api *tgbot.Bot, chatID int64, messageID int, text string) {
	_, err := api.EditMessageText(ctx, &tgbot.EditMessageTextParams{ChatID: chatID, MessageID: messageID, Text: text})
	if err != nil {
		b.send(ctx, api, chatID, text)
	}
}
