// Package config loads the public endpoints the TUI is allowed to know.
package config

import (
	"bufio"
	"bytes"
	"os"
	"path/filepath"
	"strings"

	"github.com/dannyboy-1412/FPLBud/tui/internal/version"
	"github.com/pelletier/go-toml/v2"
)

const (
	defaultAPI  = "https://fplbud.onrender.com"
	defaultSite = "https://fplbud.vercel.app"
)

// Config is everything the binary needs to reach Supabase and FastAPI.
type Config struct {
	APIURL          string
	SupabaseURL     string
	SupabaseAnonKey string
	SiteURL         string
	Theme           string
	Dir             string
}

type fileConfig struct {
	APIURL          string `toml:"api_url"`
	SupabaseURL     string `toml:"supabase_url"`
	SupabaseAnonKey string `toml:"supabase_anon_key"`
	SiteURL         string `toml:"site_url"`
	Theme           string `toml:"theme"`
}

// Load reads baked defaults, then config.toml, then public env vars.
func Load() (Config, error) {
	dir, err := os.UserConfigDir()
	if err != nil {
		dir = "."
	}
	dir = filepath.Join(dir, "fplbud")
	cfg := Config{
		APIURL:          first(version.APIURL, defaultAPI),
		SupabaseURL:     version.SupabaseURL,
		SupabaseAnonKey: version.SupabaseAnonKey,
		SiteURL:         defaultSite,
		Theme:           "auto",
		Dir:             dir,
	}
	apply(&cfg, fromDotenv(findDotenv()))
	apply(&cfg, fromFile(filepath.Join(dir, "config.toml")))
	apply(&cfg, fromEnv(os.Getenv, false))
	apply(&cfg, fromEnv(os.Getenv, true))
	return cfg, nil
}

func first(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return strings.TrimSpace(value)
		}
	}
	return ""
}

func apply(cfg *Config, next Config) {
	cfg.APIURL = first(next.APIURL, cfg.APIURL)
	cfg.SupabaseURL = first(next.SupabaseURL, cfg.SupabaseURL)
	cfg.SupabaseAnonKey = first(next.SupabaseAnonKey, cfg.SupabaseAnonKey)
	cfg.SiteURL = first(next.SiteURL, cfg.SiteURL)
	cfg.Theme = first(next.Theme, cfg.Theme)
}

func fromFile(path string) Config {
	raw, err := os.ReadFile(path)
	if err != nil {
		return Config{}
	}
	var file fileConfig
	if err := toml.Unmarshal(raw, &file); err != nil {
		return Config{}
	}
	return Config{
		APIURL:          strings.TrimRight(file.APIURL, "/"),
		SupabaseURL:     strings.TrimRight(file.SupabaseURL, "/"),
		SupabaseAnonKey: file.SupabaseAnonKey,
		SiteURL:         strings.TrimRight(file.SiteURL, "/"),
		Theme:           file.Theme,
	}
}

// fromEnv reads public website settings. The API host is not one of them:
// NEXT_PUBLIC_API_URL belongs to the Next.js app, and in this repo it points
// at a local server. The terminal uses the deployed API unless FPLBUD_API_URL
// or config.toml sets another one.
func fromEnv(getenv func(string) string, fplbud bool) Config {
	if fplbud {
		return Config{
			APIURL:          strings.TrimRight(getenv("FPLBUD_API_URL"), "/"),
			SupabaseURL:     strings.TrimRight(getenv("FPLBUD_SUPABASE_URL"), "/"),
			SupabaseAnonKey: getenv("FPLBUD_SUPABASE_ANON_KEY"),
			SiteURL:         strings.TrimRight(getenv("FPLBUD_SITE_URL"), "/"),
			Theme:           getenv("FPLBUD_THEME"),
		}
	}
	return Config{
		SupabaseURL:     strings.TrimRight(getenv("NEXT_PUBLIC_SUPABASE_URL"), "/"),
		SupabaseAnonKey: getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY"),
		SiteURL:         strings.TrimRight(getenv("NEXT_PUBLIC_SITE_URL"), "/"),
	}
}

func fromDotenv(path string) Config {
	if path == "" {
		return Config{}
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return Config{}
	}
	values := map[string]string{}
	sc := bufio.NewScanner(bytes.NewReader(raw))
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		key, value, ok := strings.Cut(line, "=")
		if !ok {
			continue
		}
		key = strings.TrimSpace(key)
		switch key {
		case "NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_ANON_KEY", "NEXT_PUBLIC_SITE_URL":
			values[key] = unquote(strings.TrimSpace(value))
		}
	}
	return Config{
		SupabaseURL:     strings.TrimRight(values["NEXT_PUBLIC_SUPABASE_URL"], "/"),
		SupabaseAnonKey: values["NEXT_PUBLIC_SUPABASE_ANON_KEY"],
		SiteURL:         strings.TrimRight(values["NEXT_PUBLIC_SITE_URL"], "/"),
	}
}

func unquote(value string) string {
	if len(value) >= 2 {
		if (value[0] == '"' && value[len(value)-1] == '"') || (value[0] == '\'' && value[len(value)-1] == '\'') {
			return value[1 : len(value)-1]
		}
	}
	return value
}

func findDotenv() string {
	dir, err := os.Getwd()
	if err != nil {
		return ""
	}
	for i := 0; i < 4; i++ {
		candidate := filepath.Join(dir, ".env")
		if _, err := os.Stat(candidate); err == nil {
			return candidate
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	return ""
}
