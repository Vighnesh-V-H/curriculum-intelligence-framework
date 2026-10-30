-- =============================================================================
-- 003_document_ingestion.sql
-- AI-Powered Curriculum Intelligence & Verification Framework
-- PostgreSQL 16+
--
-- Implements the documents table described in docs/lld/document-processing.md.
-- Requirements covered: FR-13.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- FR-13: curriculum document processing
-- -----------------------------------------------------------------------------

CREATE TABLE documents (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_filename VARCHAR(255) NOT NULL,
    file_extension    VARCHAR(10)  NOT NULL,
    content_type      VARCHAR(100),
    size_bytes        BIGINT       NOT NULL,
    checksum_sha256   VARCHAR(64)  NOT NULL,
    storage_path      VARCHAR(500) NOT NULL,
    status            VARCHAR(20)  NOT NULL DEFAULT 'UPLOADED',
    extracted_text    TEXT,
    llm_analysis      JSONB,
    llm_model         VARCHAR(100),
    error_message     TEXT,
    uploaded_by       UUID         NOT NULL REFERENCES users (id),
    uploaded_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    processed_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT chk_documents_status CHECK (
        status IN ('UPLOADED', 'PROCESSING', 'COMPLETED', 'FAILED')
    )
);

CREATE INDEX idx_documents_uploader ON documents (uploaded_by, status);

CREATE TRIGGER trg_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
