-- Longevity Platform Database Schema

-- Users table for authentication and subscriptions
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    stripe_customer_id VARCHAR(255),
    subscription_tier VARCHAR(50) DEFAULT 'free',
    subscription_id VARCHAR(255),
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Content table for all generated content
CREATE TABLE content (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    slug VARCHAR(500) UNIQUE NOT NULL,
    body TEXT NOT NULL,
    type VARCHAR(50) NOT NULL, -- 'newsletter', 'deep-dive', 'vod-lecture', 'research-brief'
    author VARCHAR(255) DEFAULT 'AI-Assisted (Prof. Oh)',
    status VARCHAR(50) DEFAULT 'draft',
    tier VARCHAR(50) DEFAULT 'free', -- 'free', 'premium', 'vip'
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- SEO fields
    meta_title VARCHAR(500),
    meta_description TEXT,
    meta_keywords TEXT,
    
    -- Analytics
    views INTEGER DEFAULT 0,
    read_time INTEGER DEFAULT 0,
    engagement_score DECIMAL(3,2) DEFAULT 0.00
);

-- Research sources tracking
CREATE TABLE research_sources (
    id SERIAL PRIMARY KEY,
    content_id INTEGER REFERENCES content(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    authors TEXT,
    journal VARCHAR(255),
    publication_date DATE,
    doi VARCHAR(255),
    url VARCHAR(1000),
    relevance_score INTEGER,
    abstract TEXT,
    key_findings TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Content-Research relationship (many-to-many)
CREATE TABLE content_research_sources (
    content_id INTEGER REFERENCES content(id) ON DELETE CASCADE,
    research_source_id INTEGER REFERENCES research_sources(id) ON DELETE CASCADE,
    PRIMARY KEY (content_id, research_source_id)
);

-- VOD lectures table
CREATE TABLE vod_lectures (
    id SERIAL PRIMARY KEY,
    content_id INTEGER REFERENCES content(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    duration_minutes INTEGER,
    price DECIMAL(10,2),
    video_url VARCHAR(1000),
    thumbnail_url VARCHAR(1000),
    transcript TEXT,
    status VARCHAR(50) DEFAULT 'published',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Newsletter issues
CREATE TABLE newsletter_issues (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    content_id INTEGER REFERENCES content(id) ON DELETE CASCADE,
    issue_number INTEGER,
    sent_at TIMESTAMP,
    open_rate DECIMAL(5,2),
    click_rate DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Email subscriptions and delivery
CREATE TABLE email_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    subscription_type VARCHAR(50) NOT NULL, -- 'newsletter', 'premium', 'vip'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Email delivery tracking
CREATE TABLE email_delivery (
    id SERIAL PRIMARY KEY,
    subscription_id INTEGER REFERENCES email_subscriptions(id) ON DELETE CASCADE,
    campaign_id VARCHAR(255),
    status VARCHAR(50), -- 'sent', 'delivered', 'opened', 'clicked', 'bounced'
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Analytics events
CREATE TABLE analytics_events (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    event_type VARCHAR(100) NOT NULL, -- 'page_view', 'content_read', 'video_watch', 'subscription'
    properties JSONB, -- Flexible event properties
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address INET,
    user_agent TEXT
);

-- Content engagement
CREATE TABLE content_engagement (
    id SERIAL PRIMARY KEY,
    content_id INTEGER REFERENCES content(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    read_progress INTEGER DEFAULT 0, -- Percentage read for articles/videos
    time_spent INTEGER DEFAULT 0, -- Seconds spent
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Automation logs
CREATE TABLE automation_logs (
    id SERIAL PRIMARY KEY,
    scenario_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL, -- 'started', 'completed', 'failed'
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    execution_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_content_tier ON content(tier);
CREATE INDEX idx_content_type ON content(type);
CREATE INDEX idx_content_status ON content(status);
CREATE INDEX idx_content_published_at ON content(published_at DESC);
CREATE INDEX idx_research_sources_date ON research_sources(publication_date DESC);
CREATE INDEX idx_research_sources_relevance ON research_sources(relevance_score DESC);
CREATE INDEX idx_analytics_events_timestamp ON analytics_events(timestamp DESC);
CREATE INDEX idx_analytics_events_type ON analytics_events(event_type);
CREATE INDEX idx_email_delivery_status ON email_delivery(status);
CREATE INDEX idx_email_delivery_timestamp ON email_delivery(timestamp DESC);

-- Triggers for updated timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_content_updated_at 
    BEFORE UPDATE ON content 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();