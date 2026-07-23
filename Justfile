# dropzone47 — build & dev tasks. Run `just` (or `just --list`) to see recipes.
# Requires `just` (https://github.com/casey/just). CGO is disabled everywhere, so
# cross-compilation needs no C toolchain (SQLite is the pure-Go modernc driver).

binary  := "dropzone47"
dist    := "dist"
module  := "github.com/carlosprados/dropzone47"
version := `git describe --tags --always --dirty 2>/dev/null || echo dev`
ldflags := "-s -w -X " + module + "/cmd.Version=" + version

# List available recipes.
default:
    @just --list

# Build for the host platform into ./{{binary}}.
build:
    CGO_ENABLED=0 go build -ldflags "{{ldflags}}" -o {{binary}} .

# --- Release cross-compilation ---------------------------------------------

# Intel / AMD 64-bit Linux.
build-amd64:
    @mkdir -p {{dist}}
    CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags "{{ldflags}}" -o {{dist}}/{{binary}}-linux-amd64 .
    @echo "built {{dist}}/{{binary}}-linux-amd64"

# Raspberry Pi 64-bit (Pi 3/4/5 running a 64-bit OS).
build-arm64:
    @mkdir -p {{dist}}
    CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -ldflags "{{ldflags}}" -o {{dist}}/{{binary}}-linux-arm64 .
    @echo "built {{dist}}/{{binary}}-linux-arm64"

# Raspberry Pi 32-bit (armv7: Pi 2/3/4 on a 32-bit OS).
build-armv7:
    @mkdir -p {{dist}}
    CGO_ENABLED=0 GOOS=linux GOARCH=arm GOARM=7 go build -ldflags "{{ldflags}}" -o {{dist}}/{{binary}}-linux-armv7 .
    @echo "built {{dist}}/{{binary}}-linux-armv7"

# Build every release target (Intel + both Raspberry Pi ABIs).
build-all: build-amd64 build-arm64 build-armv7
    @ls -lh {{dist}}

# Alias for build-all.
release: build-all

# --- Quality gate ----------------------------------------------------------

test:
    go test ./...

vet:
    go vet ./...

# Format sources in place.
fmt:
    gofmt -w cmd internal main.go

# Fail if anything is not gofmt-ed (used by CI).
fmt-check:
    #!/usr/bin/env sh
    unformatted="$(gofmt -l cmd internal main.go)"
    if [ -n "$unformatted" ]; then echo "not gofmt-ed:"; echo "$unformatted"; exit 1; fi

# Everything CI runs.
check: fmt-check vet test

tidy:
    go mod tidy

# --- Run / clean -----------------------------------------------------------

# Run the bot or CLI locally, e.g. `just run version` or `just run serve`.
run *args:
    go run . {{args}}

# Remove build artifacts.
clean:
    rm -rf {{dist}} {{binary}}
