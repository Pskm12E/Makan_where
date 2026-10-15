# Existing-server update

## Current release — combined database evidence, 4 October 2026

The live release is `/srv/makanwhere/releases/020722529efc502a`. All **61 tests passed in 106.70 seconds** against MariaDB/MongoDB; backup: `/var/backups/makanwhere/20261004T084109Z`. The evidence page shares the main orange and cream theme, displays all six sections together and provides a single **Run all checks** action and combined export. Public-browser checks passed all nine constraint probes and three password checks. All six sections and 39 expanded details were visible in the document, with no desktop horizontal overflow or browser warnings/errors. The administrator display name is now `Administrator`; login credentials and role are unchanged. Generated/sample records remain labelled. Earlier release records below are historical.

## Lecturer access and database evidence — 4 October 2026

The live release is `/srv/makanwhere/releases/a8f205aec3849494`. All **61 tests passed in 105.59 seconds** against MariaDB/MongoDB; backup: `/var/backups/makanwhere/20261004T081338Z`. The app's evidence page is now labelled **Database evidence**, and obsolete DBStudios helper scripts are excluded. Direct SQL/PyMongo socket connections and service isolation were verified under the application identity. `demo_lecturer` is the admin review account and `lecturer_user` is the normal review account; generated passwords were delivered privately, not packaged. Both logins and the normal account's admin denial were verified. Earlier release records below are historical.

## Example conversations release — 4 October 2026

The live release is `/srv/makanwhere/releases/77d931deeec7ea3c`. All 61 tests passed on MariaDB/MongoDB in 112.33 seconds. Backup: `/var/backups/makanwhere/20261004T075256Z`. The private-environment CLI `flask --app backend.app seed-listing-examples --apply` added 12 labelled fictional reviews, eight threads and 16 replies on the four explicitly selected source listings. Repeat preview added zero; ratings and rankings exclude these examples. Public API/browser and reference checks passed; see the [verification record](../docs/verification_record.md). The earlier photo/menu deployment below records its original release and backup.

## Photo and listing update — 4 October 2026

Deployment completed on 4 October 2026. NetBird is connected, and the initial photo/menu release was `/srv/makanwhere/releases/11a89bf538af436a` with MariaDB 10.11.14 and MongoDB 8.0.19. All 59 tests passed on the VM in 106.33 seconds. Nine constraint probes passed under the application identity; the post-import reference audit found no orphans or duplicate source/vote identities. SQL, MongoDB and configuration backups are retained at `/var/backups/makanwhere/20261004T073435Z` on the app VM. Both neighbouring origins remained healthy.

The server's private menu-import key was generated without copying the local key. `deploy/import_reference_menus.py --apply`, run as root on the app VM, imported 6,984 KFC rows across 72 exact-name venues and 32 Suki-Ya rows across four venues through the running service's scoped API. Repeat previews proposed zero new rows. The helper connects over the local Unix socket and never prints the key. It can be rerun safely; without `--apply` it only previews once a key exists. The admin importer and `scripts/import_menus.py` remain available for further reviewed sources.

Public checks confirmed both database health indicators, 8,421 attributed illustrative photos, the KFC #9 menu, homepage image loading and unauthenticated API rejection. The live `demo_lecturer` administrator was provisioned on 4 October 2026 with a separate generated password delivered privately to the project owner. Login and protected schema access were verified through the running service; the verification session was logged out. Stored menu receipts and coverage were verified under the application database identity. Missing factual outlet details remain unknown. See [verification evidence](../docs/verification_record.md).

Target: https://makanwhere.4bytedigi.com/ through the saved SSH alias `4bytedigi` (NetBird), then the existing isolated `app` VM. This is an update to the existing project schema, not a fresh server installer. Do not copy `.env.demo`, local databases or demonstration administrator credentials to the server.

DBStudios is not an application database dependency. MariaDB and MongoDB are accessed directly by the Python drivers over local Unix sockets. The existing host SSH configuration and shared Cloudflare tunnel still have historical `dbstudios` names; neighbour health checks protect other websites on that host. These are infrastructure references, not database operations or a requirement to open the external dashboard. Obsolete DBStudios compatibility/inspection helpers have been removed from the project and release package. Keep deployment infrastructure intact unless deliberately migrating the shared host.

## Status on 28 September 2026

The local site is populated and browser-tested. The public origin still serves the earlier SQL-only release. Deployment has **not run**: NetBird reports `NeedsLogin`, so the saved SSH route times out. The prepared installer has local boundary tests; Linux service installation and the MariaDB/MongoDB integration must still be exercised on the actual VM. Do not treat the local SQLite evidence as MariaDB verification.

## Artifacts and preflight

1. Sign in to NetBird. Confirm `ssh -o BatchMode=yes -o ConnectTimeout=10 4bytedigi hostname` reaches the expected host; retain strict SSH host-key checking.
2. Inspect the `app` VM via `/etc/dbstudios-host/ssh_config`. This artifact supports Ubuntu 24.04, Python 3.12 and x86-64 with AVX. It requires at least 2 GB RAM, 2 GiB free disk and the official MongoDB shared libraries. Inspect capacity, existing app health and existing MongoDB services before installation. It stops on a mismatch.
3. `work/wheels` contains the application/test dependencies downloaded for Linux CPython 3.12. MongoDB's official archive is `https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-ubuntu2404-8.0.19.tgz`; its vendor SHA-256 is pinned in `mongo_service.py`. Keep the downloaded archive in `work/`.
4. Run `.venv/Scripts/python.exe deploy/build_release.py` on Windows. It packages reviewed source, both catalogue CSV paths, documentation and tests; fingerprints local JS/CSS; and copies the installer entrypoints alongside the archives. It excludes private environment files, runtime databases, generated evidence and local MongoDB credentials.
5. Transfer only these eight files from `work/` into a new private staging directory on `4bytedigi`: `release.tar.gz`, `release.tar.gz.sha256`, `wheels.tar.gz`, `wheels.tar.gz.sha256`, `install_host.py`, `install_guest.py`, `mongo_service.py`, `mongodb-linux-x86_64-ubuntu2404-8.0.19.tgz`.
6. Run `sudo python3 STAGING/install_host.py prepare` in an authenticated SSH terminal (`sudo -n` works only when authentication is already available). Do not use shell tracing or put passwords in command arguments: environment files contain secrets. The existing domain/tunnel route should require no changes. `publish` is only needed if inspection shows its route is absent.

## What the update does

- Checks both artifact digests, safely extracts a unique release, and installs offline wheels.
- Creates a dedicated MongoDB service with authentication, persistent storage, a private network namespace and a Unix socket. No public database port is added. The web service retains `PrivateNetwork=yes` and `RestrictAddressFamilies=AF_UNIX`.
- Keeps the existing session secret, SQL connection, accounts and passwords. Generates a persistent pepper only if absent. Legacy hashes upgrade when their owner successfully logs in. Root MongoDB credentials stay in a root-readable file; the application receives only the project database roles.
- Runs the full test suite against disposable MariaDB and MongoDB databases before stopping the live application.
- Stops app writes, backs up SQL, cleanly stops/copies/restarts MongoDB, backs up configuration, adds missing SQL tables/view, initializes MongoDB validators/indexes, migrates existing SQL community records and inserts only missing population records. Seeded reviews and menus belong to labelled sample venues.
- Verifies the integrity audit and nine constraint probes under the actual application identity; captures database evidence in the private deployment backup.
- Switches the release, checks both engines through the service and checks health again after restart. It verifies the neighbouring origins without modifying their applications.

Failure restores the previous application symlink and configuration. Additive data and backups are retained for review; the installer never restores an old dump blindly over newer data. Backups are under `/var/backups/makanwhere/`. A failed release directory is retained; inspect its logs before building a new attempt. Stop public writes before any later manual rollback, especially after users have started posting to MongoDB.

## Public acceptance checks

After installation, require `/api/health` to report both `database` and `mongoDB` connected. Check the home page, `browse.html?dataset=demo`, an imported listing, sample menus, review pagination, login, favourites, review/discussion CRUD and Analytics. Use an existing administrator account for Database evidence and export the actual server evidence. Keep generated content clearly labelled. Confirm the current server's baseline accounts/content survived and that the source-identity/foreign-reference audit is clear.


## Evaluation gate addition — 6 October 2026

The earlier deployment history is retained. The installer now invokes `scripts/run_database_evaluation.py --full-suite` using its disposable MariaDB/MongoDB test configuration before stopping the live application. The generated `docs/evidence/database-evaluation.json` belongs to that release, contains sanitized synthetic observations and is made readable to the application user. Local evidence JSON is not packaged as server evidence. `verify_release.py` refuses activation unless the application identity can read a passing, full-suite, current-source MariaDB record.

The new revision passed 80 tests locally on SQLite/MongoDB. Its target-engine tests and deployment await NetBird reconnection. Do not reuse the older 61-test MariaDB result to describe the new code.
