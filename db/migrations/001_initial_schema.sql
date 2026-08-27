-- db/migrations/001_initial_schema.sql

-- Reference table: pipeline stages
CREATE TABLE pipeline_stages (
    name VARCHAR PRIMARY KEY,
    category VARCHAR NOT NULL,
    sort_order INTEGER NOT NULL
);

INSERT INTO pipeline_stages (name, category, sort_order) VALUES
    ('Responded', 'active', 1),
    ('Call Scheduled', 'active', 2),
    ('Discovery & Demo', 'active', 3),
    ('Evaluation', 'active', 4),
    ('Committed', 'active', 5),
    ('Referral Partner', 'active', 6),
    ('Reconnect later', 'paused', 100),
    ('Interest / Blocked - Red Tape (Org)', 'paused', 101),
    ('Interest / Blocked - internal process', 'paused', 102),
    ('Went Dark', 'closed', 200),
    ('No Show', 'closed', 201),
    ('Not a Fit - ICP Mismatch', 'closed', 202),
    ('Not a Fit - Tire Kicker', 'closed', 203),
    ('Not a Fit - No Need', 'closed', 204);

-- Contacts
CREATE SEQUENCE contacts_id_seq START 1;
CREATE TABLE contacts (
    id INTEGER DEFAULT nextval('contacts_id_seq'),
    name VARCHAR NOT NULL,
    company VARCHAR,
    title VARCHAR,
    linkedin_url VARCHAR,
    last_contact_date DATE,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (id)
);

-- Contact emails (multiple per contact for integration matching)
CREATE SEQUENCE contact_emails_id_seq START 1;
CREATE TABLE contact_emails (
    id INTEGER DEFAULT nextval('contact_emails_id_seq'),
    contact_id INTEGER NOT NULL REFERENCES contacts(id),
    email VARCHAR NOT NULL UNIQUE,
    is_primary BOOLEAN DEFAULT false,
    PRIMARY KEY (id)
);

-- Deals
CREATE SEQUENCE deals_id_seq START 1;
CREATE TABLE deals (
    id INTEGER DEFAULT nextval('deals_id_seq'),
    contact_id INTEGER NOT NULL REFERENCES contacts(id),
    name VARCHAR NOT NULL,
    stage VARCHAR NOT NULL REFERENCES pipeline_stages(name),
    value DECIMAL(12, 2),
    expected_close DATE,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (id)
);

-- Interactions
CREATE SEQUENCE interactions_id_seq START 1;
CREATE TABLE interactions (
    id INTEGER DEFAULT nextval('interactions_id_seq'),
    contact_id INTEGER NOT NULL REFERENCES contacts(id),
    deal_id INTEGER REFERENCES deals(id),
    type VARCHAR NOT NULL,
    summary TEXT,
    next_connect_date DATE,
    source VARCHAR DEFAULT 'manual',
    occurred_at TIMESTAMP DEFAULT now(),
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (id)
);

-- Action items (per-item tracking from interactions)
CREATE SEQUENCE action_items_id_seq START 1;
CREATE TABLE action_items (
    id INTEGER DEFAULT nextval('action_items_id_seq'),
    interaction_id INTEGER NOT NULL REFERENCES interactions(id),
    description TEXT NOT NULL,
    owner VARCHAR,
    due_date DATE,
    completed BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (id)
);

-- Notes (persistent context about contacts)
CREATE SEQUENCE notes_id_seq START 1;
CREATE TABLE notes (
    id INTEGER DEFAULT nextval('notes_id_seq'),
    contact_id INTEGER NOT NULL REFERENCES contacts(id),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (id)
);

-- Stage history (tracks every deal stage change)
CREATE SEQUENCE stage_history_id_seq START 1;
CREATE TABLE stage_history (
    id INTEGER DEFAULT nextval('stage_history_id_seq'),
    deal_id INTEGER NOT NULL REFERENCES deals(id),
    from_stage VARCHAR,
    to_stage VARCHAR NOT NULL REFERENCES pipeline_stages(name),
    changed_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (id)
);
