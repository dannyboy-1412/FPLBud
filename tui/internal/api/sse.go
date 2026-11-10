package api

import (
	"bufio"
	"errors"
	"io"
	"strings"

	"github.com/dannyboy-1412/FPLBud/tui/internal/protocol"
)

const MaxLine = 1 << 20

var ErrLineTooLong = errors.New("event line is too long")

// ReadAll parses a complete SSE body. Comment lines and unknown fields are ignored.
func ReadAll(r io.Reader, maxLine int) ([]protocol.Raw, error) {
	var events []protocol.Raw
	err := Scan(r, maxLine, func(ev protocol.Raw) error {
		events = append(events, ev)
		return nil
	})
	return events, err
}

// Scan calls fn for each event as it arrives.
func Scan(r io.Reader, maxLine int, fn func(protocol.Raw) error) error {
	if maxLine <= 0 {
		maxLine = MaxLine
	}
	br := bufio.NewReader(r)
	var cur protocol.Raw
	var data []string
	open := false
	flush := func() error {
		if !open {
			return nil
		}
		cur.Data = strings.Join(data, "\n")
		emit := cur.Name != "" || cur.Data != ""
		ev := cur
		cur = protocol.Raw{}
		data = nil
		open = false
		if !emit {
			return nil
		}
		return fn(ev)
	}
	for {
		line, err := readLine(br, maxLine)
		if len(line) == 0 && err == nil {
			if flushErr := flush(); flushErr != nil {
				return flushErr
			}
		} else if len(line) > 0 {
			open = true
			consume(string(line), &cur, &data)
		}
		if errors.Is(err, io.EOF) {
			return flush()
		}
		if err != nil {
			return err
		}
	}
}

func consume(line string, cur *protocol.Raw, data *[]string) {
	if strings.HasPrefix(line, ":") {
		return
	}
	field, value, ok := strings.Cut(line, ":")
	if !ok {
		field = line
		value = ""
	}
	value = strings.TrimPrefix(value, " ")
	switch field {
	case "event":
		cur.Name = strings.TrimSpace(value)
	case "data":
		*data = append(*data, value)
	case "id":
		cur.ID = value
	}
}

func readLine(r *bufio.Reader, max int) ([]byte, error) {
	var buf []byte
	for {
		part, err := r.ReadSlice('\n')
		buf = append(buf, part...)
		if len(buf) > max {
			return nil, ErrLineTooLong
		}
		if errors.Is(err, bufio.ErrBufferFull) {
			continue
		}
		if n := len(buf); n > 0 && buf[n-1] == '\n' {
			buf = buf[:n-1]
			for len(buf) > 0 && buf[len(buf)-1] == '\r' {
				buf = buf[:len(buf)-1]
			}
		}
		return buf, err
	}
}
