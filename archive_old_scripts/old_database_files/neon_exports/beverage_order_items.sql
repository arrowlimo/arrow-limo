--
-- PostgreSQL database dump
--

\restrict GrZgzm7HvWWBnDoWxlhbD27ugoUt1m0V1BP4u8JFSIbeWr2MaNo0pz1PdqTnNZc

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

ALTER TABLE IF EXISTS ONLY public.beverage_order_items DROP CONSTRAINT IF EXISTS beverage_order_items_order_id_fkey;
ALTER TABLE IF EXISTS ONLY public.beverage_order_items DROP CONSTRAINT IF EXISTS beverage_order_items_pkey;
ALTER TABLE IF EXISTS public.beverage_order_items ALTER COLUMN item_line_id DROP DEFAULT;
DROP SEQUENCE IF EXISTS public.beverage_order_items_item_line_id_seq;
DROP TABLE IF EXISTS public.beverage_order_items;
SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: beverage_order_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.beverage_order_items (
    item_line_id integer NOT NULL,
    order_id integer NOT NULL,
    item_id integer,
    item_name text NOT NULL,
    quantity integer NOT NULL,
    unit_price numeric(10,2) NOT NULL,
    total numeric(10,2) NOT NULL,
    our_cost numeric(10,2),
    markup_pct numeric(5,2),
    deposit_amount numeric(10,2) DEFAULT 0,
    fees_amount numeric(10,2) DEFAULT 0,
    gst_amount numeric(10,2) DEFAULT 0,
    price_override boolean DEFAULT false,
    override_reason text
);


--
-- Name: beverage_order_items_item_line_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.beverage_order_items_item_line_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: beverage_order_items_item_line_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.beverage_order_items_item_line_id_seq OWNED BY public.beverage_order_items.item_line_id;


--
-- Name: beverage_order_items item_line_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverage_order_items ALTER COLUMN item_line_id SET DEFAULT nextval('public.beverage_order_items_item_line_id_seq'::regclass);


--
-- Data for Name: beverage_order_items; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.beverage_order_items (item_line_id, order_id, item_id, item_name, quantity, unit_price, total, our_cost, markup_pct, deposit_amount, fees_amount, gst_amount, price_override, override_reason) FROM stdin;
\.


--
-- Name: beverage_order_items_item_line_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.beverage_order_items_item_line_id_seq', 1, false);


--
-- Name: beverage_order_items beverage_order_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverage_order_items
    ADD CONSTRAINT beverage_order_items_pkey PRIMARY KEY (item_line_id);


--
-- Name: beverage_order_items beverage_order_items_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverage_order_items
    ADD CONSTRAINT beverage_order_items_order_id_fkey FOREIGN KEY (order_id) REFERENCES public.beverage_orders(order_id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict GrZgzm7HvWWBnDoWxlhbD27ugoUt1m0V1BP4u8JFSIbeWr2MaNo0pz1PdqTnNZc

