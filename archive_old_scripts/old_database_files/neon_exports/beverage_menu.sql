--
-- PostgreSQL database dump
--

\restrict aIhBQgf1hOASIYogBXGBXKuBNXNk0MT7L9qxboSymLm4huBB8tf6ofWMIgyxpn4

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

ALTER TABLE IF EXISTS ONLY public.beverage_menu DROP CONSTRAINT IF EXISTS beverage_menu_pkey;
ALTER TABLE IF EXISTS public.beverage_menu ALTER COLUMN beverage_id DROP DEFAULT;
DROP SEQUENCE IF EXISTS public.beverage_menu_beverage_id_seq;
DROP TABLE IF EXISTS public.beverage_menu;
SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: beverage_menu; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.beverage_menu (
    beverage_id integer NOT NULL,
    name character varying(255) NOT NULL,
    category character varying(100),
    brand character varying(100),
    size character varying(50),
    alcohol_content numeric(4,2),
    cost_price numeric(8,2),
    retail_price numeric(8,2),
    requires_license boolean DEFAULT false,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: beverage_menu_beverage_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.beverage_menu_beverage_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: beverage_menu_beverage_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.beverage_menu_beverage_id_seq OWNED BY public.beverage_menu.beverage_id;


--
-- Name: beverage_menu beverage_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverage_menu ALTER COLUMN beverage_id SET DEFAULT nextval('public.beverage_menu_beverage_id_seq'::regclass);


--
-- Data for Name: beverage_menu; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.beverage_menu (beverage_id, name, category, brand, size, alcohol_content, cost_price, retail_price, requires_license, is_active, created_at) FROM stdin;
1	Champagne - Dom Perignon	wine	Dom Perignon	750ml	12.50	180.00	250.00	t	t	2025-07-26 17:57:21.532733
2	Wine - Cabernet Sauvignon	wine	Robert Mondavi	750ml	13.50	25.00	45.00	t	t	2025-07-26 17:57:21.532733
3	Wine - Chardonnay	wine	Kendall Jackson	750ml	13.00	22.00	40.00	t	t	2025-07-26 17:57:21.532733
4	Beer - Premium Lager	beer	Corona	355ml	4.60	2.50	6.00	t	t	2025-07-26 17:57:21.532733
5	Whiskey - Single Malt	spirits	Macallan 12yr	750ml	40.00	85.00	150.00	t	t	2025-07-26 17:57:21.532733
6	Vodka - Premium	spirits	Grey Goose	750ml	40.00	45.00	80.00	t	t	2025-07-26 17:57:21.532733
7	Water - Sparkling	non-alcoholic	Perrier	330ml	0.00	1.25	3.00	f	t	2025-07-26 17:57:21.532733
8	Water - Still	non-alcoholic	Evian	500ml	0.00	1.00	2.50	f	t	2025-07-26 17:57:21.532733
9	Juice - Orange	non-alcoholic	Tropicana	300ml	0.00	1.50	4.00	f	t	2025-07-26 17:57:21.532733
10	Coffee - Premium	non-alcoholic	Starbucks	355ml	0.00	2.00	5.00	f	t	2025-07-26 17:57:21.532733
11	Snacks - Mixed Nuts	snacks	Premium Mix	100g	0.00	3.00	8.00	f	t	2025-07-26 17:57:21.532733
12	Chocolate - Artisan	snacks	Godiva	50g	0.00	4.00	12.00	f	t	2025-07-26 17:57:21.532733
13	Champagne - Dom Perignon	wine	Dom Perignon	750ml	12.50	180.00	250.00	t	t	2025-07-26 17:58:08.515566
14	Wine - Cabernet Sauvignon	wine	Robert Mondavi	750ml	13.50	25.00	45.00	t	t	2025-07-26 17:58:08.515566
15	Wine - Chardonnay	wine	Kendall Jackson	750ml	13.00	22.00	40.00	t	t	2025-07-26 17:58:08.515566
16	Beer - Premium Lager	beer	Corona	355ml	4.60	2.50	6.00	t	t	2025-07-26 17:58:08.515566
17	Whiskey - Single Malt	spirits	Macallan 12yr	750ml	40.00	85.00	150.00	t	t	2025-07-26 17:58:08.515566
18	Vodka - Premium	spirits	Grey Goose	750ml	40.00	45.00	80.00	t	t	2025-07-26 17:58:08.515566
19	Water - Sparkling	non-alcoholic	Perrier	330ml	0.00	1.25	3.00	f	t	2025-07-26 17:58:08.515566
20	Water - Still	non-alcoholic	Evian	500ml	0.00	1.00	2.50	f	t	2025-07-26 17:58:08.515566
21	Juice - Orange	non-alcoholic	Tropicana	300ml	0.00	1.50	4.00	f	t	2025-07-26 17:58:08.515566
22	Coffee - Premium	non-alcoholic	Starbucks	355ml	0.00	2.00	5.00	f	t	2025-07-26 17:58:08.515566
23	Snacks - Mixed Nuts	snacks	Premium Mix	100g	0.00	3.00	8.00	f	t	2025-07-26 17:58:08.515566
24	Chocolate - Artisan	snacks	Godiva	50g	0.00	4.00	12.00	f	t	2025-07-26 17:58:08.515566
\.


--
-- Name: beverage_menu_beverage_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.beverage_menu_beverage_id_seq', 24, true);


--
-- Name: beverage_menu beverage_menu_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverage_menu
    ADD CONSTRAINT beverage_menu_pkey PRIMARY KEY (beverage_id);


--
-- PostgreSQL database dump complete
--

\unrestrict aIhBQgf1hOASIYogBXGBXKuBNXNk0MT7L9qxboSymLm4huBB8tf6ofWMIgyxpn4

