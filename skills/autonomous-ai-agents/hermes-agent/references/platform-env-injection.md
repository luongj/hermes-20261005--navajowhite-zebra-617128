# Platform-injected environment variables (managed / Hermes Agent deployments)

In managed deployments (Hermes Agent behind a control panel that injects env, e.g. hPanel →
Environment), variables are applied to the **gateway process** at container start.

## The quirk
- A variable added/changed in the panel takes effect only after the **gateway is restarted**.
- It is visible in the **gateway process's own environment** but is **NOT inherited by the agent's
  tool subprocesses**: `terminal` and the `execute_code` kernel run under a filtered environment.
- Consequence: `os.environ.get("VAR")` in `execute_code`, or `$VAR` in a `terminal` shell, can return
  empty/absent immediately after a restart that DID inject the variable. This is not a save failure.

## Read it from the gateway when a subprocess needs it
Confirm presence and pull the value without leaking it:
```bash
GPID=$(pgrep -f 'gateway run' | head -1)
VAR=$(tr '\0' '\n' < /proc/$GPID/environ | grep '^VAR=' | cut -d= -f2-)
# pipe straight into the consumer; never echo the value
printf 'https://x-access-token:%s@github.com\n' "$VAR" > ~/.git-credentials
```

## Pitfall (generalizable)
When a newly-added platform env var appears missing from the agent's shell/Python, check the gateway
process's own `/proc/<pid>/environ` before treating it as not set — tool subprocesses filter the env;
the gateway does not. Diagnose presence/absence there, not from `os.environ`.

## Token hygiene
- Check presence without printing the value: `python3 -c 'import os; print(os.environ.get("VAR") is not None)'`.
  In a subprocess this reports absent even when the gateway has it — use `/proc` to disambiguate.
- Pipe the value into the consuming command; do not write it to command-line args or echo it to logs.
- chmod 600 any file that stores the value (e.g. `~/.git-credentials`).
