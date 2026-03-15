--
-- PostgreSQL database dump
--

\restrict MCUASCeiiulk2fw7FgktbTlD3yp0ZiflSaIHm47EXBKDwKlNuwgD4ZMn7A82OlO

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

ALTER TABLE IF EXISTS ONLY public.charter_beverage_orders DROP CONSTRAINT IF EXISTS charter_beverage_orders_charter_id_fkey;
DROP INDEX IF EXISTS public.idx_beverage_orders_reserve;
ALTER TABLE IF EXISTS ONLY public.charter_beverage_orders DROP CONSTRAINT IF EXISTS charter_beverage_orders_pkey;
ALTER TABLE IF EXISTS public.charter_beverage_orders ALTER COLUMN beverage_order_id DROP DEFAULT;
DROP SEQUENCE IF EXISTS public.charter_beverage_orders_beverage_order_id_seq;
DROP TABLE IF EXISTS public.charter_beverage_orders;
SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: charter_beverage_orders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.charter_beverage_orders (
    beverage_order_id integer NOT NULL,
    charter_id integer,
    reserve_number character varying(50),
    created_at timestamp with time zone DEFAULT now(),
    created_by character varying(100),
    purchase_receipt_url character varying(500),
    receipt_attached boolean DEFAULT false,
    total_amount numeric(12,2),
    gst_amount numeric(12,2),
    deposit_amount numeric(12,2),
    grand_total numeric(12,2),
    driver_verified boolean DEFAULT false,
    driver_verified_at timestamp with time zone,
    driver_verified_by character varying(100),
    discrepancies text
);


--
-- Name: charter_beverage_orders_beverage_order_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.charter_beverage_orders_beverage_order_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: charter_beverage_orders_beverage_order_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.charter_beverage_orders_beverage_order_id_seq OWNED BY public.charter_beverage_orders.beverage_order_id;


--
-- Name: charter_beverage_orders beverage_order_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_beverage_orders ALTER COLUMN beverage_order_id SET DEFAULT nextval('public.charter_beverage_orders_beverage_order_id_seq'::regclass);


--
-- Data for Name: charter_beverage_orders; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.charter_beverage_orders (beverage_order_id, charter_id, reserve_number, created_at, created_by, purchase_receipt_url, receipt_attached, total_amount, gst_amount, deposit_amount, grand_total, driver_verified, driver_verified_at, driver_verified_by, discrepancies) FROM stdin;
\.


--
-- Name: charter_beverage_orders_beverage_order_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.charter_beverage_orders_beverage_order_id_seq', 1, false);


--
-- Name: charter_beverage_orders charter_beverage_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_beverage_orders
    ADD CONSTRAINT charter_beverage_orders_pkey PRIMARY KEY (beverage_order_id);


--
-- Name: idx_beverage_orders_reserve; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_beverage_orders_reserve ON public.charter_beverage_orders USING btree (reserve_number);


--
-- Name: charter_beverage_orders charter_beverage_orders_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_beverage_orders
    ADD CONSTRAINT charter_beverage_orders_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id);


--
-- PostgreSQL database dump complete
--

\unrestrict MCUASCeiiulk2fw7FgktbTlD3yp0ZiflSaIHm47EXBKDwKlNuwgD4ZMn7A82OlO

