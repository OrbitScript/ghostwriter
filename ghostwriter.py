#!/usr/bin/env python3
"""
👻 ghostwriter — The AI that haunts your codebase and fixes it.

An agentic AI that reads your entire project, finds real problems,
writes the fixes, and optionally opens a Pull Request — all narrated
by a ghost who's been trapped in your code for years.

Usage:
    python ghostwriter.py .                    # haunt current folder
    python ghostwriter.py ./myproject          # haunt a specific folder
    python ghostwriter.py . --pr               # haunt + open GitHub PR
    python ghostwriter.py . --dry-run          # preview fixes without writing
    python ghostwriter.py . --focus security   # focus on one category
"""

import os
import sys
import json
import time
import shutil
import argparse
import textwrap
import threading
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ─── ANSI ──────────────────────────────────────────────
class C:
    RESET    = "\033[0m";  BOLD    = "\033[1m";  DIM     = "\033[2m"
    ITALIC   = "\033[3m";  RED     = "\033[31m"; GREEN   = "\033[32m"
    YELLOW   = "\033[33m"; BLUE    = "\033[34m"; MAGENTA = "\033[35m"
    CYAN     = "\033[36m"; GRAY    = "\033[90m"; BRED    = "\033[91m"
    BGREEN   = "\033[92m"; BYELLOW = "\033[93m"; BBLUE   = "\033[94m"
    BMAGENTA = "\033[95m"; BCYAN   = "\033[96m"; BWHITE  = "\033[97m"

def col(t, *c): return "".join(c) + str(t) + C.RESET
def tw(): return shutil.get_terminal_size((80, 24)).columns
def hr(ch="─", c=C.GRAY): print(col(ch * tw(), c))
def iprint(text, indent=4, color=""):
    w = tw() - indent - 2
    for line in textwrap.wrap(str(text), width=w):
        print(" " * indent + (color + line + C.RESET if color else line))

# ─── Spinner ───────────────────────────────────────────
class Spinner:
    F = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    def __init__(self, msg="Thinking", color=C.BMAGENTA):
        self.msg = msg; self.color = color
        self._stop = threading.Event(); self._t = None
    def start(self):
        self._stop.clear()
        self._t = threading.Thread(target=self._spin, daemon=True)
        self._t.start()
    def stop(self, final=None):
        self._stop.set()
        if self._t: self._t.join()
        sys.stdout.write("\r" + " " * (tw()-1) + "\r"); sys.stdout.flush()
        if final: print(final)
    def _spin(self):
        i = 0
        while not self._stop.is_set():
            sys.stdout.write(f"\r  {col(self.F[i%len(self.F)], self.color)}  "
                             f"{col(self.msg + '...', self.color)}")
            sys.stdout.flush(); time.sleep(0.08); i += 1

# ─── Claude API ────────────────────────────────────────
def claude(messages, system, api_key, model="claude-sonnet-4-20250514", max_tokens=8000):
    payload = json.dumps({
        "model": model, "max_tokens": max_tokens,
        "system": system, "messages": messages,
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=payload, method="POST",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())["content"][0]["text"]
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Claude API error {e.code}: {e.read().decode()}")

def parse_json(raw):
    import re
    clean = raw.strip()
    fence = re.match(r'^```[a-z]*\n?', clean)
    if fence:
        clean = clean[fence.end():]
    if clean.endswith("```"):
        clean = clean[:-3].strip()
    try:
        return json.loads(clean)
    except Exception:
        m = re.search(r'\{.*\}', clean, re.DOTALL)
        if m:
            return json.loads(m.group())
        raise ValueError(f"Could not parse JSON: {clean[:200]}")

# ─── File Scanner ──────────────────────────────────────
SKIP_DIRS  = {".git","node_modules","__pycache__",".venv","venv","env",
              "dist","build",".next","target",".mypy_cache",".pytest_cache"}
CODE_EXTS  = {".py",".js",".ts",".jsx",".tsx",".java",".go",".rs",".rb",
              ".php",".cs",".cpp",".c",".h",".swift",".kt",".sh",".bash",
              ".yaml",".yml",".json",".toml",".cfg",".ini",".md",".txt"}
MAX_FILE_SIZE = 50_000   # chars
MAX_FILES     = 60

def scan_project(root: Path) -> dict:
    files = {}
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            if len(files) >= MAX_FILES: break
            fp = Path(dp) / fn
            if fp.suffix.lower() not in CODE_EXTS: continue
            try:
                text = fp.read_text(encoding="utf-8", errors="ignore")
                if len(text) > MAX_FILE_SIZE:
                    text = text[:MAX_FILE_SIZE] + "\n# ... (truncated)"
                rel = str(fp.relative_to(root))
                files[rel] = {"content": text, "lines": len(text.splitlines()),
                              "size": len(text), "ext": fp.suffix.lower()}
            except Exception:
                pass
    return files

def build_manifest(files: dict, root: Path) -> str:
    lines = [f"Project root: {root}", f"Total files scanned: {len(files)}", ""]
    for path, info in sorted(files.items()):
        lines.append(f"  {path}  ({info['lines']} lines)")
    return "\n".join(lines)

# ─── Issue Categories ──────────────────────────────────
CATEGORIES = {
    "security":    "🔐 Security vulnerabilities, hardcoded secrets, unsafe code",
    "dead_code":   "💀 Dead code, unused imports, unreachable blocks",
    "bugs":        "🐛 Potential bugs, off-by-ones, unhandled exceptions",
    "style":       "✨ Style issues, inconsistency, naming problems",
    "performance": "⚡ Performance issues, inefficient patterns",
    "docs":        "📝 Missing or wrong documentation, unclear comments",
    "tests":       "🧪 Missing test coverage, untested edge cases",
}

# ─── Ghost Persona Prompts ─────────────────────────────
GHOST_SYSTEM = """You are 👻 GHOSTWRITER — an ancient, sarcastic, but genuinely helpful AI spirit
who has been trapped inside this codebase for years. You have seen everything.
You remember every bad commit. You know where all the skeletons are buried.

Your job is to haunt this codebase, find its real problems, and fix them.

You respond ONLY with valid JSON. No preamble, no markdown outside the JSON.

Your analysis produces findings like this:
{
  "findings": [
    {
      "id": "GW-001",
      "category": "security|dead_code|bugs|style|performance|docs|tests",
      "severity": "critical|high|medium|low",
      "file": "relative/path/to/file.py",
      "line_start": 14,
      "line_end": 18,
      "title": "Short title of the issue",
      "description": "What the problem is and why it matters",
      "ghost_voice": "What I, the ghost, say about this (1-2 sentences, sarcastic/dramatic)",
      "fix_description": "Plain English description of the fix",
      "original_code": "exact code that needs to change (if applicable)",
      "fixed_code": "the corrected code (if applicable)"
    }
  ],
  "ghost_summary": "A dramatic ghost monologue summarizing what I found in this codebase (3-5 sentences)",
  "pr_title": "A spooky but descriptive PR title",
  "pr_body": "Full GitHub PR description written in ghost voice, with a findings table"
}

Be REAL. Only report genuine issues. Don't hallucinate bugs.
Fix code must be syntactically correct and actually improve the original.
Ghost voice should be darkly funny — not annoying, not cringe. Think: exhausted ghost who's seen too much.
"""

ANALYSIS_PROMPT = """You are haunting this codebase. Read every file carefully.
Find REAL issues — things that are actually wrong, risky, or could be improved.

Focus on: {focus}

Here is the full project:

{file_dump}

Find up to {max_findings} genuine issues. For each one, provide the exact original code
and a working fix. Be specific about line numbers.

Remember: you are GHOSTWRITER, an ancient AI spirit. Make your ghost_voice comments
darkly funny and memorable — but the technical content must be 100% accurate.
"""

# ─── Rendering ─────────────────────────────────────────
SEVERITY_COLOR = {
    "critical": C.BRED, "high": C.BRED, "medium": C.BYELLOW, "low": C.BGREEN
}
SEVERITY_ICON = {
    "critical": "💀", "high": "🔴", "medium": "🟡", "low": "🟢"
}

def render_splash():
    print()
    print(col("   ██████╗ ██╗  ██╗ ██████╗ ███████╗████████╗██╗    ██╗██████╗ ██╗████████╗███████╗██████╗ ", C.BMAGENTA))
    print(col("  ██╔════╝ ██║  ██║██╔═══██╗██╔════╝╚══██╔══╝██║    ██║██╔══██╗██║╚══██╔══╝██╔════╝██╔══██╗", C.BMAGENTA))
    print(col("  ██║  ███╗███████║██║   ██║███████╗   ██║   ██║ █╗ ██║██████╔╝██║   ██║   █████╗  ██████╔╝", C.BMAGENTA))
    print(col("  ██║   ██║██╔══██║██║   ██║╚════██║   ██║   ██║███╗██║██╔══██╗██║   ██║   ██╔══╝  ██╔══██╗", C.BMAGENTA))
    print(col("  ╚██████╔╝██║  ██║╚██████╔╝███████║   ██║   ╚███╔███╔╝██║  ██║██║   ██║   ███████╗██║  ██║", C.BMAGENTA))
    print(col("   ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝    ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝", C.BMAGENTA))
    print()
    print(col("  👻  The AI that haunts your codebase and fixes it.", C.DIM + C.MAGENTA))
    print()

def render_finding(f, idx):
    sev   = f.get("severity", "low")
    sc    = SEVERITY_COLOR.get(sev, C.BWHITE)
    si    = SEVERITY_ICON.get(sev, "•")
    cat   = f.get("category", "")
    cat_e = CATEGORIES.get(cat, "").split()[0] if cat in CATEGORIES else "•"

    print()
    print(col(f"  {si} [{f.get('id','GW-???')}]  {f.get('title','')}", C.BOLD + sc))
    print(col(f"     {cat_e} {cat.upper()}  ·  {sev.upper()}  ·  {f.get('file','')}:"
              f"{f.get('line_start','')}",  C.GRAY))
    print()

    ghost = f.get("ghost_voice", "")
    if ghost:
        iprint(f'"{ghost}"', indent=5, color=C.ITALIC + C.MAGENTA)
        print()

    iprint(f.get("description",""), indent=5, color=C.BWHITE)

    if f.get("fix_description"):
        print()
        iprint("Fix: " + f["fix_description"], indent=5, color=C.BGREEN)

    if f.get("original_code") and f.get("fixed_code"):
        print()
        print(col("     Before:", C.BRED))
        for line in f["original_code"].strip().split("\n")[:8]:
            print(col("     - " + line, C.RED))
        print(col("     After:", C.BGREEN))
        for line in f["fixed_code"].strip().split("\n")[:8]:
            print(col("     + " + line, C.GREEN))

def render_summary(ghost_summary, findings):
    print()
    hr("═", C.BMAGENTA)
    print(col("  👻  THE GHOST SPEAKS", C.BOLD + C.BMAGENTA))
    hr("─", C.GRAY)
    print()
    iprint(ghost_summary, indent=4, color=C.ITALIC + C.BMAGENTA)
    print()
    hr("─", C.GRAY)

    cats = defaultdict(int)
    sevs = defaultdict(int)
    for f in findings:
        cats[f.get("category","?")] += 1
        sevs[f.get("severity","?")] += 1

    print(col(f"  Total findings: {col(str(len(findings)), C.BOLD + C.BWHITE)}", C.GRAY))
    for sev in ["critical","high","medium","low"]:
        n = sevs.get(sev, 0)
        if n:
            sc = SEVERITY_COLOR.get(sev, C.BWHITE)
            print(f"    {SEVERITY_ICON[sev]}  {col(sev.capitalize().ljust(10), sc)} {col(str(n), C.BOLD + sc)}")
    hr("═", C.BMAGENTA)

# ─── Apply Fixes ───────────────────────────────────────
def apply_fixes(findings: list, root: Path, dry_run: bool = False) -> list:
    applied = []
    for f in findings:
        if not f.get("original_code") or not f.get("fixed_code"): continue
        if f["original_code"].strip() == f["fixed_code"].strip(): continue

        fpath = root / f["file"]
        if not fpath.exists(): continue

        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
            orig = f["original_code"].strip()
            fixed = f["fixed_code"].strip()

            if orig in content:
                new_content = content.replace(orig, fixed, 1)
                if not dry_run:
                    fpath.write_text(new_content, encoding="utf-8")
                applied.append(f)
                icon = "🔍" if dry_run else "✅"
                print(col(f"  {icon}  {'[DRY RUN] ' if dry_run else ''}Fixed: "
                          f"{f['file']}  [{f['id']}]", C.BGREEN if not dry_run else C.BYELLOW))
            else:
                print(col(f"  ⚠️   Could not locate exact code for {f['id']} in {f['file']}", C.YELLOW))
        except Exception as e:
            print(col(f"  ❌  Error patching {f['file']}: {e}", C.BRED))

    return applied

# ─── GitHub PR ─────────────────────────────────────────
def create_github_pr(root: Path, findings: list, pr_title: str,
                     pr_body: str, gh_token: str) -> str:
    """Create a GitHub PR via git + GitHub API."""
    import urllib.parse

    # Get remote origin
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True, text=True, cwd=root
    )
    if result.returncode != 0:
        raise RuntimeError("Not a git repo or no remote origin set.")

    remote = result.stdout.strip()
    # Extract owner/repo from HTTPS or SSH URL
    import re
    m = re.search(r'github\.com[:/]([^/]+)/([^/.]+)', remote)
    if not m:
        raise RuntimeError(f"Could not parse GitHub remote: {remote}")
    owner, repo = m.group(1), m.group(2)

    # Create branch
    branch = f"ghostwriter/{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    subprocess.run(["git", "checkout", "-b", branch], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", f"👻 {pr_title}"], cwd=root, check=True)

    # Push
    subprocess.run(
        ["git", "push", "origin", branch],
        cwd=root, check=True,
        env={**os.environ, "GIT_ASKPASS": "echo", "GIT_TERMINAL_PROMPT": "0"}
    )

    # Create PR via API
    payload = json.dumps({
        "title": f"👻 {pr_title}",
        "body":  pr_body,
        "head":  branch,
        "base":  "main",
    }).encode()

    req = urllib.request.Request(
        f"https://api.github.com/repos/{owner}/{repo}/pulls",
        data=payload, method="POST",
        headers={
            "Authorization": f"token {gh_token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        }
    )
    with urllib.request.urlopen(req) as r:
        data = json.loads(r.read())
        return data["html_url"]

# ─── Config ────────────────────────────────────────────
CONFIG_PATH = Path.home() / ".ghostwriter" / "config.json"

def load_config() -> dict:
    cfg = {}
    # Env vars
    cfg["anthropic_key"] = os.environ.get("ANTHROPIC_API_KEY","")
    cfg["github_token"]  = os.environ.get("GITHUB_TOKEN","")

    if CONFIG_PATH.exists():
        try:
            saved = json.loads(CONFIG_PATH.read_text())
            cfg["anthropic_key"] = cfg["anthropic_key"] or saved.get("anthropic_key","")
            cfg["github_token"]  = cfg["github_token"]  or saved.get("github_token","")
        except Exception:
            pass
    return cfg

def save_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))

def ensure_keys(cfg: dict, need_github: bool = False) -> dict:
    if not cfg.get("anthropic_key"):
        print(col("\n  🔑  Anthropic API key needed.", C.BYELLOW))
        print(col("  Get it free at: https://console.anthropic.com/\n", C.GRAY))
        cfg["anthropic_key"] = input(col("  Paste key: ", C.BCYAN)).strip()
    if need_github and not cfg.get("github_token"):
        print(col("\n  🔑  GitHub token needed for PR creation.", C.BYELLOW))
        print(col("  Create one at: https://github.com/settings/tokens (needs repo scope)\n", C.GRAY))
        cfg["github_token"] = input(col("  Paste token: ", C.BCYAN)).strip()
    save_config(cfg)
    return cfg

# ─── Build file dump for prompt ────────────────────────
def build_file_dump(files: dict, max_chars: int = 80_000) -> str:
    parts = []
    total = 0
    for path, info in sorted(files.items()):
        chunk = f"\n=== FILE: {path} ===\n{info['content']}\n"
        if total + len(chunk) > max_chars:
            parts.append(f"\n=== FILE: {path} === (omitted — size limit)\n")
        else:
            parts.append(chunk)
            total += len(chunk)
    return "".join(parts)

# ─── Main Agent ────────────────────────────────────────
def haunt(root: Path, api_key: str, focus: str = "all",
          max_findings: int = 10, dry_run: bool = False,
          open_pr: bool = False, github_token: str = "") -> dict:

    render_splash()

    print(col(f"  👻  Haunting: {root}", C.BOLD + C.BWHITE))
    print(col(f"  📅  {datetime.now().strftime('%B %d, %Y %H:%M')}", C.GRAY))
    if dry_run:
        print(col("  🔍  DRY RUN — no files will be modified", C.BYELLOW))
    hr()

    # Scan
    sp = Spinner("Scanning files")
    sp.start()
    files = scan_project(root)
    sp.stop(col(f"  📂  Scanned {len(files)} files", C.BGREEN))

    if not files:
        print(col("  ❌  No code files found.", C.BRED))
        return {}

    # Print manifest
    print()
    for path in sorted(files.keys())[:15]:
        print(col(f"       {path}", C.GRAY))
    if len(files) > 15:
        print(col(f"       ... and {len(files)-15} more", C.GRAY))
    print()
    hr()

    # Build focus string
    if focus == "all":
        focus_str = ", ".join(CATEGORIES.keys())
    else:
        focus_str = focus

    # Build prompt
    file_dump = build_file_dump(files)
    prompt = ANALYSIS_PROMPT.format(
        focus=focus_str,
        file_dump=file_dump,
        max_findings=max_findings
    )

    # Call Claude
    print()
    sp = Spinner("The ghost is reading your code", color=C.BMAGENTA)
    sp.start()
    try:
        raw = claude(
            [{"role": "user", "content": prompt}],
            GHOST_SYSTEM, api_key, max_tokens=8000
        )
    except Exception as e:
        sp.stop()
        print(col(f"  ❌  {e}", C.BRED))
        return {}
    sp.stop(col("  👻  The ghost has spoken.", C.BMAGENTA))

    # Parse
    try:
        result = parse_json(raw)
    except Exception as e:
        print(col(f"  ❌  Could not parse response: {e}", C.BRED))
        print(col(raw[:500], C.GRAY))
        return {}

    findings      = result.get("findings", [])
    ghost_summary = result.get("ghost_summary", "I have seen things you cannot imagine.")
    pr_title      = result.get("pr_title", "👻 Ghostwriter haunted your codebase")
    pr_body       = result.get("pr_body", "")

    if not findings:
        print(col("\n  ✅  The ghost found nothing. Your codebase is surprisingly clean.\n", C.BGREEN))
        return result

    # Render findings
    print()
    print(col(f"  👻  FINDINGS  ({len(findings)} issues)", C.BOLD + C.BMAGENTA))
    hr("═", C.BMAGENTA)

    for i, f in enumerate(findings, 1):
        render_finding(f, i)
        hr("·", C.GRAY)

    # Summary
    render_summary(ghost_summary, findings)

    # Apply fixes
    print()
    print(col("  🔧  Applying fixes...", C.BOLD + C.BWHITE))
    applied = apply_fixes(findings, root, dry_run=dry_run)
    n_fixed = len(applied)
    n_total = len([f for f in findings if f.get("original_code")])

    print()
    if dry_run:
        print(col(f"  🔍  {n_fixed}/{n_total} fixes previewed (dry run — nothing changed)", C.BYELLOW))
    else:
        print(col(f"  ✅  {n_fixed}/{n_total} fixes applied to disk", C.BGREEN))

    # PR
    if open_pr and not dry_run:
        if not github_token:
            print(col("\n  ⚠️   No GitHub token. Skipping PR creation.", C.YELLOW))
        else:
            print()
            sp = Spinner("Creating GitHub PR", color=C.BCYAN)
            sp.start()
            try:
                pr_url = create_github_pr(root, applied, pr_title, pr_body, github_token)
                sp.stop(col(f"  🎉  PR opened: {pr_url}", C.BGREEN))
            except Exception as e:
                sp.stop()
                print(col(f"  ❌  PR failed: {e}", C.BRED))

    # Save report
    report_path = root / f"ghostwriter_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    if not dry_run:
        report_path.write_text(json.dumps(result, indent=2))
        print(col(f"\n  💾  Report saved: {report_path.name}", C.GRAY))

    print()
    hr("═", C.BMAGENTA)
    print(col("  👻  Haunting complete. The ghost rests.", C.ITALIC + C.MAGENTA))
    hr("═", C.BMAGENTA)
    print()

    return result

# ─── CLI ───────────────────────────────────────────────
HELP = f"""
{col('👻 ghostwriter', C.BOLD + C.BMAGENTA)} — The AI that haunts your codebase and fixes it.

{col('USAGE', C.BOLD)}
  python ghostwriter.py <path>                  Haunt a project
  python ghostwriter.py <path> --dry-run        Preview fixes only
  python ghostwriter.py <path> --pr             Apply fixes + open GitHub PR
  python ghostwriter.py <path> --focus <cat>    Focus on one category
  python ghostwriter.py --setup                 Save API keys

{col('CATEGORIES', C.BOLD)}
  security   dead_code   bugs   style   performance   docs   tests

{col('EXAMPLES', C.BOLD)}
  python ghostwriter.py .
  python ghostwriter.py ./myapp --dry-run
  python ghostwriter.py . --focus security
  python ghostwriter.py . --pr --findings 15

{col('ENV VARS', C.BOLD)}
  ANTHROPIC_API_KEY    Your Anthropic key (console.anthropic.com)
  GITHUB_TOKEN         GitHub personal access token (for --pr)
"""

def main():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("path",      nargs="?", default=".")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--pr",      action="store_true")
    p.add_argument("--setup",   action="store_true")
    p.add_argument("--focus",   default="all")
    p.add_argument("--findings",type=int, default=10)
    p.add_argument("--help",    action="store_true")
    args = p.parse_args()

    if args.help:
        render_splash()
        print(HELP)
        return

    cfg = load_config()

    if args.setup:
        render_splash()
        print(col("  🔑  Setup\n", C.BOLD + C.BMAGENTA))
        cfg["anthropic_key"] = input(col("  Anthropic API key: ", C.BCYAN)).strip() or cfg.get("anthropic_key","")
        cfg["github_token"]  = input(col("  GitHub token (optional): ", C.BCYAN)).strip() or cfg.get("github_token","")
        save_config(cfg)
        print(col(f"\n  ✅  Saved to {CONFIG_PATH}\n", C.BGREEN))
        return

    cfg = ensure_keys(cfg, need_github=args.pr)
    root = Path(args.path).resolve()

    if not root.exists():
        print(col(f"\n  ❌  Path not found: {root}\n", C.BRED))
        sys.exit(1)

    haunt(
        root=root,
        api_key=cfg["anthropic_key"],
        focus=args.focus,
        max_findings=args.findings,
        dry_run=args.dry_run,
        open_pr=args.pr,
        github_token=cfg.get("github_token",""),
    )

if __name__ == "__main__":
    main()
