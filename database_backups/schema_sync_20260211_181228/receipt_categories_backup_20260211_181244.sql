--
-- PostgreSQL database dump
--

\restrict qy5m1KZNgmrosp7bJAHX9c0hqbH32dNKErK9KyJXKUwtYfzmXaiyGupEd7bfGQZ

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
-- Name: receipt_categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.receipt_categories (
    category_id integer NOT NULL,
    category_code character varying(100) NOT NULL,
    category_name character varying(200) NOT NULL,
    is_tax_deductible boolean DEFAULT true,
    requires_vehicle boolean DEFAULT false,
    requires_employee boolean DEFAULT false,
    parent_category character varying(100),
    display_order integer,
    notes text,
    gl_account_code character varying(20),
    is_business_expense boolean DEFAULT true
);


--
-- Name: receipt_categories_category_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.receipt_categories_category_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: receipt_categories_category_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.receipt_categories_category_id_seq OWNED BY public.receipt_categories.category_id;


--
-- Name: receipt_categories category_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_categories ALTER COLUMN category_id SET DEFAULT nextval('public.receipt_categories_category_id_seq'::regclass);


--
-- Data for Name: receipt_categories; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.receipt_categories (category_id, category_code, category_name, is_tax_deductible, requires_vehicle, requires_employee, parent_category, display_order, notes, gl_account_code, is_business_expense) VALUES (1, 'fuel', 'Vehicle Fuel', true, true, false, NULL, 1, NULL, NULL, true);
INSERT INTO public.receipt_categories (category_id, category_code, category_name, is_tax_deductible, requires_vehicle, requires_employee, parent_category, display_order, notes, gl_account_code, is_business_expense) VALUES (2, 'vehicle_maintenance', 'Vehicle Maintenance', true, true, false, NULL, 2, NULL, NULL, true);
INSERT INTO public.receipt_categories (category_id, category_code, category_name, is_tax_deductible, requires_vehicle, requires_employee, parent_category, display_order, notes, gl_account_code, is_business_expense) VALUES (3, 'vehicle_supplies', 'Vehicle Supplies', true, true, false, NULL, 3, NULL, NULL, true);
INSERT INTO public.receipt_categories (category_id, category_code, category_name, is_tax_deductible, requires_vehicle, requires_employee, parent_category, display_order, notes, gl_account_code, is_business_expense) VALUES (4, 'driver_meal', 'Driver Meals', true, false, true, 'meals', 10, NULL, NULL, true);
INSERT INTO public.receipt_categories (category_id, category_code, category_name, is_tax_deductible, requires_vehicle, requires_employee, parent_category, display_order, notes, gl_account_code, is_business_expense) VALUES (5, 'customer_beverages', 'Customer Beverages', true, false, false, 'customer_supplies', 20, NULL, NULL, true);
INSERT INTO public.receipt_categories (category_id, category_code, category_name, is_tax_deductible, requires_vehicle, requires_employee, parent_category, display_order, notes, gl_account_code, is_business_expense) VALUES (6, 'customer_snacks', 'Customer Snacks', true, false, false, 'customer_supplies', 21, NULL, NULL, true);
INSERT INTO public.receipt_categories (category_id, category_code, category_name, is_tax_deductible, requires_vehicle, requires_employee, parent_category, display_order, notes, gl_account_code, is_business_expense) VALUES (7, 'customer_supplies', 'Customer Supplies (General)', true, false, false, NULL, 22, NULL, NULL, true);
INSERT INTO public.receipt_categories (category_id, category_code, category_name, is_tax_deductible, requires_vehicle, requires_employee, parent_category, display_order, notes, gl_account_code, is_business_expense) VALUES (8, 'office_supplies', 'Office Supplies', true, false, false, NULL, 30, NULL, NULL, true);
INSERT INTO public.receipt_categories (category_id, category_code, category_name, is_tax_deductible, requires_vehicle, requires_employee, parent_category, display_order, notes, gl_account_code, is_business_expense) VALUES (9, 'communication', 'Phone/Internet', true, false, false, NULL, 40, NULL, NULL, true);
INSERT INTO public.receipt_categories (category_id, category_code, category_name, is_tax_deductible, requires_vehicle, requires_employee, parent_category, display_order, notes, gl_account_code, is_business_expense) VALUES (10, 'insurance', 'Insurance', true, false, false, NULL, 50, NULL, NULL, true);
INSERT INTO public.receipt_categories (category_id, category_code, category_name, is_tax_deductible, requires_vehicle, requires_employee, parent_category, display_order, notes, gl_account_code, is_business_expense) VALUES (11, 'vehicle_lease', 'Vehicle Lease/Financing', true, true, false, NULL, 51, NULL, NULL, true);
INSERT INTO public.receipt_categories (category_id, category_code, category_name, is_tax_deductible, requires_vehicle, requires_employee, parent_category, display_order, notes, gl_account_code, is_business_expense) VALUES (12, 'banking_fees', 'Banking Fees', true, false, false, NULL, 60, NULL, NULL, true);
INSERT INTO public.receipt_categories (category_id, category_code, category_name, is_tax_deductible, requires_vehicle, requires_employee, parent_category, display_order, notes, gl_account_code, is_business_expense) VALUES (13, 'personal', 'Personal (Non-deductible)', false, false, false, NULL, 90, NULL, NULL, false);


--
-- Name: receipt_categories_category_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.receipt_categories_category_id_seq', 13, true);


--
-- Name: receipt_categories receipt_categories_category_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_categories
    ADD CONSTRAINT receipt_categories_category_code_key UNIQUE (category_code);


--
-- Name: receipt_categories receipt_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_categories
    ADD CONSTRAINT receipt_categories_pkey PRIMARY KEY (category_id);


--
-- PostgreSQL database dump complete
--

\unrestrict qy5m1KZNgmrosp7bJAHX9c0hqbH32dNKErK9KyJXKUwtYfzmXaiyGupEd7bfGQZ

