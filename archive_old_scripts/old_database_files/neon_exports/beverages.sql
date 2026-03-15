--
-- PostgreSQL database dump
--

\restrict MbS08Od6DiqKfaBL5e1VtFmds0f2GcJ2ZuCuJwAMDMo27fwuOalmhWDCRX0nfKC

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

ALTER TABLE IF EXISTS ONLY public.beverages DROP CONSTRAINT IF EXISTS beverages_pkey;
ALTER TABLE IF EXISTS public.beverages ALTER COLUMN beverage_id DROP DEFAULT;
DROP SEQUENCE IF EXISTS public.beverages_beverage_id_seq;
DROP TABLE IF EXISTS public.beverages;
SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: beverages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.beverages (
    beverage_id integer NOT NULL,
    beverage_name character varying(100) NOT NULL,
    category character varying(50),
    brand character varying(100),
    description text,
    price numeric(8,2),
    cost numeric(8,2),
    is_alcoholic boolean DEFAULT false,
    alcohol_content numeric(4,2),
    size_ml integer,
    is_active boolean DEFAULT true,
    inventory_level integer DEFAULT 0,
    reorder_point integer DEFAULT 5,
    supplier character varying(100),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    gst_deposit_amount numeric(10,2),
    ice_charge numeric(10,2),
    is_charter_eligible boolean DEFAULT true
);


--
-- Name: beverages_beverage_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.beverages_beverage_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: beverages_beverage_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.beverages_beverage_id_seq OWNED BY public.beverages.beverage_id;


--
-- Name: beverages beverage_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverages ALTER COLUMN beverage_id SET DEFAULT nextval('public.beverages_beverage_id_seq'::regclass);


--
-- Data for Name: beverages; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.beverages (beverage_id, beverage_name, category, brand, description, price, cost, is_alcoholic, alcohol_content, size_ml, is_active, inventory_level, reorder_point, supplier, created_at, updated_at, gst_deposit_amount, ice_charge, is_charter_eligible) FROM stdin;
1	Dom P�rignon Champagne	Champagne	Dom P�rignon	Premium vintage champagne	150.00	120.00	t	12.50	750	t	34	5	\N	2025-07-25 09:03:28.762102	2025-07-25 09:03:28.762102	\N	\N	t
2	Cristal Champagne	Champagne	Louis Roederer	Ultra-premium champagne	250.00	200.00	t	12.00	750	t	19	5	\N	2025-07-25 09:03:28.763158	2025-07-25 09:03:28.763158	\N	\N	t
3	Mo�t & Chandon	Champagne	Mo�t & Chandon	Classic premium champagne	80.00	65.00	t	12.00	750	t	14	5	\N	2025-07-25 09:03:28.763439	2025-07-25 09:03:28.763439	\N	\N	t
4	Premium Red Wine	Wine	Various	Selection of premium red wines	45.00	35.00	t	13.50	750	t	14	5	\N	2025-07-25 09:03:28.763661	2025-07-25 09:03:28.763661	\N	\N	t
5	Premium White Wine	Wine	Various	Selection of premium white wines	45.00	35.00	t	12.50	750	t	13	5	\N	2025-07-25 09:03:28.7639	2025-07-25 09:03:28.7639	\N	\N	t
6	Hennessy Cognac	Spirits	Hennessy	Premium cognac selection	80.00	65.00	t	40.00	700	t	19	5	\N	2025-07-25 09:03:28.764244	2025-07-25 09:03:28.764244	\N	\N	t
7	Grey Goose Vodka	Spirits	Grey Goose	Premium French vodka	60.00	45.00	t	40.00	750	t	29	5	\N	2025-07-25 09:03:28.764531	2025-07-25 09:03:28.764531	\N	\N	t
8	Macallan Whiskey	Spirits	Macallan	Premium single malt scotch	120.00	95.00	t	43.00	700	t	24	5	\N	2025-07-25 09:03:28.764815	2025-07-25 09:03:28.764815	\N	\N	t
9	Fiji Water	Water	Fiji	Premium artesian water	4.00	2.00	f	0.00	500	t	17	5	\N	2025-07-25 09:03:28.765071	2025-07-25 09:03:28.765071	\N	\N	t
10	San Pellegrino	Water	San Pellegrino	Sparkling mineral water	4.50	2.50	f	0.00	500	t	24	5	\N	2025-07-25 09:03:28.765338	2025-07-25 09:03:28.765338	\N	\N	t
11	Perrier	Water	Perrier	French sparkling water	4.00	2.25	f	0.00	330	t	39	5	\N	2025-07-25 09:03:28.765614	2025-07-25 09:03:28.765614	\N	\N	t
12	Fresh Orange Juice	Juice	Fresh	Freshly squeezed orange juice	8.00	4.00	f	0.00	250	t	25	5	\N	2025-07-25 09:03:28.765831	2025-07-25 09:03:28.765831	\N	\N	t
13	Cranberry Juice	Juice	Premium	Premium cranberry juice	6.00	3.50	f	0.00	250	t	22	5	\N	2025-07-25 09:03:28.76601	2025-07-25 09:03:28.76601	\N	\N	t
14	Coca-Cola	Soft Drinks	Coca-Cola	Classic Coca-Cola	3.50	1.50	f	0.00	355	t	21	5	\N	2025-07-25 09:03:28.766186	2025-07-25 09:03:28.766186	\N	\N	t
15	Sprite	Soft Drinks	Coca-Cola	Lemon-lime soda	3.50	1.50	f	0.00	355	t	27	5	\N	2025-07-25 09:03:28.766347	2025-07-25 09:03:28.766347	\N	\N	t
16	Red Bull	Energy	Red Bull	Premium energy drink	5.00	2.50	f	0.00	250	t	15	5	\N	2025-07-25 09:03:28.766498	2025-07-25 09:03:28.766498	\N	\N	t
17	Monster Energy	Energy	Monster	Energy drink selection	4.50	2.25	f	0.00	473	t	11	5	\N	2025-07-25 09:03:28.766653	2025-07-25 09:03:28.766653	\N	\N	t
18	Premium Coffee	Coffee	Various	Artisan coffee service	6.00	3.00	f	0.00	240	t	29	5	\N	2025-07-25 09:03:28.7668	2025-07-25 09:03:28.7668	\N	\N	t
19	Hot Chocolate	Coffee	Premium	Gourmet hot chocolate	5.00	2.50	f	0.00	240	t	21	5	\N	2025-07-25 09:03:28.766943	2025-07-25 09:03:28.766943	\N	\N	t
20	Assorted Nuts	Snacks	Premium	Mixed premium nuts	8.00	4.00	f	0.00	150	t	10	5	\N	2025-07-25 09:03:28.76717	2025-07-25 09:03:28.76717	\N	\N	t
\.


--
-- Name: beverages_beverage_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.beverages_beverage_id_seq', 20, true);


--
-- Name: beverages beverages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverages
    ADD CONSTRAINT beverages_pkey PRIMARY KEY (beverage_id);


--
-- PostgreSQL database dump complete
--

\unrestrict MbS08Od6DiqKfaBL5e1VtFmds0f2GcJ2ZuCuJwAMDMo27fwuOalmhWDCRX0nfKC

