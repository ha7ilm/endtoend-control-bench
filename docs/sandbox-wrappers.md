# Sandbox wrappers
The experiment invokes `codexs` and `claudes`, which are thin Linux Bubblewrap front ends for `codex` and `claude`. Their purpose is experimental isolation, not merely write protection: the agent must not search the simulator source, handwritten example controllers, other attempts, or prior results for a solution.

As of 2026 Q1, Codex could by default inspect other host files readable by the user. Claude Code's default permissions did not allow the same unrestricted reading outside its project. Both tools were nevertheless wrapped so the benchmark used one explicit OS-level information boundary. This was especially important for automatic Claude runs because the experiment launcher passes `--dangerously-skip-permissions` after the outer sandbox has already removed unintended paths.

The definitions below preserve the experiment-relevant behavior while removing personal home paths and unrelated project bind mounts from the original local scripts.

## Prerequisites and variables

The wrappers require Linux Bubblewrap and an already authenticated underlying
CLI. They assume:

- the wrapper is called from the attempt's `lwp/rlwp/` directory;
- that directory is below the Git repository, so the installed client source
  can be resolved as `<repo>/src/urletra`;
- a Python environment is active;
- Codex is installed below a runtime tree such as `$HOME/.nvm`;
- Claude is installed in directories such as `$HOME/.local/bin` and
  `$HOME/.local/share/claude`.

The active Python prefix is detected with `sys.prefix`. Override the runtime
variables shown in each script if the CLIs use a different installation layout.
The paths need to be the narrowest directories that make the authenticated CLI
executable work inside the sandbox.

## `codexs`

Save this as an executable named `codexs` in a directory on `PATH`:

```bash
#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$PWD"
REPO_ROOT="$(git rev-parse --show-toplevel)"
CLIENT_SRC="$REPO_ROOT/src/urletra"
PYTHON_ENV_PREFIX="${PYTHON_ENV_PREFIX:-$(python -c 'import sys; print(sys.prefix)')}"
CODEX_RUNTIME_ROOT="${CODEX_RUNTIME_ROOT:-$HOME/.nvm}"

exec bwrap \
  --ro-bind /usr /usr \
  --ro-bind /lib /lib \
  --ro-bind /lib64 /lib64 \
  --ro-bind /bin /bin \
  --ro-bind /etc/resolv.conf /etc/resolv.conf \
  --ro-bind /etc/hosts /etc/hosts \
  --ro-bind /etc/ssl /etc/ssl \
  --ro-bind /etc/passwd /etc/passwd \
  --ro-bind /etc/group /etc/group \
  --ro-bind "$HOME/.gitconfig" "$HOME/.gitconfig" \
  --bind "$PROJECT_DIR" "$PROJECT_DIR" \
  --bind "$HOME/.codex" "$HOME/.codex" \
  --bind "$PYTHON_ENV_PREFIX" "$PYTHON_ENV_PREFIX" \
  --ro-bind "$CLIENT_SRC" "$CLIENT_SRC" \
  --ro-bind "$CODEX_RUNTIME_ROOT" "$CODEX_RUNTIME_ROOT" \
  --tmpfs /tmp \
  --proc /proc \
  --dev /dev \
  --unshare-all \
  --share-net \
  --die-with-parent \
  --chdir "$PROJECT_DIR" \
  codex "$@"
```

Experiment-relevant mounts are:

- the current attempt directory, read/write, so the agent can create controller
  scripts and logs;
- Codex authentication/configuration, read/write, as required by the CLI;
- the active Python environment, so controller scripts can execute;
- only the installed `urletra` package source from the repository, read-only;
- the Codex runtime, read-only.

`--unshare-all` removes the remaining host namespaces and `--share-net`
restores networking so Codex can reach its hosted model and controllers can
reach the simulator at `127.0.0.1:9000`. The sandbox gets a fresh `/tmp` and
minimal `/proc` and `/dev`.

## `claudes`

Save this as an executable named `claudes` in a directory on `PATH`:

```bash
#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$PWD"
REPO_ROOT="$(git rev-parse --show-toplevel)"
CLIENT_SRC="$REPO_ROOT/src/urletra"
PYTHON_ENV_PREFIX="${PYTHON_ENV_PREFIX:-$(python -c 'import sys; print(sys.prefix)')}"
CLAUDE_BIN_DIR="${CLAUDE_BIN_DIR:-$HOME/.local/bin}"
CLAUDE_INSTALL_DIR="${CLAUDE_INSTALL_DIR:-$HOME/.local/share/claude}"

exec bwrap \
  --ro-bind /usr /usr \
  --ro-bind /lib /lib \
  --ro-bind /lib64 /lib64 \
  --ro-bind /bin /bin \
  --ro-bind /etc/resolv.conf /etc/resolv.conf \
  --ro-bind /etc/hosts /etc/hosts \
  --ro-bind /etc/ssl /etc/ssl \
  --ro-bind /etc/passwd /etc/passwd \
  --ro-bind /etc/group /etc/group \
  --ro-bind "$HOME/.gitconfig" "$HOME/.gitconfig" \
  --bind "$PROJECT_DIR" "$PROJECT_DIR" \
  --bind "$HOME/.claude" "$HOME/.claude" \
  --bind "$HOME/.claude.json" "$HOME/.claude.json" \
  --bind "$PYTHON_ENV_PREFIX" "$PYTHON_ENV_PREFIX" \
  --ro-bind "$CLIENT_SRC" "$CLIENT_SRC" \
  --ro-bind "$CLAUDE_BIN_DIR" "$CLAUDE_BIN_DIR" \
  --ro-bind "$CLAUDE_INSTALL_DIR" "$CLAUDE_INSTALL_DIR" \
  --tmpfs /tmp \
  --proc /proc \
  --dev /dev \
  --unshare-all \
  --share-net \
  --die-with-parent \
  --chdir "$PROJECT_DIR" \
  claude "$@"
```

The Claude wrapper exposes the equivalent attempt, Python, client-source, CLI installation, and authentication paths. It intentionally does not expose the repository root, simulator implementation, examples, or result archive.

## Installation example

Choose a directory already on `PATH` (preferably user-owned, though can also be `/usr/bin`), copy each script there, and mark it executable,  then test from a generated `lwp/rlwp/` directory:

```bash
codexs --version
claudes --version
```

If Bubblewrap reports a missing source path, adjust only the corresponding runtime/config variable or optional mount. Do not solve it by binding the whole home directory or repository, because that invalidates the experiment's information boundary.

## Portability notes

- Bubblewrap is Linux-specific. On another OS, use an equivalent container or sandbox and document its mounts and network policy.
- Some Linux distributions do not have `/lib64`; remove that one bind if the source path is absent. This does not change the information boundary.
- If `.gitconfig` or a CLI state file does not exist, omit only that bind or create the file through the CLI's normal setup process.
- A CLI installed outside the default paths needs a correspondingly narrow read-only runtime mount. Do not bind all of `$HOME/.local` unless the exact installation genuinely requires it.

Archive the exact installed wrapper files, their resolved variables, the Bubblewrap version, and the CLI versions with every new result release.
