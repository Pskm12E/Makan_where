# Makan Where user manual

## Photos, business details and linked menus

Every listing has a photo, with **Illustrative photo** shown whenever the image is not an actual venue photograph. Click that label or the detail-page credit to see its source. Venue pages offer website/menu/map links when available; menu highlights without published prices are clearly identified. KFC and Suki-Ya prices are labelled chain references.

In Admin, find a venue and click **Edit → Photos, links and venue details**. You can manage the description, opening hours, business phone, website/menu link, photo URL, photo type, source and credit. Leave the image URL blank for an automatic illustrative photo. Use actual venue photography only when you have its correct source/credit. Existing descriptions and hours are fetched before editing. Admin thumbnails and overview counts make coverage visible; **Manage menu** also exposes published menu highlights and their source.

Use the [README enrichment commands](../README.md#photos-and-business-details) to preview/reapply retained source data. Re-importing preserves manual edits and deliberately cleared links. The public website receives these changes only after deployment; current local availability does not establish that the public site has been updated.

First follow the [current startup guide](../README.md). Once the local server is running, open [http://127.0.0.1:5055](http://127.0.0.1:5055). Administrators can open [Database evidence](http://127.0.0.1:5055/database-lab.html) from the Admin/Analytics navigation. Its six sections appear together on one scrolling page, with an overview of population, keys/integrity, dependencies, queries/plans, passwords and Weeks 1–5. **Run all checks** refreshes the database evidence, runs the constraint checks and checks password protection. All details start expanded; Expand details and Collapse details control supporting tables without hiding sections. Export JSON saves the complete captured evidence and check results.

The current local lecturer credentials are in private `.env.demo`. Community fixtures are fictional and labelled DEMO. The studio engine badge distinguishes SQLite preview evidence from MariaDB evidence; do not present one as the other.

Seeding and importing the retained dataset provides 8,415 OpenStreetMap listings plus six labelled sample venues and 18 sample dishes. Sample prices and details are for demonstration. Use the footer's Download listings CSV link to obtain the source dataset.

## Discover food

Use Home or Browse to search by name, cuisine, area or address. Filter by category, cuisine, area, price and available hygiene information, or sort by name, price or rating. Browse shows 24 results per page. Open a place to see its details, dishes, reviews and discussions. Ratings appear after users submit reviews.

Imported places link to their OpenStreetMap source and show available opening hours and collection dates. Missing prices, hygiene grades, menus and photographs are not inferred. Areas without a source neighbourhood tag display as Singapore.

## Your account

Choose Log in, then Create account. Provide a display name, unique username, valid email and password of 8-128 characters. Phone is optional. Log in using your username or email. Settings changes your profile; Logout ends your session. Email verification and password recovery are not implemented.

## Favourites and community

While logged in, click a heart to save or remove a place. Favourites are stored with your account in the configured database.

On a place page, write a review with an integer rating from 1 to 5, start a discussion or reply to an existing discussion. Replies are flat. You can upvote and report content, edit your own posts and remove your own posts. Administrators may remove content, but only authors may edit it. Removed content is hidden and removed reviews no longer contribute to ratings.

The optional dish dropdown lists that venue's available database dishes alphabetically. Published chain items can be selected even if their source provides no price; these display **Price not listed** and do not count as free items in price comparisons. The selected dish and its feedback are saved together with the review. Display-only highlights on an older installation need the menu-name import described in the README before they can be selected.

**Edit** opens fields in the post itself. Change the title, rating, message or existing dish feedback, then choose **Save changes** or **Cancel**. **Report** opens a reason/details form below that post. **Remove** shows **Keep it** and a specific removal button in the same card. Errors appear beside the action and keep your input. Escape cancels an inline action; Ctrl+Enter (Cmd+Enter on Mac) submits it. Save or cancel the current action before starting another. These controls are available after the UI update is deployed.

## Administration

The server operator promotes a registered account using the [administrator setup steps](../README.md#8-create-an-administrator-and-populate-content). Registration cannot grant an administrator role.

Administrators can add/edit/archive establishments and resolve or dismiss reports with a note. In Catalogue, **Manage menu** adds or edits dish names, prices, descriptions and dietary information. Remove/restore changes menu visibility while preserving past review links. The Menu coverage filter finds missing menus. Archiving hides a place from public discovery and preserves related records. Bulk venue CSV import uses an operator command; browser venue CSV upload and archive restoration are not implemented.

**Import menus** accepts source-attributed JSON. Choose a file or load the included KFC reference, review the target establishments and dish prices, then preview and import. Existing records and administrator edits are preserved. Import history and menu coverage are visible in this tab. The API-key import script and complete format are documented in [Add menus](../README.md#add-menus-and-manage-them-in-admin).

KFC listings can show 97 published items from the official Singapore chain menu observed on 4 October 2026. These are visibly labelled chain reference prices: the specific outlet's prices and availability may differ. No real reviews, hygiene grades or photos are generated to fill missing fields.

See [roles and permissions](roles_and_permissions.md) for the complete action matrix and backend checks. To inspect tables and joined queries, follow [schema, queries and normalization](../README.md#schema-queries-and-normalization).

## Database evaluation addition — 6 October 2026

Database evidence now includes a seventh section, **Correctness & measured performance**. Use its overview link to inspect recorded MongoDB operations, cross-database fault detection, concurrent requests, recovery and controlled benchmarks. Each experiment states the expected invariant and observed result. Timings include the dataset, repeated samples and query plans rather than a single unqualified duration.

Check the engine names, capture time and source-match status before presenting a result. Local SQLite results do not verify MariaDB. **Refresh data** reloads the recorded artifact; **Run all checks** only executes the safe live constraint/password probes and does not rerun load/failure experiments. **Export JSON** includes both kinds of evidence. Known limitations are displayed after the experiments.

## Running your own laptop copy - 16 October 2026

Use the [Docker laptop guide](docker_laptop_guide.md) to start the website and both database engines together. The default URL is <http://localhost:5056/>. The generated `.env.laptop` contains distinct administrator and normal-user accounts. Database evidence is available to the administrator at `/database-lab.html`; run the isolated evaluation profile before expecting recorded concurrency, recovery and benchmark results. This installation does not use public-server credentials or DBStudios.

## Explore the database schema

Log in as an administrator, then choose **Admin → Database schema**, or open `/admin.html#schema` on your running website. This is a read-only view; no separate database client is required. **Refresh schema** reloads metadata from the connected SQL database. **SQL relationships** currently shows 10 active tables; the count follows the connected schema and may change.

Each table marks primary keys (**PK**) and foreign keys (**FK**). Solid arrows point to the referenced parent table. Relationship labels show `1` (one), `0..1` (zero or one) and `0..*` (zero or many), derived from the database's keys and constraints.

Click a table or choose it in **Inspect** to highlight its connected lines and read its keys and relationships below the diagram. Use **Clear selection** to see all relationships equally. The **−** and **+** controls change zoom; **Reset view** restores the starting zoom and scroll position. On small screens, scroll the diagram or use **Inspect**. **View all SQL columns** filters and scrolls to the selected table in **All SQL tables & columns**. That searchable list also includes legacy SQL community tables retained for migration.

Switch to **MongoDB references** to explore the application model for community content and its SQL identities. Dashed lines describe references checked by the application, not live database foreign-key constraints or a shared transaction across databases. Select a collection to read its reference details; **Open database evidence** provides the supporting evidence view.

## Schema editing and live records — 27 October 2026

**Admin → Database schema → Edit tables, columns & relationships** now adds schema editing alongside the read-only exploration described above. It changes the connected MariaDB/MySQL database directly from the app; no DBStudios or separate database client is required. Other database engines remain read-only in this editor.

Choose **Create table**, **Add column** or **Add foreign key**. New table names must begin with `custom_` followed by a lowercase letter, such as `custom_booking`; creation adds an integer, auto-increment primary key named `id` by default. Added columns are nullable, so existing records receive `NULL`. Supported types are Integer, Text (255 characters), Decimal (10, 2), Boolean, and Date and time. New columns on existing application tables must use the `custom_` prefix; columns on custom tables can use names such as `place_id`. Names start with a lowercase letter and contain only lowercase letters, digits and underscores, up to 48 characters. The editor allows up to 30 custom tables and 60 columns per table.

**Add foreign key** links an existing child column to a single-column primary key. Both columns must have matching signed integer types, and the child must not already have a foreign key. On application tables, the child column must have the `custom_` prefix. The database checks existing values and rejects orphan references. Both delete and update rules are `RESTRICT`, preventing deletion or key changes of referenced parent records while linked. The editor provides no drop, rename, or other destructive operations.

For every operation, choose **Preview SQL**, review the generated statement and description, then choose **Apply schema change**. A preview belongs to the administrator who requested it and expires after five minutes. Changing the proposal or relevant database structure requires a new preview. The diagram and column details refresh after a successful apply. With **Live updates every 10 seconds** enabled, structure and record reads also refresh while this page and its Database schema panel are visible; **Refresh schema** refreshes both manually.

For example, preview and apply each of these three operations in order:

1. **Create table**: new table `custom_booking`, primary key `id`.
2. **Add column**: table `custom_booking`, new column `place_id`, type **Integer**.
3. **Add foreign key**: table `custom_booking`, existing child column `place_id`, referenced table `food_place`, referenced primary key `place_id`.

The resulting table, field and relationship appear in the SQL diagram. App forms do not automatically use new fields or tables; that requires separate application code changes.

**Live records** watches the listed core SQL tables and MongoDB collections while you make changes through the app in another tab. Choose a table or collection, optionally enter its **Record key**, and select **Watch records**. A blank key shows the highest 20 keys; a record leaving this window may simply have moved outside it. Highlighted cells compare observed reads and show previous values or **New in this view**. This watcher is read-only and is not a transaction log; it may miss changes between reads, and each database is read separately. Custom tables appear in the schema diagram but are not added to this core-record watcher.

## Database correctness update — 27 October 2026

Post edits and removal use the revision originally displayed. If another tab edits the post first, the application rejects the stale change; reload the current post before editing again. A failed submission can be retried from the same unchanged form. The form retains its request identity through a failed response or failed follow-up feed load. Changing the form's contents or starting a new form represents a new submission.

Imported chain menu facts are shared across outlets. Administrator edits apply as outlet-specific overrides, including a deliberate zero price or cleared description. Existing dish IDs and removed/unavailable items survive the design upgrade. The schema diagram reflects 21 declared SQL tables after upgrade; the physical `dish` table retains outlet-offering identities. Its record preview shows effective names/prices from shared facts and overrides.

For a new laptop, follow the Docker laptop guide. For existing data, stop application writes and retain a matching SQL/Mongo backup pair before running the documented upgrade. The latest verification record distinguishes current native tests and restore observations from Docker runtime checks, which still require a working Docker engine.
