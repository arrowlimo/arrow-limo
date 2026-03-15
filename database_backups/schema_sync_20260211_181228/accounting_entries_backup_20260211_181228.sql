--
-- PostgreSQL database dump
--

\restrict YM6catv0sg02nKx929ml4VFmmx0lbIS2nkf3zFybpRUD2XlZE6JUHVjB5usZGch

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
-- Name: accounting_entries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.accounting_entries (
    id integer NOT NULL,
    entry_date date,
    reference character varying,
    description text,
    account_code character varying,
    account_name character varying,
    debit_amount numeric,
    credit_amount numeric,
    source_type character varying,
    import_batch character varying,
    created_date timestamp without time zone,
    charter_id integer,
    payment_reference character varying,
    payment_id bigint,
    receipt_id bigint,
    banking_transaction_id bigint,
    income_ledger_id bigint
);


--
-- Name: accounting_entries_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.accounting_entries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: accounting_entries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.accounting_entries_id_seq OWNED BY public.accounting_entries.id;


--
-- Name: accounting_entries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounting_entries ALTER COLUMN id SET DEFAULT nextval('public.accounting_entries_id_seq'::regclass);


--
-- Data for Name: accounting_entries; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.accounting_entries (id, entry_date, reference, description, account_code, account_name, debit_amount, credit_amount, source_type, import_batch, created_date, charter_id, payment_reference, payment_id, receipt_id, banking_transaction_id, income_ledger_id) VALUES (1, '2025-08-02', 'Migration-eTransfers-2025-08-03', 'eTransfer payments migration to ALMSData', '1000', 'Cash - Operating Account', 15971.39, 0.00, 'eTransfer', 'MIGRATION-2025-08-03', '2025-08-02 21:46:36.851647', NULL, NULL, NULL, NULL, NULL, NULL);
INSERT INTO public.accounting_entries (id, entry_date, reference, description, account_code, account_name, debit_amount, credit_amount, source_type, import_batch, created_date, charter_id, payment_reference, payment_id, receipt_id, banking_transaction_id, income_ledger_id) VALUES (2, '2025-08-02', 'Migration-eTransfers-2025-08-03', 'eTransfer payments migration to ALMSData', '4000', 'Service Revenue', 0.00, 15971.39, 'eTransfer', 'MIGRATION-2025-08-03', '2025-08-02 21:46:36.851647', NULL, NULL, NULL, NULL, NULL, NULL);
INSERT INTO public.accounting_entries (id, entry_date, reference, description, account_code, account_name, debit_amount, credit_amount, source_type, import_batch, created_date, charter_id, payment_reference, payment_id, receipt_id, banking_transaction_id, income_ledger_id) VALUES (3, '2025-08-02', 'Migration-Square-2025-08-03', 'Square credit card payments migration to ALMSData', '1000', 'Cash - Operating Account', 14315.13, 0.00, 'Square', 'MIGRATION-2025-08-03', '2025-08-02 21:46:36.855162', NULL, NULL, NULL, NULL, NULL, NULL);
INSERT INTO public.accounting_entries (id, entry_date, reference, description, account_code, account_name, debit_amount, credit_amount, source_type, import_batch, created_date, charter_id, payment_reference, payment_id, receipt_id, banking_transaction_id, income_ledger_id) VALUES (4, '2025-08-02', 'Migration-Square-2025-08-03', 'Square credit card payments migration to ALMSData', '4000', 'Service Revenue', 0.00, 14315.13, 'Square', 'MIGRATION-2025-08-03', '2025-08-02 21:46:36.855162', NULL, NULL, NULL, NULL, NULL, NULL);
INSERT INTO public.accounting_entries (id, entry_date, reference, description, account_code, account_name, debit_amount, credit_amount, source_type, import_batch, created_date, charter_id, payment_reference, payment_id, receipt_id, banking_transaction_id, income_ledger_id) VALUES (5, '2025-08-02', 'Migration-CIBC Banking-2025-08-03', 'CIBC banking transactions migration to ALMSData', '1000', 'Cash - Operating Account', 108143.66, 0.00, 'CIBC Banking', 'MIGRATION-2025-08-03', '2025-08-02 21:46:36.855558', NULL, NULL, NULL, NULL, NULL, NULL);
INSERT INTO public.accounting_entries (id, entry_date, reference, description, account_code, account_name, debit_amount, credit_amount, source_type, import_batch, created_date, charter_id, payment_reference, payment_id, receipt_id, banking_transaction_id, income_ledger_id) VALUES (6, '2025-08-02', 'Migration-CIBC Banking-2025-08-03', 'CIBC banking transactions migration to ALMSData', '4000', 'Service Revenue', 0.00, 108143.66, 'CIBC Banking', 'MIGRATION-2025-08-03', '2025-08-02 21:46:36.855558', NULL, NULL, NULL, NULL, NULL, NULL);
INSERT INTO public.accounting_entries (id, entry_date, reference, description, account_code, account_name, debit_amount, credit_amount, source_type, import_batch, created_date, charter_id, payment_reference, payment_id, receipt_id, banking_transaction_id, income_ledger_id) VALUES (7, '2025-08-02', 'Migration-Summary-2025-08-03', 'Total verified revenue migration summary', '1000', 'Cash - Operating Account', 138430.18, 0.00, 'MIGRATION_SUMMARY', 'MIGRATION-2025-08-03', '2025-08-02 21:46:36.85593', NULL, NULL, NULL, NULL, NULL, NULL);
INSERT INTO public.accounting_entries (id, entry_date, reference, description, account_code, account_name, debit_amount, credit_amount, source_type, import_batch, created_date, charter_id, payment_reference, payment_id, receipt_id, banking_transaction_id, income_ledger_id) VALUES (8, '2025-08-02', 'Migration-Summary-2025-08-03', 'Total verified revenue migration summary', '4000', 'Service Revenue', 0.00, 138430.18, 'MIGRATION_SUMMARY', 'MIGRATION-2025-08-03', '2025-08-02 21:46:36.85593', NULL, NULL, NULL, NULL, NULL, NULL);
INSERT INTO public.accounting_entries (id, entry_date, reference, description, account_code, account_name, debit_amount, credit_amount, source_type, import_batch, created_date, charter_id, payment_reference, payment_id, receipt_id, banking_transaction_id, income_ledger_id) VALUES (9, '2025-08-03', 'FAMILY-LOAN-CORRECTION-2025-08-03', 'CORRECTION: Reclassify family loan from service revenue', '4000', 'Service Revenue', 8720.26, 0.00, 'family_loan_correction', 'FAMILY-LOAN-CORRECTION-2025-08-03', '2025-08-03 21:14:32.338407', NULL, NULL, NULL, NULL, NULL, NULL);
INSERT INTO public.accounting_entries (id, entry_date, reference, description, account_code, account_name, debit_amount, credit_amount, source_type, import_batch, created_date, charter_id, payment_reference, payment_id, receipt_id, banking_transaction_id, income_ledger_id) VALUES (10, '2025-08-03', 'FAMILY-LOAN-CORRECTION-2025-08-03', 'CORRECTION: Record family loan receivable from David Richard', '1200', 'Family Loans Receivable', 0.00, 8720.26, 'family_loan_correction', 'FAMILY-LOAN-CORRECTION-2025-08-03', '2025-08-03 21:14:44.241458', NULL, NULL, NULL, NULL, NULL, NULL);
INSERT INTO public.accounting_entries (id, entry_date, reference, description, account_code, account_name, debit_amount, credit_amount, source_type, import_batch, created_date, charter_id, payment_reference, payment_id, receipt_id, banking_transaction_id, income_ledger_id) VALUES (12, '2013-04-20', 'PMT-UNK-7', 'Charter Revenue - 007801', '4000', NULL, 0.00, 1250.00, 'Square Payment', NULL, '2025-08-07 22:13:12.411878', 6736, 'UNK-7', NULL, NULL, NULL, NULL);
INSERT INTO public.accounting_entries (id, entry_date, reference, description, account_code, account_name, debit_amount, credit_amount, source_type, import_batch, created_date, charter_id, payment_reference, payment_id, receipt_id, banking_transaction_id, income_ledger_id) VALUES (13, '2014-12-18', 'PMT-UNK-3', 'Charter Revenue - 010533', '4000', NULL, 0.00, 325.00, 'Square Payment', NULL, '2025-08-07 22:13:12.411878', 9469, 'UNK-3', NULL, NULL, NULL, NULL);
INSERT INTO public.accounting_entries (id, entry_date, reference, description, account_code, account_name, debit_amount, credit_amount, source_type, import_batch, created_date, charter_id, payment_reference, payment_id, receipt_id, banking_transaction_id, income_ledger_id) VALUES (14, '2017-01-12', 'PMT-UNK-2', 'Charter Revenue - 012769', '4000', NULL, 0.00, 275.50, 'Square Payment', NULL, '2025-08-07 22:13:12.411878', 11671, 'UNK-2', NULL, NULL, NULL, NULL);
INSERT INTO public.accounting_entries (id, entry_date, reference, description, account_code, account_name, debit_amount, credit_amount, source_type, import_batch, created_date, charter_id, payment_reference, payment_id, receipt_id, banking_transaction_id, income_ledger_id) VALUES (15, '2018-09-22', 'PMT-UNK-1', 'Charter Revenue - 014140', '4000', NULL, 0.00, 485.00, 'Square Payment', NULL, '2025-08-07 22:13:12.411878', 12943, 'UNK-1', NULL, NULL, NULL, NULL);
INSERT INTO public.accounting_entries (id, entry_date, reference, description, account_code, account_name, debit_amount, credit_amount, source_type, import_batch, created_date, charter_id, payment_reference, payment_id, receipt_id, banking_transaction_id, income_ledger_id) VALUES (16, '2021-01-13', 'PMT-UNK-9', 'Charter Revenue - 015643', '4000', NULL, 0.00, 2100.75, 'Square Payment', NULL, '2025-08-07 22:13:12.411878', 14547, 'UNK-9', NULL, NULL, NULL, NULL);
INSERT INTO public.accounting_entries (id, entry_date, reference, description, account_code, account_name, debit_amount, credit_amount, source_type, import_batch, created_date, charter_id, payment_reference, payment_id, receipt_id, banking_transaction_id, income_ledger_id) VALUES (17, '2023-10-07', 'PMT-UNK-8', 'Charter Revenue - 017448', '4000', NULL, 0.00, 875.50, 'Square Payment', NULL, '2025-08-07 22:13:12.411878', 16325, 'UNK-8', NULL, NULL, NULL, NULL);


--
-- Name: accounting_entries_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.accounting_entries_id_seq', 17, true);


--
-- Name: accounting_entries accounting_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounting_entries
    ADD CONSTRAINT accounting_entries_pkey PRIMARY KEY (id);


--
-- Name: idx_accounting_entries_account; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_accounting_entries_account ON public.accounting_entries USING btree (account_code);


--
-- Name: idx_accounting_entries_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_accounting_entries_date ON public.accounting_entries USING btree (entry_date);


--
-- Name: accounting_entries accounting_entries_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounting_entries
    ADD CONSTRAINT accounting_entries_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id);


--
-- PostgreSQL database dump complete
--

\unrestrict YM6catv0sg02nKx929ml4VFmmx0lbIS2nkf3zFybpRUD2XlZE6JUHVjB5usZGch

