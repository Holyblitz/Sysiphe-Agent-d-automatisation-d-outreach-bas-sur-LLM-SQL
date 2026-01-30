-- Sysiphe database schema (V1)
-- PostgreSQL

CREATE TABLE IF NOT EXISTS scrape_runs (
    run_id UUID PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_url TEXT,
    country_code CHAR(2) NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS companies_raw (
    raw_id BIGSERIAL PRIMARY KEY,
    run_id UUID REFERENCES scrape_runs(run_id),
    scraped_at TIMESTAMPTZ DEFAULT now(),
    source_name TEXT NOT NULL,
    source_url TEXT,
    company_name TEXT,
    website_url TEXT,
    country_code CHAR(2) NOT NULL,
    category_hint TEXT,
    extra JSONB
);

CREATE TABLE IF NOT EXISTS companies (
    company_id UUID PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    website_url TEXT NOT NULL,
    website_domain TEXT NOT NULL UNIQUE,
    country_code CHAR(2) NOT NULL,
    source_names TEXT[] NOT NULL DEFAULT '{}',
    source_urls TEXT[] NOT NULL DEFAULT '{}',
    first_seen_at TIMESTAMPTZ DEFAULT now(),
    last_seen_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS outreach_queue (
    outreach_id UUID PRIMARY KEY,
    company_id UUID REFERENCES companies(company_id),
    status TEXT NOT NULL CHECK (
        status IN (
            'new',
            'qualified',
            'draft_ready',
            'sent',
            'replied',
            'bounced',
            'do_not_contact'
        )
    ),
    priority SMALLINT DEFAULT 3,
    contact_email TEXT,
    contact_name TEXT,
    contact_role TEXT,
    email_subject TEXT,
    email_body TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    sent_at TIMESTAMPTZ
);
