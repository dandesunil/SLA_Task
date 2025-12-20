-- =========================================================
-- SLA Tracker - Complete Database Initialization Script
-- =========================================================

-- -------------------------
-- Extensions
-- -------------------------
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- -------------------------
-- ENUM Types (MUST MATCH PYTHON ENUMS)
-- -------------------------

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ticketstatus') THEN
        CREATE TYPE ticketstatus AS ENUM (
            'open',
            'in_progress',
            'pending_customer',
            'pending_internal',
            'resolved',
            'closed',
            'cancelled'
        );
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'priority') THEN
        CREATE TYPE priority AS ENUM ('P0', 'P1', 'P2', 'P3');
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'customertier') THEN
        CREATE TYPE customertier AS ENUM (
            'ENTERPRISE',
            'PREMIUM',
            'STANDARD',
            'BASIC'
        );
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'slastatus') THEN
        CREATE TYPE slastatus AS ENUM (
            'COMPLIANT',
            'WARNING',
            'CRITICAL',
            'BREACHED',
            'PAUSED'
        );
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'escalationlevel') THEN
        CREATE TYPE escalationlevel AS ENUM (
            'LEVEL_0',
            'LEVEL_1',
            'LEVEL_2',
            'LEVEL_3',
            'LEVEL_4'
        );
    END IF;
END$$;

-- -------------------------
-- Trigger function
-- -------------------------
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =========================================================
-- 🚨 SQLAlchemy MUST CREATE TABLES AFTER THIS POINT 🚨
-- =========================================================
-- Run:
--   python scripts/init_db.py
-- =========================================================


-- =========================================================
-- POST-TABLE SETUP (SAFE TO RUN AFTER TABLE CREATION)
-- =========================================================

-- -------------------------
-- Indexes
-- -------------------------

CREATE INDEX IF NOT EXISTS idx_tickets_status_created
    ON tickets(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tickets_priority_customer_tier
    ON tickets(priority, customer_tier);

CREATE INDEX IF NOT EXISTS idx_tickets_response_sla_status
    ON tickets(response_sla_status);

CREATE INDEX IF NOT EXISTS idx_tickets_resolution_sla_status
    ON tickets(resolution_sla_status);

CREATE INDEX IF NOT EXISTS idx_tickets_escalation_level
    ON tickets(escalation_level);

CREATE INDEX IF NOT EXISTS idx_tickets_assigned_to
    ON tickets(assigned_to);

CREATE INDEX IF NOT EXISTS idx_tickets_department
    ON tickets(department);

CREATE INDEX IF NOT EXISTS idx_alerts_active_created
    ON alerts(is_active, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_alerts_ticket_id
    ON alerts(ticket_id);

CREATE INDEX IF NOT EXISTS idx_alerts_type_sla_type
    ON alerts(alert_type, sla_type);

CREATE INDEX IF NOT EXISTS idx_status_history_ticket_changed
    ON ticket_status_history(ticket_id, changed_at DESC);

-- -------------------------
-- Trigger on tickets.updated_at
-- -------------------------
DROP TRIGGER IF EXISTS update_tickets_updated_at ON tickets;

CREATE TRIGGER update_tickets_updated_at
BEFORE UPDATE ON tickets
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();
