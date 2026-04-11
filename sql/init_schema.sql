CREATE TABLE IF NOT EXISTS performers (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    source TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS performer_aliases (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    performer_id BIGINT NOT NULL REFERENCES performers(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    UNIQUE (performer_id, normalized_alias)
);

CREATE TABLE IF NOT EXISTS works (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    title TEXT,
    release_date DATE,
    studio TEXT,
    series TEXT,
    synopsis TEXT,
    source_name TEXT NOT NULL DEFAULT '',
    source_url TEXT,
    extra JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS work_performers (
    work_id BIGINT NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    performer_id BIGINT NOT NULL REFERENCES performers(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'performer',
    sort_order INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (work_id, performer_id)
);

CREATE TABLE IF NOT EXISTS tags (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL DEFAULT 'general'
);

CREATE TABLE IF NOT EXISTS work_tags (
    work_id BIGINT NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    tag_id BIGINT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    source TEXT NOT NULL DEFAULT 'pipeline',
    PRIMARY KEY (work_id, tag_id)
);

CREATE TABLE IF NOT EXISTS source_records (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_key TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT,
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (entity_type, entity_key, source_name)
);
