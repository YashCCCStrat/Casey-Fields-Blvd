# Working rules for AI assistants in this repository

The owner set these rules (carried over from YashCCCStrat/Contribution-Plans); they apply to every session.

## Git
- **GitHub has one branch, `main`.** Never push any other branch, never open a pull request, and never force-push `main`.
- **Commits are authored and committed by the owner:** `Yashar <yjamei@casey.vic.gov.au>`. Set it in the repository's local git config if it isn't. Do not add `Co-Authored-By`, `Claude-Session` or any other assistant trailer or footer to commit messages.
- Push only work that passes its checks.

## Data
- **This repository is private, but treat it as shareable.** Never commit Casey-internal data: levy payments, works-in-kind or s173 agreements, landowner or parcel-ownership details, draft documents not yet public, or licensed data (forecast.id, DEECA-licensed extracts). Keep them in `data/private/` (git-ignored).
- Plan documents and GIS layers here are public (gazetted plans; Vicmap and VPA open data, CC BY 4.0; OpenStreetMap/Overture, ODbL; symbology CC0 / CC BY-SA as noted in `symbology/`).
- Do not reverse-engineer or probe third-party platforms. Use public pages and documents only.
- Page numbers given by the owner are the plan's **printed** page numbers unless stated otherwise.

## Docs travel with code
- A user-visible change adds a line to `CHANGELOG.md`.
- A method change updates `docs/HOW_IT_WORKS.md`.
- A decision goes in `docs/PROJECT_LOG.md`.
- A change to how things fit together updates `docs/ARCHITECTURE.md`.
