CREATE TABLE pages (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    catalog_url text NOT NULL UNIQUE,
    title text NOT NULL,
    issue_date date NOT NULL,
    page_number integer NOT NULL CHECK (page_number > 0),
    scan_url text NOT NULL
);

CREATE TABLE blocks (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    page_id bigint NOT NULL REFERENCES pages(id),
    source_id text NOT NULL,
    position integer NOT NULL CHECK (position > 0),
    original_text text NOT NULL CHECK (original_text ~ '[^[:space:]]'),
    UNIQUE (page_id, source_id),
    UNIQUE (page_id, position)
);

CREATE FUNCTION protect_original_text() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Original OCR cannot be overwritten'
        USING ERRCODE = 'check_violation';
END;
$$;

CREATE TRIGGER keep_original_text
BEFORE UPDATE ON blocks FOR EACH ROW
WHEN (OLD.original_text IS DISTINCT FROM NEW.original_text)
EXECUTE FUNCTION protect_original_text();
