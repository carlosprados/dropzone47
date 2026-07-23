package i18n

import "testing"

func TestTFormatsAndFallsBack(t *testing.T) {
	en := New("en")
	if got := en.T("downloading", "Song", "audio"); got != "🔽 Downloading 'Song' as audio…" {
		t.Fatalf("format: %q", got)
	}
	if got := en.T("does_not_exist"); got != "does_not_exist" {
		t.Fatalf("unknown key: %q", got)
	}
}

func TestUnknownLanguageFallsBackToEnglish(t *testing.T) {
	fr := New("fr")
	if fr.Lang() != EN {
		t.Fatalf("expected EN fallback, got %s", fr.Lang())
	}
	if fr.T("btn_audio") != messages[EN]["btn_audio"] {
		t.Fatal("should use English catalog")
	}
}

func TestSpanish(t *testing.T) {
	es := New("ES") // case-insensitive
	if es.Lang() != ES {
		t.Fatalf("got %s", es.Lang())
	}
	if es.T("cancel_requested") != "Cancelación solicitada. ⏹️" {
		t.Fatalf("es: %q", es.T("cancel_requested"))
	}
}

func TestCatalogsShareKeys(t *testing.T) {
	c := catalog()
	en, es := c[EN], c[ES]
	if len(en) != len(es) {
		t.Fatalf("key count mismatch: en=%d es=%d", len(en), len(es))
	}
	for k := range en {
		if _, ok := es[k]; !ok {
			t.Fatalf("missing es key: %s", k)
		}
	}
}
