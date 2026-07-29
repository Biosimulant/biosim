# Unified Biosimulant CLI

The `biosimulant` Python package owns one headless CLI for Desktop, Studio,
local terminals, CI, servers, and containers. There is no separate command
extension package or Desktop CLI implementation.

The public CLI owns simulation, lab, package, registry, authentication, and
managed-runtime operations. Run `biosimulant commands list --json` for the
machine-readable catalog.

Desktop remains a graphical client. Window management, navigation,
notifications, visual settings, and Desktop persistence are ordinary private
application code rather than public commands. Desktop invokes the pinned PyPI
CLI for operations such as validation, runs, pull, and publish.

Registry credentials are stored independently by registry origin. The CLI
checks an operation-scoped environment token, a configured credential helper,
an OS keychain when available, and finally an owner-only credential file.
Headless login accepts tokens through standard input:

```bash
printf '%s\n' "$TOKEN" | biosimulant auth login registry.example.com --token-stdin
```

Machine consumers should use the versioned JSON envelope:

```json
{
  "ok": true,
  "data": {},
  "error": null,
  "meta": {
    "schemaVersion": "1",
    "command": "doctor",
    "cliVersion": "0.0.22"
  }
}
```

For the first unified-CLI migration release only,
`--legacy-json=bare` preserves the previous Python payload shape and
`--legacy-json=desktop` preserves the former Desktop `{ok,data,error,meta}`
envelope. New integrations must use `--json` or `--json-stream`; the legacy
adapters are scheduled for removal after one complete release.
