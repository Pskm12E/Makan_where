# Makan Where API

## Listing photos and business details

Catalogue/detail responses include `photo` (`url`, `kind`, `alt`, `credit`, `sourceUrl`), `customImage`, `website`, `menuUrl`, `phone`, `detailSources`, `detailsObservedAt`, `menuLinkKind`, `menuHighlights` and `menuHighlightsSource`. `image` is the effective display image, including an explicitly illustrative fallback; `customImage` is the stored override. These are not claims of actual outlet-photo coverage or confirmed prices. Unknown prices remain null.

Existing administrator establishment POST/PATCH routes also accept `description`, `openingHours`, `website`, `menuUrl`, `phone`, `image`, `photoKind`, `photoSourceUrl`, `photoCredit`. Session, administrator role and CSRF checks remain required. Links accept HTTP/HTTPS without embedded credentials; photos accept approved HTTPS hosts or `/assets/` raster paths. A supplied image requires attribution. Omitted optional fields preserve their value; empty strings clear them. Cleared website/menu/phone fields are protected from automatic re-import. Editing a menu link clears previously imported menu highlights. Photo/contact/link provenance and import overrides are stored in the additive `food_place.enrichment` JSON column.

## Application routes

Current storage: SQL for accounts/catalogue/favourites/events, MongoDB for content/votes/reports. IDs remain numeric. `GET /api/health` checks both databases and returns 503 if either is unavailable. New passwords use versioned peppered scrypt; successful legacy logins upgrade their stored hash.

Database evidence endpoints (administrator only): `GET /api/admin/database-lab` returns counts, schema, population receipts, reference/duplicate audits, fixed SQL results/plans, Mongo evidence and normalization examples. `POST /api/admin/database-lab/probes` runs rollback-only SQL and disposable Mongo constraint tests. `POST /api/admin/database-lab/security` demonstrates hashes with dummy inputs only. Both POSTs require CSRF; no arbitrary query execution or real credential/hash exposure is provided.

All routes use the same origin as the website and return JSON. Fetch `GET /api/session` first; preserve the session cookie and send its `csrfToken` as `X-CSRF-Token` on every mutation, including registration, login and discovery events. Login/registration rotate the token. Error responses have `{"error":"message"}` and an appropriate HTTP status. API responses are not cached.

| Method and route | Purpose / access |
| --- | --- |
| `GET /api/health` | Database and application health |
| `GET /api/session` | Current user, CSRF token, favourite IDs, sample-catalogue flag |
| `POST /api/register` | `fullName`, `username`, `email`, `password`, optional `phone` |
| `POST /api/login` | `identity` (email or username), `password` |
| `POST /api/logout` | Clear session |
| `PATCH /api/profile` | Logged-in user's complete `fullName`, `username`, `email`, optional `phone` |
| `GET /api/catalogue` | Compact public catalogue for browser filters, gzip supported, bounded to 20,000 entries |
| `GET /api/establishments?cursor=0&limit=100` | Active places with cuisines, dishes and calculated values; maximum 200 per page |
| `GET /api/establishments/:id` | One active place |
| `PUT /api/favourites/:placeId` | Save for current user; idempotent |
| `DELETE /api/favourites/:placeId` | Unsave for current user; idempotent |
| `GET /api/content?place_id=1&cursor=0` | Visible content, 100 per page, `nextCursor` |
| `GET /api/reviews?place_id=1&cursor=0` | Same response filtered to reviews |
| `POST /api/content` | Logged-in user creates review/thread/comment |
| `POST /api/reviews` | Review creation alias |
| `PATCH /api/content/:id` | Author edits `text`, plus `title` and review `rating` where applicable |
| `DELETE /api/content/:id` | Author/admin soft removal |
| `PUT /api/content/:id/upvote` | Vote as current user; idempotent |
| `DELETE /api/content/:id/upvote` | Remove current user's vote |
| `POST /api/content/:id/reports` | Logged-in user submits `reason` |
| `GET /api/admin/reports` | Admin: up to 200 open reports |
| `PATCH /api/admin/reports/:id` | Admin: `status` resolved/dismissed, `note` |
| `POST /api/events` | `type` search/place_view; `placeId` required for place_view; guests allowed |
| `GET /api/analytics` | MongoDB review rankings, SQL favourite/cuisine/menu rankings and historical discovery counts |
| `POST /api/admin/establishments` | Admin creates place |
| `PATCH /api/admin/establishments/:id` | Admin edits place |
| `DELETE /api/admin/establishments/:id` | Admin archives place |
| `POST /api/admin/establishments/:id/dishes` | Admin adds `name`, decimal `price`, optional `dietary` |
| `PATCH /api/admin/establishments/:placeId/dishes/:dishId` | Admin edits name, price, dietary label and boolean availability |
| `DELETE /api/admin/establishments/:placeId/dishes/:dishId` | Admin marks a dish unavailable; preserves feedback history |
| `GET /api/admin/schema` | Admin reads live application-table metadata; no arbitrary SQL or record values |
| `GET /api/admin/menu-imports` | Admin: menu coverage, import history and whether a server key is configured; never returns the key |
| `POST /api/admin/menu-imports` | Admin + CSRF: preview `menu`, then apply using the returned `previewToken` |
| `GET /api/admin/establishments/:id/menu-template` | Admin: exact venue identity and blank source/item fields |
| `GET /api/admin/menu-imports/kfc-reference` | Admin: reviewed KFC source mapped to active imported venues with exact name KFC |
| `GET /api/integrations/menu-targets?name=KFC` | Scoped bearer key only: exact imported venue identities for menu matching |
| `POST /api/integrations/menu-imports` | Scoped bearer key only: same preview/apply contract; no session/CSRF bypass for other routes |

`GET /api/analytics` returns `topRated`, `mostFavourited`, `cuisineCoverage`,
`affordableItems`, `affordableMenus` and the existing `discovery` object. Each
ranking contains at most three rows. Review aggregates execute in MongoDB; catalogue/favourite/event aggregates execute in SQL. The browser displays the results.
Reviews removed from public view and archived places are excluded from current
rankings; unavailable dishes are excluded from price calculations. Places with
no available dishes have no known menu average and are excluded, not priced at
zero. Affordable menus have an average available-dish price at most SGD 12.
Cuisine coverage counts listed venues, not user preference. Discovery counts
remain historical totals, including events for subsequently archived places.
Sample menu results carry `isSample`. See [the lecturer walkthrough](lecturer_walkthrough.md).

Content creation fields: `kind` (`review`, `thread` or `comment`), `placeId`, `text`; review/thread require `title`, reviews require integer `rating` 1-5, comments require `threadId`. Optional `dishes` is an array of `{id, feedback}` for dishes belonging to the same place. Parent discussion and reply must belong to the same place.

Place creation/edit fields: `name`, `address`, `area`, `category`, `cuisine` (comma-separated names). Lookups and cuisine links are maintained by the API. Derived ratings/minimum prices cannot be supplied by clients.

Menu items additionally return `description`, `isReference`, `sourceName`, `sourceUrl` and `sourceObservedAt`. Venue `hasReferenceMenu` labels derived prices that include chain reference items. Dish POST/PATCH accepts an optional `description` of at most 1,000 characters. Manual edits preserve source identity for deduplication but clear the observation date when name/price/description/dietary data changes. Availability toggles preserve the original source date.

Menu imports validate the entire batch before writing, check each venue's current name and source ID, require SGD, preserve existing/removed dishes, and reject cross-source name conflicts. The signed preview is bound to the payload, current menu state and authenticated actor, and expires after 15 minutes. Menu rows and their `population_run` receipt commit in one SQL transaction. Limits: 100 items, 100 venues, 64 KB request body; 30 requests/hour per IP for each import/target endpoint. See the [payload and setup guide](../README.md#import-through-an-api-key).

Registration creates only normal users. Passwords are hashed; session cookies are HttpOnly and SameSite=Lax, with Secure enabled for HTTPS deployment and disabled only for the documented local HTTP setup. CSRF, ownership checks and administrator checks apply on the server. Registration, login, content, reports and discovery have dedicated rate limits. The local setup uses one Waitress process with in-memory limits; configure shared limiter storage before using multiple application processes. See the [startup guide](../README.md#startup-and-database-configuration).

## Database correctness addendum — 6 October 2026

The earlier reference is retained. `PUT /api/favourites/:placeId` now uses a native SQL upsert with a duplicate-key no-op rather than a SELECT followed by INSERT. This preserves its idempotent contract under simultaneous requests and retains the first `saved_at`. DELETE is a single predicate-based SQL operation.

`GET /api/admin/database-evaluation` returns the recorded isolated evaluation. It requires the administrator role and performs no load/fault tests. Its `status` is `not_run`, `unavailable`, `stale` or `recorded`; `currentSource` compares the recorded backend/test hash with this installation. Completed records contain `summary`, engine/platform metadata, per-experiment invariants and observations, raw benchmark samples/plans and explicit `limits`. The same object is included as `evaluation` in the database-lab snapshot and JSON export. `passed` describes the recorded run and must be interpreted together with source currency, the actual engine and each experiment's stated scope.

A failed content POST may return 503 after its Mongo insert has committed if response serialization subsequently fails. This is explicitly tested. POST has no request-key deduplication contract; read back recent content before retrying an ambiguous submission. Do not equate an HTTP error with a distributed rollback. Concurrent normal content edits use last-write-wins, while removal and report resolution have conditional Mongo predicates. See the appended [database design](system_architecture.md#database-design-and-evaluation-addendum--6-october-2026).
