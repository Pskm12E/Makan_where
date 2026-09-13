# MakanWhereSG

MakanWhereSG is a Singapore food discovery and review system for the INF2003 Database Systems group project. It helps users discover food establishments by cuisine, category, price, location, hygiene grade, rating, and dietary needs.

The project demonstrates how a relational database and a NoSQL database can work together:

- MariaDB stores consistent, structured, and related application data.
- MongoDB stores flexible user reviews with tags, dish feedback, and optional photo metadata.

## Project status

The current repository contains a functional static frontend prototype using local JavaScript data. It includes the main user journeys and browser interactions, while the Flask, MariaDB, and MongoDB layers are scaffolded for the next implementation phase.

### Implemented now

- Responsive food discovery homepage.
- Establishment search, filtering, and sorting.
- Establishment detail pages with menu items and mock reviews.
- Browser-based favourites using `localStorage`.
- Food-themed login and registration pages.
- Demo account profile with full name, username, Gmail, and phone number.
- Profile settings and logout.
- Mock admin create, edit, and delete actions.
- Food analytics summaries.
- MariaDB schema, seed data, view, indexes, and sample queries.
- MongoDB review document examples and aggregation queries.

### Not connected yet

- The frontend does not currently call the Flask API.
- MariaDB and MongoDB are not required to run the static prototype.
- Authentication is demo-only and stores account data in browser storage.
- Backend routes for database CRUD are placeholders.

## Main features

### Food discovery

- Search by establishment name, cuisine, or area.
- Filter by category, cuisine, area, price range, and hygiene grade.
- Sort by rating, price, or establishment name.
- View establishment address, cuisine, hygiene grade, price, menu, and reviews.

### User account

- Register with full name, username, Gmail address, phone number, and password.
- Log in using either a username or Gmail address.
- Edit profile details from the settings page.
- Log out from the navigation or settings page.
- Access settings only after logging in.

### Favourites and reviews

- Save and remove favourite establishments.
- View all saved establishments on the favourites page.
- Submit mock reviews from an establishment detail page.
- Display review ratings, review text, and review tags.

### Administration and analytics

- Add establishments through the mock admin form.
- Edit and delete existing mock establishments.
- View establishment count and average menu price.
- View top-rated establishments, popular cuisines, affordable menu items, favourite counts, and common review tags.

## Application pages

| Page | File | Purpose |
| --- | --- | --- |
| Home | `index.html` | Featured establishments, search entry point, and popular cuisines. |
| Browse | `browse.html` | Search, filtering, sorting, and establishment cards. |
| Restaurant details | `restaurant.html` | Menu, establishment information, reviews, and review form. |
| Favourites | `favourites.html` | Saved establishments for the current browser user. |
| Login and registration | `auth.html` | Separate login and registration modes using the `mode` query parameter. |
| User settings | `settings.html` | Edit profile information and log out. |
| Admin | `admin.html` | Mock establishment management and summary statistics. |
| Analytics | `analytics.html` | Food-related summary metrics. |

Use these authentication URLs:

```text
http://localhost:8000/auth.html?mode=login
http://localhost:8000/auth.html?mode=register
```

## Technology stack

### Current frontend

- HTML5
- CSS3
- Vanilla JavaScript
- Browser `localStorage` for prototype favourites and accounts
- External Unsplash food images for prototype cards and authentication artwork

### Planned backend

- Python Flask
- Flask-SQLAlchemy
- PyMySQL
- PyMongo
- MariaDB
- MongoDB
- REST API with JSON responses

## Database design

### MariaDB

MariaDB is designed for structured data with clear relationships and constraints.

Tables:

- `Users`
- `FoodCategories`
- `Cuisines`
- `FoodEstablishments`
- `EstablishmentCuisines`
- `MenuItems`
- `Favourites`

The schema demonstrates:

- Primary keys and foreign keys.
- Unique usernames, email addresses, and licence numbers.
- Composite keys for favourites and establishment-cuisine relationships.
- One-to-many relationships between establishments and menu items.
- Many-to-many relationships between establishments and cuisines.
- Indexes for establishment names, areas, menu names, and cuisine relationships.
- An `affordable_food_items` SQL view.
- Aggregate queries using `COUNT`, `AVG`, `MIN`, `MAX`, `SUM`, `GROUP BY`, and `HAVING`.

### MongoDB

MongoDB is designed for flexible review documents. A review may contain different combinations of tags, dish-level feedback, photos, visit dates, and helpful votes.

The planned `reviews` collection includes:

- `establishment_id`
- `user_id`
- `overall_rating`
- `review_title`
- `review_text`
- `visited_at`
- `created_at`
- `tags`
- `dish_reviews`
- `photo_metadata`
- `helpful_votes`

MongoDB queries will support filtering by rating and tags, as well as aggregation for average ratings by review tag.

## Project structure

```text
MakanWhere/
|-- README.md
|-- index.html
|-- browse.html
|-- restaurant.html
|-- favourites.html
|-- auth.html
|-- settings.html
|-- admin.html
|-- analytics.html
|
|-- css/
|   `-- style.css
|
|-- js/
|   |-- data.js          # Mock establishments and reviews
|   |-- auth.js          # Login, registration, session, and settings logic
|   |-- app.js           # Homepage rendering and favourites
|   |-- browse.js        # Search, filters, and sorting
|   |-- restaurant.js    # Detail pages and mock review form
|   |-- favourites.js    # Saved establishment display
|   |-- admin.js         # Mock admin CRUD
|   `-- analytics.js     # Food analytics summaries
|
|-- assets/
|   `-- images/
|
|-- backend/
|   |-- app.py           # Flask API scaffold
|   |-- config.py        # Database connection configuration
|   |-- requirements.txt # Python dependencies
|   |-- models/          # Planned SQLAlchemy models
|   |-- routes/          # Planned REST API routes
|   |-- services/        # Planned database service layer
|   `-- seed_data/       # Planned backend seed scripts
|
|-- database/
|   |-- maria_schema.sql
|   |-- maria_seed.sql
|   |-- mongo_seed.json
|   `-- queries/
|       `-- advanced_queries.sql
|
`-- docs/
    |-- API_design.md
    |-- NoSQL_schema.md
    `-- user_manual.md
```

## Run the frontend prototype

The frontend has no build step. Use a local HTTP server so all pages and scripts load consistently.

### Windows PowerShell

```powershell
cd "C:\Users\User\Desktop\MakanWhere"
python -m http.server 8000
```

Open:

```text
http://localhost:8000
```

Useful pages:

```text
http://localhost:8000/index.html
http://localhost:8000/browse.html
http://localhost:8000/auth.html?mode=login
http://localhost:8000/auth.html?mode=register
http://localhost:8000/settings.html
http://localhost:8000/admin.html
http://localhost:8000/analytics.html
```

Stop the server with `Ctrl+C`.

## Run the Flask scaffold

The backend is currently a minimal API scaffold with health, establishment, and review placeholder endpoints.

```powershell
cd "C:\Users\User\Desktop\MakanWhere\backend"
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Test the health endpoint:

```text
http://127.0.0.1:5000/api/health
```

The current database connection values are examples in `backend/config.py`. Replace the username, password, host, and database settings before connecting to MariaDB or MongoDB.

## Database setup direction

### MariaDB

Run these scripts in order after MariaDB is installed and running:

```text
database/maria_schema.sql
database/maria_seed.sql
```

The schema creates the `makanwheresg` database, relational tables, indexes, and the affordable food view.

### MongoDB

Import `database/mongo_seed.json` into a `makanwheresg` database and `reviews` collection. Add indexes for `establishment_id` and `overall_rating` during backend integration.

## Development roadmap

1. Complete requirements, wireframes, ERD, and MongoDB document design.
2. Finish the static frontend prototype and responsive testing.
3. Implement SQLAlchemy models and MariaDB CRUD endpoints.
4. Implement PyMongo review CRUD, tag queries, and aggregations.
5. Replace frontend mock data with Flask API calls.
6. Add validation, error handling, loading states, and integration tests.
7. Compare MariaDB and MongoDB for schema flexibility, consistency, query complexity, and performance.
8. Prepare the final report, screenshots, presentation, and demo video.

## Scope exclusions

This project is limited to food discovery and reviews. It does not include:

- Food ordering or delivery.
- Payment processing.
- Delivery rider tracking.
- Real-time queue tracking.
- Reservations or bookings.
- Complex map routing.
- AI chatbots or recommendation engines.

## Prototype security note

The current login and registration flow is for frontend demonstration only. Account records, including the demo password, are stored in browser `localStorage`. Do not use this implementation for real users or real credentials.

For production authentication, move account handling to Flask and MariaDB, hash passwords with a dedicated password hashing library, validate all inputs server-side, use secure sessions or tokens, and protect sensitive data in transit and at rest.

## Supporting documentation

- [API design](docs/API_design.md)
- [MongoDB schema](docs/NoSQL_schema.md)
- [User manual](docs/user_manual.md)
- [MariaDB schema](database/maria_schema.sql)
- [MariaDB seed data](database/maria_seed.sql)
- [MongoDB seed data](database/mongo_seed.json)
- [Advanced SQL queries](database/queries/advanced_queries.sql)
