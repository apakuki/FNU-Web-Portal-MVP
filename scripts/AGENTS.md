# Scripts

Shell scripts for starting and stopping the full Docker Compose stack.

## Files

| Script | Platform | Purpose |
|--------|----------|---------|
| `start.sh` | Mac / Linux | Start all services (frontend, backend, postgres, proxy) |
| `start.bat` | Windows | Same, Windows batch |
| `stop.sh` | Mac / Linux | Stop all services |
| `stop.bat` | Windows | Same, Windows batch |

## Conventions

- Scripts run from the project root directory
- They invoke `docker compose` (v2 syntax, not `docker-compose`)
- `start` scripts build images if needed, then run in detached mode
- `stop` scripts run `docker compose down` (volumes preserved by default)
- Exit with clear error messages if Docker is not installed or not running
- No elevated permissions required (no `sudo`)

## Environment

Scripts expect a `.env` file in the project root with all required secrets. See `backend/AGENTS.md` for the variable list.
