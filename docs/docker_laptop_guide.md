# Run Makan Where on another laptop

This setup runs the website, MariaDB and MongoDB locally using Docker Compose. Python database operations remain in the project code: SQLAlchemy/PyMySQL for MariaDB and PyMongo for MongoDB. No DBStudios, separate database installation, server VPN, production credentials or external data API is required.

## What you need

- The complete project folder, including `data/`, `database/` and the retained source CSV/JSON files. Copy source files, not `.env.demo`, `.env.laptop`, `.venv`, `work`, or anyone else's database volumes.
- [Docker Desktop](https://docs.docker.com/desktop/) running Linux containers on Windows/macOS, or Docker Engine with Compose on Linux. Windows installation/WSL requirements are in [Docker's installation guide](https://docs.docker.com/desktop/setup/install/windows-install/).
- Internet for the first image/package download. Catalogue/menu fixtures are retained locally; remote photographs and fonts still need internet to display.
- Allow roughly 6 GB free RAM and 10 GB disk for the app and evaluation engines. Actual resource use depends on the machine. The evaluation starts two additional, isolated database containers.

Check `docker version` shows both Client and Server, and `docker compose version` works. Use `compose.laptop.yaml` for this guide; the older `compose.yaml` remains the database-only setup for host Python development.

## 1. Generate private local settings once

Open a terminal in the project folder. These commands use Python inside a container, so host Python is optional.

Windows PowerShell:

```powershell
docker run --rm --mount "type=bind,source=$($PWD.Path),target=/workspace" --workdir /workspace python:3.12-slim python scripts/configure_laptop.py
```

macOS/Linux:

```bash
docker run --rm --user "$(id -u):$(id -g)" --mount "type=bind,source=$(pwd),target=/workspace" --workdir /workspace python:3.12-slim python scripts/configure_laptop.py
```

If Python is already installed, `python scripts/configure_laptop.py` is equivalent. The script creates `.env.laptop` with fresh random secrets and separate administrator/user passwords. Rerunning preserves the existing file. Keep the file with this installation: changing the password pepper or database passwords while retaining old volumes can break login or database access. It is ignored by Git and excluded from the image.

## 2. Build and start everything

The same command works in both shells:

```text
docker compose --env-file .env.laptop -f compose.laptop.yaml up --build -d --wait --wait-timeout 600
docker compose --env-file .env.laptop -f compose.laptop.yaml ps -a
```

The setup job waits for healthy databases, creates the current schema/validators/indexes, runs the resumable coursework population, adds retained listing details and imports the two attributed reference menus through the application's validated import path. It creates the two lecturer accounts once. The app starts only after setup succeeds. [Compose's dependency conditions](https://docs.docker.com/compose/how-tos/startup-order/) distinguish database health from successful setup completion.

Expect `setup` to show **Exited (0)** and `app`, `mariadb`, `mongodb` to be healthy. Setup may take several minutes, especially while hashing passwords. Reruns preserve existing accounts, source identities, user edits and removed items.

Open:

| View | Default local link |
| --- | --- |
| Website | <http://localhost:5056/> |
| Administrator | <http://localhost:5056/auth.html?next=admin.html> |
| Database evidence | <http://localhost:5056/database-lab.html> |
| Normal user | <http://localhost:5056/auth.html?mode=login> |
| Both-engine health | <http://localhost:5056/api/health> |

Read `.env.laptop` in your editor:

| Access | Username key | Password key |
| --- | --- | --- |
| Administrator | `LECTURER_ADMIN_USERNAME` (default `lecturer_admin`) | `LECTURER_ADMIN_PASSWORD` |
| Normal user | `LECTURER_USER_USERNAME` (default `lecturer_user`) | `LECTURER_USER_PASSWORD` |

These accounts belong to this laptop. Share only these two account details when needed, not the entire env file. Use separate browser profiles or an incognito window to compare permissions. Registering through the public form cannot grant administrator access.

The default website port is **5056**, avoiding the older host-Python preview on 5055. Change `APP_PORT` in `.env.laptop` if needed and rerun `up`. The website binds to loopback; MariaDB/MongoDB publish no host ports. All database queries run in Python code over the private Compose network. SQL and Mongo credentials passed to the app have access to the application databases; root credentials are not passed to the web process.

## 3. Reproduce the lecturer's requested evaluation

```text
docker compose --env-file .env.laptop -f compose.laptop.yaml --profile evaluation run --build --rm evaluate
```

This runs the full regression suite and the focused database experiments against **real MariaDB and MongoDB** in separate `test-sql` / `test-mongo` containers. Each test creates unique disposable database names; the test engines do not use the app's data volumes. The runner exits nonzero on failures or missing-engine skips, and records actual engine/package versions, invariants, observations, source hash, workload, plans and timing samples.

| Lecturer priority | Evidence produced |
| --- | --- |
| MongoDB operations | Review/thread/reply lifecycle, ownership, validation, aggregation, atomic rejection of invalid document updates, votes and moderation |
| Cross-database behaviour | SQL reference checks before Mongo writes, six broken-reference audits, archive visibility, SQL failure blocking a Mongo insert |
| Concurrency/recovery | Six-worker writes, unique vote/favourite pairs and content IDs, one moderation winner, partial population resume, rollback/reconnect and ambiguous acknowledgement limits |
| Controlled benchmarks | About 30,000 records per engine, identical results, three warm-ups, 20 alternating paired samples, median/p95, plans, Mongo execution statistics and MariaDB `ANALYZE FORMAT=JSON` |

Open **Database evidence -> Correctness & measured performance**, then refresh. The app reads the generated JSON from a shared evidence volume mounted read-only in the web container. No earlier machine's passing artifact is baked into the image. Running live constraint checks in the page is separate from the isolated load/failure tests.

Export using the page's combined JSON button, or copy the raw artifact:

```text
docker compose --env-file .env.laptop -f compose.laptop.yaml cp app:/evidence/database-evaluation.json ./database-evaluation-laptop.json
docker compose --env-file .env.laptop -f compose.laptop.yaml --profile evaluation stop test-sql test-mongo
```

Keep results with their machine/date/source version. A stale-source label means rebuild the images and rerun the evaluation. A passing test that records an acknowledged-write ambiguity establishes that limitation; it does not establish retry safety. Standalone MongoDB and independent SQL/Mongo commits do not provide distributed transactions or replica failover.

MariaDB's [ANALYZE FORMAT=JSON](https://mariadb.com/docs/server/reference/sql-statements/administrative-sql-statements/analyze-and-explain-statements/analyze-format-json) executes the SELECT and adds observed row/loop statistics. Ordinary EXPLAIN remains an estimated plan. Benchmark timings describe the stated workload and machine, not general production capacity or a SQL-versus-NoSQL race.

## Stop, restart and retain data

```text
docker compose --env-file .env.laptop -f compose.laptop.yaml stop
docker compose --env-file .env.laptop -f compose.laptop.yaml start
```

To remove containers while keeping the named database/evidence volumes:

```text
docker compose --env-file .env.laptop -f compose.laptop.yaml --profile evaluation down
```

Run the `up --build` command again to recreate containers with the retained data. Keep the same `.env.laptop` and Compose project name. **Do not add `--volumes` / `-v` to `down` unless you intend to permanently erase this local installation's database volumes.** Stopping containers is not a backup; a machine/volume loss still loses local data.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Docker reports Client but no Server / named-pipe failure | Open Docker Desktop, wait for Linux engine readiness, check its startup error. Do not reset its data to fix an app login problem. |
| Port 5056 is occupied | Pick another `APP_PORT`, rerun `up`, use that port in the URL. |
| Setup exits nonzero | Run the logs command below. Preserve volumes; fix the cause and rerun `up --build`. |
| Database access denied after changing env | Restore the env file used to initialise the retained volumes. Official database images initialise users only on first creation of an empty data directory. |
| Login fails | Use the matching laptop passwords. A retained account is not silently reset by setup. Keep the original pepper. Use `localhost` consistently for session cookies. |
| Evaluation is missing | Run the evaluation profile. `up` deliberately does not run load/fault tests. |
| Evaluation fails | Keep the JSON/logs and fix the failed invariant. Do not present an older successful run as evidence for new code. |
| ARM laptop or different machine | Images select their supported native architecture. Repeat all tests there; a Windows/amd64 result is not an Apple Silicon test result. |

```text
docker compose --env-file .env.laptop -f compose.laptop.yaml logs --tail 100 setup app
docker compose --env-file .env.laptop -f compose.laptop.yaml logs --tail 100 mariadb mongodb
```

The proposed normalised menu redesign in `database/design_v2.py` remains a separate validated proposal. This portable build runs the existing implemented application schema; it does not silently migrate to the proposal. Refer to the appended verification record for the environments and checks actually exercised.

## Verification status and code updates

On 16 October 2026, Compose configuration validation passed and **82 tests passed against native Windows MariaDB 11.4.13/MongoDB 8.0.19**. The same setup script completed twice with identical row/document counts and lecturer password hashes. **The Docker image/container flow is not yet runtime-verified:** this computer's Docker Desktop crashed in its internal listener startup. These native results are not a substitute for running the commands above on a working Docker engine. See the [dated verification record](verification_record.md#lecturer-feedback-and-portable-setup-verification---16-october-2026).

For later code updates, stop the app before setup/migrations and rebuild:

```text
docker compose --env-file .env.laptop -f compose.laptop.yaml stop app
docker compose --env-file .env.laptop -f compose.laptop.yaml up --build -d --wait --wait-timeout 600
```

Then rerun the evaluation profile so its artifact matches the new source. Keep the same private env file and retained volumes.
