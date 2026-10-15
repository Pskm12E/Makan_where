-- Makan Where: 10 live SQL tables and 7 retained legacy community migration tables.

-- Existing installations: run migrate-catalogue, migrate-menus and migrate-details before init-db.

-- Canonical source: backend/models.py; live community documents are in MongoDB.

-- This is additive DDL. Use init-db for the derived catalogue view too.

CREATE TABLE IF NOT EXISTS area (
	area_id INTEGER NOT NULL AUTO_INCREMENT,
	area_name VARCHAR(100) NOT NULL,
	CONSTRAINT pk_area PRIMARY KEY (area_id),
	CONSTRAINT uq_area_area_name UNIQUE (area_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS category (
	category_id INTEGER NOT NULL AUTO_INCREMENT,
	category_name VARCHAR(100) NOT NULL,
	CONSTRAINT pk_category PRIMARY KEY (category_id),
	CONSTRAINT uq_category_category_name UNIQUE (category_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cuisine (
	cuisine_id INTEGER NOT NULL AUTO_INCREMENT,
	cuisine_name VARCHAR(100) NOT NULL,
	CONSTRAINT pk_cuisine PRIMARY KEY (cuisine_id),
	CONSTRAINT uq_cuisine_cuisine_name UNIQUE (cuisine_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS population_run (
	run_key VARCHAR(100) NOT NULL,
	created_at DATETIME NOT NULL,
	details JSON NOT NULL,
	CONSTRAINT pk_population_run PRIMARY KEY (run_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user (
	user_id INTEGER NOT NULL AUTO_INCREMENT,
	display_name VARCHAR(100) NOT NULL,
	email VARCHAR(254) NOT NULL,
	password_hash VARCHAR(255) NOT NULL,
	`role` VARCHAR(20) NOT NULL,
	created_at DATETIME NOT NULL,
	username VARCHAR(50) NOT NULL,
	phone VARCHAR(25) NOT NULL,
	CONSTRAINT pk_user PRIMARY KEY (user_id),
	CONSTRAINT ck_user_role CHECK (role IN ('user', 'admin')),
	CONSTRAINT uq_user_email UNIQUE (email),
	CONSTRAINT uq_user_username UNIQUE (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS food_place (
	place_id INTEGER NOT NULL AUTO_INCREMENT,
	area_id INTEGER NOT NULL,
	category_id INTEGER NOT NULL,
	place_name VARCHAR(150) NOT NULL,
	address VARCHAR(255) NOT NULL,
	latitude NUMERIC(9, 6),
	longitude NUMERIC(9, 6),
	google_place_id VARCHAR(255),
	description TEXT NOT NULL,
	image_url VARCHAR(1000) NOT NULL,
	enrichment JSON,
	hygiene_grade VARCHAR(1),
	tags JSON NOT NULL,
	archived_at DATETIME,
	source_name VARCHAR(40),
	source_id VARCHAR(80),
	source_url VARCHAR(500),
	source_fetched_at DATETIME,
	opening_hours VARCHAR(1000),
	is_sample BOOL NOT NULL DEFAULT '0',
	CONSTRAINT pk_food_place PRIMARY KEY (place_id),
	CONSTRAINT uq_food_place_source UNIQUE (source_name, source_id),
	CONSTRAINT fk_food_place_area_id_area FOREIGN KEY(area_id) REFERENCES area (area_id),
	CONSTRAINT fk_food_place_category_id_category FOREIGN KEY(category_id) REFERENCES category (category_id),
	CONSTRAINT uq_food_place_google_place_id UNIQUE (google_place_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX IF NOT EXISTS ix_food_place_area_id ON food_place (area_id);

CREATE INDEX IF NOT EXISTS ix_food_place_place_name ON food_place (place_name);

CREATE TABLE IF NOT EXISTS content (
	content_id INTEGER NOT NULL AUTO_INCREMENT,
	author_id INTEGER NOT NULL,
	place_id INTEGER NOT NULL,
	body TEXT NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	removed_by_id INTEGER,
	removed_at DATETIME,
	kind VARCHAR(10) NOT NULL,
	CONSTRAINT pk_content PRIMARY KEY (content_id),
	CONSTRAINT ck_content_kind CHECK (kind IN ('review','thread','comment')),
	CONSTRAINT ck_content_removal CHECK ((removed_at IS NULL AND removed_by_id IS NULL) OR (removed_at IS NOT NULL AND removed_by_id IS NOT NULL)),
	CONSTRAINT uq_content_content_id UNIQUE (content_id, kind),
	CONSTRAINT fk_content_author_id_user FOREIGN KEY(author_id) REFERENCES user (user_id),
	CONSTRAINT fk_content_place_id_food_place FOREIGN KEY(place_id) REFERENCES food_place (place_id),
	CONSTRAINT fk_content_removed_by_id_user FOREIGN KEY(removed_by_id) REFERENCES user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX IF NOT EXISTS ix_content_author_id ON content (author_id);

CREATE INDEX IF NOT EXISTS ix_content_place_id ON content (place_id);

CREATE TABLE IF NOT EXISTS discovery_event (
	event_id INTEGER NOT NULL AUTO_INCREMENT,
	user_id INTEGER,
	place_id INTEGER,
	event_type VARCHAR(20) NOT NULL,
	occurred_at DATETIME NOT NULL,
	CONSTRAINT pk_discovery_event PRIMARY KEY (event_id),
	CONSTRAINT ck_discovery_type CHECK (event_type IN ('search','place_view')),
	CONSTRAINT ck_discovery_place CHECK (event_type != 'place_view' OR place_id IS NOT NULL),
	CONSTRAINT fk_discovery_event_user_id_user FOREIGN KEY(user_id) REFERENCES user (user_id),
	CONSTRAINT fk_discovery_event_place_id_food_place FOREIGN KEY(place_id) REFERENCES food_place (place_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX IF NOT EXISTS ix_discovery_event_occurred_at ON discovery_event (occurred_at);

CREATE TABLE IF NOT EXISTS dish (
	dish_id INTEGER NOT NULL AUTO_INCREMENT,
	place_id INTEGER NOT NULL,
	dish_name VARCHAR(150) NOT NULL,
	description TEXT NOT NULL,
	price NUMERIC(10, 2) NOT NULL,
	is_available BOOL NOT NULL,
	dietary_label VARCHAR(80) NOT NULL,
	source_name VARCHAR(80),
	source_item_id VARCHAR(100),
	source_url VARCHAR(500),
	source_observed_at DATETIME,
	is_reference BOOL NOT NULL DEFAULT '0',
	CONSTRAINT pk_dish PRIMARY KEY (dish_id),
	CONSTRAINT ck_dish_price CHECK (price >= 0),
	CONSTRAINT uq_dish_source UNIQUE (place_id, source_name, source_item_id),
	CONSTRAINT fk_dish_place_id_food_place FOREIGN KEY(place_id) REFERENCES food_place (place_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX IF NOT EXISTS ix_dish_place_id ON dish (place_id);

CREATE TABLE IF NOT EXISTS favourite (
	user_id INTEGER NOT NULL,
	place_id INTEGER NOT NULL,
	saved_at DATETIME NOT NULL,
	CONSTRAINT pk_favourite PRIMARY KEY (user_id, place_id),
	CONSTRAINT fk_favourite_user_id_user FOREIGN KEY(user_id) REFERENCES user (user_id),
	CONSTRAINT fk_favourite_place_id_food_place FOREIGN KEY(place_id) REFERENCES food_place (place_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS place_cuisine (
	place_id INTEGER NOT NULL,
	cuisine_id INTEGER NOT NULL,
	CONSTRAINT pk_place_cuisine PRIMARY KEY (place_id, cuisine_id),
	CONSTRAINT fk_place_cuisine_place_id_food_place FOREIGN KEY(place_id) REFERENCES food_place (place_id),
	CONSTRAINT fk_place_cuisine_cuisine_id_cuisine FOREIGN KEY(cuisine_id) REFERENCES cuisine (cuisine_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS content_dish (
	content_id INTEGER NOT NULL,
	dish_id INTEGER NOT NULL,
	dish_feedback TEXT,
	CONSTRAINT pk_content_dish PRIMARY KEY (content_id, dish_id),
	CONSTRAINT fk_content_dish_content_id_content FOREIGN KEY(content_id) REFERENCES content (content_id),
	CONSTRAINT fk_content_dish_dish_id_dish FOREIGN KEY(dish_id) REFERENCES dish (dish_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS report (
	report_id INTEGER NOT NULL AUTO_INCREMENT,
	reporter_id INTEGER NOT NULL,
	content_id INTEGER NOT NULL,
	reason VARCHAR(1000) NOT NULL,
	created_at DATETIME NOT NULL,
	status VARCHAR(20) NOT NULL,
	resolved_by_id INTEGER,
	resolved_at DATETIME,
	resolution_note VARCHAR(1000),
	CONSTRAINT pk_report PRIMARY KEY (report_id),
	CONSTRAINT ck_report_status CHECK (status IN ('open','resolved','dismissed')),
	CONSTRAINT fk_report_reporter_id_user FOREIGN KEY(reporter_id) REFERENCES user (user_id),
	CONSTRAINT fk_report_content_id_content FOREIGN KEY(content_id) REFERENCES content (content_id),
	CONSTRAINT fk_report_resolved_by_id_user FOREIGN KEY(resolved_by_id) REFERENCES user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX IF NOT EXISTS ix_report_content_id ON report (content_id);

CREATE TABLE IF NOT EXISTS review (
	content_id INTEGER NOT NULL,
	kind VARCHAR(10) NOT NULL,
	rating INTEGER NOT NULL,
	title VARCHAR(150) NOT NULL,
	CONSTRAINT pk_review PRIMARY KEY (content_id),
	CONSTRAINT fk_review_content_id_content FOREIGN KEY(content_id, kind) REFERENCES content (content_id, kind),
	CONSTRAINT ck_review_kind CHECK (kind = 'review'),
	CONSTRAINT ck_review_rating CHECK (rating BETWEEN 1 AND 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS thread (
	content_id INTEGER NOT NULL,
	kind VARCHAR(10) NOT NULL,
	title VARCHAR(150) NOT NULL,
	CONSTRAINT pk_thread PRIMARY KEY (content_id),
	CONSTRAINT fk_thread_content_id_content FOREIGN KEY(content_id, kind) REFERENCES content (content_id, kind),
	CONSTRAINT ck_thread_kind CHECK (kind = 'thread')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS upvote (
	user_id INTEGER NOT NULL,
	content_id INTEGER NOT NULL,
	voted_at DATETIME NOT NULL,
	CONSTRAINT pk_upvote PRIMARY KEY (user_id, content_id),
	CONSTRAINT fk_upvote_user_id_user FOREIGN KEY(user_id) REFERENCES user (user_id),
	CONSTRAINT fk_upvote_content_id_content FOREIGN KEY(content_id) REFERENCES content (content_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS comment (
	content_id INTEGER NOT NULL,
	kind VARCHAR(10) NOT NULL,
	thread_id INTEGER NOT NULL,
	CONSTRAINT pk_comment PRIMARY KEY (content_id),
	CONSTRAINT fk_comment_content_id_content FOREIGN KEY(content_id, kind) REFERENCES content (content_id, kind),
	CONSTRAINT ck_comment_kind CHECK (kind = 'comment'),
	CONSTRAINT fk_comment_thread_id_thread FOREIGN KEY(thread_id) REFERENCES thread (content_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX IF NOT EXISTS ix_comment_thread_id ON comment (thread_id);
