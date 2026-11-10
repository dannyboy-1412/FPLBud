// Package version is the build identity baked in with -ldflags.
package version

// Number, APIURL, SupabaseURL and SupabaseAnonKey are overridden at release time.
var (
	Number          = "dev"
	APIURL          = ""
	SupabaseURL     = ""
	SupabaseAnonKey = ""
)

const Protocol = "1"
