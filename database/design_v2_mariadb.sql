-- PROPOSED DESIGN ONLY. Not a migration and not applied to the live server.

-- Requires the existing food_place(place_id) parent relation.

-- Keep dish_id as offering_id during a separately reviewed migration.


CREATE TABLE menu_publication (
	publication_id INTEGER NOT NULL AUTO_INCREMENT, 
	source_name VARCHAR(80) NOT NULL, 
	source_url VARCHAR(500) NOT NULL, 
	observed_at DATETIME NOT NULL, 
	payload_sha256 VARCHAR(64) NOT NULL, 
	is_reference BOOL NOT NULL, 
	PRIMARY KEY (publication_id), 
	CONSTRAINT ck_publication_reference CHECK (is_reference IN (0, 1)), 
	UNIQUE (payload_sha256)
)ENGINE=InnoDB

;


CREATE TABLE menu_entry (
	publication_id INTEGER NOT NULL, 
	source_item_id VARCHAR(100) NOT NULL, 
	item_name VARCHAR(150) NOT NULL, 
	description VARCHAR(1000) NOT NULL, 
	reference_price NUMERIC(10, 2) NOT NULL, 
	dietary_label VARCHAR(80) NOT NULL, 
	PRIMARY KEY (publication_id, source_item_id), 
	CONSTRAINT ck_entry_price CHECK (reference_price >= 0), 
	FOREIGN KEY(publication_id) REFERENCES menu_publication (publication_id) ON DELETE RESTRICT
)ENGINE=InnoDB

;


CREATE TABLE outlet_offering (
	offering_id INTEGER NOT NULL AUTO_INCREMENT, 
	place_id INTEGER NOT NULL, 
	publication_id INTEGER NOT NULL, 
	source_item_id VARCHAR(100) NOT NULL, 
	is_available BOOL NOT NULL, 
	price_override NUMERIC(10, 2), 
	name_override VARCHAR(150), 
	description_override VARCHAR(1000), 
	dietary_override VARCHAR(80), 
	PRIMARY KEY (offering_id), 
	CONSTRAINT fk_offering_entry FOREIGN KEY(publication_id, source_item_id) REFERENCES menu_entry (publication_id, source_item_id) ON DELETE RESTRICT, 
	CONSTRAINT uq_outlet_entry UNIQUE (place_id, publication_id, source_item_id), 
	CONSTRAINT ck_offering_price CHECK (price_override IS NULL OR price_override >= 0), 
	CONSTRAINT ck_offering_available CHECK (is_available IN (0, 1)), 
	FOREIGN KEY(place_id) REFERENCES food_place (place_id) ON DELETE RESTRICT
)ENGINE=InnoDB

;

CREATE INDEX ix_offering_venue_available ON outlet_offering (place_id, is_available, offering_id);


CREATE TABLE tag (
	tag_id INTEGER NOT NULL AUTO_INCREMENT, 
	tag_name VARCHAR(80) NOT NULL, 
	PRIMARY KEY (tag_id), 
	UNIQUE (tag_name)
)ENGINE=InnoDB

;


CREATE TABLE place_tag (
	place_id INTEGER NOT NULL, 
	tag_id INTEGER NOT NULL, 
	PRIMARY KEY (place_id, tag_id), 
	FOREIGN KEY(place_id) REFERENCES food_place (place_id) ON DELETE RESTRICT, 
	FOREIGN KEY(tag_id) REFERENCES tag (tag_id) ON DELETE RESTRICT
)ENGINE=InnoDB

;
