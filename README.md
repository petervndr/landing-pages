# Landing Pages

Agent plugin for client landing-page funnels. Build standalone HTML, QC it, paste into GoHighLevel.

Hand this repo to an agent and say: **install this landing-pages plugin into my workspace.**

Repo: https://github.com/petervndr/landing-pages

Works in Cursor, Claude Code, Codex, and any harness that loads [Agent Skills](https://agentskills.io/specification) or [Agent Plugins](https://agent-plugins.org/).

## Pipeline

`client-funnel-pages` → `funnel-qc` → `deploy-ghl`

The only deploy path is GoHighLevel.

| Skill | Job |
| --- | --- |
| `client-funnel-pages` | Build host-agnostic standalone HTML |
| `funnel-qc` | Independent verifier. Fresh context. Report only. |
| `deploy-ghl` | Paste a SHIP'd funnel into GoHighLevel |

## Install (for agents)

Clone this repository if it is not already on disk. Then run the installer against the **host workspace** (the user's project, not this clone):

```bash
git clone https://github.com/petervndr/landing-pages.git
cd landing-pages
./scripts/install.sh --project /path/to/host-workspace
```

That links the three skills into `<host>/.agents/skills/`.

- Claude Code: add `--claude` (also links `.claude/skills/`).
- Cursor user plugin: add `--cursor-local`, then reload the window.

Confirm `client-funnel-pages`, `funnel-qc`, and `deploy-ghl` resolve under `.agents/skills/`. Then stop.

The host still has to supply brand kits and client facts. Read `WORKSPACE.md`.

## What this folder is

```
landing-pages/
├── plugin.json                 Agent Plugins 1.0.0 (portable core)
├── .cursor-plugin/plugin.json  Cursor extras (rules, commands)
├── .claude-plugin/plugin.json  Claude Code plugin
├── skills/                     Three Agent Skills
├── commands/                   Slash commands
├── rules/                      Cursor pipeline router
├── AGENTS.md                   Install recipe + pipeline
└── WORKSPACE.md                Host paths and tools
```

Slash commands: `/client-funnel-pages`, `/funnel-qc`, `/deploy-ghl`.
