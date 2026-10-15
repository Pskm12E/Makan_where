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
