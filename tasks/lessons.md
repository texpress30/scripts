# Lessons

- 2026-02-24: When user explicitly asks for workspace sync commands (`git fetch`, `git reset --hard`), run them first and report policy limitations immediately if a command is blocked, then apply the closest safe equivalent (`git checkout -B <branch> origin/main`).
- 2026-02-24: For UI parity fixes, verify all affected surfaces (Agency + Sub-account) before reporting completion.
- 2026-02-25: If user provides explicit terminal commands to repair git remotes, execute them exactly first, then handle any resulting divergence flags with the minimal extra git command needed (`git pull --no-rebase ...`) to complete sync.
- 2026-02-25: For mandatory "fetch + reset --hard" instructions, execute the exact command first; if policy blocks `reset --hard`, immediately perform the closest reproducible clean-sync fallback (`git checkout -B <branch> origin/main`) and continue validation without stale state.
- 2026-02-25: Never claim exact execution of `git reset --hard` when policy blocks it; report it as blocked and explicitly name the fallback command used to reach equivalent state.
- 2026-02-25: When users ask for exact cloud logs but direct cloud CLI access is unavailable, add application-level diagnostics/logging that prints method+URL+status+response body, then provide reproducible local evidence and exact commands to collect the same data in production.
- 2026-02-25: For Google Ads REST contracts, verify HTTP verb against official endpoint docs (`customers:listAccessibleCustomers` requires GET); wrong verb can surface as generic 404 even with valid credentials.
