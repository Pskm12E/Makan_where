# Makan Where users and administrators

The application provides public browsing, registered user features and an administrator dashboard. The account model stores two roles, `user` and `admin`, in MariaDB. A guest is an unauthenticated visitor, not another stored account role. The same backend protects both user and administrator interfaces.

## Responsibilities

Registered users manage their profiles, save favourite places and participate in reviews and discussions. They can edit and remove their own content, vote on visible content and report content for review. They cannot change the catalogue or resolve moderation reports.

Administrators populate and maintain the catalogue through application forms. They can add and edit establishments, add dishes to a place, archive establishments, remove inappropriate community content and resolve or dismiss reports with a note. Administrators retain ordinary user features. They cannot rewrite another author's review or discussion: editing remains restricted to the author.

## Current permission matrix

| Action | Guest | Registered user | Administrator |
| --- | --- | --- | --- |
| Browse active places, menus and visible content | Yes | Yes | Yes |
| Edit profile | No | Own profile | Own profile |
| Save or remove favourites | No | Own saved places | Own saved places |
| Create reviews, discussions and replies | No | Yes | Yes |
| Edit existing community content | No | Own content only | Own content only |
| Remove community content | No | Own content only | Any visible content |
| Add or remove an upvote | No | Own vote | Own vote |
| Submit a content report | No | Yes | Yes |
| Add or edit an establishment | No | No | Yes |
| Archive an establishment | No | No | Yes |
| Add a dish to an active establishment | No | No | Yes |
| Edit, remove or restore a dish | No | No | Yes |
| Preview/import sourced menus and inspect import history | No | No | Yes |
| View open reports and resolve or dismiss them | No | No | Yes |

Registration assigns every new account the ordinary `user` role. A submitted role field cannot grant administrator privileges.

## How an administrator populates the catalogue

1. Sign in with an account that the server operator has promoted to administrator.
2. Open the Admin dashboard and submit the establishment's name, area, category, cuisine and address.
3. The frontend sends `POST /api/admin/establishments`. The backend requires an authenticated administrator and a valid CSRF token.
4. The backend validates fields, finds or creates area/category/cuisine lookup rows, creates the place and its cuisine links, and commits the SQL transaction.
5. To populate a menu, open the place from the dashboard and add a dish. `POST /api/admin/establishments/:id/dishes` validates its name and price before inserting the dish.
6. To update place details, use Edit. To remove a place from public discovery, use Archive.

This workflow demonstrates application-controlled writes across multiple relational tables. It does not require the administrator to edit rows in DBstudios. The existing `import-places` CLI supports bulk import of the retained CSV; a browser CSV upload is a separate feature that has not been implemented.

## Removal and moderation

Archiving sets `food_place.archived_at` and excludes the establishment from public listings. It preserves related reviews, favourites and other references. Community removal sets `content.removed_at` and `content.removed_by_id`. Removed reviews stop contributing to displayed ratings; replies under removed threads are hidden. These operations are soft removal, not a cascade that deletes related user data.

The Admin dashboard lists open reports. The administrator can remove the reported content and then resolve the report with a note, or dismiss the report. Report resolution stores the acting administrator and resolution time. Content removal and report resolution are separate API actions, not a single atomic moderation transaction.

## Where permissions execute

| Backend code or route | Responsibility |
| --- | --- |
| `backend/app.py:protect_api` | Load the session user from MariaDB and check CSRF on API mutations |
| `backend/services.py:authenticated` | Reject guests with 401 and non-administrators on admin-only routes with 403 |
| `POST /api/admin/establishments` | Administrator adds a place and its catalogue relationships |
| `PATCH /api/admin/establishments/:id` | Administrator edits place details |
| `DELETE /api/admin/establishments/:id` | Administrator archives a place |
| `POST /api/admin/establishments/:id/dishes` | Administrator adds a dish |
| `PATCH /api/content/:id` | Only the author edits content, including when the caller is an administrator |
| `DELETE /api/content/:id` | The author or an administrator removes content |
| `GET /api/admin/reports` | Administrator reads open reports |
| `PATCH /api/admin/reports/:id` | Administrator resolves or dismisses a report |

The website checks the role to display the dashboard, but the backend independently checks every protected request. The server loads the current account role from SQL; a client-controlled form field or hidden control does not establish authorization. Flask uses that role to authorize live community operations in MongoDB. Accounts stay in SQL. The Database evidence endpoints are administrator-only, including evidence export and disposable constraint probes.

## Administrator setup and remaining extensions

The server operator grants the first administrator role after the intended account is registered, using the existing `python -m flask --app backend.app set-admin ACCOUNT_EMAIL` command with the intended database configured. No default administrator password is seeded. The command changes the selected existing account's role; it is not exposed as a public signup option.

Dish creation, editing, removal/restoration and source-attributed JSON menu imports are implemented. Browser venue CSV upload, restoring archived places and account suspension/role-management screens are not implemented. See the [startup manual](../README.md) for both database connections and repeatable population.

The optional menu integration key is a separate, narrowly scoped machine credential. It authorizes only exact venue matching and previewed menu imports; it cannot sign in, promote users, change profiles, moderate content or inspect schema. Browser admin imports continue to require a session and CSRF. The key is held in server environment configuration and is never returned by the status endpoint.

## Lecturer demonstration

Use separate local demonstration accounts. First show that an ordinary user cannot submit an administrator-only request. Then sign in as an administrator, add a test establishment and a dish, edit the establishment and show the resulting rows and links. Have a user post content and submit a report; demonstrate administrator removal and report resolution. Finally archive the test place and show that it disappears from discovery while related rows remain.

Existing tests cover unauthorized admin access, place administration, author ownership, administrator removal and report resolution in `tests/test_api.py`. The 23 September assessment passed on SQLite; the 24 September startup-documentation check also passed all 16 tests against MariaDB and exercised registration, denied user access, administrator promotion, place/dish creation and archiving through HTTP. See the [verification record](verification_record.md) and [startup manual](../README.md).
