package auth

import (
	"context"
	"errors"
	"sync"
	"time"
)

// Manager loads and refreshes one session, serialised across processes with a lock file.
type Manager struct {
	dir      string
	supabase string
	anon     string
	now      func() time.Time
	keys     Store
	files    Store
	mu       sync.Mutex
	File     bool
}

func NewManager(dir, supabaseURL, anonKey string) *Manager {
	return &Manager{
		dir:      dir,
		supabase: supabaseURL,
		anon:     anonKey,
		now:      time.Now,
		keys:     keyStore{account: ProjectRef(supabaseURL)},
		files:    fileStore{path: sessionPath(dir)},
	}
}

func (m *Manager) Load() (Session, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.load()
}

func (m *Manager) Token(ctx context.Context) (string, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	sess, err := m.load()
	if err != nil || !sess.SignedIn() {
		return "", ErrSignedOut
	}
	if !NeedsRefresh(sess, m.now()) {
		return sess.AccessToken, nil
	}
	next, err := m.refreshLocked(ctx, sess, false)
	if err != nil {
		return "", err
	}
	return next.AccessToken, nil
}

// ForceRefresh always rotates the session. A 401 from the API uses this once.
func (m *Manager) ForceRefresh(ctx context.Context) (string, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	sess, err := m.load()
	if err != nil || !sess.SignedIn() {
		return "", ErrSignedOut
	}
	next, err := m.refreshLocked(ctx, sess, true)
	if err != nil {
		return "", err
	}
	return next.AccessToken, nil
}

func (m *Manager) Save(s Session) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.save(s)
}

func (m *Manager) Clear() error {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.clear()
}

func (m *Manager) load() (Session, error) {
	sess, err := m.keys.Load()
	if err == nil && sess.SignedIn() {
		m.File = false
		return sess, nil
	}
	sess, ferr := m.files.Load()
	if ferr == nil && sess.SignedIn() {
		m.File = true
		return sess, nil
	}
	if ferr != nil && !errors.Is(ferr, osErrNotExist()) && !errors.Is(ferr, ErrSignedOut) {
		return Session{}, ferr
	}
	return Session{}, ErrSignedOut
}

func (m *Manager) save(s Session) error {
	if err := m.keys.Save(s); err == nil {
		m.File = false
		_ = m.files.Clear()
		return nil
	}
	_ = m.keys.Clear()
	m.File = true
	return m.files.Save(s)
}

func (m *Manager) clear() error {
	keyErr := m.keys.Clear()
	fileErr := m.files.Clear()
	if keyErr != nil && fileErr != nil {
		return fileErr
	}
	return nil
}

func (m *Manager) refreshLocked(ctx context.Context, sess Session, force bool) (Session, error) {
	release, err := lock(m.dir)
	if err != nil {
		return Session{}, err
	}
	defer release()
	current, loadErr := m.load()
	if loadErr == nil && current.SignedIn() {
		sess = current
		if !force && !NeedsRefresh(current, m.now()) {
			return current, nil
		}
	}
	next, err := Refresh(ctx, m.supabase, m.anon, sess.RefreshToken)
	if err != nil {
		if errors.Is(err, ErrInvalidGrant) {
			_ = m.clear()
		}
		return Session{}, err
	}
	if err := m.save(next); err != nil {
		return Session{}, err
	}
	return next, nil
}

func osErrNotExist() error {
	return errNoFile
}
