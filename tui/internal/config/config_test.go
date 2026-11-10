package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestEnvOverridesFile(t *testing.T) {
	cfg := Config{APIURL: defaultAPI, SiteURL: defaultSite, Theme: "auto"}
	apply(&cfg, Config{APIURL: "http://localhost:8000"})
	apply(&cfg, fromEnv(func(key string) string {
		if key == "FPLBUD_API_URL" {
			return "https://example.test"
		}
		return ""
	}, true))
	if cfg.APIURL != "https://example.test" {
		t.Fatal(cfg.APIURL)
	}
}

func TestLocalWebEnvDoesNotMoveTheAPI(t *testing.T) {
	cfg := Config{APIURL: defaultAPI}
	apply(&cfg, fromEnv(func(key string) string {
		if key == "NEXT_PUBLIC_API_URL" {
			return "http://localhost:8000"
		}
		return ""
	}, false))
	if cfg.APIURL != "https://fplbud.onrender.com" {
		t.Fatal(cfg.APIURL)
	}
	dir := t.TempDir()
	path := filepath.Join(dir, ".env")
	body := "NEXT_PUBLIC_API_URL=http://localhost:8000\nNEXT_PUBLIC_SUPABASE_URL=https://example.supabase.co\n"
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatal(err)
	}
	got := fromDotenv(path)
	if got.APIURL != "" || got.SupabaseURL != "https://example.supabase.co" {
		t.Fatalf("%+v", got)
	}
}

func TestLoadUsesDeployedAPI(t *testing.T) {
	cfg, err := Load()
	if err != nil {
		t.Fatal(err)
	}
	if os.Getenv("FPLBUD_API_URL") == "" && cfg.APIURL != defaultAPI {
		t.Fatal(cfg.APIURL)
	}
}

func TestUnquote(t *testing.T) {
	if unquote(`"abc"`) != "abc" || unquote("abc") != "abc" {
		t.Fatal(unquote(`"abc"`))
	}
}
