--
-- PostgreSQL database dump
--

\restrict xLNkiEVtxNMbQkoNr8Om8d58JIHcTmUyUK76UlA8ItN8MsCfZXcBKxvDWh2VxeR

-- Dumped from database version 18.0
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

ALTER TABLE IF EXISTS ONLY public.charter_beverages DROP CONSTRAINT IF EXISTS charter_beverages_charter_id_fkey;
ALTER TABLE IF EXISTS ONLY public.charter_beverages DROP CONSTRAINT IF EXISTS charter_beverages_beverage_item_id_fkey;
DROP INDEX IF EXISTS public.idx_charter_beverages_created_at;
DROP INDEX IF EXISTS public.idx_charter_beverages_charter_id;
DROP INDEX IF EXISTS public.idx_charter_beverages_beverage_item_id;
ALTER TABLE IF EXISTS ONLY public.charter_beverages DROP CONSTRAINT IF EXISTS charter_beverages_pkey;
ALTER TABLE IF EXISTS public.charter_beverages ALTER COLUMN id DROP DEFAULT;
DROP SEQUENCE IF EXISTS public.charter_beverages_id_seq;
DROP TABLE IF EXISTS public.charter_beverages;
SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: charter_beverages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.charter_beverages (
    id integer NOT NULL,
    charter_id integer NOT NULL,
    beverage_item_id integer,
    item_name character varying(255) NOT NULL,
    quantity integer DEFAULT 1 NOT NULL,
    unit_price_charged numeric(10,2) NOT NULL,
    unit_our_cost numeric(10,2) NOT NULL,
    deposit_per_unit numeric(10,2) DEFAULT 0.00,
    line_amount_charged numeric(10,2) GENERATED ALWAYS AS (((quantity)::numeric * unit_price_charged)) STORED,
    line_cost numeric(10,2) GENERATED ALWAYS AS (((quantity)::numeric * unit_our_cost)) STORED,
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_prices CHECK (((unit_price_charged >= (0)::numeric) AND (unit_our_cost >= (0)::numeric))),
    CONSTRAINT valid_quantities CHECK ((quantity > 0))
);


--
-- Name: TABLE charter_beverages; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.charter_beverages IS 'Snapshot of beverages charged to charter. Prices are locked at time of charter creation.
Editing quantities/prices here does NOT affect master beverage_products table.
Used for historical accuracy, guest disputes, and profit margin tracking.';


--
-- Name: COLUMN charter_beverages.unit_price_charged; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.charter_beverages.unit_price_charged IS 'What we charged the GUEST for this item (includes GST). LOCKED at snapshot time.';


--
-- Name: COLUMN charter_beverages.unit_our_cost; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.charter_beverages.unit_our_cost IS 'What Arrow Limousine PAID the supplier (wholesale cost). LOCKED at snapshot time.';


--
-- Name: COLUMN charter_beverages.notes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.charter_beverages.notes IS 'Audit trail: "Price negotiated down $5.49→$4.99", "Guest requested substitution", etc.';


--
-- Name: charter_beverages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.charter_beverages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: charter_beverages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.charter_beverages_id_seq OWNED BY public.charter_beverages.id;


--
-- Name: charter_beverages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_beverages ALTER COLUMN id SET DEFAULT nextval('public.charter_beverages_id_seq'::regclass);


--
-- Data for Name: charter_beverages; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.charter_beverages (id, charter_id, beverage_item_id, item_name, quantity, unit_price_charged, unit_our_cost, deposit_per_unit, notes, created_at, updated_at) FROM stdin;
\.


--
-- Name: charter_beverages_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.charter_beverages_id_seq', 2, true);


--
-- Name: charter_beverages charter_beverages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_beverages
    ADD CONSTRAINT charter_beverages_pkey PRIMARY KEY (id);


--
-- Name: idx_charter_beverages_beverage_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charter_beverages_beverage_item_id ON public.charter_beverages USING btree (beverage_item_id);


--
-- Name: idx_charter_beverages_charter_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charter_beverages_charter_id ON public.charter_beverages USING btree (charter_id);


--
-- Name: idx_charter_beverages_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charter_beverages_created_at ON public.charter_beverages USING btree (created_at);


--
-- Name: charter_beverages charter_beverages_beverage_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_beverages
    ADD CONSTRAINT charter_beverages_beverage_item_id_fkey FOREIGN KEY (beverage_item_id) REFERENCES public.beverage_products(item_id);


--
-- Name: charter_beverages charter_beverages_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_beverages
    ADD CONSTRAINT charter_beverages_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict xLNkiEVtxNMbQkoNr8Om8d58JIHcTmUyUK76UlA8ItN8MsCfZXcBKxvDWh2VxeR

