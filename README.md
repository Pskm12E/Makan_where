# MakanWhereSG

MakanWhereSG is a Singapore food discovery and review system developed as an INF2003 Database Systems group project. The current prototype focuses on the first phase: a static frontend with realistic mock data, search, filtering, favourites, restaurant details, admin management, and analytics.

## Goals

- Help users discover food establishments across Singapore.
- Support browsing by cuisine, category, area, hygiene grade, and price.
- Show menu items and user reviews.
- Demonstrate how relational data and NoSQL review content fit different database needs.

## Prototype pages

- `index.html` – home landing page
- `browse.html` – search and filter page
- `restaurant.html` – establishment detail and review page
- `favourites.html` – saved favourites using localStorage
- `admin.html` – mock admin dashboard
- `analytics.html` – summary metrics and insights
- `auth.html` – food-themed login and registration
- `settings.html` – profile settings for name, username, Gmail, and phone

## Frontend stack

- HTML5
- CSS3
- Vanilla JavaScript
- Responsive design for desktop and mobile

## Prototype account features

- Register with full name, username, Gmail address, phone number, and password.
- Log in using the registered Gmail address or username.
- Update profile details from the settings page.
- Log out from the shared navigation or settings page.
- Account data is stored in browser localStorage for this prototype only.

This is not production authentication. Passwords are intentionally stored locally only to demonstrate the frontend flow. A production version should use the Flask backend, hashed passwords, server-side sessions or tokens, validation, and secure database storage.

## Local preview

From the project folder, run:

```bash
python -m http.server 8000
```

Then open `http://localhost:8000` in a browser.

## Project structure

```
makanwheresg/
├── README.md
├── index.html
├── browse.html
├── restaurant.html
├── favourites.html
├── admin.html
├── analytics.html
├── css/
│   └── style.css
├── js/
│   ├── data.js
│   ├── app.js
│   ├── browse.js
│   ├── restaurant.js
│   ├── favourites.js
│   ├── admin.js
│   └── analytics.js
├── backend/
│   ├── app.py
│   ├── config.py
│   ├── requirements.txt
│   ├── models/
│   ├── routes/
│   ├── services/
│   └── seed_data/
├── database/
│   ├── maria_schema.sql
│   ├── mongo_seed.json
│   └── queries/
├── docs/
│   ├── NoSQL_schema.md
│   └── API_design.md
└── assets/
    └── images/
```

## Database direction

- MariaDB is intended for structured relational data such as users, establishments, categories, cuisines, menu items, and favourites.
- MongoDB is intended for flexible review documents with tags, dish reviews, and optional metadata.

## Notes

This first stage is intentionally static and uses mock JavaScript data only. The database-backed backend and API layer will be developed in later project phases.
