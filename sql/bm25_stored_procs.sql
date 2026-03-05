-- BM25 Stored Procedures for PostgreSQL 14.22
-- Pure SQL implementation without pg_search extension

-- Table for document statistics (IDF and collection stats)
CREATE TABLE IF NOT EXISTS bm25_doc_stats (
    id SERIAL PRIMARY KEY,
    total_docs INTEGER NOT NULL DEFAULT 0,
    avg_doc_length FLOAT NOT NULL DEFAULT 0.0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table for term statistics (document frequency)
CREATE TABLE IF NOT EXISTS bm25_term_stats (
    id SERIAL PRIMARY KEY,
    term TEXT UNIQUE NOT NULL,
    doc_freq INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table for term frequency per document
CREATE TABLE IF NOT EXISTS bm25_term_freq (
    id SERIAL PRIMARY KEY,
    prompt_id UUID REFERENCES refined_prompts(id) ON DELETE CASCADE,
    term TEXT NOT NULL,
    term_count INTEGER NOT NULL DEFAULT 0,
    doc_length INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(prompt_id, term)
);

-- Index for term lookup
CREATE INDEX IF NOT EXISTS idx_bm25_term_freq_term ON bm25_term_freq(term);
CREATE INDEX IF NOT EXISTS idx_bm25_term_freq_prompt_id ON bm25_term_freq(prompt_id);

-- Function to extract terms from text (simple tokenization)
CREATE OR REPLACE FUNCTION extract_terms(text_input TEXT)
RETURNS TEXT[] AS $$
DECLARE
    cleaned_text TEXT;
    terms TEXT[];
BEGIN
    -- Convert to lowercase
    cleaned_text := LOWER(text_input);
    
    -- Remove special characters (keep alphanumeric and spaces)
    cleaned_text := REGEXP_REPLACE(cleaned_text, '[^a-z0-9\s]', ' ', 'g');
    
    -- Split into array (PostgreSQL array from string)
    SELECT ARRAY_AGG(term)
    INTO terms
    FROM (
        SELECT DISTINCT TRIM(term) AS term
        FROM UNNEST(STRING_TO_ARRAY(cleaned_text, ' ')) AS term
        WHERE LENGTH(TRIM(term)) > 2  -- Filter short words
    ) subq;
    
    RETURN COALESCE(terms, ARRAY[]::TEXT[]);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to calculate Inverse Document Frequency (IDF)
CREATE OR REPLACE FUNCTION bm25_idf(term TEXT)
RETURNS FLOAT AS $$
DECLARE
    total_docs INTEGER;
    doc_freq INTEGER;
    idf FLOAT;
BEGIN
    -- Get total document count
    SELECT COALESCE(total_docs, 0) INTO total_docs
    FROM bm25_doc_stats
    ORDER BY updated_at DESC
    LIMIT 1;
    
    IF total_docs = 0 THEN
        RETURN 0.0;
    END IF;
    
    -- Get document frequency for term
    SELECT COALESCE(doc_freq, 0) INTO doc_freq
    FROM bm25_term_stats
    WHERE bm25_term_stats.term = term;
    
    -- BM25 IDF: log((N - n + 0.5) / (n + 0.5))
    -- Using natural log (ln) as per standard BM25
    idf := LN((total_docs - doc_freq + 0.5) / (doc_freq + 0.5));
    
    RETURN GREATEST(idf, 0.0);  -- Ensure non-negative
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to calculate term frequency in a specific document
CREATE OR REPLACE FUNCTION bm25_term_frequency(term TEXT, prompt_id UUID)
RETURNS INTEGER AS $$
DECLARE
    tf INTEGER;
BEGIN
    SELECT COALESCE(term_count, 0) INTO tf
    FROM bm25_term_freq
    WHERE bm25_term_freq.term = term
      AND bm25_term_freq.prompt_id = prompt_id;
    
    RETURN COALESCE(tf, 0);
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to get document length
CREATE OR REPLACE FUNCTION bm25_doc_length(prompt_id UUID)
RETURNS INTEGER AS $$
DECLARE
    doc_len INTEGER;
BEGIN
    SELECT MAX(doc_length) INTO doc_len
    FROM bm25_term_freq
    WHERE bm25_term_freq.prompt_id = $1
    LIMIT 1;
    
    RETURN COALESCE(doc_len, 0);
END;
$$ LANGUAGE plpgsql STABLE;

-- Main BM25 scoring function for a single document
CREATE OR REPLACE FUNCTION bm25_score(
    query_terms TEXT[],
    prompt_id UUID,
    k1 FLOAT DEFAULT 1.2,
    b FLOAT DEFAULT 0.75
)
RETURNS FLOAT AS $$
DECLARE
    total_docs INTEGER;
    avg_doc_length FLOAT;
    doc_len INTEGER;
    score FLOAT := 0.0;
    term TEXT;
    idf FLOAT;
    tf INTEGER;
    term_score FLOAT;
BEGIN
    -- Get collection statistics
    SELECT COALESCE(total_docs, 0), COALESCE(avg_doc_length, 1.0)
    INTO total_docs, avg_doc_length
    FROM bm25_doc_stats
    ORDER BY updated_at DESC
    LIMIT 1;
    
    IF total_docs = 0 OR avg_doc_length = 0 THEN
        RETURN 0.0;
    END IF;
    
    -- Get document length for this specific document
    doc_len := bm25_doc_length(prompt_id);
    
    -- Calculate BM25 score for each query term
    FOREACH term IN ARRAY query_terms
    LOOP
        -- Get IDF for term
        idf := bm25_idf(term);
        
        -- Get term frequency in document
        tf := bm25_term_frequency(term, prompt_id);
        
        -- BM25 term score: IDF * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_len / avg_doc_length)))
        IF tf > 0 THEN
            term_score := idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_len::FLOAT / avg_doc_length)));
            score := score + term_score;
        END IF;
    END LOOP;
    
    RETURN score;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to search prompts using BM25
CREATE OR REPLACE FUNCTION bm25_search(
    query_text TEXT,
    agent_type_filter TEXT DEFAULT NULL,
    limit_count INTEGER DEFAULT 5,
    k1 FLOAT DEFAULT 1.2,
    b FLOAT DEFAULT 0.75
)
RETURNS TABLE(
    prompt_id UUID,
    prompt_key UUID,
    original_prompt TEXT,
    refined_prompt TEXT,
    agent_type TEXT,
    average_score FLOAT,
    usage_count INTEGER,
    bm25_score_result FLOAT
) AS $$
DECLARE
    query_terms TEXT[];
BEGIN
    -- Extract terms from query
    query_terms := extract_terms(query_text);
    
    IF array_length(query_terms, 1) IS NULL THEN
        RETURN;
    END IF;
    
    RETURN QUERY
    SELECT 
        rp.id AS prompt_id,
        rp.prompt_key,
        rp.original_prompt,
        rp.refined_prompt,
        rp.agent_type::TEXT,  -- Cast VARCHAR(100) to TEXT
        rp.average_score,
        rp.usage_count,
        bm25_score(query_terms, rp.id, k1, b) AS bm25_score_result
    FROM refined_prompts rp
    WHERE rp.is_active = TRUE
      AND (agent_type_filter IS NULL OR rp.agent_type = agent_type_filter)
      AND EXISTS (
          SELECT 1 FROM bm25_term_freq btf
          WHERE btf.prompt_id = rp.id
            AND btf.term = ANY(query_terms)
      )
    ORDER BY bm25_score_result DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql STABLE;

-- Procedure to update document statistics
CREATE OR REPLACE PROCEDURE bm25_update_stats()
LANGUAGE plpgsql AS $$
DECLARE
    total_docs INTEGER;
    avg_length FLOAT;
BEGIN
    -- Calculate total document count
    SELECT COUNT(DISTINCT prompt_id) INTO total_docs
    FROM bm25_term_freq;
    
    -- Calculate average document length
    SELECT COALESCE(AVG(doc_length), 0.0) INTO avg_length
    FROM (
        SELECT DISTINCT ON (prompt_id) doc_length
        FROM bm25_term_freq
    ) subq;
    
    -- Update or insert stats
    INSERT INTO bm25_doc_stats (total_docs, avg_doc_length, updated_at)
    VALUES (total_docs, avg_length, NOW())
    ON CONFLICT (id) DO UPDATE
    SET total_docs = EXCLUDED.total_docs,
        avg_doc_length = EXCLUDED.avg_doc_length,
        updated_at = EXCLUDED.updated_at;
    
    -- Update term document frequencies
    INSERT INTO bm25_term_stats (term, doc_freq, updated_at)
    SELECT 
        term,
        COUNT(DISTINCT prompt_id) AS doc_freq,
        NOW()
    FROM bm25_term_freq
    GROUP BY term
    ON CONFLICT (term) DO UPDATE
    SET doc_freq = EXCLUDED.doc_freq,
        updated_at = EXCLUDED.updated_at;
END;
$$;

-- Procedure to index a new prompt for BM25
CREATE OR REPLACE PROCEDURE bm25_index_prompt(
    p_prompt_id UUID,
    p_original_prompt TEXT,
    p_refined_prompt TEXT
)
LANGUAGE plpgsql AS $$
DECLARE
    combined_text TEXT;
    all_terms TEXT[];
    term TEXT;
    term_counts TEXT[];
    term_count INTEGER;
    doc_len INTEGER;
BEGIN
    -- Combine original and refined prompt
    combined_text := COALESCE(p_original_prompt, '') || ' ' || COALESCE(p_refined_prompt, '');
    
    -- Extract terms
    all_terms := extract_terms(combined_text);
    
    IF array_length(all_terms, 1) IS NULL THEN
        RETURN;
    END IF;
    
    -- Calculate document length (total word count)
    SELECT COUNT(*) INTO doc_len
    FROM UNNEST(STRING_TO_ARRAY(LOWER(combined_text), ' ')) AS word
    WHERE LENGTH(TRIM(word)) > 0;
    
    -- Delete existing index entries for this prompt
    DELETE FROM bm25_term_freq WHERE prompt_id = p_prompt_id;
    
    -- Insert term frequencies
    FOREACH term IN ARRAY all_terms
    LOOP
        -- Count occurrences of term in combined text
        SELECT COUNT(*) INTO term_count
        FROM UNNEST(STRING_TO_ARRAY(LOWER(combined_text), ' ')) AS w
        WHERE TRIM(w) = term;
        
        INSERT INTO bm25_term_freq (prompt_id, term, term_count, doc_length)
        VALUES (p_prompt_id, term, term_count, doc_len)
        ON CONFLICT (prompt_id, term) DO UPDATE
        SET term_count = EXCLUDED.term_count,
            doc_length = EXCLUDED.doc_length;
    END LOOP;
    
    -- Update collection stats (optional - can be batched)
    -- CALL bm25_update_stats();
END;
$$;

-- Trigger to automatically index new prompts
CREATE OR REPLACE FUNCTION bm25_index_trigger()
RETURNS TRIGGER AS $$
BEGIN
    CALL bm25_index_prompt(NEW.id, NEW.original_prompt, NEW.refined_prompt);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Uncomment to enable automatic indexing on prompt creation
-- CREATE TRIGGER trg_bm25_index_prompt
--     AFTER INSERT ON refined_prompts
--     FOR EACH ROW
--     EXECUTE FUNCTION bm25_index_trigger();

-- Initial data: index existing prompts
-- CALL bm25_index_prompt(prompt_id, original_prompt, refined_prompt) for each existing row
