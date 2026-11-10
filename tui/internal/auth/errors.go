package auth

import (
	"errors"
	"io/fs"

	"github.com/zalando/go-keyring"
)

var errNoFile = fs.ErrNotExist

func IsNotFound(err error) bool {
	return errors.Is(err, ErrSignedOut) || errors.Is(err, keyring.ErrNotFound) || errors.Is(err, fs.ErrNotExist)
}
