--
-- PostgreSQL database dump
--

\restrict DxEEP6KEqoT3PN0yJZF1R8MQWPndsHRN52YLCCpzM3baGifmvsN6kQsnuKdJexG

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
-- Name: run_type_default_charges; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.run_type_default_charges (
    id integer NOT NULL,
    run_type_id integer,
    charge_description character varying(255) NOT NULL,
    charge_type character varying(50) DEFAULT 'other'::character varying,
    amount numeric(10,2),
    calc_type character varying(20) DEFAULT 'Fixed'::character varying,
    value numeric(10,2),
    formula character varying(100),
    is_taxable boolean DEFAULT true,
    sequence integer DEFAULT 100,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: run_type_default_charges_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.run_type_default_charges_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: run_type_default_charges_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.run_type_default_charges_id_seq OWNED BY public.run_type_default_charges.id;


--
-- Name: run_type_default_charges id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.run_type_default_charges ALTER COLUMN id SET DEFAULT nextval('public.run_type_default_charges_id_seq'::regclass);


--
-- Data for Name: run_type_default_charges; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.run_type_default_charges (id, run_type_id, charge_description, charge_type, amount, calc_type, value, formula, is_taxable, sequence, created_at, updated_at) VALUES (1, 1, 'Calgary Airport Fee', 'airport_fee', 18.00, 'Fixed', 18.00, NULL, true, 100, '2026-01-31 00:07:47.553811', '2026-01-31 00:07:47.553811');
INSERT INTO public.run_type_default_charges (id, run_type_id, charge_description, charge_type, amount, calc_type, value, formula, is_taxable, sequence, created_at, updated_at) VALUES (2, 2, 'Calgary Airport Fee', 'airport_fee', 18.00, 'Fixed', 18.00, NULL, true, 100, '2026-01-31 00:07:47.553811', '2026-01-31 00:07:47.553811');
INSERT INTO public.run_type_default_charges (id, run_type_id, charge_description, charge_type, amount, calc_type, value, formula, is_taxable, sequence, created_at, updated_at) VALUES (3, 3, 'Edmonton Airport Fee', 'airport_fee', 18.00, 'Fixed', 18.00, NULL, true, 100, '2026-01-31 00:07:47.553811', '2026-01-31 00:07:47.553811');
INSERT INTO public.run_type_default_charges (id, run_type_id, charge_description, charge_type, amount, calc_type, value, formula, is_taxable, sequence, created_at, updated_at) VALUES (4, 4, 'Edmonton Airport Fee', 'airport_fee', 18.00, 'Fixed', 18.00, NULL, true, 100, '2026-01-31 00:07:47.553811', '2026-01-31 00:07:47.553811');
INSERT INTO public.run_type_default_charges (id, run_type_id, charge_description, charge_type, amount, calc_type, value, formula, is_taxable, sequence, created_at, updated_at) VALUES (5, 5, 'Red Deer Airport Fee', 'airport_fee', 25.00, 'Fixed', 25.00, NULL, true, 100, '2026-01-31 00:07:47.553811', '2026-01-31 00:07:47.553811');
INSERT INTO public.run_type_default_charges (id, run_type_id, charge_description, charge_type, amount, calc_type, value, formula, is_taxable, sequence, created_at, updated_at) VALUES (6, 6, 'Red Deer Airport Fee', 'airport_fee', 25.00, 'Fixed', 25.00, NULL, true, 100, '2026-01-31 00:07:47.553811', '2026-01-31 00:07:47.553811');


--
-- Name: run_type_default_charges_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.run_type_default_charges_id_seq', 6, true);


--
-- Name: run_type_default_charges run_type_default_charges_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.run_type_default_charges
    ADD CONSTRAINT run_type_default_charges_pkey PRIMARY KEY (id);


--
-- Name: run_type_default_charges run_type_default_charges_run_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.run_type_default_charges
    ADD CONSTRAINT run_type_default_charges_run_type_id_fkey FOREIGN KEY (run_type_id) REFERENCES public.charter_run_types(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict DxEEP6KEqoT3PN0yJZF1R8MQWPndsHRN52YLCCpzM3baGifmvsN6kQsnuKdJexG

