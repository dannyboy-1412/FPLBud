package main

import (
	"bufio"
	"context"
	"errors"
	"flag"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/pkg/browser"
	"golang.org/x/term"

	"github.com/dannyboy-1412/FPLBud/tui/internal/api"
	"github.com/dannyboy-1412/FPLBud/tui/internal/ask"
	"github.com/dannyboy-1412/FPLBud/tui/internal/auth"
	"github.com/dannyboy-1412/FPLBud/tui/internal/config"
	"github.com/dannyboy-1412/FPLBud/tui/internal/ui"
	"github.com/dannyboy-1412/FPLBud/tui/internal/version"
)

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run(args []string) error {
	cmd, rest := split(args)
	switch cmd {
	case "chat":
		return chat(rest)
	case "ask":
		return askCmd(rest)
	case "login":
		return loginCmd(rest)
	case "logout":
		return logoutCmd()
	case "whoami":
		return whoamiCmd()
	case "version", "--version", "-v":
		fmt.Printf("fplbud %s\nprotocol %s\n", version.Number, version.Protocol)
		return nil
	case "help", "--help", "-h":
		fmt.Fprint(os.Stdout, usageText)
		return nil
	default:
		return fmt.Errorf("unknown command %q\n%s", cmd, usageText)
	}
}

func split(args []string) (string, []string) {
	if len(args) == 0 || strings.HasPrefix(args[0], "-") {
		return "chat", args
	}
	return args[0], args[1:]
}

func chat(args []string) error {
	fs := flag.NewFlagSet("chat", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)
	plain := fs.Bool("plain", false, "linear text without boxes")
	themeName := fs.String("theme", "", "light, dark, or auto")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if !term.IsTerminal(int(os.Stdout.Fd())) {
		return errors.New("fplbud needs a terminal. Use fplbud ask \"question\" to run one turn")
	}
	cfg, err := config.Load()
	if err != nil {
		return err
	}
	return ui.Run(cfg, *plain, *themeName, nil)
}

func askCmd(args []string) error {
	fs := flag.NewFlagSet("ask", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)
	thread := fs.String("thread", "", "existing thread id")
	asJSON := fs.Bool("json", false, "print raw events")
	if err := fs.Parse(args); err != nil {
		return err
	}
	question := strings.TrimSpace(strings.Join(fs.Args(), " "))
	if question == "" {
		return errors.New("usage: fplbud ask \"who should I captain?\"")
	}
	cfg, err := config.Load()
	if err != nil {
		return err
	}
	_, client := newClient(cfg)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	return ask.Run(ctx, client, *thread, question, *asJSON, os.Stdout, os.Stderr)
}

func loginCmd(args []string) error {
	fs := flag.NewFlagSet("login", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)
	noBrowser := fs.Bool("no-browser", false, "print the link and paste the redirect")
	if err := fs.Parse(args); err != nil {
		return err
	}
	cfg, err := config.Load()
	if err != nil {
		return err
	}
	if cfg.SupabaseURL == "" || cfg.SupabaseAnonKey == "" {
		return errors.New("set FPLBUD_SUPABASE_URL and FPLBUD_SUPABASE_ANON_KEY")
	}
	login, err := auth.Begin(context.Background(), cfg.SupabaseURL)
	if err != nil {
		return err
	}
	defer login.Cancel()
	fmt.Fprintln(os.Stderr, login.URL)
	var code string
	if *noBrowser {
		fmt.Fprint(os.Stderr, "Paste the redirected URL: ")
		sc := bufio.NewScanner(os.Stdin)
		if !sc.Scan() {
			return errors.New("no login link pasted")
		}
		code, err = auth.CodeFromRedirect(sc.Text())
		if err != nil {
			return err
		}
	} else {
		_ = browser.OpenURL(login.URL)
		fmt.Fprintln(os.Stderr, "Waiting for the browser…")
		select {
		case code = <-login.Code:
		case err = <-login.Err:
			if err != nil {
				return err
			}
		case <-time.After(3 * time.Minute):
			return errors.New("sign-in timed out")
		}
	}
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	sess, err := auth.Exchange(ctx, cfg.SupabaseURL, cfg.SupabaseAnonKey, code, login.Verifier)
	if err != nil {
		return err
	}
	sessions, _ := newClient(cfg)
	if err := sessions.Save(sess); err != nil {
		return err
	}
	who := sess.Email
	if who == "" {
		who = sess.UserID
	}
	fmt.Printf("signed in as %s\n", who)
	return nil
}

func logoutCmd() error {
	cfg, err := config.Load()
	if err != nil {
		return err
	}
	sessions, _ := newClient(cfg)
	sess, err := sessions.Load()
	if err == nil {
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		_ = auth.End(ctx, cfg.SupabaseURL, cfg.SupabaseAnonKey, sess.AccessToken)
	}
	if err := sessions.Clear(); err != nil {
		return err
	}
	fmt.Println("signed out")
	return nil
}

func whoamiCmd() error {
	cfg, err := config.Load()
	if err != nil {
		return err
	}
	sessions, _ := newClient(cfg)
	sess, err := sessions.Load()
	if err != nil || !sess.SignedIn() {
		return errors.New("not signed in")
	}
	if sess.Email != "" {
		fmt.Println(sess.Email)
		return nil
	}
	fmt.Println(sess.UserID)
	return nil
}

func newClient(cfg config.Config) (*auth.Manager, *api.Client) {
	sessions := auth.NewManager(cfg.Dir, cfg.SupabaseURL, cfg.SupabaseAnonKey)
	client := &api.Client{
		BaseURL: cfg.APIURL,
		Version: version.Number,
		Token:   sessions.Token,
		ForceRefresh: func(ctx context.Context) (string, error) {
			return sessions.ForceRefresh(ctx)
		},
		SignOut: func() { _ = sessions.Clear() },
	}
	return sessions, client
}

const usageText = `fplbud is the terminal client for the FPLBud assistant.

  fplbud                         open the chat
  fplbud ask "question"          one turn, answer on stdout
  fplbud login [--no-browser]    sign in with Google
  fplbud logout
  fplbud whoami
  fplbud version

Environment: FPLBUD_API_URL, FPLBUD_SUPABASE_URL, FPLBUD_SUPABASE_ANON_KEY, FPLBUD_SITE_URL, FPLBUD_THEME.
`
