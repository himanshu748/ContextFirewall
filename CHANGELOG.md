# Changelog

All notable changes to ContextFirewall are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) once it reaches 1.0.

## [Unreleased]

### Security
- Graph nodes that Cognee derives from a transcript are tagged with the namespace that produced
  them; untagged or multi-namespace nodes are hidden unless the caller may read every namespace
  involved ([#35](https://github.com/himanshu748/ContextFirewall/pull/35)).
- Admin and write tokens are compared in constant time, and the write gate fails closed when no
  token is configured ([#30](https://github.com/himanshu748/ContextFirewall/pull/30)).
- The graph view filters by namespace before applying `limit`, reports truncation, and no longer
  returns exception details ([#50](https://github.com/himanshu748/ContextFirewall/pull/50)).
- `forget_memory` resolves a memory ID within the caller's namespace, and orphan cleanup no longer
  touches other namespaces' sessions ([#61](https://github.com/himanshu748/ContextFirewall/pull/61)).
- Forgetting another namespace's memory ID returns the same `not_found` response as a missing ID,
  so callers can't learn that it exists or who owns it
  ([#64](https://github.com/himanshu748/ContextFirewall/pull/64)).

### Privacy
- Cognee product telemetry is disabled by default; set `TELEMETRY_DISABLED=0` to opt in
  ([#60](https://github.com/himanshu748/ContextFirewall/pull/60)).

### Fixed
- Staleness checks no longer crash when timestamps mix timezone-aware and date-only values
  ([#33](https://github.com/himanshu748/ContextFirewall/pull/33)).
- `remember()` stores a full UTC timestamp, so same-day updates supersede each other
  ([#54](https://github.com/himanshu748/ContextFirewall/pull/54)).
- Fresh installs work again: `mcp` is pinned below 2.0, which removed `FastMCP`
  ([#51](https://github.com/himanshu748/ContextFirewall/pull/51)).

### Documentation
- Contributor guide, Code of Conduct, security policy, issue forms, PR template, and CI for
  backend tests and the frontend build ([#11](https://github.com/himanshu748/ContextFirewall/pull/11)).
- Configuration reference for every backend and frontend environment variable
  ([#34](https://github.com/himanshu748/ContextFirewall/pull/34)).
- Privacy boundaries of the local MCP client
  ([#53](https://github.com/himanshu748/ContextFirewall/pull/53)) and community contributor
  credits ([#57](https://github.com/himanshu748/ContextFirewall/pull/57)).

### Changed
- The Hugging Face deploy runs only after the full CI suite passes. CI also imports the app,
  tests the MCP stdio package on Python 3.10, pins actions to commit SHAs, and Dependabot keeps
  dependencies current.

## [0.1.0] - 2026-07-25

Initial release, built for the WeMakeDevs × Cognee hackathon.

### Added
- Four firewall checks (staleness, contradiction, secrets, evidence) and the trusted context pack.
- Six MCP tools over hosted streamable HTTP and a local `uvx` stdio package.
- Multi-tenant namespaces with Supabase Auth and per-account API keys.
- Next.js console with knowledge graph, session replay, and a live MCP activity feed.
- Cognee remember, recall, improve (coding rules), and forget lifecycle.

[Unreleased]: https://github.com/himanshu748/ContextFirewall/compare/e43d7b4...HEAD
[0.1.0]: https://github.com/himanshu748/ContextFirewall/tree/e43d7b4
