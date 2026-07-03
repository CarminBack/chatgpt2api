# Codex Project Rules

## Image3 Custom Maintenance

- Before changing image3 custom authentication, billing, deployment, or token2/sub2api integration behavior, read `docs/CODEX_IMAGE3_CUSTOM.md`.
- If a change adds a feature, changes behavior, changes runtime requirements, changes deployment steps, changes validation steps, or makes this document inaccurate, update `docs/CODEX_IMAGE3_CUSTOM.md` in the same commit.
- Do not commit runtime secrets, real API keys, database DSNs with credentials, production admin keys, or customer/user tokens. Use placeholders or environment variable names.
- Keep image3 custom changes easy to rebase onto upstream `basketikun/chatgpt2api`: prefer isolated service modules and small API integration points.
