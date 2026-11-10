package render

import (
	"fmt"
	"regexp"
	"strings"
	"unicode/utf8"

	"github.com/dannyboy-1412/FPLBud/tui/internal/protocol"
	"github.com/mattn/go-runewidth"
)

var inlineToken = regexp.MustCompile(`\[\[p:(\d+)\|([^\]]+)\]\]|\*\*([^*]+)\*\*`)

type Kind int

const (
	KindText Kind = iota
	KindBold
	KindChip
)

type Span struct {
	Kind Kind
	Text string
	Chip protocol.Citation
}

type Block struct {
	Bullet bool
	Number int
	Spans  []Span
}

// Blocks parses the restricted subset: paragraphs, bold, lists and player chips.
func Blocks(text string) []Block {
	text = Sanitize(text)
	text = strings.ReplaceAll(text, "\r\n", "\n")
	if strings.TrimSpace(text) == "" {
		return nil
	}
	var blocks []Block
	for _, part := range strings.Split(text, "\n\n") {
		part = strings.Trim(part, "\n")
		if strings.TrimSpace(part) == "" {
			continue
		}
		lines := strings.Split(part, "\n")
		if bullets, ok := asList(lines, "- "); ok {
			for _, line := range bullets {
				blocks = append(blocks, Block{Bullet: true, Spans: inlines(line)})
			}
			continue
		}
		if numbered, ns, ok := asNumbered(lines); ok {
			for i, line := range numbered {
				blocks = append(blocks, Block{Number: ns[i], Spans: inlines(line)})
			}
			continue
		}
		var spans []Span
		for i, line := range lines {
			if i > 0 {
				spans = append(spans, Span{Text: "\n"})
			}
			spans = append(spans, inlines(line)...)
		}
		blocks = append(blocks, Block{Spans: spans})
	}
	return blocks
}

func asList(lines []string, prefix string) ([]string, bool) {
	out := make([]string, 0, len(lines))
	for _, line := range lines {
		if strings.TrimSpace(line) == "" {
			continue
		}
		if !strings.HasPrefix(line, prefix) {
			return nil, false
		}
		out = append(out, strings.TrimPrefix(line, prefix))
	}
	return out, len(out) > 0
}

func asNumbered(lines []string) ([]string, []int, bool) {
	out := make([]string, 0, len(lines))
	ns := make([]int, 0, len(lines))
	for _, line := range lines {
		if strings.TrimSpace(line) == "" {
			continue
		}
		n, rest, ok := cutNumber(line)
		if !ok {
			return nil, nil, false
		}
		out = append(out, rest)
		ns = append(ns, n)
	}
	return out, ns, len(out) > 0
}

func cutNumber(line string) (int, string, bool) {
	i := 0
	n := 0
	for i < len(line) && line[i] >= '0' && line[i] <= '9' {
		n = n*10 + int(line[i]-'0')
		i++
	}
	if i == 0 || i+1 >= len(line) || line[i] != '.' || line[i+1] != ' ' {
		return 0, "", false
	}
	return n, line[i+2:], true
}

func inlines(line string) []Span {
	var spans []Span
	rest := line
	for {
		loc := inlineToken.FindStringSubmatchIndex(rest)
		if loc == nil {
			if rest != "" {
				spans = append(spans, Span{Text: rest})
			}
			return spans
		}
		if loc[0] > 0 {
			spans = append(spans, Span{Text: rest[:loc[0]]})
		}
		match := inlineToken.FindStringSubmatch(rest)
		if match[3] != "" {
			inner := inlines(match[3])
			if len(inner) == 0 {
				spans = append(spans, Span{Kind: KindBold, Text: match[3]})
			}
			for _, span := range inner {
				if span.Kind == KindText {
					span.Kind = KindBold
				}
				spans = append(spans, span)
			}
		} else {
			var id int
			fmt.Sscanf(match[1], "%d", &id)
			spans = append(spans, Span{Kind: KindChip, Text: match[2], Chip: protocol.Citation{PlayerID: id, Name: match[2]}})
		}
		rest = rest[loc[1]:]
	}
}

// Line is one visual row of spans, already wrapped.
type Line struct {
	Prefix string
	Spans  []Span
}

// LayOut wraps blocks to width. Draft chips keep the bare name.
func LayOut(text string, citations []protocol.Citation, draft bool, width int) []Line {
	if width < 8 {
		width = 8
	}
	known := map[int]protocol.Citation{}
	for _, c := range citations {
		known[c.PlayerID] = c
	}
	var lines []Line
	for i, block := range Blocks(text) {
		if i > 0 {
			lines = append(lines, Line{})
		}
		prefix := ""
		contentWidth := width
		if block.Bullet {
			prefix = "• "
			contentWidth = width - 2
		} else if block.Number > 0 {
			prefix = fmt.Sprintf("%d. ", block.Number)
			contentWidth = width - runewidth.StringWidth(prefix)
		}
		if contentWidth < 4 {
			contentWidth = 4
		}
		wrapped := wrapSpans(resolve(block.Spans, known, draft), contentWidth)
		if len(wrapped) == 0 {
			lines = append(lines, Line{Prefix: prefix})
			continue
		}
		for j, row := range wrapped {
			line := Line{Spans: row}
			if j == 0 {
				line.Prefix = prefix
			} else if prefix != "" {
				line.Prefix = strings.Repeat(" ", runewidth.StringWidth(prefix))
			}
			lines = append(lines, line)
		}
	}
	return lines
}

func resolve(spans []Span, known map[int]protocol.Citation, draft bool) []Span {
	out := make([]Span, 0, len(spans))
	for _, span := range spans {
		if span.Kind != KindChip {
			out = append(out, span)
			continue
		}
		cite, ok := known[span.Chip.PlayerID]
		if !ok {
			cite = span.Chip
		}
		if draft {
			out = append(out, Span{Kind: KindText, Text: cite.Name})
			continue
		}
		out = append(out, Span{Kind: KindChip, Text: chipLabel(cite), Chip: cite})
	}
	return out
}

func chipLabel(c protocol.Citation) string {
	label := c.Name
	if c.Team != nil && *c.Team != "" {
		label += " " + *c.Team
	}
	if c.PriceM != nil {
		label += fmt.Sprintf(" £%.1fm", *c.PriceM)
	}
	return label
}

type atom struct {
	span      Span
	softBreak bool
	hardBreak bool
}

func wrapSpans(spans []Span, width int) [][]Span {
	var rows [][]Span
	var row []Span
	used := 0
	flush := func() {
		if len(row) == 0 {
			return
		}
		rows = append(rows, row)
		row = nil
		used = 0
	}
	for _, atom := range atomsOf(spans) {
		if atom.hardBreak {
			flush()
			continue
		}
		w := runewidth.StringWidth(atom.span.Text)
		if atom.softBreak {
			if used == 0 || used+w > width {
				continue
			}
			row = append(row, atom.span)
			used += w
			continue
		}
		if w > width {
			if used > 0 {
				flush()
			}
			rest := atom.span.Text
			for rest != "" {
				cut := cutWidth(rest, width)
				if cut == "" {
					_, size := utf8.DecodeRuneInString(rest)
					if size <= 0 {
						break
					}
					cut = rest[:size]
				}
				row = append(row, Span{Kind: atom.span.Kind, Text: cut, Chip: atom.span.Chip})
				rest = rest[len(cut):]
				if rest != "" {
					flush()
				} else {
					used = runewidth.StringWidth(cut)
				}
			}
			continue
		}
		if used > 0 && used+w > width {
			flush()
		}
		row = append(row, atom.span)
		used += w
	}
	flush()
	return rows
}

func atomsOf(spans []Span) []atom {
	var out []atom
	for _, span := range spans {
		parts := strings.Split(span.Text, "\n")
		for i, part := range parts {
			if i > 0 {
				out = append(out, atom{hardBreak: true})
			}
			out = append(out, words(span, part)...)
		}
	}
	return out
}

func words(span Span, text string) []atom {
	var out []atom
	for text != "" {
		if text[0] == ' ' || text[0] == '\t' {
			j := 0
			for j < len(text) && (text[j] == ' ' || text[j] == '\t') {
				j++
			}
			out = append(out, atom{span: Span{Kind: span.Kind, Text: " ", Chip: span.Chip}, softBreak: true})
			text = text[j:]
			continue
		}
		j := 0
		for j < len(text) && text[j] != ' ' && text[j] != '\t' {
			j++
		}
		out = append(out, atom{span: Span{Kind: span.Kind, Text: text[:j], Chip: span.Chip}})
		text = text[j:]
	}
	return out
}

func cutWidth(s string, width int) string {
	if width <= 0 {
		return ""
	}
	used := 0
	end := 0
	for end < len(s) {
		r, size := utf8.DecodeRuneInString(s[end:])
		if size <= 0 {
			break
		}
		w := runewidth.RuneWidth(r)
		if w < 1 {
			w = 1
		}
		if used+w > width {
			break
		}
		used += w
		end += size
	}
	return s[:end]
}

// Plain is the wrapped text with chips expanded and no styling.
func Plain(text string, citations []protocol.Citation, width int) string {
	lines := LayOut(text, citations, false, width)
	var b strings.Builder
	for i, line := range lines {
		if i > 0 {
			b.WriteByte('\n')
		}
		b.WriteString(line.Prefix)
		for _, span := range line.Spans {
			b.WriteString(span.Text)
		}
	}
	return b.String()
}
