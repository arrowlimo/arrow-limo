--
-- PostgreSQL database dump
--

\restrict RKgd05mKhXjoFqqGh8TMaxsz3iduGrhC8I5oGGwTwkObgXUEiSVIOTpO9Xb4356

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

ALTER TABLE IF EXISTS ONLY public.charter_beverage_items DROP CONSTRAINT IF EXISTS charter_beverage_items_beverage_order_id_fkey;
ALTER TABLE IF EXISTS ONLY public.charter_beverage_items DROP CONSTRAINT IF EXISTS charter_beverage_items_pkey;
ALTER TABLE IF EXISTS public.charter_beverage_items ALTER COLUMN beverage_item_id DROP DEFAULT;
DROP SEQUENCE IF EXISTS public.charter_beverage_items_beverage_item_id_seq;
DROP TABLE IF EXISTS public.charter_beverage_items;
SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: charter_beverage_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.charter_beverage_items (
    beverage_item_id integer NOT NULL,
    beverage_order_id integer,
    item_type character varying(255),
    quantity integer,
    unit_price numeric(12,2),
    gst_per_line numeric(12,2),
    deposit_per_line numeric(12,2),
    line_total numeric(12,2),
    driver_count integer,
    stocked boolean DEFAULT false,
    notes text
);


--
-- Name: charter_beverage_items_beverage_item_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.charter_beverage_items_beverage_item_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: charter_beverage_items_beverage_item_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.charter_beverage_items_beverage_item_id_seq OWNED BY public.charter_beverage_items.beverage_item_id;


--
-- Name: charter_beverage_items beverage_item_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_beverage_items ALTER COLUMN beverage_item_id SET DEFAULT nextval('public.charter_beverage_items_beverage_item_id_seq'::regclass);


--
-- Data for Name: charter_beverage_items; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.charter_beverage_items (beverage_item_id, beverage_order_id, item_type, quantity, unit_price, gst_per_line, deposit_per_line, line_total, driver_count, stocked, notes) FROM stdin;
\.


--
-- Name: charter_beverage_items_beverage_item_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.charter_beverage_items_beverage_item_id_seq', 1, false);


--
-- Name: charter_beverage_items charter_beverage_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_beverage_items
    ADD CONSTRAINT charter_beverage_items_pkey PRIMARY KEY (beverage_item_id);


--
-- Name: charter_beverage_items charter_beverage_items_beverage_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_beverage_items
    ADD CONSTRAINT charter_beverage_items_beverage_order_id_fkey FOREIGN KEY (beverage_order_id) REFERENCES public.charter_beverage_orders(beverage_order_id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict RKgd05mKhXjoFqqGh8TMaxsz3iduGrhC8I5oGGwTwkObgXUEiSVIOTpO9Xb4356

