package auth

import "testing"

func TestChallengeIsS256(t *testing.T) {
	const verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
	if got := Challenge(verifier); got != "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM" {
		t.Fatal(got)
	}
}

func TestCodeFromRedirect(t *testing.T) {
	code, err := CodeFromRedirect("http://127.0.0.1:53682/callback?code=abc123")
	if err != nil || code != "abc123" {
		t.Fatalf("%s %v", code, err)
	}
	if _, err := CodeFromRedirect("http://127.0.0.1:53682/callback?error_description=nope"); err == nil {
		t.Fatal("expected error")
	}
	code, err = CodeFromRedirect("bare-code")
	if err != nil || code != "bare-code" {
		t.Fatal(code, err)
	}
}
