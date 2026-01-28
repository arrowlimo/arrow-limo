-- Create external_documents table for audit artifacts (year-end PDFs, etc.)
CREATE TABLE IF NOT EXISTS external_documents (
    id SERIAL PRIMARY KEY,
    doc_type VARCHAR(100) NOT NULL,
    tax_year INTEGER,
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size BIGINT,
    sha256 CHAR(64),
    source_system VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sha256)
);

CREATE INDEX IF NOT EXISTS idx_external_documents_year ON external_documents(tax_year);
CREATE INDEX IF NOT EXISTS idx_external_documents_type ON external_documents(doc_type);
