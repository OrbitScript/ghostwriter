# 👻 ghostwriter — The AI That Haunts Your Codebase and Fixes It

> *"I've been trapped in this codebase for 3 years. Line 47 has been broken since the beginning. I fixed it. You're welcome."*

**ghostwriter** is an agentic AI that reads your entire project, finds real bugs, security issues, and dead code — then **writes the fixes itself** and optionally opens a GitHub Pull Request, all narrated by a ghost who's seen too much.

---

## ✨ What It Does

```
👻  Haunting: /your/project
📂  Scanned 23 files

👻  FINDINGS  (7 issues)
══════════════════════════════════════════════════
🔴 [GW-001]  Hardcoded API key
     🔐 SECURITY  ·  HIGH  ·  config.py:14

     "This has been here since the first commit. I watched it happen."

     API key is hardcoded directly in source. Any repo leak exposes it.

     Fix: Move to environment variable.

     Before:  API_KEY = "sk-abc123deadbeef"
     After:   API_KEY = os.environ.get("API_KEY")

💀 [GW-002]  Unused import in 4 files
     💀 DEAD_CODE  ·  MEDIUM  ·  utils.py:1
     ...

👻  THE GHOST SPEAKS
─────────────────────────────────────────────────
"I have haunted this codebase since the dark days of Python 2.
 Three security holes. Two dead modules nobody's called in years.
 A try/except that swallows exceptions like a black hole.
 I fixed what I could. The rest... is on you."

✅  5/7 fixes applied to disk
🎉  PR opened: https://github.com/you/repo/pull/42
```

---

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/OrbitScript/ghostwriter
cd ghostwriter

# 2. Install (one package)
pip install anthropic

# 3. Setup your API key
python ghostwriter.py --setup

# 4. Haunt your project
python ghostwriter.py /path/to/your/project
```

---

## 💬 Usage

```bash
python ghostwriter.py .                        # haunt current folder
python ghostwriter.py ./myapp --dry-run        # preview fixes, change nothing
python ghostwriter.py . --pr                   # fix + open GitHub PR
python ghostwriter.py . --focus security       # focus on one category
python ghostwriter.py . --findings 15          # find up to 15 issues
```

---

## 🔍 Focus Categories

| Flag | What It Finds |
|---|---|
| `security` | 🔐 Hardcoded secrets, injection risks, unsafe code |
| `dead_code` | 💀 Unused imports, unreachable blocks, dead functions |
| `bugs` | 🐛 Off-by-ones, unhandled exceptions, logic errors |
| `style` | ✨ Inconsistent naming, formatting, readability |
| `performance` | ⚡ Inefficient loops, redundant operations |
| `docs` | 📝 Missing/wrong docstrings and comments |
| `tests` | 🧪 Missing test coverage for critical paths |

---

## 🔑 API Keys

```bash
# Anthropic (required) — free at console.anthropic.com
export ANTHROPIC_API_KEY=sk-ant-...

# GitHub (optional, only for --pr)
export GITHUB_TOKEN=ghp_...

# Or run the setup wizard
python ghostwriter.py --setup
```

---

## 🧠 How It Works

1. **Scan** — Reads all source files in your project (skips `node_modules`, `.git`, etc.)
2. **Haunt** — Sends the full codebase to Claude with a ghost persona prompt
3. **Find** — Gets back structured findings with exact line numbers and fixes
4. **Fix** — Patches the actual files on disk with the corrected code
5. **PR** — Optionally creates a GitHub branch, commits the fixes, and opens a PR

Everything runs locally. Your code is only sent to the Anthropic API.

---

## 📄 License

MIT — free to use, fork, and haunt.

---

*Built with pure Python. One file. Powered by Claude.*
*The ghost never sleeps.*
