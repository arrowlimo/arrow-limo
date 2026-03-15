--
-- PostgreSQL database dump
--

\restrict AJVigfFfISuj9xmRr6855Mu1usXbPSdLaxAp2o4yI7R0Go9dPFNy96mz8WE1TAR

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

ALTER TABLE IF EXISTS ONLY public.beverage_cart DROP CONSTRAINT IF EXISTS beverage_cart_beverage_id_fkey;
ALTER TABLE IF EXISTS ONLY public.beverage_cart DROP CONSTRAINT IF EXISTS beverage_cart_pkey;
ALTER TABLE IF EXISTS public.beverage_cart ALTER COLUMN cart_id DROP DEFAULT;
DROP SEQUENCE IF EXISTS public.beverage_cart_cart_id_seq;
DROP TABLE IF EXISTS public.beverage_cart;
SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: beverage_cart; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.beverage_cart (
    cart_id integer NOT NULL,
    charter_id integer,
    beverage_id integer,
    quantity integer DEFAULT 1,
    ice_requested boolean DEFAULT false,
    our_cost_total numeric(10,2),
    marked_up_total numeric(10,2),
    free_flag boolean DEFAULT false,
    cost_only_flag boolean DEFAULT false,
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: beverage_cart_cart_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.beverage_cart_cart_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: beverage_cart_cart_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.beverage_cart_cart_id_seq OWNED BY public.beverage_cart.cart_id;


--
-- Name: beverage_cart cart_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverage_cart ALTER COLUMN cart_id SET DEFAULT nextval('public.beverage_cart_cart_id_seq'::regclass);


--
-- Data for Name: beverage_cart; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.beverage_cart (cart_id, charter_id, beverage_id, quantity, ice_requested, our_cost_total, marked_up_total, free_flag, cost_only_flag, notes, created_at) FROM stdin;
\.


--
-- Name: beverage_cart_cart_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.beverage_cart_cart_id_seq', 1, false);


--
-- Name: beverage_cart beverage_cart_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverage_cart
    ADD CONSTRAINT beverage_cart_pkey PRIMARY KEY (cart_id);


--
-- Name: beverage_cart beverage_cart_beverage_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverage_cart
    ADD CONSTRAINT beverage_cart_beverage_id_fkey FOREIGN KEY (beverage_id) REFERENCES public.beverages(beverage_id);


--
-- PostgreSQL database dump complete
--

\unrestrict AJVigfFfISuj9xmRr6855Mu1usXbPSdLaxAp2o4yI7R0Go9dPFNy96mz8WE1TAR

