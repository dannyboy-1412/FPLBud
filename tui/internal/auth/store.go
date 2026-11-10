package auth

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"

	"github.com/zalando/go-keyring"
)

const keyringService = "fplbud"

type Store interface {
	Load() (Session, error)
	Save(Session) error
	Clear() error
}

type keyStore struct {
	account string
}

func (k keyStore) Load() (Session, error) {
	raw, err := keyring.Get(keyringService, k.account)
	if err != nil {
		return Session{}, err
	}
	return decodeSession(raw)
}

func (k keyStore) Save(s Session) error {
	raw, err := json.Marshal(s)
	if err != nil {
		return err
	}
	return keyring.Set(keyringService, k.account, string(raw))
}

func (k keyStore) Clear() error {
	err := keyring.Delete(keyringService, k.account)
	if errors.Is(err, keyring.ErrNotFound) {
		return nil
	}
	return err
}

type fileStore struct {
	path string
}

func (f fileStore) Load() (Session, error) {
	raw, err := os.ReadFile(f.path)
	if err != nil {
		return Session{}, err
	}
	return decodeSession(string(raw))
}

func (f fileStore) Save(s Session) error {
	if err := os.MkdirAll(filepath.Dir(f.path), 0o700); err != nil {
		return err
	}
	raw, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(f.path, raw, 0o600)
}

func (f fileStore) Clear() error {
	err := os.Remove(f.path)
	if errors.Is(err, os.ErrNotExist) {
		return nil
	}
	return err
}

func decodeSession(raw string) (Session, error) {
	var s Session
	err := json.Unmarshal([]byte(raw), &s)
	return s, err
}

func sessionPath(dir string) string {
	return filepath.Join(dir, "session.json")
}
