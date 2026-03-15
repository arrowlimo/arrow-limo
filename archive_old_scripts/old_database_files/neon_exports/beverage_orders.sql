--
-- PostgreSQL database dump
--

\restrict tDYEXNlvZ79jjE4jIP0yaOTm1MbICh999V8l7HQUXkElTFLBFCtnBLCdY1mZHo9

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

ALTER TABLE IF EXISTS ONLY public.beverage_orders DROP CONSTRAINT IF EXISTS beverage_orders_pkey;
ALTER TABLE IF EXISTS public.beverage_orders ALTER COLUMN order_id DROP DEFAULT;
DROP SEQUENCE IF EXISTS public.beverage_orders_order_id_seq;
DROP TABLE IF EXISTS public.beverage_orders;
SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: beverage_orders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.beverage_orders (
    order_id integer NOT NULL,
    reserve_number character varying(32) NOT NULL,
    order_date timestamp without time zone NOT NULL,
    subtotal numeric(10,2) NOT NULL,
    gst numeric(10,2) NOT NULL,
    total numeric(10,2) NOT NULL,
    status text DEFAULT 'pending'::text
);


--
-- Name: beverage_orders_order_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.beverage_orders_order_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: beverage_orders_order_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.beverage_orders_order_id_seq OWNED BY public.beverage_orders.order_id;


--
-- Name: beverage_orders order_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverage_orders ALTER COLUMN order_id SET DEFAULT nextval('public.beverage_orders_order_id_seq'::regclass);


--
-- Data for Name: beverage_orders; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.beverage_orders (order_id, reserve_number, order_date, subtotal, gst, total, status) FROM stdin;
\.


--
-- Name: beverage_orders_order_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.beverage_orders_order_id_seq', 1, false);


--
-- Name: beverage_orders beverage_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverage_orders
    ADD CONSTRAINT beverage_orders_pkey PRIMARY KEY (order_id);


--
-- PostgreSQL database dump complete
--

\unrestrict tDYEXNlvZ79jjE4jIP0yaOTm1MbICh999V8l7HQUXkElTFLBFCtnBLCdY1mZHo9

