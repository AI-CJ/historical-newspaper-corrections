CREATE TABLE block_revisions (
    block_id bigint NOT NULL REFERENCES blocks(id),
    version bigint NOT NULL CHECK (version > 0),
    transcription text NOT NULL CHECK (transcription ~ '[^[:space:]]'),
    saved_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (block_id, version)
);

CREATE VIEW current_blocks AS
SELECT b.*, COALESCE(r.version, 0) AS version,
       COALESCE(r.transcription, b.original_text) AS transcription
FROM blocks AS b
LEFT JOIN LATERAL (
    SELECT version, transcription FROM block_revisions
    WHERE block_id = b.id ORDER BY version DESC LIMIT 1
) AS r ON true;
