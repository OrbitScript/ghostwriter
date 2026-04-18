# Changelog

## [1.0.0] - 2026-04-18

### Added
- 👻 Agentic AI that reads full codebase and finds real issues
- 7 finding categories: security, dead_code, bugs, style, performance, docs, tests
- Ghost persona with darkly funny narration per finding
- Automatic code patching — writes fixes directly to disk
- `--dry-run` mode to preview without changing files
- `--pr` mode to create GitHub branch + pull request automatically
- `--focus` flag to target specific issue categories
- `--findings` flag to control max issues returned
- API key setup wizard saved to `~/.ghostwriter/config.json`
- JSON report saved after each run
- Spinner animations during scan and API calls
- File size limits and truncation for large codebases
