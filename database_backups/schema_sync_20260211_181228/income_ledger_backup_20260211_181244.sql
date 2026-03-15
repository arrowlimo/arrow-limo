--
-- PostgreSQL database dump
--

\restrict 9JrgtzXRA7Rw8zOL2PFaSwdNaTQG67kTiEak9TmfaIk1xldZpYUpil61eFScSXd

-- Dumped from database version 17.7
-- Dumped by pg_dump version 18.0

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: income_ledger; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.income_ledger (
    income_id integer NOT NULL,
    payment_id integer,
    source_system character varying(50) DEFAULT 'payments'::character varying,
    transaction_date date NOT NULL,
    fiscal_year integer GENERATED ALWAYS AS (EXTRACT(year FROM transaction_date)) STORED,
    fiscal_quarter integer GENERATED ALWAYS AS (EXTRACT(quarter FROM transaction_date)) STORED,
    revenue_category character varying(100) NOT NULL,
    revenue_subcategory character varying(100),
    gross_amount numeric(12,2) NOT NULL,
    gst_collected numeric(12,2) DEFAULT 0,
    net_amount numeric(12,2) GENERATED ALWAYS AS ((gross_amount - gst_collected)) STORED,
    is_taxable boolean DEFAULT true,
    tax_province character varying(2) DEFAULT 'AB'::character varying,
    client_id integer,
    charter_id integer,
    reserve_number character varying(50),
    payment_method character varying(100),
    payment_reference character varying(200),
    description text,
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    created_by character varying(100) DEFAULT 'create_income_ledger.py'::character varying,
    reconciled boolean DEFAULT false,
    reconciled_date date,
    reconciled_by character varying(100),
    receipt_id bigint,
    banking_transaction_id bigint,
    accounting_entry_id bigint
);


--
-- Name: TABLE income_ledger; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.income_ledger IS 'Revenue tracking ledger with QuickBooks-style categorization and GST extraction';


--
-- Name: COLUMN income_ledger.revenue_category; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.income_ledger.revenue_category IS 'Top-level revenue classification: Operating Revenue, Other Revenue, Contra Revenue';


--
-- Name: COLUMN income_ledger.revenue_subcategory; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.income_ledger.revenue_subcategory IS 'Detailed revenue type: Charter Services, Retainers, Miscellaneous, etc.';


--
-- Name: COLUMN income_ledger.gst_collected; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.income_ledger.gst_collected IS 'GST extracted from gross_amount using included-tax formula (AB: 5%)';


--
-- Name: income_ledger_income_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.income_ledger_income_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: income_ledger_income_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.income_ledger_income_id_seq OWNED BY public.income_ledger.income_id;


--
-- Name: income_ledger income_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.income_ledger ALTER COLUMN income_id SET DEFAULT nextval('public.income_ledger_income_id_seq'::regclass);


--
-- Data for Name: income_ledger; Type: TABLE DATA; Schema: public; Owner: -
--



--
-- Name: income_ledger_income_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.income_ledger_income_id_seq', 1, false);


--
-- Name: income_ledger income_ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.income_ledger
    ADD CONSTRAINT income_ledger_pkey PRIMARY KEY (income_id);


--
-- Name: idx_income_ledger_charter_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_income_ledger_charter_id ON public.income_ledger USING btree (charter_id);


--
-- Name: idx_income_ledger_client_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_income_ledger_client_id ON public.income_ledger USING btree (client_id);


--
-- Name: idx_income_ledger_fiscal_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_income_ledger_fiscal_year ON public.income_ledger USING btree (fiscal_year);


--
-- Name: idx_income_ledger_payment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_income_ledger_payment_id ON public.income_ledger USING btree (payment_id);


--
-- Name: idx_income_ledger_revenue_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_income_ledger_revenue_category ON public.income_ledger USING btree (revenue_category);


--
-- Name: idx_income_ledger_transaction_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_income_ledger_transaction_date ON public.income_ledger USING btree (transaction_date);


--
-- Name: income_ledger income_ledger_payment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.income_ledger
    ADD CONSTRAINT income_ledger_payment_id_fkey FOREIGN KEY (payment_id) REFERENCES public.payments(payment_id);


--
-- PostgreSQL database dump complete
--

\unrestrict 9JrgtzXRA7Rw8zOL2PFaSwdNaTQG67kTiEak9TmfaIk1xldZpYUpil61eFScSXd

