ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS file_data BYTEA,
    ADD COLUMN IF NOT EXISTS mime_type TEXT,
    ADD COLUMN IF NOT EXISTS storage_source TEXT,
    ADD COLUMN IF NOT EXISTS entity_id TEXT,
    ADD COLUMN IF NOT EXISTS subfolder TEXT,
    ADD COLUMN IF NOT EXISTS uploaded_by_username TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_web_location
ON documents (category, entity_id, subfolder, file_path)
WHERE storage_source = 'web';
