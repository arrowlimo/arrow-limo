--
-- PostgreSQL database dump
--

\restrict HL9bKEBXy0bTFb9nhfMx6knK8nIwQm2qn16chHTdsaYclO3eby5yL5kHzVHLan1

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

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA public;


--
-- Name: asset_category; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.asset_category AS ENUM (
    'vehicle',
    'equipment',
    'furniture',
    'electronics',
    'real_estate',
    'other'
);


--
-- Name: asset_ownership_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.asset_ownership_type AS ENUM (
    'owned',
    'leased',
    'loaned_in',
    'rental'
);


--
-- Name: charter_record_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.charter_record_type AS ENUM (
    'charter',
    'placeholder'
);


--
-- Name: depreciation_method; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.depreciation_method AS ENUM (
    'straight_line',
    'declining_balance',
    'none'
);


--
-- Name: acquire_record_lock(integer, character varying, character varying, character varying); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.acquire_record_lock(p_user_id integer, p_module character varying, p_record_type character varying, p_record_id character varying) RETURNS boolean
    LANGUAGE plpgsql
    AS $$
BEGIN
  INSERT INTO record_locks (module, record_type, record_id, locked_by_user_id, expires_at)
  VALUES (p_module, p_record_type, p_record_id, p_user_id, NOW() + INTERVAL '10 minutes')
  ON CONFLICT (module, record_type, record_id) DO UPDATE
  SET locked_by_user_id = CASE WHEN record_locks.locked_by_user_id = p_user_id THEN p_user_id ELSE record_locks.locked_by_user_id END,
      expires_at = CASE WHEN record_locks.locked_by_user_id = p_user_id THEN NOW() + INTERVAL '10 minutes' ELSE record_locks.expires_at END;
  RETURN TRUE;
END;
$$;


--
-- Name: add_maintenance_record(integer, character varying, date, integer, character varying, text, numeric); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.add_maintenance_record(p_vehicle_id integer, p_activity_code character varying, p_service_date date, p_odometer_reading integer, p_performed_by character varying DEFAULT NULL::character varying, p_notes text DEFAULT NULL::text, p_total_cost numeric DEFAULT NULL::numeric) RETURNS integer
    LANGUAGE plpgsql
    AS $$
      DECLARE
        v_activity_type_id INTEGER;
        v_record_id INTEGER;
        v_next_km INTEGER;
        v_next_date DATE;
        v_interval_km INTEGER;
        v_interval_months INTEGER;
      BEGIN
        -- Get activity type details
        SELECT activity_type_id, default_interval_km, default_interval_months
        INTO v_activity_type_id, v_interval_km, v_interval_months
        FROM maintenance_activity_types 
        WHERE activity_code = p_activity_code;
        
        -- Calculate next service due
        IF v_interval_km IS NOT NULL THEN
          v_next_km := p_odometer_reading + v_interval_km;
        END IF;
        
        IF v_interval_months IS NOT NULL THEN
          v_next_date := p_service_date + (v_interval_months || ' months')::INTERVAL;
        END IF;
        
        -- Insert maintenance record
        INSERT INTO maintenance_records 
        (vehicle_id, activity_type_id, service_date, odometer_reading, 
         performed_by, notes, total_cost, next_service_km, next_service_date)
        VALUES (p_vehicle_id, v_activity_type_id, p_service_date, p_odometer_reading,
                p_performed_by, p_notes, p_total_cost, v_next_km, v_next_date)
        RETURNING record_id INTO v_record_id;
        
        -- Update vehicle's last service date
        UPDATE vehicles 
        SET last_service_date = p_service_date,
            odometer = GREATEST(COALESCE(odometer, 0), p_odometer_reading),
            updated_at = CURRENT_TIMESTAMP
        WHERE vehicle_id = p_vehicle_id;
        
        RETURN v_record_id;
      END;
      $$;


--
-- Name: add_vehicle_document(integer, character varying, character varying, character varying, date, date, numeric); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.add_vehicle_document(p_vehicle_id integer, p_type_code character varying, p_document_number character varying, p_file_path character varying, p_issue_date date, p_expiry_date date DEFAULT NULL::date, p_cost numeric DEFAULT NULL::numeric) RETURNS integer
    LANGUAGE plpgsql
    AS $$
      DECLARE
        v_doc_type_id INTEGER;
        v_document_id INTEGER;
      BEGIN
        -- Get document type ID
        SELECT doc_type_id INTO v_doc_type_id
        FROM vehicle_document_types 
        WHERE type_code = p_type_code;
        
        -- Insert document record
        INSERT INTO vehicle_documents 
        (vehicle_id, doc_type_id, document_number, file_path, 
         issue_date, expiry_date, cost_amount, uploaded_by)
        VALUES (p_vehicle_id, v_doc_type_id, p_document_number, p_file_path,
                p_issue_date, p_expiry_date, p_cost, 'system')
        RETURNING document_id INTO v_document_id;
        
        RETURN v_document_id;
      END;
      $$;


--
-- Name: assign_fleet_position(integer, integer, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.assign_fleet_position(p_fleet_position integer, p_vehicle_id integer, p_assignment_reason text DEFAULT 'Fleet Assignment'::text) RETURNS integer
    LANGUAGE plpgsql
    AS $$
      DECLARE
        new_history_id INTEGER;
      BEGIN
        -- Mark previous assignment as inactive if exists
        UPDATE vehicle_fleet_history 
        SET is_active = false, released_date = CURRENT_TIMESTAMP,
            release_reason = 'Position Reassigned'
        WHERE fleet_position = p_fleet_position AND is_active = true;
        
        -- Create new assignment
        INSERT INTO vehicle_fleet_history 
        (fleet_position, vehicle_id, assignment_reason, make, model, year, license_plate, vehicle_identifier)
        SELECT p_fleet_position, p_vehicle_id, p_assignment_reason, 
               make, model, year, license_plate, vehicle_number
        FROM vehicles WHERE vehicle_id = p_vehicle_id
        RETURNING history_id INTO new_history_id;
        
        -- Update vehicle record
        UPDATE vehicles 
        SET fleet_position = p_fleet_position,
            vehicle_number = 'L-' || p_fleet_position,
            vehicle_history_id = new_history_id
        WHERE vehicle_id = p_vehicle_id;
        
        RETURN new_history_id;
      END;
      $$;


--
-- Name: audit_user_action(integer, character varying, character varying, character varying, character varying, jsonb, jsonb, boolean, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.audit_user_action(p_user_id integer, p_action character varying, p_module character varying, p_record_type character varying, p_record_id character varying, p_before_values jsonb DEFAULT NULL::jsonb, p_after_values jsonb DEFAULT NULL::jsonb, p_success boolean DEFAULT true, p_error_message text DEFAULT NULL::text) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  INSERT INTO security_audit_log (user_id, action, module, record_type, record_id, before_values, after_values, success, error_message)
  VALUES (p_user_id, p_action, p_module, p_record_type, p_record_id, p_before_values, p_after_values, p_success, p_error_message);
END;
$$;


--
-- Name: auto_assign_driver_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.auto_assign_driver_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
      BEGIN
        IF NEW.is_chauffeur = true AND (NEW.driver_code IS NULL OR NEW.driver_code = '') THEN
          NEW.driver_code := generate_next_driver_code();
        END IF;
        RETURN NEW;
      END;
      $$;


--
-- Name: auto_flag_aged_accounts(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.auto_flag_aged_accounts() RETURNS void
    LANGUAGE plpgsql
    AS $_$
      DECLARE
        rec RECORD;
      BEGIN
        -- Flag accounts for review (61-90 days)
        UPDATE clients 
        SET bad_debt_status = 'review'
        WHERE bad_debt_status = 'current'
          AND balance > 100
          AND (CURRENT_DATE - COALESCE(first_overdue_date, created_at::date))::integer > 60
          AND (CURRENT_DATE - COALESCE(first_overdue_date, created_at::date))::integer <= 90;
        
        -- Flag accounts for collection (91-120 days)
        UPDATE clients 
        SET bad_debt_status = 'collection'
        WHERE bad_debt_status = 'review'
          AND balance > 500
          AND (CURRENT_DATE - COALESCE(first_overdue_date, created_at::date))::integer > 90
          AND (CURRENT_DATE - COALESCE(first_overdue_date, created_at::date))::integer <= 120;
        
        -- Flag high-value accounts approaching writeoff (>120 days, >$10K)
        UPDATE clients 
        SET recovery_probability = 'low',
            bad_debt_reason = 'Aged over 120 days - writeoff consideration'
        WHERE bad_debt_status = 'collection'
          AND balance > 10000
          AND (CURRENT_DATE - COALESCE(first_overdue_date, created_at::date))::integer > 120;
          
      END;
      $_$;


--
-- Name: auto_populate_payment_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.auto_populate_payment_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
                BEGIN
                    -- Auto-populate payment_code_4char from payment_key (first 4 chars)
                    IF NEW.payment_key IS NOT NULL AND NEW.payment_code_4char IS NULL THEN
                        NEW.payment_code_4char = UPPER(LEFT(NEW.payment_key, 4));
                    END IF;
                    
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $$;


--
-- Name: auto_post_payroll_entry(integer, date, numeric, numeric, numeric); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.auto_post_payroll_entry(p_employee_id integer, p_pay_date date, p_hours numeric, p_rate numeric, p_total_pay numeric) RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
    header_id INTEGER;
    employee_name VARCHAR(255);
BEGIN
    -- Get employee name
    SELECT COALESCE(first_name || ' ' || last_name, 'Unknown Employee') 
    INTO employee_name
    FROM employees WHERE employee_id = p_employee_id;
    
    -- Create journal entry using template
    SELECT create_journal_entry_from_template(
        (SELECT template_id FROM journal_entry_templates WHERE template_name = 'Payroll Entry'),
        p_pay_date,
        'Payroll for ' || employee_name || ' - ' || p_hours || ' hours',
        ARRAY[p_total_pay, p_total_pay]
    ) INTO header_id;
    
    -- Post the entry
    UPDATE general_ledger_headers 
    SET status = 'posted', posted_at = CURRENT_TIMESTAMP
    WHERE header_id = header_id;
    
    RETURN header_id;
END;
$$;


--
-- Name: auto_post_revenue_entry(integer, numeric, boolean); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.auto_post_revenue_entry(p_charter_id integer, p_amount numeric, p_is_paid boolean DEFAULT false) RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
    header_id INTEGER;
    charter_info VARCHAR(255);
    entry_date DATE;
BEGIN
    -- Get charter information
    SELECT 
        'Charter #' || charter_number || ' - ' || COALESCE(client_name, 'Client'),
        charter_date
    INTO charter_info, entry_date
    FROM charters WHERE charter_id = p_charter_id;
    
    -- Create journal entry
    SELECT create_journal_entry_from_template(
        (SELECT template_id FROM journal_entry_templates WHERE template_name = 'Revenue Recognition'),
        entry_date,
        'Revenue for ' || charter_info,
        ARRAY[p_amount, p_amount]
    ) INTO header_id;
    
    -- Update account codes based on payment status
    UPDATE general_ledger_lines 
    SET account_code = CASE WHEN p_is_paid THEN '1000' ELSE '1200' END,
        account_name = CASE WHEN p_is_paid THEN 'Cash and Cash Equivalents' ELSE 'Accounts Receivable' END
    WHERE header_id = header_id AND line_number = 1;
    
    -- Post the entry
    UPDATE general_ledger_headers 
    SET status = 'posted', posted_at = CURRENT_TIMESTAMP
    WHERE header_id = header_id;
    
    RETURN header_id;
END;
$$;


--
-- Name: calc_effective_hourly(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.calc_effective_hourly() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF NEW.actual_payable_hours IS NOT NULL AND NEW.actual_payable_hours > 0 THEN
    NEW.effective_hourly := ROUND(NEW.total_driver_pay / NEW.actual_payable_hours, 2);
  ELSE
    NEW.effective_hourly := NULL;
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: calculate_driver_expense(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.calculate_driver_expense(charter_id_param integer) RETURNS TABLE(charter_id integer, driver_code text, hours_worked numeric, hourly_rate numeric, base_pay numeric, gratuity_amount numeric, total_expense numeric)
    LANGUAGE plpgsql
    AS $$
      DECLARE
        charter_rec RECORD;
        employee_rate DECIMAL;
        gratuity_amt DECIMAL := 0;
      BEGIN
        -- Get charter details
        SELECT c.charter_id, c.driver, c.calculated_hours, c.rate
        INTO charter_rec
        FROM charters c
        WHERE c.charter_id = charter_id_param;
        
        IF NOT FOUND THEN
          RAISE EXCEPTION 'Charter % not found', charter_id_param;
        END IF;
        
        -- Get employee hourly rate
        SELECT e.hourly_rate
        INTO employee_rate
        FROM employees e
        WHERE e.employee_number::text = charter_rec.driver
          AND e.is_chauffeur = true;
        
        IF NOT FOUND THEN
          employee_rate := 15.00; -- Default fallback
        END IF;
        
        -- Calculate gratuity from charter_charges
        SELECT COALESCE(SUM(cc.amount), 0)
        INTO gratuity_amt
        FROM charter_charges cc
        WHERE cc.charter_id = charter_id_param
          AND (
            cc.description ILIKE '%gratuity%'
            OR cc.description ILIKE '%tip%'
            OR cc.description ILIKE '%service charge%'
          );
        
        -- Return calculated values
        RETURN QUERY SELECT
          charter_rec.charter_id,
          charter_rec.driver,
          charter_rec.calculated_hours,
          employee_rate,
          (charter_rec.calculated_hours * employee_rate),
          gratuity_amt,
          (charter_rec.calculated_hours * employee_rate) + gratuity_amt;
      END;
      $$;


--
-- Name: calculate_gst_amounts(numeric, character, boolean); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.calculate_gst_amounts(p_raw_amount numeric, p_province_code character DEFAULT 'AB'::bpchar, p_tax_included boolean DEFAULT true) RETURNS TABLE(gross_amount numeric, gst_amount numeric, net_amount numeric)
    LANGUAGE plpgsql
    AS $$
        DECLARE
            v_rate DECIMAL(6,4);
        BEGIN
            -- Get tax rate for province
            SELECT total_rate INTO v_rate 
            FROM gst_rates_lookup 
            WHERE province_code = p_province_code;
            
            -- Default to Alberta rate if province not found
            IF v_rate IS NULL THEN
                v_rate := 0.0500;
            END IF;
            
            IF p_tax_included THEN
                -- Tax is included in the raw amount
                gross_amount := p_raw_amount;
                gst_amount := ROUND(p_raw_amount * v_rate / (1 + v_rate), 2);
                net_amount := gross_amount - gst_amount;
            ELSE
                -- Tax is additional to raw amount
                net_amount := p_raw_amount;
                gst_amount := ROUND(p_raw_amount * v_rate, 2);
                gross_amount := net_amount + gst_amount;
            END IF;
            
            RETURN NEXT;
        END;
        $$;


--
-- Name: calculate_monthly_interest(integer, character varying); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.calculate_monthly_interest(credit_line_id integer, month_year character varying) RETURNS numeric
    LANGUAGE plpgsql
    AS $$
DECLARE
    avg_balance DECIMAL(10,2);
    interest_rate DECIMAL(5,2);
    monthly_interest DECIMAL(10,2);
BEGIN
    -- Get the interest rate for the credit line
    SELECT cl.interest_rate INTO interest_rate
    FROM credit_lines cl
    WHERE cl.id = credit_line_id;
    
    -- For now, use current balance as average (in real implementation, calculate from daily balances)
    SELECT cl.current_balance INTO avg_balance
    FROM credit_lines cl
    WHERE cl.id = credit_line_id;
    
    -- Calculate monthly interest (annual rate / 12)
    monthly_interest := (avg_balance * interest_rate / 100) / 12;
    
    RETURN monthly_interest;
END;
$$;


--
-- Name: calculate_next_service_due(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.calculate_next_service_due() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
      DECLARE
        service_freq_km INTEGER;
        service_freq_months INTEGER;
        vehicle_odometer INTEGER;
      BEGIN
        -- Get service frequency
        SELECT frequency_km, frequency_months 
        INTO service_freq_km, service_freq_months
        FROM maintenance_service_types 
        WHERE service_type_id = NEW.service_type_id;
        
        -- Get current vehicle odometer
        SELECT odometer INTO vehicle_odometer
        FROM vehicles 
        WHERE vehicle_id = NEW.vehicle_id;
        
        -- Calculate next due date
        IF service_freq_months IS NOT NULL THEN
          NEW.next_due_date = COALESCE(NEW.last_service_date, CURRENT_DATE) + INTERVAL '1 month' * service_freq_months;
        END IF;
        
        -- Calculate next due kilometers
        IF service_freq_km IS NOT NULL THEN
          NEW.next_due_km = COALESCE(NEW.last_service_km, vehicle_odometer) + service_freq_km;
        END IF;
        
        RETURN NEW;
      END;
      $$;


--
-- Name: can_edit_record(integer, character varying, character varying, character varying); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.can_edit_record(p_user_id integer, p_module character varying, p_record_type character varying, p_record_id character varying) RETURNS TABLE(can_edit boolean, locked_by_username character varying, reason text)
    LANGUAGE plpgsql
    AS $$
BEGIN
  RETURN QUERY
  SELECT
    CASE WHEN rl.id IS NULL THEN TRUE ELSE FALSE END,
    su.username,
    CASE
      WHEN rl.id IS NULL THEN 'OK'
      WHEN rl.locked_by_user_id = p_user_id THEN 'Locked by you; edit in progress'
      WHEN rl.expires_at < NOW() THEN 'Lock expired; you can proceed (refreshing lock)'
      ELSE 'In use by ' || su.username || '; try again in 1 minute'
    END
  FROM (SELECT 1 dummy) d
  LEFT JOIN record_locks rl ON rl.module = p_module AND rl.record_type = p_record_type AND rl.record_id = p_record_id AND rl.expires_at > NOW()
  LEFT JOIN system_users su ON rl.locked_by_user_id = su.user_id;
END;
$$;


--
-- Name: check_document_expiry(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.check_document_expiry() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
      BEGIN
        -- Check for documents expiring in 30 days
        INSERT INTO compliance_alerts (employee_id, alert_type, severity, title, description, related_document_id, due_date)
        SELECT 
          ed.employee_id,
          CASE 
            WHEN ed.expiry_date <= CURRENT_DATE THEN 'document_expired'
            ELSE 'document_expiring'
          END,
          CASE 
            WHEN ed.expiry_date <= CURRENT_DATE THEN 'critical'
            WHEN ed.expiry_date <= CURRENT_DATE + INTERVAL '7 days' THEN 'high'
            ELSE 'medium'
          END,
          'Document ' || CASE 
            WHEN ed.expiry_date <= CURRENT_DATE THEN 'Expired'
            ELSE 'Expiring Soon'
          END,
          'Document "' || ed.document_name || '" ' || 
          CASE 
            WHEN ed.expiry_date <= CURRENT_DATE THEN 'has expired'
            ELSE 'expires on ' || ed.expiry_date::TEXT
          END,
          ed.document_id,
          ed.expiry_date
        FROM employee_documents ed
        WHERE ed.expiry_date IS NOT NULL 
          AND ed.expiry_date <= CURRENT_DATE + INTERVAL '30 days'
          AND ed.status = 'active'
          AND NOT EXISTS (
            SELECT 1 FROM compliance_alerts ca 
            WHERE ca.employee_id = ed.employee_id 
              AND ca.related_document_id = ed.document_id 
              AND ca.resolved = false
          );
        
        RETURN NULL;
      END;
      $$;


--
-- Name: check_hos_compliance(integer, date); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.check_hos_compliance(emp_id integer, check_date date) RETURNS boolean
    LANGUAGE plpgsql
    AS $$
      DECLARE
        daily_driving_hours DECIMAL;
        daily_duty_hours DECIMAL;
        weekly_hours DECIMAL;
        violation_found BOOLEAN := false;
      BEGIN
        -- Calculate daily driving hours
        SELECT COALESCE(SUM(duration_minutes), 0) / 60.0 INTO daily_driving_hours
        FROM duty_log_entries dle
        JOIN duty_status_types dst ON dle.status_id = dst.status_id
        WHERE dle.employee_id = emp_id 
          AND DATE(dle.start_time) = check_date
          AND dst.counts_as_driving = true;

        -- Calculate daily duty hours
        SELECT COALESCE(SUM(duration_minutes), 0) / 60.0 INTO daily_duty_hours
        FROM duty_log_entries dle
        JOIN duty_status_types dst ON dle.status_id = dst.status_id
        WHERE dle.employee_id = emp_id 
          AND DATE(dle.start_time) = check_date
          AND dst.counts_as_on_duty = true;

        -- Calculate weekly hours
        SELECT COALESCE(SUM(duration_minutes), 0) / 60.0 INTO weekly_hours
        FROM duty_log_entries dle
        JOIN duty_status_types dst ON dle.status_id = dst.status_id
        WHERE dle.employee_id = emp_id 
          AND dle.start_time >= check_date - INTERVAL '6 days'
          AND dle.start_time < check_date + INTERVAL '1 day'
          AND dst.counts_as_on_duty = true;

        -- Check violations
        IF daily_driving_hours > 13 THEN
          INSERT INTO hos_violations (employee_id, violation_date, violation_type, description, hours_exceeded, severity)
          VALUES (emp_id, check_date, 'daily_driving_limit', 'Exceeded 13-hour daily driving limit', daily_driving_hours - 13, 'high');
          violation_found := true;
        END IF;

        IF daily_duty_hours > 16 THEN
          INSERT INTO hos_violations (employee_id, violation_date, violation_type, description, hours_exceeded, severity)
          VALUES (emp_id, check_date, 'daily_duty_limit', 'Exceeded 16-hour daily duty limit', daily_duty_hours - 16, 'critical');
          violation_found := true;
        END IF;

        IF weekly_hours > 70 THEN
          INSERT INTO hos_violations (employee_id, violation_date, violation_type, description, hours_exceeded, severity)
          VALUES (emp_id, check_date, 'weekly_limit', 'Exceeded 70-hour weekly limit', weekly_hours - 70, 'critical');
          violation_found := true;
        END IF;

        RETURN NOT violation_found;
      END;
      $$;


--
-- Name: check_vehicle_compliance(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.check_vehicle_compliance(p_vehicle_id integer) RETURNS TABLE(category character varying, required_docs integer, current_docs integer, expired_docs integer, compliance_status character varying)
    LANGUAGE plpgsql
    AS $$
      BEGIN
        RETURN QUERY
        SELECT 
          vdt.category,
          COUNT(CASE WHEN vdt.is_mandatory THEN 1 END)::INTEGER as required_docs,
          COUNT(CASE WHEN vd.document_id IS NOT NULL AND vd.status = 'active' THEN 1 END)::INTEGER as current_docs,
          COUNT(CASE WHEN vd.expiry_date < CURRENT_DATE AND vd.status = 'active' THEN 1 END)::INTEGER as expired_docs,
          CASE 
            WHEN COUNT(CASE WHEN vd.expiry_date < CURRENT_DATE AND vd.status = 'active' THEN 1 END) > 0 THEN 'NON_COMPLIANT'
            WHEN COUNT(CASE WHEN vdt.is_mandatory THEN 1 END) > COUNT(CASE WHEN vd.document_id IS NOT NULL AND vd.status = 'active' THEN 1 END) THEN 'INCOMPLETE'
            ELSE 'COMPLIANT'
          END as compliance_status
        FROM vehicle_document_types vdt
        LEFT JOIN vehicle_documents vd ON vdt.doc_type_id = vd.doc_type_id AND vd.vehicle_id = p_vehicle_id
        GROUP BY vdt.category
        ORDER BY vdt.category;
      END;
      $$;


--
-- Name: create_journal_entry_from_template(integer, date, text, numeric[]); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.create_journal_entry_from_template(p_template_id integer, p_entry_date date, p_description text, p_amounts numeric[]) RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
    header_id INTEGER;
    template_line RECORD;
    line_counter INTEGER := 1;
    total_debits DECIMAL := 0;
    total_credits DECIMAL := 0;
BEGIN
    -- Create header
    INSERT INTO general_ledger_headers (
        entry_date, reference_number, description, total_debits, total_credits, created_by, status
    ) VALUES (
        p_entry_date,
        'JE-' || TO_CHAR(NOW(), 'YYYYMMDD') || '-' || nextval('general_ledger_headers_header_id_seq'),
        p_description,
        0, 0, -- Will be updated after lines
        'system',
        'draft'
    ) RETURNING header_id INTO header_id;
    
    -- Create lines from template
    FOR template_line IN 
        SELECT * FROM journal_entry_template_lines 
        WHERE template_id = p_template_id 
        ORDER BY line_number
    LOOP
        INSERT INTO general_ledger_lines (
            header_id, line_number, account_code, account_name,
            debit_amount, credit_amount, description
        ) VALUES (
            header_id,
            template_line.line_number,
            template_line.account_code,
            template_line.account_name,
            CASE WHEN template_line.debit_credit = 'debit' THEN p_amounts[line_counter] ELSE 0 END,
            CASE WHEN template_line.debit_credit = 'credit' THEN p_amounts[line_counter] ELSE 0 END,
            template_line.description_template
        );
        
        -- Update totals
        IF template_line.debit_credit = 'debit' THEN
            total_debits := total_debits + p_amounts[line_counter];
        ELSE
            total_credits := total_credits + p_amounts[line_counter];
        END IF;
        
        line_counter := line_counter + 1;
    END LOOP;
    
    -- Update header with totals
    UPDATE general_ledger_headers 
    SET total_debits = total_debits, total_credits = total_credits
    WHERE header_id = header_id;
    
    RETURN header_id;
END;
$$;


--
-- Name: FUNCTION create_journal_entry_from_template(p_template_id integer, p_entry_date date, p_description text, p_amounts numeric[]); Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON FUNCTION public.create_journal_entry_from_template(p_template_id integer, p_entry_date date, p_description text, p_amounts numeric[]) IS 'Creates standardized journal entries from templates';


--
-- Name: derive_code4_from_banking(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.derive_code4_from_banking(description text) RETURNS character varying
    LANGUAGE plpgsql IMMUTABLE
    AS $$
                DECLARE
                    ref TEXT;
                BEGIN
                    -- Take last 4 digits of the 12-digit numeric reference in banking description, if present
                    ref := substring(description FROM 'E-TRANSFER ([0-9]{12})');
                    IF ref IS NULL THEN
                        RETURN NULL;
                    END IF;
                    RETURN RIGHT(ref, 4);
                END;
                $$;


--
-- Name: derive_code4_from_interac(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.derive_code4_from_interac(interac_ref text) RETURNS character varying
    LANGUAGE plpgsql IMMUTABLE
    AS $$
                DECLARE
                    cleaned TEXT;
                BEGIN
                    IF interac_ref IS NULL THEN
                        RETURN NULL;
                    END IF;
                    -- Keep only letters and digits, then take first 4
                    cleaned := regexp_replace(interac_ref, '[^A-Za-z0-9]', '', 'g');
                    IF cleaned IS NULL OR length(cleaned) = 0 THEN
                        RETURN NULL;
                    END IF;
                    RETURN UPPER(LEFT(cleaned, 4));
                END;
                $$;


--
-- Name: ensure_ledger_on_receipts_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.ensure_ledger_on_receipts_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF NEW.banking_transaction_id IS NOT NULL THEN
    IF NOT EXISTS (
      SELECT 1 FROM banking_receipt_matching_ledger brml
      WHERE brml.receipt_id = NEW.receipt_id
        AND brml.banking_transaction_id = NEW.banking_transaction_id
    ) THEN
      INSERT INTO banking_receipt_matching_ledger (
        banking_transaction_id, receipt_id, match_date,
        match_type, match_status, match_confidence, notes, created_by
      ) VALUES (
        NEW.banking_transaction_id,
        NEW.receipt_id,
        COALESCE(NEW.receipt_date, NOW()),
        'auto_generated', 'linked', 'auto',
        'Trigger: auto-created from receipts change', 'trigger'
      );
    END IF;
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: estimate_charter_hours(numeric, time without time zone, date); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.estimate_charter_hours(charter_rate numeric, pickup_time time without time zone, charter_date date) RETURNS numeric
    LANGUAGE plpgsql
    AS $$
      DECLARE
        estimated_hours DECIMAL := 0;
      BEGIN
        -- Base estimation logic
        CASE 
          -- High-value charters (likely longer trips)
          WHEN charter_rate >= 1000 THEN estimated_hours := 8.0;
          WHEN charter_rate >= 500 THEN estimated_hours := 6.0;
          WHEN charter_rate >= 300 THEN estimated_hours := 4.0;
          WHEN charter_rate >= 200 THEN estimated_hours := 3.0;
          WHEN charter_rate >= 100 THEN estimated_hours := 2.0;
          ELSE estimated_hours := 1.5;
        END CASE;
        
        -- Adjust for time of day (evening/night might be longer)
        IF pickup_time IS NOT NULL THEN
          IF pickup_time >= '18:00:00' OR pickup_time <= '06:00:00' THEN
            estimated_hours := estimated_hours * 1.2; -- 20% longer for evening/night
          END IF;
        END IF;
        
        -- Weekend adjustment (might be longer events)
        IF EXTRACT(DOW FROM charter_date) IN (0, 6) THEN -- Sunday = 0, Saturday = 6
          estimated_hours := estimated_hours * 1.1; -- 10% longer for weekends
        END IF;
        
        -- Minimum 1 hour, maximum 12 hours
        estimated_hours := GREATEST(1.0, LEAST(12.0, estimated_hours));
        
        RETURN estimated_hours;
      END;
      $$;


--
-- Name: extract_etransfer_reference(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.extract_etransfer_reference(description text) RETURNS character varying
    LANGUAGE plpgsql IMMUTABLE
    AS $$
                BEGIN
                    -- Extract e-transfer reference number from banking descriptions
                    -- Pattern: "Internet Banking E-TRANSFER 105613659340 DAVIDRICH"
                    IF description IS NULL THEN
                        RETURN NULL;
                    END IF;
                    
                    -- Look for 12-digit reference number pattern
                    RETURN substring(description FROM 'E-TRANSFER ([0-9]{12})');
                END;
                $$;


--
-- Name: extract_etransfer_sender(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.extract_etransfer_sender(description text) RETURNS character varying
    LANGUAGE plpgsql IMMUTABLE
    AS $_$
                BEGIN
                    -- Extract sender name after the reference number
                    -- Pattern: "Internet Banking E-TRANSFER 105613659340 DAVIDRICH"
                    IF description IS NULL THEN
                        RETURN NULL;
                    END IF;
                    
                    -- Extract text after 12-digit number
                    RETURN trim(substring(description FROM 'E-TRANSFER [0-9]{12} (.+)$'));
                END;
                $_$;


--
-- Name: find_duplicate_expenses(text, numeric, date, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.find_duplicate_expenses(p_description text, p_amount numeric, p_date date, p_exclude_id integer DEFAULT NULL::integer) RETURNS TABLE(id integer, description text, amount numeric, date date, similarity_score numeric)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT 
        pe.id,
        pe.description,
        pe.amount,
        pe.date,
        CASE 
            WHEN pe.amount = p_amount AND pe.date = p_date THEN 1.0
            WHEN pe.amount = p_amount AND ABS(EXTRACT(DAY FROM pe.date - p_date)) <= 1 THEN 0.9
            WHEN ABS(pe.amount - p_amount) <= 5.00 AND pe.date = p_date THEN 0.8
            ELSE 0.7
        END as similarity_score
    FROM personal_expenses pe
    WHERE 
        (p_exclude_id IS NULL OR pe.id != p_exclude_id)
        AND (
            (pe.amount = p_amount AND pe.date = p_date) OR
            (pe.amount = p_amount AND ABS(EXTRACT(DAY FROM pe.date - p_date)) <= 1) OR
            (ABS(pe.amount - p_amount) <= 5.00 AND pe.date = p_date) OR
            (SIMILARITY(pe.description, p_description) > 0.6 AND ABS(pe.amount - p_amount) <= 10.00)
        )
    ORDER BY similarity_score DESC, pe.date DESC
    LIMIT 5;
END;
$$;


--
-- Name: generate_next_driver_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.generate_next_driver_code() RETURNS character varying
    LANGUAGE plpgsql
    AS $_$
      DECLARE
        next_code VARCHAR(10);
        code_num INTEGER;
      BEGIN
        -- Find the highest existing code number
        SELECT COALESCE(MAX(CAST(SUBSTRING(driver_code FROM 3) AS INTEGER)), 0) + 1
        INTO code_num
        FROM employees 
        WHERE driver_code ~ '^DR[0-9]{3}$';
        
        -- Format as DR### (e.g., DR001, DR002)
        next_code := 'DR' || LPAD(code_num::TEXT, 3, '0');
        
        RETURN next_code;
      END;
      $_$;


--
-- Name: generate_trial_balance(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.generate_trial_balance(p_period_id integer) RETURNS boolean
    LANGUAGE plpgsql
    AS $$
DECLARE
    period_start DATE;
    period_end DATE;
    account_rec RECORD;
BEGIN
    -- Get period dates
    SELECT start_date, end_date INTO period_start, period_end
    FROM accounting_periods WHERE period_id = p_period_id;
    
    -- Clear existing trial balance for this period
    DELETE FROM trial_balance WHERE period_id = p_period_id;
    
    -- Generate trial balance for each account
    FOR account_rec IN 
        SELECT account_code, account_name, account_type 
        FROM chart_of_accounts 
        WHERE is_active = true
    LOOP
        INSERT INTO trial_balance (
            period_id, account_code, account_name, account_type,
            debit_total, credit_total, ending_balance
        )
        SELECT 
            p_period_id,
            account_rec.account_code,
            account_rec.account_name,
            account_rec.account_type,
            COALESCE(SUM(gll.debit_amount), 0) as debit_total,
            COALESCE(SUM(gll.credit_amount), 0) as credit_total,
            CASE 
                WHEN account_rec.account_type IN ('Asset', 'Expense') THEN 
                    COALESCE(SUM(gll.debit_amount), 0) - COALESCE(SUM(gll.credit_amount), 0)
                ELSE 
                    COALESCE(SUM(gll.credit_amount), 0) - COALESCE(SUM(gll.debit_amount), 0)
            END as ending_balance
        FROM general_ledger_lines gll
        JOIN general_ledger_headers glh ON gll.header_id = glh.header_id
        WHERE gll.account_code = account_rec.account_code
        AND glh.entry_date BETWEEN period_start AND period_end
        AND glh.status = 'posted';
    END LOOP;
    
    RETURN true;
END;
$$;


--
-- Name: FUNCTION generate_trial_balance(p_period_id integer); Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON FUNCTION public.generate_trial_balance(p_period_id integer) IS 'Generates trial balance for specified accounting period';


--
-- Name: generate_work_order_number(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.generate_work_order_number() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
      BEGIN
        NEW.work_order_number = 'WO' || TO_CHAR(CURRENT_DATE, 'YYYYMMDD') || '-' || LPAD(NEW.work_order_id::TEXT, 4, '0');
        RETURN NEW;
      END;
      $$;


--
-- Name: get_maintenance_due(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.get_maintenance_due(p_vehicle_id integer) RETURNS TABLE(activity_name character varying, category character varying, last_service_date date, last_service_km integer, next_due_date date, next_due_km integer, days_overdue integer, km_overdue integer, priority character varying)
    LANGUAGE plpgsql
    AS $$
      BEGIN
        RETURN QUERY
        WITH vehicle_maintenance AS (
          SELECT 
            mat.activity_name,
            mat.category,
            MAX(mr.service_date) as last_service_date,
            MAX(mr.odometer_reading) as last_service_km,
            MAX(mr.next_service_date) as next_due_date,
            MAX(mr.next_service_km) as next_due_km
          FROM maintenance_activity_types mat
          LEFT JOIN maintenance_records mr ON mat.activity_type_id = mr.activity_type_id 
            AND mr.vehicle_id = p_vehicle_id
          WHERE mat.default_interval_km IS NOT NULL OR mat.default_interval_months IS NOT NULL
          GROUP BY mat.activity_type_id, mat.activity_name, mat.category
        ),
        current_vehicle AS (
          SELECT odometer FROM vehicles WHERE vehicle_id = p_vehicle_id
        )
        SELECT 
          vm.activity_name,
          vm.category,
          vm.last_service_date,
          vm.last_service_km,
          vm.next_due_date,
          vm.next_due_km,
          CASE 
            WHEN vm.next_due_date IS NOT NULL AND vm.next_due_date < CURRENT_DATE 
            THEN (CURRENT_DATE - vm.next_due_date)::INTEGER
            ELSE 0
          END as days_overdue,
          CASE 
            WHEN vm.next_due_km IS NOT NULL AND cv.odometer > vm.next_due_km 
            THEN (cv.odometer - vm.next_due_km)
            ELSE 0
          END as km_overdue,
          CASE 
            WHEN (vm.next_due_date IS NOT NULL AND vm.next_due_date < CURRENT_DATE - INTERVAL '30 days')
              OR (vm.next_due_km IS NOT NULL AND cv.odometer > vm.next_due_km + 2000)
            THEN 'HIGH'
            WHEN (vm.next_due_date IS NOT NULL AND vm.next_due_date < CURRENT_DATE)
              OR (vm.next_due_km IS NOT NULL AND cv.odometer > vm.next_due_km)
            THEN 'MEDIUM'
            WHEN (vm.next_due_date IS NOT NULL AND vm.next_due_date <= CURRENT_DATE + INTERVAL '30 days')
              OR (vm.next_due_km IS NOT NULL AND cv.odometer >= vm.next_due_km - 1000)
            THEN 'LOW'
            ELSE 'NORMAL'
          END as priority
        FROM vehicle_maintenance vm, current_vehicle cv
        WHERE (vm.next_due_date <= CURRENT_DATE + INTERVAL '30 days'
               OR cv.odometer >= vm.next_due_km - 1000)
        ORDER BY 
          CASE 
            WHEN vm.next_due_date < CURRENT_DATE OR cv.odometer > vm.next_due_km THEN 1
            ELSE 2
          END,
          vm.next_due_date,
          vm.next_due_km;
      END;
      $$;


--
-- Name: get_user_scopes(integer, character varying); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.get_user_scopes(p_user_id integer, p_scope_type character varying) RETURNS TABLE(scope_value character varying)
    LANGUAGE plpgsql
    AS $$
BEGIN
  RETURN QUERY
  SELECT us.scope_value::VARCHAR
  FROM user_scopes us
  WHERE us.user_id = p_user_id AND us.scope_type = p_scope_type;
END;
$$;


--
-- Name: get_vehicles_due_for_maintenance(integer, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.get_vehicles_due_for_maintenance(p_days_ahead integer DEFAULT 30, p_km_threshold integer DEFAULT 1000) RETURNS TABLE(vehicle_id integer, vehicle_name text, current_km integer, last_service_date date, last_service_km integer, next_service_km integer, km_until_service integer, service_type character varying)
    LANGUAGE plpgsql
    AS $$
    BEGIN
        RETURN QUERY
        SELECT 
            v.vehicle_id,
            CONCAT(v.make, ' ', v.model, ' ', v.year) as vehicle_name,
            v.odometer as current_km,
            mr.service_date as last_service_date,
            mr.odometer_reading as last_service_km,
            mr.next_service_km,
            (mr.next_service_km - v.odometer) as km_until_service,
            mr.service_type
        FROM vehicles v
        JOIN maintenance_records mr ON v.vehicle_id = mr.vehicle_id
        WHERE mr.next_service_km IS NOT NULL
        AND v.odometer IS NOT NULL
        AND (mr.next_service_km - v.odometer) <= p_km_threshold
        ORDER BY km_until_service;
    END;
    $$;


--
-- Name: mark_charter_placeholder(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.mark_charter_placeholder() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Basic rules: explicit statuses, or zero-dollar REF/AUDIT reserve placeholders
    IF (NEW.status IN ('refund_pair','AUDIT_REVIEW'))
       OR ((COALESCE(NEW.total_amount_due,0) = 0
            AND COALESCE(NEW.paid_amount,0) = 0)
           AND NEW.reserve_number ~ '^(REF|AUDIT)') THEN
        NEW.is_placeholder := true;
    ELSIF NEW.is_placeholder IS NULL THEN
        NEW.is_placeholder := false;
    END IF;
    RETURN NEW;
END;
$$;


--
-- Name: normalize_vendor(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.normalize_vendor(vendor text) RETURNS text
    LANGUAGE plpgsql IMMUTABLE
    AS $$
    BEGIN
        RETURN UPPER(TRIM(
            REGEXP_REPLACE(
                REGEXP_REPLACE(vendor, '[^A-Za-z0-9 ]', '', 'g'),
                '\s+', ' ', 'g'
            )
        ));
    END;
    $$;


--
-- Name: release_fleet_position(integer, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.release_fleet_position(p_fleet_position integer, p_release_reason text DEFAULT 'Vehicle Decommissioned'::text) RETURNS boolean
    LANGUAGE plpgsql
    AS $$
      BEGIN
        -- Mark current assignment as inactive
        UPDATE vehicle_fleet_history 
        SET is_active = false, released_date = CURRENT_TIMESTAMP, release_reason = p_release_reason
        WHERE fleet_position = p_fleet_position AND is_active = true;
        
        -- Update vehicle record
        UPDATE vehicles 
        SET fleet_position = NULL, is_active = false, decommission_date = CURRENT_TIMESTAMP
        WHERE fleet_position = p_fleet_position;
        
        RETURN true;
      END;
      $$;


--
-- Name: release_record_lock(integer, character varying, character varying, character varying); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.release_record_lock(p_user_id integer, p_module character varying, p_record_type character varying, p_record_id character varying) RETURNS boolean
    LANGUAGE plpgsql
    AS $$
BEGIN
  DELETE FROM record_locks
  WHERE module = p_module AND record_type = p_record_type AND record_id = p_record_id
    AND locked_by_user_id = p_user_id;
  RETURN TRUE;
END;
$$;


--
-- Name: round_amounts(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.round_amounts() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    BEGIN
        NEW.amount := ROUND(NEW.amount, 2);
        RETURN NEW;
    END;
    $$;


--
-- Name: round_charter_amounts(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.round_charter_amounts() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    BEGIN
        NEW.total_amount_due := ROUND(NEW.total_amount_due, 2);
        NEW.paid_amount := ROUND(NEW.paid_amount, 2);
        NEW.balance := ROUND(NEW.balance, 2);
        RETURN NEW;
    END;
    $$;


--
-- Name: round_to_penny(numeric); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.round_to_penny(amount numeric) RETURNS numeric
    LANGUAGE plpgsql IMMUTABLE
    AS $$
    BEGIN
        RETURN ROUND(amount, 2);
    END;
    $$;


--
-- Name: trg_sync_charter_client_display_name(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_sync_charter_client_display_name() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- If invoked from charters (insert/update): set display name based on current client_id
    IF TG_TABLE_NAME = 'charters' THEN
        IF NEW.client_id IS NOT NULL THEN
            SELECT client_name INTO NEW.client_display_name FROM clients WHERE client_id = NEW.client_id;
        END IF;
        RETURN NEW;
    END IF;

    -- If invoked from clients (name change): propagate to all related charters
    IF TG_TABLE_NAME = 'clients' THEN
        UPDATE charters SET client_display_name = NEW.client_name WHERE client_id = NEW.client_id;
        RETURN NEW;
    END IF;
    RETURN NEW;
END;$$;


--
-- Name: trigger_compliance_check(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trigger_compliance_check() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
      BEGIN
        PERFORM check_hos_compliance(NEW.employee_id, DATE(NEW.start_time));
        RETURN NEW;
      END;
      $$;


--
-- Name: update_allocation_pool_balance(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_allocation_pool_balance() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    UPDATE wage_allocation_pool 
    SET allocated_amount = (
        SELECT COALESCE(SUM(allocated_amount), 0) 
        FROM wage_allocation_decisions 
        WHERE pool_id = NEW.pool_id
    ),
    remaining_balance = total_available - (
        SELECT COALESCE(SUM(allocated_amount), 0) 
        FROM wage_allocation_decisions 
        WHERE pool_id = NEW.pool_id
    ),
    updated_at = CURRENT_TIMESTAMP
    WHERE pool_id = NEW.pool_id;
    
    RETURN NEW;
END;
$$;


--
-- Name: update_banking_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_banking_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
                BEGIN
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $$;


--
-- Name: update_charter_routes_timestamp(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_charter_routes_timestamp() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


--
-- Name: update_compliance_status(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_compliance_status() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
      BEGIN
        UPDATE employees 
        SET compliance_status = (
          SELECT overall_status 
          FROM compliance_summary 
          WHERE employee_id = NEW.employee_id
        )
        WHERE employee_id = NEW.employee_id;
        RETURN NEW;
      END;
      $$;


--
-- Name: update_deferred_wage_balance(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_deferred_wage_balance() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Update the account balance based on transaction type
    IF NEW.transaction_type IN ('deferral', 'interest') THEN
        UPDATE deferred_wage_accounts 
        SET current_balance = current_balance + NEW.deferred_amount,
            updated_at = CURRENT_TIMESTAMP
        WHERE account_id = NEW.account_id;
    ELSIF NEW.transaction_type = 'payment' THEN
        UPDATE deferred_wage_accounts 
        SET current_balance = current_balance - NEW.paid_amount,
            updated_at = CURRENT_TIMESTAMP
        WHERE account_id = NEW.account_id;
    ELSIF NEW.transaction_type = 'adjustment' THEN
        UPDATE deferred_wage_accounts 
        SET current_balance = current_balance + (NEW.deferred_amount - COALESCE(NEW.paid_amount, 0)),
            updated_at = CURRENT_TIMESTAMP
        WHERE account_id = NEW.account_id;
    END IF;
    
    RETURN NEW;
END;
$$;


--
-- Name: update_invoice_balance(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_invoice_balance() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Calculate balance_due as total_amount - amount_paid
    NEW.balance_due := NEW.total_amount - COALESCE(NEW.amount_paid, 0);
    
    -- Update status based on balance
    IF NEW.balance_due <= 0 THEN
        NEW.status := 'Paid';
    ELSIF NEW.amount_paid > 0 AND NEW.balance_due > 0 THEN
        NEW.status := 'PartiallyPaid';
    ELSIF NEW.is_voided THEN
        NEW.status := 'Void';
    ELSIF NEW.due_date IS NOT NULL AND NEW.due_date < CURRENT_DATE AND NEW.balance_due > 0 THEN
        NEW.status := 'Overdue';
    ELSE
        NEW.status := 'Open';
    END IF;
    
    -- Calculate aging days
    IF NEW.invoice_date IS NOT NULL THEN
        NEW.aging_days := (CURRENT_DATE - NEW.invoice_date);
    END IF;
    
    -- Update updated_at timestamp
    NEW.updated_at := CURRENT_TIMESTAMP;
    
    RETURN NEW;
END;
$$;


--
-- Name: FUNCTION update_invoice_balance(); Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON FUNCTION public.update_invoice_balance() IS 'Automatically calculates invoice balance, status, and aging before insert/update.';


--
-- Name: update_loan_balances(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_loan_balances() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Recalculate totals for the affected loan
    UPDATE vehicle_loans SET
        total_paid = (
            SELECT COALESCE(SUM(amount), 0) 
            FROM loan_payments 
            WHERE loan_id = COALESCE(NEW.loan_id, OLD.loan_id) 
            AND status = 'cleared'
        ),
        total_interest_paid = (
            SELECT COALESCE(SUM(interest_portion), 0) 
            FROM loan_payments 
            WHERE loan_id = COALESCE(NEW.loan_id, OLD.loan_id) 
            AND status = 'cleared'
        ),
        total_fees = (
            SELECT COALESCE(SUM(fee_amount), 0) 
            FROM loan_payments 
            WHERE loan_id = COALESCE(NEW.loan_id, OLD.loan_id) 
            AND status = 'cleared'
        ),
        nsf_count = (
            SELECT COUNT(*) 
            FROM loan_payments 
            WHERE loan_id = COALESCE(NEW.loan_id, OLD.loan_id) 
            AND fee_type = 'nsf'
        ),
        current_balance = GREATEST(0, 
            principal_amount - (
                SELECT COALESCE(SUM(principal_portion), 0) 
                FROM loan_payments 
                WHERE loan_id = COALESCE(NEW.loan_id, OLD.loan_id) 
                AND status = 'cleared'
            )
        ),
        updated_at = now()
    WHERE loan_id = COALESCE(NEW.loan_id, OLD.loan_id);
    
    RETURN COALESCE(NEW, OLD);
END;
$$;


--
-- Name: update_qb_accounts_staging_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_qb_accounts_staging_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
    END;
    $$;


--
-- Name: update_timestamp(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_timestamp() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


--
-- Name: update_vehicle_odometer(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_vehicle_odometer() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    BEGIN
        -- Update vehicle's odometer to the latest reading
        UPDATE vehicles 
        SET odometer = NEW.odometer_reading,
            updated_at = CURRENT_TIMESTAMP
        WHERE vehicle_id = NEW.vehicle_id
        AND (odometer IS NULL OR NEW.odometer_reading > odometer);
        
        RETURN NEW;
    END;
    $$;


--
-- Name: update_work_order_vehicle_info(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_work_order_vehicle_info() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
      BEGIN
        SELECT vehicle_number, vin_number, vehicle_code 
        INTO NEW.vehicle_number, NEW.vin_number, NEW.vehicle_code
        FROM vehicles 
        WHERE vehicle_id = NEW.vehicle_id;
        RETURN NEW;
      END;
      $$;


--
-- Name: user_has_permission(integer, character varying, character varying); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.user_has_permission(p_user_id integer, p_module character varying, p_action character varying) RETURNS boolean
    LANGUAGE plpgsql
    AS $$
DECLARE
  v_has_perm BOOLEAN;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM user_roles ur
    JOIN system_roles sr ON ur.role_id = sr.role_id
    JOIN role_permissions rp ON sr.role_id = rp.role_id
    JOIN permissions p ON rp.permission_id = p.permission_id
    WHERE ur.user_id = p_user_id
      AND p.module = p_module
      AND p.action = p_action
  ) INTO v_has_perm;
  RETURN COALESCE(v_has_perm, FALSE);
END;
$$;


--
-- Name: user_is_superuser(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.user_is_superuser(p_user_id integer) RETURNS boolean
    LANGUAGE plpgsql
    AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM user_roles ur
    JOIN system_roles sr ON ur.role_id = sr.role_id
    WHERE ur.user_id = p_user_id AND sr.role_name = 'super_user'
  );
END;
$$;


--
-- Name: validate_receipt_banking_amounts(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.validate_receipt_banking_amounts(p_receipt_id integer) RETURNS TABLE(is_valid boolean, banking_total numeric, receipt_total numeric, variance numeric)
    LANGUAGE plpgsql
    AS $$
            DECLARE
                v_banking_total NUMERIC;
                v_receipt_total NUMERIC;
            BEGIN
                SELECT COALESCE(SUM(linked_amount), 0) INTO v_banking_total
                FROM receipt_banking_links WHERE receipt_id = p_receipt_id;
                
                SELECT gross_amount INTO v_receipt_total
                FROM receipts WHERE receipt_id = p_receipt_id;
                
                RETURN QUERY SELECT 
                    (ABS(v_banking_total - v_receipt_total) < 0.01)::BOOLEAN,
                    v_banking_total,
                    v_receipt_total,
                    ABS(v_banking_total - v_receipt_total);
            END;
            $$;


--
-- Name: validate_receipt_split_amounts(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.validate_receipt_split_amounts(p_receipt_id integer) RETURNS TABLE(is_valid boolean, split_total numeric, receipt_total numeric, variance numeric)
    LANGUAGE plpgsql
    AS $$
            DECLARE
                v_split_total NUMERIC;
                v_receipt_total NUMERIC;
            BEGIN
                SELECT COALESCE(SUM(amount), 0) INTO v_split_total
                FROM receipt_splits WHERE receipt_id = p_receipt_id;
                
                SELECT gross_amount INTO v_receipt_total
                FROM receipts WHERE receipt_id = p_receipt_id;
                
                RETURN QUERY SELECT 
                    (ABS(v_split_total - v_receipt_total) < 0.01)::BOOLEAN,
                    v_split_total,
                    v_receipt_total,
                    ABS(v_split_total - v_receipt_total);
            END;
            $$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: account_categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.account_categories (
    category_id integer NOT NULL,
    category_code character varying(50) NOT NULL,
    category_name character varying(100) NOT NULL,
    account_type character varying(50) NOT NULL,
    parent_category character varying(50),
    is_active boolean DEFAULT true,
    auto_categorize boolean DEFAULT true,
    description text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    gl_account_code character varying(20),
    gl_account_code_alt character varying(20),
    CONSTRAINT account_categories_account_type_check CHECK (((account_type)::text = ANY (ARRAY[('expense'::character varying)::text, ('income'::character varying)::text, ('asset'::character varying)::text, ('liability'::character varying)::text, ('equity'::character varying)::text, ('transfer'::character varying)::text])))
);


--
-- Name: account_categories_category_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.account_categories_category_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: account_categories_category_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.account_categories_category_id_seq OWNED BY public.account_categories.category_id;


--
-- Name: account_number_aliases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.account_number_aliases (
    alias_id integer NOT NULL,
    statement_format character varying(50) NOT NULL,
    canonical_account_number character varying(50) NOT NULL,
    institution_name character varying(100),
    account_type character varying(50),
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: account_number_aliases_alias_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.account_number_aliases_alias_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: account_number_aliases_alias_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.account_number_aliases_alias_id_seq OWNED BY public.account_number_aliases.alias_id;


--
-- Name: accounting_entries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.accounting_entries (
    id integer NOT NULL,
    entry_date date NOT NULL,
    reference character varying(100) NOT NULL,
    description text,
    account_code character varying(10),
    account_name character varying(100),
    debit_amount numeric(10,2) DEFAULT 0,
    credit_amount numeric(10,2) DEFAULT 0,
    source_type character varying(50),
    import_batch character varying(50),
    created_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    charter_id integer,
    payment_reference character varying(100)
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
-- Name: accounting_periods; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.accounting_periods (
    period_id integer NOT NULL,
    period_name character varying(50) NOT NULL,
    period_type character varying(20) NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    status character varying(20) DEFAULT 'open'::character varying,
    closed_by integer,
    closed_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT accounting_periods_period_type_check CHECK (((period_type)::text = ANY (ARRAY[('monthly'::character varying)::text, ('quarterly'::character varying)::text, ('yearly'::character varying)::text]))),
    CONSTRAINT accounting_periods_status_check CHECK (((status)::text = ANY (ARRAY[('open'::character varying)::text, ('closed'::character varying)::text, ('adjusting'::character varying)::text])))
);


--
-- Name: accounting_periods_period_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.accounting_periods_period_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: accounting_periods_period_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.accounting_periods_period_id_seq OWNED BY public.accounting_periods.period_id;


--
-- Name: accounting_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.accounting_records (
    id integer NOT NULL,
    transaction_date date,
    transaction_type character varying(100),
    amount numeric(10,2),
    description text,
    account_code character varying(50),
    account_name character varying(100),
    vendor character varying(100),
    reference character varying(50),
    category character varying(50),
    source_file character varying(200),
    imported_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: accounting_records_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.accounting_records_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: accounting_records_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.accounting_records_id_seq OWNED BY public.accounting_records.id;


--
-- Name: banking_transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.banking_transactions (
    transaction_id integer NOT NULL,
    account_number character varying(20) NOT NULL,
    transaction_date date NOT NULL,
    posted_date date,
    description text NOT NULL,
    debit_amount numeric(12,2),
    credit_amount numeric(12,2),
    balance numeric(12,2),
    vendor_extracted character varying(200),
    vendor_truncated boolean DEFAULT false,
    card_last4_detected character varying(4),
    category character varying(100),
    source_file character varying(200),
    import_batch character varying(50),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    bank_id integer,
    transaction_hash character varying(64),
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    receipt_id integer,
    source_hash character varying(64),
    reconciliation_status character varying(20) DEFAULT 'unreconciled'::character varying,
    reconciled_receipt_id integer,
    reconciled_payment_id integer,
    reconciled_charter_id integer,
    reconciliation_notes text,
    reconciled_at timestamp without time zone,
    reconciled_by character varying(100),
    is_transfer boolean DEFAULT false,
    transaction_uid character varying(20),
    business_personal character varying(20) DEFAULT 'Business'::character varying,
    gst_applicable boolean,
    verified boolean DEFAULT false,
    locked boolean DEFAULT false,
    is_nsf_charge boolean DEFAULT false,
    check_number character varying(20),
    check_recipient character varying(200),
    verified_date timestamp without time zone,
    verified_by character varying(100)
);


--
-- Name: charters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.charters (
    charter_id integer NOT NULL,
    reserve_number character varying(50) NOT NULL,
    client_id integer,
    charter_date date,
    pickup_time time without time zone,
    pickup_address text,
    dropoff_address text,
    passenger_count integer,
    rate numeric(10,2),
    balance numeric(12,2),
    payment_totals numeric(10,2),
    status character varying(50),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    driver_notes text,
    client_notes text,
    booking_notes text,
    total_amount_due numeric(10,2),
    dispatcher_approved boolean DEFAULT false,
    driver_base_pay numeric(10,2),
    driver_gratuity numeric(10,2) DEFAULT 0.00,
    driver_total_expense numeric(10,2),
    expense_calculated_at timestamp without time zone,
    odometer_start numeric(10,1),
    odometer_end numeric(10,1),
    total_kms numeric(10,1),
    vehicle_notes text,
    is_placeholder boolean DEFAULT false NOT NULL,
    default_hourly_price numeric(10,2),
    package_rate numeric(10,2),
    extra_time_rate numeric(10,2),
    daily_rate numeric(10,2),
    airport_pickup_price numeric(10,2),
    employee_id integer,
    vehicle_id integer,
    client_display_name text,
    nrd_received boolean DEFAULT false,
    nrd_amount numeric,
    nrd_method character varying,
    is_out_of_town boolean DEFAULT false,
    fuel_litres numeric,
    float_received numeric,
    float_reimbursement_needed numeric,
    calendar_color character varying(20),
    separate_customer_printout boolean DEFAULT false,
    charter_type character varying DEFAULT 'hourly'::character varying,
    quoted_hours numeric DEFAULT 0.00,
    standby_rate numeric DEFAULT 25.00,
    split_run_start_time numeric DEFAULT 0.00,
    split_run_time numeric DEFAULT 0.00,
    calendar_sync_status character varying,
    outlook_entry_id character varying,
    calendar_notes text,
    record_type public.charter_record_type,
    version integer,
    do_time time without time zone,
    cart_order_list text,
    fuel_price numeric,
    fuel_gst numeric,
    locked boolean DEFAULT false NOT NULL
);


--
-- Name: COLUMN charters.employee_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.charters.employee_id IS 'Foreign key reference to employees.employee_id for proper driver/chauffeur relational linking';


--
-- Name: COLUMN charters.vehicle_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.charters.vehicle_id IS 'Foreign key reference to vehicles.vehicle_id for proper relational linking';


--
-- Name: COLUMN charters.is_out_of_town; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.charters.is_out_of_town IS 'True if charter is outside Red Deer city limits - exempt from municipal bylaw requirements and excluded from bylaw audit reports';


--
-- Name: chauffeur_float_tracking; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chauffeur_float_tracking (
    id integer NOT NULL,
    charter_id integer,
    reserve_number character varying(50),
    driver_id integer,
    driver_name character varying(200),
    float_amount numeric(10,2),
    float_type character varying(50),
    float_date date,
    payment_method character varying(50),
    collection_amount numeric(10,2),
    return_amount numeric(10,2),
    net_float numeric(10,2),
    reconciliation_status character varying(50) DEFAULT 'outstanding'::character varying,
    matched_payment_id integer,
    square_payment_id character varying(100),
    etransfer_reference character varying(100),
    reconciled_date timestamp without time zone,
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    banking_transaction_id integer,
    receipt_date date,
    vendor_name character varying(200),
    receipt_reference character varying(100)
);


--
-- Name: employees; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.employees (
    employee_id integer NOT NULL,
    employee_number character varying(50) NOT NULL,
    full_name character varying(255) NOT NULL,
    last_name character varying(100),
    first_name character varying(100),
    phone character varying(50),
    cell_phone character varying(50),
    employee_category character varying(100) DEFAULT 'driver'::character varying,
    "position" character varying(100) DEFAULT 'chauffeur'::character varying,
    is_chauffeur boolean DEFAULT true,
    salary numeric(12,2) DEFAULT 0,
    tax_exemptions integer DEFAULT 0,
    deduction_per_voucher numeric(10,2) DEFAULT 0,
    deduction_radio_dues numeric(10,2) DEFAULT 0,
    deduction_misc_fees numeric(10,2) DEFAULT 0,
    status character varying(20) DEFAULT 'active'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    hire_date date,
    emergency_contact_name character varying(100),
    emergency_contact_phone character varying(20),
    employment_status character varying(20) DEFAULT 'active'::character varying,
    compliance_status character varying(20) DEFAULT 'unknown'::character varying,
    total_trips integer DEFAULT 0,
    total_hours numeric(8,2) DEFAULT 0.00,
    total_revenue numeric(10,2) DEFAULT 0.00,
    profile_updated timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    hourly_rate numeric(8,2) DEFAULT 15.00,
    rate_effective_date date DEFAULT CURRENT_DATE,
    quickbooks_id character varying(50),
    name character varying(255),
    email character varying(255),
    quickbooks_source character varying(255),
    t4_sin character varying(15),
    legacy_name character varying(255),
    legacy_employee boolean DEFAULT false,
    street_address character varying(200),
    city character varying(100),
    province character varying(50) DEFAULT 'AB'::character varying,
    postal_code character varying(10),
    country character varying(50) DEFAULT 'Canada'::character varying,
    driver_license_number character varying(50),
    driver_license_expiry date,
    chauffeur_permit_number character varying(50),
    chauffeur_permit_expiry date,
    salary_deferred numeric(10,2) DEFAULT 0.00,
    hourly_pay_rate numeric(8,2),
    gratuity_eligible boolean DEFAULT true,
    gratuity_percentage integer DEFAULT 100,
    red_deer_compliant boolean DEFAULT false,
    red_deer_required boolean DEFAULT true,
    license_class character varying(10),
    medical_fitness_expiry date,
    vulnerable_sector_check_date date,
    drivers_abstract_date date,
    proserve_number character varying,
    proserve_expiry date,
    bylaw_permit_renewal_fee numeric(12,2) DEFAULT 0.00,
    driver_license_class character varying,
    driver_license_restrictions text,
    qualification_1_date date,
    qualification_2_date date,
    qualification_3_date date,
    qualification_4_date date,
    qualification_5_date date,
    CONSTRAINT employees_compliance_status_check CHECK (((compliance_status)::text = ANY (ARRAY[('compliant'::character varying)::text, ('expiring'::character varying)::text, ('expired'::character varying)::text, ('unknown'::character varying)::text]))),
    CONSTRAINT employees_employment_status_check CHECK (((employment_status)::text = ANY (ARRAY[('active'::character varying)::text, ('inactive'::character varying)::text, ('suspended'::character varying)::text, ('terminated'::character varying)::text])))
);


--
-- Name: COLUMN employees.last_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.employees.last_name IS 'Corrected: now stores last name';


--
-- Name: COLUMN employees.first_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.employees.first_name IS 'Corrected: now stores first name';


--
-- Name: COLUMN employees.quickbooks_source; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.employees.quickbooks_source IS 'Source QuickBooks file';


--
-- Name: COLUMN employees.t4_sin; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.employees.t4_sin IS 'SIN for T4 reporting';


--
-- Name: COLUMN employees.legacy_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.employees.legacy_name IS 'Original name from legacy files';


--
-- Name: COLUMN employees.legacy_employee; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.employees.legacy_employee IS 'Flag for legacy employees from QuickBooks';


--
-- Name: float_activity_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.float_activity_log (
    log_id integer NOT NULL,
    float_id integer,
    activity_type character varying(50) NOT NULL,
    description text,
    created_by character varying(100),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    metadata jsonb
);


--
-- Name: active_floats_detailed; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.active_floats_detailed AS
 SELECT cft.id AS float_id,
    cft.driver_id,
    cft.driver_name,
    cft.float_amount,
    cft.float_date,
    cft.float_type,
    cft.reserve_number,
    cft.collection_amount,
    cft.reconciliation_status,
    cft.notes,
    cft.payment_method,
    cft.receipt_date,
    cft.vendor_name,
    cft.receipt_reference,
        CASE
            WHEN (cft.float_date IS NOT NULL) THEN (CURRENT_DATE - cft.float_date)
            ELSE 0
        END AS days_outstanding,
    c.charter_date,
    c.pickup_address,
    c.dropoff_address,
    c.driver_total_expense,
    e.full_name AS employee_name,
    e.employee_number,
    e.status AS employee_status,
    bt.transaction_date AS banking_date,
    bt.description AS banking_description,
    bt.debit_amount AS banking_debit,
    bt.credit_amount AS banking_credit,
    ( SELECT fal.activity_type
           FROM public.float_activity_log fal
          WHERE (fal.float_id = cft.id)
          ORDER BY fal.created_at DESC
         LIMIT 1) AS last_activity,
    ( SELECT fal.created_at
           FROM public.float_activity_log fal
          WHERE (fal.float_id = cft.id)
          ORDER BY fal.created_at DESC
         LIMIT 1) AS last_activity_date
   FROM (((public.chauffeur_float_tracking cft
     LEFT JOIN public.charters c ON (((cft.reserve_number)::text = (c.reserve_number)::text)))
     LEFT JOIN public.employees e ON (((cft.driver_id)::text = (e.employee_number)::text)))
     LEFT JOIN public.banking_transactions bt ON ((cft.banking_transaction_id = bt.transaction_id)))
  WHERE ((cft.reconciliation_status)::text = ANY ((ARRAY['pending'::character varying, 'partial'::character varying, 'overdue'::character varying, 'outstanding'::character varying])::text[]))
  ORDER BY cft.float_date DESC, cft.driver_name;


--
-- Name: agreement_terms; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agreement_terms (
    term_id integer NOT NULL,
    term_name character varying(200) NOT NULL,
    description text,
    term_text text NOT NULL,
    category character varying(50),
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: agreement_terms_term_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.agreement_terms_term_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: agreement_terms_term_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.agreement_terms_term_id_seq OWNED BY public.agreement_terms.term_id;


--
-- Name: alberta_tax_brackets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alberta_tax_brackets (
    year integer NOT NULL,
    bracket_number integer NOT NULL,
    income_from numeric(12,2) NOT NULL,
    income_to numeric(12,2),
    tax_rate numeric(5,3) NOT NULL,
    marginal_rate_description text
);


--
-- Name: alcohol_business_tracking; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alcohol_business_tracking (
    id integer NOT NULL,
    transaction_date date,
    transaction_type character varying(50),
    alcohol_type character varying(100),
    quantity numeric(8,2),
    unit_cost numeric(8,2),
    total_cost numeric(12,2),
    sale_price numeric(8,2),
    total_revenue numeric(12,2),
    profit_loss numeric(12,2),
    charter_id integer,
    receipt_id integer,
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: alcohol_business_tracking_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.alcohol_business_tracking_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: alcohol_business_tracking_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.alcohol_business_tracking_id_seq OWNED BY public.alcohol_business_tracking.id;


--
-- Name: alert_policy; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alert_policy (
    policy_id integer NOT NULL,
    alert_type character varying(50) NOT NULL,
    alert_category character varying(50) NOT NULL,
    can_prevent_usage boolean DEFAULT false,
    can_block_assignments boolean DEFAULT false,
    can_stop_operations boolean DEFAULT false,
    notification_level character varying(20) DEFAULT 'INFO'::character varying,
    policy_description text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: alert_policy_policy_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.alert_policy_policy_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: alert_policy_policy_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.alert_policy_policy_id_seq OWNED BY public.alert_policy.policy_id;


--
-- Name: app_errors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.app_errors (
    error_id integer NOT NULL,
    "timestamp" timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    error_type character varying(100),
    error_message text,
    traceback text,
    widget_name character varying(200),
    action character varying(200),
    user_context text,
    resolved boolean DEFAULT false,
    resolution_notes text,
    resolved_at timestamp without time zone
);


--
-- Name: app_errors_error_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.app_errors_error_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: app_errors_error_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.app_errors_error_id_seq OWNED BY public.app_errors.error_id;


--
-- Name: asset_depreciation_schedule; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.asset_depreciation_schedule (
    schedule_id bigint NOT NULL,
    asset_id bigint NOT NULL,
    fiscal_year integer NOT NULL,
    opening_book_value numeric(14,2) NOT NULL,
    depreciation_expense numeric(14,2) NOT NULL,
    closing_book_value numeric(14,2) NOT NULL,
    cca_claimed numeric(14,2),
    notes text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: asset_depreciation_schedule_schedule_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.asset_depreciation_schedule_schedule_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: asset_depreciation_schedule_schedule_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.asset_depreciation_schedule_schedule_id_seq OWNED BY public.asset_depreciation_schedule.schedule_id;


--
-- Name: asset_documentation; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.asset_documentation (
    doc_id bigint NOT NULL,
    asset_id bigint NOT NULL,
    document_type character varying(50) NOT NULL,
    file_path text,
    description text,
    document_date date,
    created_at timestamp without time zone DEFAULT now(),
    CONSTRAINT document_type_ck CHECK (((document_type)::text = ANY ((ARRAY['purchase_contract'::character varying, 'loan_agreement'::character varying, 'lease_agreement'::character varying, 'title_deed'::character varying, 'registration'::character varying, 'photo'::character varying, 'appraisal'::character varying, 'insurance_policy'::character varying, 'maintenance_record'::character varying, 'other'::character varying])::text[])))
);


--
-- Name: asset_documentation_doc_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.asset_documentation_doc_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: asset_documentation_doc_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.asset_documentation_doc_id_seq OWNED BY public.asset_documentation.doc_id;


--
-- Name: assets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assets (
    asset_id bigint NOT NULL,
    asset_name character varying(255) NOT NULL,
    asset_category public.asset_category DEFAULT 'other'::public.asset_category NOT NULL,
    ownership_status public.asset_ownership_type DEFAULT 'owned'::public.asset_ownership_type NOT NULL,
    serial_number character varying(100),
    vin character varying(17),
    make character varying(100),
    model character varying(100),
    year integer,
    acquisition_date date,
    acquisition_cost numeric(14,2),
    current_book_value numeric(14,2),
    salvage_value numeric(14,2) DEFAULT 0.00,
    depreciation_method public.depreciation_method DEFAULT 'straight_line'::public.depreciation_method,
    useful_life_years integer,
    cca_class character varying(10),
    cca_rate numeric(5,2),
    legal_owner character varying(255),
    lender_contact character varying(255),
    loan_agreement_ref character varying(100),
    lease_start_date date,
    lease_end_date date,
    lease_monthly_payment numeric(14,2),
    purchase_receipt_id bigint,
    insurance_policy_number character varying(100),
    location character varying(255),
    status character varying(20) DEFAULT 'active'::character varying,
    notes text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    CONSTRAINT status_ck CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'sold'::character varying, 'disposed'::character varying, 'stolen'::character varying, 'retired'::character varying])::text[])))
);


--
-- Name: TABLE assets; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.assets IS 'Business asset tracking for CRA compliance - owned, leased, and loaned items';


--
-- Name: COLUMN assets.ownership_status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assets.ownership_status IS 'owned=business asset, leased=monthly payments, loaned_in=borrowed from others';


--
-- Name: COLUMN assets.cca_class; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assets.cca_class IS 'CRA Capital Cost Allowance class (e.g., Class 10 for vehicles)';


--
-- Name: COLUMN assets.legal_owner; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.assets.legal_owner IS 'Owner name for leased/loaned items (e.g., Lease Finance Group, Jack Carter)';


--
-- Name: assets_asset_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.assets_asset_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assets_asset_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.assets_asset_id_seq OWNED BY public.assets.asset_id;


--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_log (
    audit_id bigint NOT NULL,
    entity_type character varying(50) NOT NULL,
    entity_id integer NOT NULL,
    field_changed character varying(100),
    old_value text,
    new_value text,
    changed_by integer,
    changed_at timestamp without time zone DEFAULT now(),
    reason text,
    ip_address inet,
    CONSTRAINT audit_entity CHECK (((entity_type)::text = ANY ((ARRAY['receipt'::character varying, 'split'::character varying, 'banking_link'::character varying, 'cashbox_link'::character varying])::text[])))
);


--
-- Name: audit_log_audit_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_log_audit_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_log_audit_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_log_audit_id_seq OWNED BY public.audit_log.audit_id;


--
-- Name: bank_accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bank_accounts (
    bank_id integer NOT NULL,
    account_name character varying(100) NOT NULL,
    institution_name character varying(100) NOT NULL,
    account_number character varying(50),
    account_type character varying(50) NOT NULL,
    currency character varying(3) DEFAULT 'CAD'::character varying,
    routing_number character varying(20),
    swift_code character varying(20),
    branch_name character varying(100),
    branch_address text,
    is_active boolean DEFAULT true,
    opened_date date,
    closed_date date,
    auto_reconcile boolean DEFAULT false,
    reconciliation_rules jsonb,
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT bank_accounts_account_type_check CHECK (((account_type)::text = ANY (ARRAY[('checking'::character varying)::text, ('savings'::character varying)::text, ('credit_card'::character varying)::text, ('line_of_credit'::character varying)::text, ('loan'::character varying)::text, ('investment'::character varying)::text, ('other'::character varying)::text])))
);


--
-- Name: bank_accounts_bank_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bank_accounts_bank_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bank_accounts_bank_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bank_accounts_bank_id_seq OWNED BY public.bank_accounts.bank_id;


--
-- Name: bank_reconciliation; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bank_reconciliation (
    reconciliation_id integer NOT NULL,
    bank_account_name character varying(100) NOT NULL,
    statement_date date NOT NULL,
    opening_balance numeric(15,2),
    closing_balance numeric(15,2),
    book_balance numeric(15,2),
    reconciled_balance numeric(15,2),
    reconciliation_status character varying(20) DEFAULT 'pending'::character varying,
    reconciled_by character varying(50),
    reconciled_date timestamp without time zone,
    notes text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: bank_reconciliation_reconciliation_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bank_reconciliation_reconciliation_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bank_reconciliation_reconciliation_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bank_reconciliation_reconciliation_id_seq OWNED BY public.bank_reconciliation.reconciliation_id;


--
-- Name: banking_inter_account_transfers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.banking_inter_account_transfers (
    transfer_id integer NOT NULL,
    from_transaction_id bigint NOT NULL,
    to_transaction_id bigint NOT NULL,
    from_account_number character varying(50),
    to_account_number character varying(50),
    from_bank_id integer,
    to_bank_id integer,
    transfer_date date,
    amount numeric(12,2),
    date_diff_days integer,
    match_reason text,
    transfer_type character varying(50),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: banking_inter_account_transfers_transfer_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.banking_inter_account_transfers_transfer_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: banking_inter_account_transfers_transfer_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.banking_inter_account_transfers_transfer_id_seq OWNED BY public.banking_inter_account_transfers.transfer_id;


--
-- Name: banking_receipt_matching_ledger; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.banking_receipt_matching_ledger (
    id integer NOT NULL,
    banking_transaction_id bigint NOT NULL,
    receipt_id bigint,
    match_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    match_type character varying(50),
    match_status character varying(20),
    match_confidence character varying(20),
    notes text,
    created_by character varying(50) DEFAULT 'system'::character varying,
    amount_allocated numeric(10,2),
    allocation_date timestamp without time zone DEFAULT now(),
    allocation_type character varying(50) DEFAULT 'payment'::character varying
);


--
-- Name: banking_receipt_matching_ledger_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.banking_receipt_matching_ledger_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: banking_receipt_matching_ledger_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.banking_receipt_matching_ledger_id_seq OWNED BY public.banking_receipt_matching_ledger.id;


--
-- Name: banking_transactions_transaction_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.banking_transactions_transaction_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: banking_transactions_transaction_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.banking_transactions_transaction_id_seq OWNED BY public.banking_transactions.transaction_id;


--
-- Name: batch_deposit_allocations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.batch_deposit_allocations (
    allocation_id integer NOT NULL,
    deposit_payment_id integer NOT NULL,
    target_payment_id integer,
    reserve_number character varying(20),
    allocation_amount numeric(12,2) NOT NULL,
    method character varying(50) NOT NULL,
    remainder boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    notes text
);


--
-- Name: batch_deposit_allocations_allocation_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.batch_deposit_allocations_allocation_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: batch_deposit_allocations_allocation_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.batch_deposit_allocations_allocation_id_seq OWNED BY public.batch_deposit_allocations.allocation_id;


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
-- Name: beverage_products; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.beverage_products (
    item_id integer NOT NULL,
    item_name character varying(255) NOT NULL,
    category character varying(100),
    unit_price numeric(10,2) NOT NULL,
    stock_quantity integer,
    image_url text,
    image_path text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    our_cost numeric(10,2),
    default_markup_pct numeric(5,2) DEFAULT 35,
    deposit_amount numeric(10,2) DEFAULT 0,
    fees_amount numeric(10,2) DEFAULT 0,
    gst_included boolean DEFAULT false,
    description character varying(500) DEFAULT NULL::character varying
);


--
-- Name: beverage_products_item_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.beverage_products_item_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: beverage_products_item_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.beverage_products_item_id_seq OWNED BY public.beverage_products.item_id;


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
-- Name: billing_audit_issues; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.billing_audit_issues (
    id integer NOT NULL,
    issue_type character varying(50),
    positive_payment_id integer,
    negative_payment_id integer,
    amount numeric(10,2),
    identified_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    audit_notes text,
    resolution_status character varying(20) DEFAULT 'identified'::character varying
);


--
-- Name: billing_audit_issues_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.billing_audit_issues_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: billing_audit_issues_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.billing_audit_issues_id_seq OWNED BY public.billing_audit_issues.id;


--
-- Name: billing_audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.billing_audit_log (
    id integer NOT NULL,
    issue_type character varying(50),
    positive_payment_id integer,
    negative_payment_id integer,
    amount numeric(10,2),
    audit_notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: billing_audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.billing_audit_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: billing_audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.billing_audit_log_id_seq OWNED BY public.billing_audit_log.id;


--
-- Name: business_expenses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.business_expenses (
    id integer NOT NULL,
    expense_date date,
    amount numeric(12,2),
    vendor character varying(255),
    description text,
    category character varying(100),
    source_file character varying(255),
    source_row character varying(100),
    imported_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    notes text
);


--
-- Name: business_expenses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.business_expenses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: business_expenses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.business_expenses_id_seq OWNED BY public.business_expenses.id;


--
-- Name: business_losses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.business_losses (
    loss_id integer NOT NULL,
    loss_date date NOT NULL,
    loss_type character varying(100) NOT NULL,
    description text NOT NULL,
    amount numeric(12,2) NOT NULL,
    category character varying(100),
    status character varying(50) DEFAULT 'active'::character varying,
    insurance_claim_number character varying(100),
    recovery_amount numeric(12,2) DEFAULT 0,
    notes text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    created_by integer
);


--
-- Name: TABLE business_losses; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.business_losses IS 'Track all business losses with detailed categorization and recovery tracking';


--
-- Name: business_losses_loss_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.business_losses_loss_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: business_losses_loss_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.business_losses_loss_id_seq OWNED BY public.business_losses.loss_id;


--
-- Name: cash_box_transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cash_box_transactions (
    transaction_id integer NOT NULL,
    transaction_date date NOT NULL,
    transaction_type character varying(50) NOT NULL,
    amount numeric(12,2) NOT NULL,
    banking_transaction_id integer,
    receipt_id integer,
    employee_id integer,
    description text,
    balance_after numeric(12,2),
    created_by character varying(100),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    notes text,
    CONSTRAINT cash_box_transactions_transaction_type_check CHECK (((transaction_type)::text = ANY ((ARRAY['withdrawal_from_bank'::character varying, 'driver_float_issued'::character varying, 'driver_reimbursement'::character varying, 'customer_change'::character varying, 'deposit_to_bank'::character varying, 'adjustment'::character varying])::text[])))
);


--
-- Name: cash_box_transactions_transaction_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cash_box_transactions_transaction_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cash_box_transactions_transaction_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.cash_box_transactions_transaction_id_seq OWNED BY public.cash_box_transactions.transaction_id;


--
-- Name: cash_flow_categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cash_flow_categories (
    category_id integer NOT NULL,
    category_name character varying(100) NOT NULL,
    category_type character varying(20),
    description text,
    is_inflow boolean DEFAULT true,
    CONSTRAINT cash_flow_categories_category_type_check CHECK (((category_type)::text = ANY (ARRAY[('operating'::character varying)::text, ('investing'::character varying)::text, ('financing'::character varying)::text])))
);


--
-- Name: cash_flow_categories_category_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cash_flow_categories_category_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cash_flow_categories_category_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.cash_flow_categories_category_id_seq OWNED BY public.cash_flow_categories.category_id;


--
-- Name: cash_flow_tracking; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cash_flow_tracking (
    flow_id integer NOT NULL,
    transaction_date date NOT NULL,
    flow_type character varying(30) NOT NULL,
    amount numeric(15,2) NOT NULL,
    source_reference character varying(200),
    destination_reference character varying(200),
    cash_purpose character varying(200),
    supporting_receipt_id integer,
    reconciled boolean DEFAULT false,
    reconciliation_notes text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: cash_flow_tracking_flow_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cash_flow_tracking_flow_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cash_flow_tracking_flow_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.cash_flow_tracking_flow_id_seq OWNED BY public.cash_flow_tracking.flow_id;


--
-- Name: categorization_rules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.categorization_rules (
    rule_id integer NOT NULL,
    category_code character varying(50),
    rule_type character varying(20),
    rule_pattern text NOT NULL,
    confidence_weight numeric(3,2) DEFAULT 0.5,
    is_active boolean DEFAULT true,
    priority integer DEFAULT 100,
    created_by character varying(100),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT categorization_rules_rule_type_check CHECK (((rule_type)::text = ANY (ARRAY[('keyword'::character varying)::text, ('merchant'::character varying)::text, ('amount'::character varying)::text, ('regex'::character varying)::text])))
);


--
-- Name: categorization_rules_rule_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.categorization_rules_rule_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: categorization_rules_rule_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.categorization_rules_rule_id_seq OWNED BY public.categorization_rules.rule_id;


--
-- Name: category_mappings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.category_mappings (
    mapping_id integer NOT NULL,
    old_category character varying(200) NOT NULL,
    new_account_code character varying(10),
    mapping_confidence character varying(20),
    notes text,
    requires_review boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: category_mappings_mapping_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.category_mappings_mapping_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: category_mappings_mapping_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.category_mappings_mapping_id_seq OWNED BY public.category_mappings.mapping_id;


--
-- Name: category_to_account_map; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.category_to_account_map (
    mapping_id integer NOT NULL,
    category_code character varying(50) NOT NULL,
    gl_account_code character varying(20) NOT NULL,
    priority integer DEFAULT 1,
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: category_to_account_map_mapping_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.category_to_account_map_mapping_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: category_to_account_map_mapping_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.category_to_account_map_mapping_id_seq OWNED BY public.category_to_account_map.mapping_id;


--
-- Name: charge_catalog; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.charge_catalog (
    catalog_id integer NOT NULL,
    charge_code character varying(50) NOT NULL,
    charge_name character varying(100) NOT NULL,
    charge_type character varying(50) NOT NULL,
    default_amount numeric(12,2) DEFAULT 0.00,
    is_taxable boolean DEFAULT true,
    is_active boolean DEFAULT true,
    display_order integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    calculation_type character varying(20) DEFAULT 'fixed'::character varying,
    percentage_rate numeric(5,2) DEFAULT 0.00,
    CONSTRAINT chk_calculation_type CHECK (((calculation_type)::text = ANY ((ARRAY['fixed'::character varying, 'percentage'::character varying, 'quantity'::character varying])::text[])))
);


--
-- Name: charge_catalog_catalog_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.charge_catalog_catalog_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: charge_catalog_catalog_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.charge_catalog_catalog_id_seq OWNED BY public.charge_catalog.catalog_id;


--
-- Name: charges; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.charges (
    charge_id integer NOT NULL,
    reserve_number character varying(6) NOT NULL,
    charge_type character varying(50) NOT NULL,
    amount numeric(12,2) NOT NULL,
    description character varying(255),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: charges_charge_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.charges_charge_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: charges_charge_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.charges_charge_id_seq OWNED BY public.charges.charge_id;


--
-- Name: charity_trade_charters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.charity_trade_charters (
    id integer NOT NULL,
    charter_id integer,
    reserve_number character varying(20) NOT NULL,
    classification character varying(100) NOT NULL,
    is_tax_locked boolean DEFAULT false,
    rate numeric(12,2),
    payments_total numeric(12,2),
    refunds_total numeric(12,2),
    deposit numeric(12,2),
    balance numeric(12,2),
    beverage_service character(1),
    payment_count integer,
    payment_methods text,
    booking_excerpt text,
    client_excerpt text,
    notes_excerpt text,
    source character varying(50) DEFAULT 'LMS_Promo_Trade'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    gratuity_amount numeric(12,2) DEFAULT 0,
    gst_base_amount numeric(12,2) DEFAULT 0,
    gst_amount_optimized numeric(12,2) DEFAULT 0,
    optimization_strategy text
);


--
-- Name: TABLE charity_trade_charters; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.charity_trade_charters IS 'Authoritative list of charity/trade/promo charters from LMS Pymt_Type field. Pre-2012 entries are tax-locked (CRA filing complete).';


--
-- Name: COLUMN charity_trade_charters.classification; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.charity_trade_charters.classification IS 'full_donation, partial_trade, partial_trade_extras, paid_full, donated_unredeemed_or_unpaid, mixed_or_uncertain';


--
-- Name: COLUMN charity_trade_charters.is_tax_locked; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.charity_trade_charters.is_tax_locked IS 'TRUE if charter_date < 2012-01-01. These entries are immutable (CRA tax filing complete).';


--
-- Name: COLUMN charity_trade_charters.gratuity_amount; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.charity_trade_charters.gratuity_amount IS 'GST-EXEMPT: Voluntary payment after service completion. Not subject to GST per CRA guidelines.';


--
-- Name: COLUMN charity_trade_charters.gst_base_amount; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.charity_trade_charters.gst_base_amount IS 'Taxable base after gratuity separation. payments_total - gratuity_amount = gst_base_amount.';


--
-- Name: COLUMN charity_trade_charters.gst_amount_optimized; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.charity_trade_charters.gst_amount_optimized IS 'Actual GST liability using optimized classification (gratuity exempt, donations exempt, etc).';


--
-- Name: COLUMN charity_trade_charters.optimization_strategy; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.charity_trade_charters.optimization_strategy IS 'Documentation of GST optimization approach for CRA audit trail.';


--
-- Name: charity_trade_charters_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.charity_trade_charters_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: charity_trade_charters_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.charity_trade_charters_id_seq OWNED BY public.charity_trade_charters.id;


--
-- Name: chart_of_accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chart_of_accounts (
    account_code character varying(10) NOT NULL,
    parent_account character varying(10),
    account_name character varying(200) NOT NULL,
    account_type character varying(50) NOT NULL,
    description text,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    qb_account_type character varying(50),
    account_level integer DEFAULT 0,
    is_header_account boolean DEFAULT false,
    normal_balance character varying(10),
    current_balance numeric(15,2) DEFAULT 0,
    bank_account_number text,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chart_of_accounts_normal_balance_check CHECK (((normal_balance)::text = ANY ((ARRAY['DEBIT'::character varying, 'CREDIT'::character varying])::text[])))
);


--
-- Name: chart_of_accounts_backup_2026; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chart_of_accounts_backup_2026 (
    account_code character varying(10),
    parent_account character varying(10),
    account_name character varying(200),
    account_type character varying(50),
    description text,
    is_active boolean,
    created_at timestamp without time zone,
    qb_account_type character varying(50),
    account_level integer,
    is_header_account boolean,
    normal_balance character varying(10),
    current_balance numeric(15,2),
    bank_account_number text,
    updated_at timestamp without time zone
);


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
-- Name: charter_beverages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.charter_beverages (
    id integer NOT NULL,
    charter_id integer NOT NULL,
    beverage_item_id integer,
    item_name character varying(255) NOT NULL,
    quantity integer DEFAULT 1 NOT NULL,
    unit_price_charged numeric(10,2) NOT NULL,
    unit_our_cost numeric(10,2) NOT NULL,
    deposit_per_unit numeric(10,2) DEFAULT 0.00,
    line_amount_charged numeric(10,2) GENERATED ALWAYS AS (((quantity)::numeric * unit_price_charged)) STORED,
    line_cost numeric(10,2) GENERATED ALWAYS AS (((quantity)::numeric * unit_our_cost)) STORED,
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_prices CHECK (((unit_price_charged >= (0)::numeric) AND (unit_our_cost >= (0)::numeric))),
    CONSTRAINT valid_quantities CHECK ((quantity > 0))
);


--
-- Name: TABLE charter_beverages; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.charter_beverages IS 'Snapshot of beverages charged to charter. Prices are locked at time of charter creation.
Editing quantities/prices here does NOT affect master beverage_products table.
Used for historical accuracy, guest disputes, and profit margin tracking.';


--
-- Name: COLUMN charter_beverages.unit_price_charged; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.charter_beverages.unit_price_charged IS 'What we charged the GUEST for this item (includes GST). LOCKED at snapshot time.';


--
-- Name: COLUMN charter_beverages.unit_our_cost; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.charter_beverages.unit_our_cost IS 'What Arrow Limousine PAID the supplier (wholesale cost). LOCKED at snapshot time.';


--
-- Name: COLUMN charter_beverages.notes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.charter_beverages.notes IS 'Audit trail: "Price negotiated down $5.49→$4.99", "Guest requested substitution", etc.';


--
-- Name: charter_beverages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.charter_beverages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: charter_beverages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.charter_beverages_id_seq OWNED BY public.charter_beverages.id;


--
-- Name: charter_charges; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.charter_charges (
    charge_id integer NOT NULL,
    account_number character varying(50),
    reserve_number character varying(50),
    charter_id integer,
    amount numeric(12,2),
    rate numeric(10,2),
    description text,
    sequence integer,
    closed boolean DEFAULT false,
    frozen boolean DEFAULT false,
    tag character varying(50),
    note text,
    last_updated timestamp without time zone,
    last_updated_by character varying(100),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    charge_type character varying(50) DEFAULT 'other'::character varying NOT NULL,
    category character varying(100) DEFAULT 'unspecified'::character varying,
    gratuity_type character varying(20),
    gst_amount numeric(12,2),
    tax_rate numeric(5,4),
    CONSTRAINT amount_rounded_penny CHECK ((amount = round(amount, 2)))
);


--
-- Name: charter_charges_charge_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.charter_charges_charge_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: charter_charges_charge_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.charter_charges_charge_id_seq OWNED BY public.charter_charges.charge_id;


--
-- Name: charter_credit_ledger; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.charter_credit_ledger (
    credit_id integer NOT NULL,
    source_reserve_number character varying(50) NOT NULL,
    source_charter_id integer,
    client_id integer,
    credit_amount numeric(12,2) NOT NULL,
    credit_reason character varying(100) NOT NULL,
    remaining_balance numeric(12,2) NOT NULL,
    created_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    applied_date timestamp without time zone,
    applied_to_reserve_number character varying(50),
    applied_to_charter_id integer,
    notes text,
    created_by character varying(100) DEFAULT 'system'::character varying,
    CONSTRAINT charter_credit_ledger_check CHECK (((remaining_balance >= (0)::numeric) AND (remaining_balance <= credit_amount))),
    CONSTRAINT charter_credit_ledger_credit_amount_check CHECK ((credit_amount > (0)::numeric)),
    CONSTRAINT valid_balance CHECK ((remaining_balance <= credit_amount))
);


--
-- Name: TABLE charter_credit_ledger; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.charter_credit_ledger IS 'Tracks client credits from overpayments and cancelled charter deposits';


--
-- Name: COLUMN charter_credit_ledger.credit_reason; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.charter_credit_ledger.credit_reason IS 'Values: UNIFORM_INSTALLMENT, CANCELLED_RETENTION, ETR_OVERPAY, MULTI_CHARTER_PREPAY, MIXED_OVERPAY';


--
-- Name: COLUMN charter_credit_ledger.remaining_balance; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.charter_credit_ledger.remaining_balance IS 'Available credit balance (decreases as applied to future charters)';


--
-- Name: COLUMN charter_credit_ledger.applied_date; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.charter_credit_ledger.applied_date IS 'When credit was fully exhausted or applied to another charter';


--
-- Name: charter_credit_ledger_credit_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.charter_credit_ledger_credit_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: charter_credit_ledger_credit_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.charter_credit_ledger_credit_id_seq OWNED BY public.charter_credit_ledger.credit_id;


--
-- Name: charter_gst_details_2010_2012; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.charter_gst_details_2010_2012 (
    id integer NOT NULL,
    charter_id integer,
    reserve_number character varying(50) NOT NULL,
    reserve_date date,
    service_fee numeric(12,2),
    travel_time numeric(12,2),
    extra_stops numeric(12,2),
    gratuity numeric(12,2),
    fuel_surcharge numeric(12,2),
    beverage_charge numeric(12,2),
    other_charge numeric(12,2),
    other_charge_2 numeric(12,2),
    extra_charge numeric(12,2),
    gst_amount numeric(12,2),
    gst_taxable numeric(12,2),
    total_amount numeric(12,2),
    total_bill numeric(12,2),
    reduced_revenue numeric(12,2),
    adjusted_delivery numeric(12,2),
    reconcil_e_to_total numeric(12,2),
    difference_e_to_total numeric(12,2),
    diff_total numeric(12,2),
    diff_gst numeric(12,2),
    source_sheet character varying(100),
    source_file character varying(500),
    source_hash character varying(64),
    imported_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: charter_gst_details_2010_2012_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.charter_gst_details_2010_2012_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: charter_gst_details_2010_2012_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.charter_gst_details_2010_2012_id_seq OWNED BY public.charter_gst_details_2010_2012.id;


--
-- Name: charter_incidents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.charter_incidents (
    incident_id integer NOT NULL,
    charter_id integer,
    reserve_number character varying(50),
    incident_type character varying(50),
    incident_severity character varying(20),
    occurred_at timestamp with time zone,
    description text,
    poor_service_reimbursement numeric(12,2),
    gratuity_impact boolean DEFAULT false,
    requires_manager_review boolean DEFAULT false,
    manager_reviewed_by character varying(100),
    manager_reviewed_at timestamp with time zone,
    resolution_notes text,
    created_at timestamp with time zone DEFAULT now(),
    created_by character varying(100)
);


--
-- Name: charter_incidents_incident_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.charter_incidents_incident_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: charter_incidents_incident_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.charter_incidents_incident_id_seq OWNED BY public.charter_incidents.incident_id;


--
-- Name: charter_payments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.charter_payments (
    id integer NOT NULL,
    payment_id integer,
    charter_id character varying(20),
    client_name character varying(255),
    charter_date date,
    amount numeric(10,2),
    payment_date date,
    payment_method character varying(50),
    payment_key character varying(50),
    source character varying(100),
    imported_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: charter_payments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.charter_payments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: charter_payments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.charter_payments_id_seq OWNED BY public.charter_payments.id;


--
-- Name: charter_receipts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.charter_receipts (
    receipt_id integer NOT NULL,
    charter_id integer,
    reserve_number character varying(50),
    vehicle_id integer,
    receipt_date date,
    vendor character varying(255),
    category character varying(50),
    amount numeric(12,2),
    payment_method character varying(20),
    receipt_image_url character varying(500),
    banking_transaction_id integer,
    status character varying(20),
    notes text,
    created_by character varying(100),
    created_at timestamp with time zone DEFAULT now(),
    matched_by character varying(100),
    matched_at timestamp with time zone
);


--
-- Name: charter_receipts_receipt_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.charter_receipts_receipt_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: charter_receipts_receipt_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.charter_receipts_receipt_id_seq OWNED BY public.charter_receipts.receipt_id;


--
-- Name: charter_reconciliation_status; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.charter_reconciliation_status (
    charter_id integer NOT NULL,
    reserve_number character varying(50),
    reconciliation_status character varying(50),
    calculated_balance numeric(10,2),
    overpaid_amount numeric(10,2),
    credit_carried_forward boolean DEFAULT false,
    credit_applied_to_charter integer,
    locked_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    notes text
);


--
-- Name: charter_refunds; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.charter_refunds (
    id integer NOT NULL,
    refund_date date NOT NULL,
    amount numeric(12,2) NOT NULL,
    reserve_number character varying(20),
    charter_id integer,
    payment_id integer,
    square_payment_id character varying(100),
    description text,
    customer text,
    source_file text,
    source_row integer,
    reference text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    payment_method character varying(50)
);


--
-- Name: charter_refund_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.charter_refund_summary AS
 SELECT c.reserve_number,
    c.charter_id,
    COALESCE(sum(cr.amount), (0)::numeric) AS total_refunded,
    count(*) AS refund_count
   FROM (public.charters c
     LEFT JOIN public.charter_refunds cr ON (((cr.reserve_number)::text = (c.reserve_number)::text)))
  GROUP BY c.reserve_number, c.charter_id;


--
-- Name: charter_refunds_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.charter_refunds_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: charter_refunds_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.charter_refunds_id_seq OWNED BY public.charter_refunds.id;


--
-- Name: charter_routes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.charter_routes (
    route_id integer NOT NULL,
    charter_id integer NOT NULL,
    route_sequence integer DEFAULT 1 NOT NULL,
    pickup_location text,
    pickup_time time without time zone,
    dropoff_location text,
    dropoff_time time without time zone,
    estimated_duration_minutes integer,
    actual_duration_minutes integer,
    estimated_distance_km numeric(10,2),
    actual_distance_km numeric(10,2),
    route_price numeric(10,2),
    route_notes text,
    route_status character varying(50) DEFAULT 'pending'::character varying,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    event_type_code character varying,
    CONSTRAINT route_sequence_positive CHECK ((route_sequence > 0))
);


--
-- Name: TABLE charter_routes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.charter_routes IS 'Individual route segments for each charter booking';


--
-- Name: COLUMN charter_routes.route_sequence; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.charter_routes.route_sequence IS 'Order of routes within a charter (1, 2, 3, ...)';


--
-- Name: COLUMN charter_routes.estimated_duration_minutes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.charter_routes.estimated_duration_minutes IS 'Calculated time for this route segment in minutes';


--
-- Name: COLUMN charter_routes.actual_duration_minutes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.charter_routes.actual_duration_minutes IS 'Actual time taken for this route segment';


--
-- Name: COLUMN charter_routes.route_status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.charter_routes.route_status IS 'Status: pending, in_progress, completed, cancelled';


--
-- Name: CONSTRAINT route_sequence_positive ON charter_routes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON CONSTRAINT route_sequence_positive ON public.charter_routes IS 'Ensures route_sequence is always a positive integer (1, 2, 3, ...)';


--
-- Name: charter_routes_route_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.charter_routes_route_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: charter_routes_route_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.charter_routes_route_id_seq OWNED BY public.charter_routes.route_id;


--
-- Name: charter_run_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.charter_run_types (
    run_type_id integer NOT NULL,
    run_type_name character varying(100) NOT NULL,
    display_order integer DEFAULT 100,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: charter_run_types_run_type_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.charter_run_types_run_type_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: charter_run_types_run_type_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.charter_run_types_run_type_id_seq OWNED BY public.charter_run_types.run_type_id;


--
-- Name: charter_time_updates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.charter_time_updates (
    update_id integer NOT NULL,
    charter_id integer,
    driver_id integer,
    update_type character varying(50),
    old_time timestamp without time zone,
    new_time timestamp without time zone,
    reason text,
    location_lat numeric(10,8),
    location_lon numeric(11,8),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: charter_time_updates_update_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.charter_time_updates_update_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: charter_time_updates_update_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.charter_time_updates_update_id_seq OWNED BY public.charter_time_updates.update_id;


--
-- Name: charter_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.charter_types (
    charter_type_id integer NOT NULL,
    type_code character varying(50) NOT NULL,
    type_name character varying(100) NOT NULL,
    description text,
    requires_hours boolean DEFAULT true,
    is_active boolean DEFAULT true,
    display_order integer DEFAULT 0
);


--
-- Name: charter_types_charter_type_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.charter_types_charter_type_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: charter_types_charter_type_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.charter_types_charter_type_id_seq OWNED BY public.charter_types.charter_type_id;


--
-- Name: charters_charter_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.charters_charter_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: charters_charter_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.charters_charter_id_seq OWNED BY public.charters.charter_id;


--
-- Name: charters_routing_times; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.charters_routing_times (
    routing_time_id integer NOT NULL,
    charter_id integer,
    reserve_number character varying(50),
    route_sequence integer,
    leg_description text,
    dispatcher_expected_time time without time zone,
    dispatcher_notes text,
    driver_actual_time time without time zone,
    driver_notes character varying(255),
    leg_status character varying(20),
    recorded_by character varying(100),
    recorded_at timestamp with time zone
);


--
-- Name: charters_routing_times_routing_time_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.charters_routing_times_routing_time_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: charters_routing_times_routing_time_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.charters_routing_times_routing_time_id_seq OWNED BY public.charters_routing_times.routing_time_id;


--
-- Name: chauffeur_float_tracking_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.chauffeur_float_tracking_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: chauffeur_float_tracking_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.chauffeur_float_tracking_id_seq OWNED BY public.chauffeur_float_tracking.id;


--
-- Name: chauffeur_pay_entries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chauffeur_pay_entries (
    entry_id integer NOT NULL,
    chauffeur_id integer,
    chauffeur_name character varying(255) NOT NULL,
    pay_date date NOT NULL,
    hours_worked numeric(5,2),
    hourly_rate numeric(8,2),
    total_pay numeric(10,2),
    charter_reference character varying(50),
    status character varying(50) DEFAULT 'pending'::character varying,
    notes text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    created_by integer
);


--
-- Name: TABLE chauffeur_pay_entries; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.chauffeur_pay_entries IS 'Accounting records for chauffeur pay - separate from operational charter data';


--
-- Name: chauffeur_pay_entries_entry_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.chauffeur_pay_entries_entry_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: chauffeur_pay_entries_entry_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.chauffeur_pay_entries_entry_id_seq OWNED BY public.chauffeur_pay_entries.entry_id;


--
-- Name: cheque_register; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cheque_register (
    id integer NOT NULL,
    cheque_number character varying(50) NOT NULL,
    cheque_date date,
    cleared_date date,
    payee character varying(200),
    amount numeric(12,2) NOT NULL,
    memo text,
    banking_transaction_id integer,
    status character varying(50) DEFAULT 'cleared'::character varying,
    account_number character varying(50),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: cheque_register_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cheque_register_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cheque_register_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.cheque_register_id_seq OWNED BY public.cheque_register.id;


--
-- Name: cibc_accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cibc_accounts (
    account_id integer NOT NULL,
    account_number character varying(20) NOT NULL,
    account_name character varying(100) NOT NULL,
    account_type character varying(50) NOT NULL,
    last4 character varying(4) NOT NULL,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: cibc_accounts_account_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cibc_accounts_account_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cibc_accounts_account_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.cibc_accounts_account_id_seq OWNED BY public.cibc_accounts.account_id;


--
-- Name: cibc_auto_categorization_rules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cibc_auto_categorization_rules (
    rule_id integer NOT NULL,
    card_id integer,
    merchant_pattern character varying(200),
    description_pattern character varying(200),
    amount_min numeric(12,2),
    amount_max numeric(12,2),
    expense_category character varying(100) NOT NULL,
    business_purpose character varying(200),
    auto_approve boolean DEFAULT false,
    rule_priority integer DEFAULT 100,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: cibc_auto_categorization_rules_rule_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cibc_auto_categorization_rules_rule_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cibc_auto_categorization_rules_rule_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.cibc_auto_categorization_rules_rule_id_seq OWNED BY public.cibc_auto_categorization_rules.rule_id;


--
-- Name: cibc_business_cards; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cibc_business_cards (
    card_id integer NOT NULL,
    card_name character varying(100) NOT NULL,
    card_type character varying(50) NOT NULL,
    card_number_last4 character varying(4),
    credit_limit numeric(12,2) NOT NULL,
    current_balance numeric(12,2) DEFAULT 0,
    available_credit numeric(12,2),
    statement_date date,
    payment_due_date date,
    minimum_payment numeric(12,2) DEFAULT 0,
    owner_equity_account_id integer,
    auto_categorization_enabled boolean DEFAULT true,
    default_expense_category character varying(100) DEFAULT 'Business Expenses'::character varying,
    banking_sync_enabled boolean DEFAULT true,
    last_banking_sync timestamp without time zone,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: TABLE cibc_business_cards; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.cibc_business_cards IS 'Paul Heffner CIBC Business Cards: Business ($25k), Personal ($15k), Salary ($10k)';


--
-- Name: cibc_business_cards_card_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cibc_business_cards_card_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cibc_business_cards_card_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.cibc_business_cards_card_id_seq OWNED BY public.cibc_business_cards.card_id;


--
-- Name: cibc_card_transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cibc_card_transactions (
    transaction_id integer NOT NULL,
    card_id integer,
    transaction_date date NOT NULL,
    posting_date date,
    description text NOT NULL,
    amount numeric(12,2) NOT NULL,
    transaction_type character varying(50) DEFAULT 'Purchase'::character varying,
    merchant_name character varying(200),
    merchant_category character varying(100),
    expense_category character varying(100),
    business_purpose text,
    auto_categorized boolean DEFAULT false,
    manual_review_required boolean DEFAULT false,
    banking_transaction_id integer,
    reconciled boolean DEFAULT false,
    reconciled_at timestamp without time zone,
    receipt_required boolean DEFAULT false,
    receipt_uploaded boolean DEFAULT false,
    receipt_path character varying(500),
    gst_applicable boolean DEFAULT true,
    gst_amount numeric(12,2) DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: TABLE cibc_card_transactions; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.cibc_card_transactions IS 'CIBC card transactions with auto-categorization and banking reconciliation';


--
-- Name: cibc_card_transactions_transaction_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cibc_card_transactions_transaction_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cibc_card_transactions_transaction_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.cibc_card_transactions_transaction_id_seq OWNED BY public.cibc_card_transactions.transaction_id;


--
-- Name: clients; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clients (
    client_id integer NOT NULL,
    account_number character varying(50) NOT NULL,
    company_name character varying(255),
    primary_phone character varying(50),
    email character varying(255),
    address_line1 character varying(255),
    city character varying(100),
    state character varying(50),
    zip_code character varying(20),
    balance numeric(12,2) DEFAULT 0,
    credit_limit numeric(12,2) DEFAULT 0,
    discount_percentage numeric(5,2) DEFAULT 0,
    discount_flat numeric(10,2) DEFAULT 0,
    gratuity_percentage numeric(5,2) DEFAULT 18.00,
    interest_rate numeric(5,4) DEFAULT 0,
    grace_days integer DEFAULT 0,
    is_inactive boolean DEFAULT false,
    status character varying(20) DEFAULT 'active'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    billing_no character varying,
    is_gst_exempt boolean DEFAULT false,
    exemption_certificate_number character varying(50),
    exemption_certificate_expiry date,
    exemption_type character varying(50),
    exemption_notes text,
    bad_debt_status character varying(20) DEFAULT 'current'::character varying,
    collection_attempts_count integer DEFAULT 0,
    last_collection_date date,
    first_overdue_date date,
    writeoff_date date,
    writeoff_amount numeric(10,2) DEFAULT 0.00,
    bankruptcy_status character varying(20) DEFAULT 'none'::character varying,
    collection_notes text,
    bad_debt_reason character varying(100) DEFAULT NULL::character varying,
    recovery_probability character varying(10) DEFAULT 'high'::character varying,
    fraud_case_id integer,
    client_name text,
    lms_customer_number text,
    qb_customer_id character varying(50),
    qb_customer_type character varying(50),
    payment_terms character varying(50) DEFAULT 'Net 30'::character varying,
    tax_code character varying(20),
    billing_rate_level character varying(50),
    sales_tax_code character varying(20),
    province character varying(50),
    country character varying(50) DEFAULT 'Canada'::character varying,
    warning_flag boolean DEFAULT false,
    billing_address character varying(500) DEFAULT ''::character varying,
    contact_info character varying(200) DEFAULT ''::character varying,
    notes text DEFAULT ''::text,
    name character varying,
    phone character varying,
    address text,
    first_name character varying(100),
    last_name character varying(100),
    cell_phone character varying(20),
    home_phone character varying(20),
    work_phone character varying(20),
    fax_phone character varying(20),
    full_name_search text,
    corporate_parent_id integer DEFAULT 0,
    corporate_role character varying,
    gst_exempt boolean DEFAULT false
);


--
-- Name: COLUMN clients.qb_customer_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.clients.qb_customer_id IS 'External QuickBooks customer ID for sync';


--
-- Name: COLUMN clients.qb_customer_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.clients.qb_customer_type IS 'Customer classification (Commercial, Residential, Wholesale, etc.)';


--
-- Name: COLUMN clients.payment_terms; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.clients.payment_terms IS 'Payment terms (Net 30, Net 15, Due on Receipt, etc.)';


--
-- Name: client_aging_report; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.client_aging_report AS
 SELECT client_id,
    account_number,
    company_name,
    balance,
    bad_debt_status,
    collection_attempts_count,
    last_collection_date,
    bankruptcy_status,
    recovery_probability,
        CASE
            WHEN (balance <= (0)::numeric) THEN 0
            WHEN (first_overdue_date IS NULL) THEN (CURRENT_DATE - (created_at)::date)
            ELSE (CURRENT_DATE - first_overdue_date)
        END AS days_outstanding,
        CASE
            WHEN (balance <= (0)::numeric) THEN 'Paid'::text
            WHEN ((CURRENT_DATE - COALESCE(first_overdue_date, (created_at)::date)) <= 30) THEN '0-30 days'::text
            WHEN ((CURRENT_DATE - COALESCE(first_overdue_date, (created_at)::date)) <= 60) THEN '31-60 days'::text
            WHEN ((CURRENT_DATE - COALESCE(first_overdue_date, (created_at)::date)) <= 90) THEN '61-90 days'::text
            WHEN ((CURRENT_DATE - COALESCE(first_overdue_date, (created_at)::date)) <= 120) THEN '91-120 days'::text
            ELSE '>120 days'::text
        END AS aging_bucket,
        CASE
            WHEN (balance <= (0)::numeric) THEN 'Current'::text
            WHEN ((CURRENT_DATE - COALESCE(first_overdue_date, (created_at)::date)) <= 30) THEN 'Current'::text
            WHEN ((CURRENT_DATE - COALESCE(first_overdue_date, (created_at)::date)) <= 60) THEN 'Follow-up'::text
            WHEN ((CURRENT_DATE - COALESCE(first_overdue_date, (created_at)::date)) <= 90) THEN 'Collection'::text
            WHEN ((CURRENT_DATE - COALESCE(first_overdue_date, (created_at)::date)) <= 120) THEN 'Serious'::text
            ELSE 'Write-off Risk'::text
        END AS risk_level
   FROM public.clients cl
  WHERE (balance > (0)::numeric)
  ORDER BY
        CASE
            WHEN (balance <= (0)::numeric) THEN 0
            WHEN (first_overdue_date IS NULL) THEN (CURRENT_DATE - (created_at)::date)
            ELSE (CURRENT_DATE - first_overdue_date)
        END DESC, balance DESC;


--
-- Name: clients_client_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.clients_client_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: clients_client_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.clients_client_id_seq OWNED BY public.clients.client_id;


--
-- Name: comprehensive_payment_reconciliation; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.comprehensive_payment_reconciliation (
    id integer NOT NULL,
    payment_source character varying(50) NOT NULL,
    payment_date date,
    amount numeric(10,2),
    sender_name character varying(200),
    sender_email character varying(200),
    recipient_name character varying(200),
    description text,
    reference_number character varying(100),
    charter_id integer,
    client_id integer,
    is_loan boolean DEFAULT false,
    loan_type character varying(50),
    reconciliation_status character varying(50) DEFAULT 'unmatched'::character varying,
    matched_to_payment_id integer,
    raw_data jsonb,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: comprehensive_payment_reconciliation_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.comprehensive_payment_reconciliation_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: comprehensive_payment_reconciliation_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.comprehensive_payment_reconciliation_id_seq OWNED BY public.comprehensive_payment_reconciliation.id;


--
-- Name: cra_vehicle_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cra_vehicle_events (
    event_id integer NOT NULL,
    vehicle_id integer,
    event_type character varying(50),
    event_date date NOT NULL,
    police_report_number character varying(50),
    insurance_claim_number character varying(50),
    reported_to_cra boolean DEFAULT false,
    report_date date,
    cra_reference_number character varying(50),
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: cra_vehicle_events_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cra_vehicle_events_event_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cra_vehicle_events_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.cra_vehicle_events_event_id_seq OWNED BY public.cra_vehicle_events.event_id;


--
-- Name: credit_lines_backup_20260123_233917; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.credit_lines_backup_20260123_233917 (
    id integer,
    account_id character varying(50),
    account_name character varying(100),
    bank_name character varying(50),
    account_number character varying(20),
    credit_limit numeric(10,2),
    current_balance numeric(10,2),
    available_credit numeric(10,2),
    utilization numeric(5,2),
    interest_rate numeric(5,2),
    business_percentage integer,
    payment_due_date date,
    minimum_payment numeric(10,2),
    monthly_interest numeric(10,2),
    ytd_business_interest numeric(10,2),
    is_active boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: customer_comms_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.customer_comms_log (
    comm_id integer NOT NULL,
    charter_id integer,
    reserve_number character varying(50),
    comm_type character varying(20),
    sent_at timestamp with time zone,
    sent_by character varying(100),
    subject character varying(255),
    message_summary text,
    delivery_status character varying(20),
    customer_response text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: customer_comms_log_comm_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.customer_comms_log_comm_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: customer_comms_log_comm_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.customer_comms_log_comm_id_seq OWNED BY public.customer_comms_log.comm_id;


--
-- Name: customer_feedback; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.customer_feedback (
    feedback_id integer NOT NULL,
    charter_id integer,
    reserve_number character varying(50),
    feedback_type character varying(20),
    feedback_source character varying(20),
    feedback_text text,
    rating integer,
    incident_id integer,
    requires_follow_up boolean DEFAULT false,
    follow_up_completed boolean DEFAULT false,
    follow_up_notes text,
    submitted_at timestamp with time zone DEFAULT now(),
    submitted_by character varying(100),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: customer_feedback_feedback_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.customer_feedback_feedback_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: customer_feedback_feedback_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.customer_feedback_feedback_id_seq OWNED BY public.customer_feedback.feedback_id;


--
-- Name: customer_name_mapping; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.customer_name_mapping (
    id integer NOT NULL,
    alms_client_id integer,
    alms_account_number character varying(50),
    alms_company_name text,
    lms_account_no character varying(20),
    lms_primary_name text,
    lms_company_name text,
    match_type character varying(50),
    match_confidence numeric(3,2),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: customer_name_mapping_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.customer_name_mapping_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: customer_name_mapping_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.customer_name_mapping_id_seq OWNED BY public.customer_name_mapping.id;


--
-- Name: customer_name_resolver; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.customer_name_resolver AS
 SELECT c.client_id AS alms_client_id,
    c.account_number AS alms_account,
    COALESCE(concat(c.first_name, ' ', c.last_name), (c.company_name)::text, c.client_name, (c.name)::text, 'Unknown'::text) AS resolved_name,
    c.email AS resolved_email,
    COALESCE(c.cell_phone, c.work_phone, c.home_phone, c.phone, c.primary_phone) AS resolved_phone,
    c.full_name_search,
    cnm.match_type,
    cnm.match_confidence
   FROM (public.clients c
     LEFT JOIN public.customer_name_mapping cnm ON ((c.client_id = cnm.alms_client_id)));


--
-- Name: cvip_compliance_alerts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cvip_compliance_alerts (
    alert_id integer NOT NULL,
    vehicle_id integer,
    alert_type character varying(50),
    alert_date date,
    due_date date,
    days_until_due integer,
    severity character varying(20),
    resolved boolean DEFAULT false,
    resolved_date date,
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: cvip_compliance_alerts_alert_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cvip_compliance_alerts_alert_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cvip_compliance_alerts_alert_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.cvip_compliance_alerts_alert_id_seq OWNED BY public.cvip_compliance_alerts.alert_id;


--
-- Name: cvip_defects; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cvip_defects (
    defect_id integer NOT NULL,
    inspection_id integer,
    defect_code character varying(20),
    defect_description text,
    severity character varying(20),
    remediation_required boolean,
    remediation_deadline date,
    remediated_date date,
    remediation_notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: cvip_defects_defect_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cvip_defects_defect_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cvip_defects_defect_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.cvip_defects_defect_id_seq OWNED BY public.cvip_defects.defect_id;


--
-- Name: cvip_inspections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cvip_inspections (
    inspection_id integer NOT NULL,
    vehicle_id integer,
    inspection_date date NOT NULL,
    inspection_number character varying(50),
    inspection_location character varying(200),
    inspector_name character varying(100),
    inspection_station character varying(200),
    passed boolean,
    inspection_result character varying(50),
    defect_count integer DEFAULT 0,
    critical_defects integer DEFAULT 0,
    valid_until date,
    is_current boolean DEFAULT true,
    renewal_due_date date,
    days_remaining integer,
    defects_json text,
    cost numeric(10,2),
    receipt_id integer,
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: cvip_inspections_inspection_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cvip_inspections_inspection_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cvip_inspections_inspection_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.cvip_inspections_inspection_id_seq OWNED BY public.cvip_inspections.inspection_id;


--
-- Name: david_account_tracking; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.david_account_tracking (
    id integer NOT NULL,
    transaction_date date,
    description text,
    debit_amount numeric(12,2),
    credit_amount numeric(12,2),
    running_balance numeric(12,2),
    source_reference character varying(200),
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: david_account_tracking_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.david_account_tracking_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: david_account_tracking_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.david_account_tracking_id_seq OWNED BY public.david_account_tracking.id;


--
-- Name: david_richard_vehicle_loans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.david_richard_vehicle_loans (
    id integer NOT NULL,
    payment_date date NOT NULL,
    amount numeric(10,2) NOT NULL,
    description text,
    loan_type character varying(100) DEFAULT 'Vehicle Loan Payment'::character varying,
    source_file character varying(500),
    raw_text text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: david_richard_vehicle_loans_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.david_richard_vehicle_loans_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: david_richard_vehicle_loans_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.david_richard_vehicle_loans_id_seq OWNED BY public.david_richard_vehicle_loans.id;


--
-- Name: deferred_wage_accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.deferred_wage_accounts (
    account_id integer NOT NULL,
    employee_id integer NOT NULL,
    account_name character varying(100),
    account_type character varying(30) DEFAULT 'employee_deferred'::character varying,
    account_status character varying(20) DEFAULT 'active'::character varying,
    current_balance numeric(12,2) DEFAULT 0,
    ytd_deferred_amount numeric(12,2) DEFAULT 0,
    ytd_paid_amount numeric(12,2) DEFAULT 0,
    lifetime_deferred numeric(12,2) DEFAULT 0,
    lifetime_paid numeric(12,2) DEFAULT 0,
    interest_rate numeric(5,4) DEFAULT 0,
    last_interest_calculation date,
    accumulated_interest numeric(12,2) DEFAULT 0,
    max_deferred_amount numeric(12,2),
    minimum_payment_frequency character varying(20) DEFAULT 'monthly'::character varying,
    auto_payment_enabled boolean DEFAULT false,
    auto_payment_amount numeric(12,2),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    created_by integer
);


--
-- Name: TABLE deferred_wage_accounts; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.deferred_wage_accounts IS 'Employee deferred wage accounts for cash flow management';


--
-- Name: COLUMN deferred_wage_accounts.current_balance; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.deferred_wage_accounts.current_balance IS 'Current amount owed to employee (can grow with interest)';


--
-- Name: deferred_wage_accounts_account_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.deferred_wage_accounts_account_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: deferred_wage_accounts_account_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.deferred_wage_accounts_account_id_seq OWNED BY public.deferred_wage_accounts.account_id;


--
-- Name: deferred_wage_transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.deferred_wage_transactions (
    transaction_id integer NOT NULL,
    account_id integer NOT NULL,
    employee_id integer NOT NULL,
    transaction_date date NOT NULL,
    transaction_type character varying(30) NOT NULL,
    description text,
    gross_amount numeric(12,2) NOT NULL,
    deferred_amount numeric(12,2),
    paid_amount numeric(12,2),
    tax_withholdings numeric(12,2) DEFAULT 0,
    net_payment numeric(12,2),
    payroll_id integer,
    charter_id integer,
    expense_id integer,
    balance_before numeric(12,2),
    balance_after numeric(12,2),
    processed_by integer,
    processing_notes text,
    approved_by integer,
    approval_date timestamp without time zone,
    journal_entry_id integer,
    qb_transaction_id character varying(50),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: TABLE deferred_wage_transactions; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.deferred_wage_transactions IS 'Detailed log of all deferred wage activities';


--
-- Name: deferred_wage_transactions_transaction_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.deferred_wage_transactions_transaction_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: deferred_wage_transactions_transaction_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.deferred_wage_transactions_transaction_id_seq OWNED BY public.deferred_wage_transactions.transaction_id;


--
-- Name: deposit_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.deposit_records (
    id bigint NOT NULL,
    deposit_key character varying(30),
    transaction_number character varying(100),
    hash_pattern character varying(30),
    amount numeric(15,2) NOT NULL,
    deposit_date date NOT NULL,
    payment_type character varying(50),
    matched boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: deposit_records_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.deposit_records_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: deposit_records_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.deposit_records_id_seq OWNED BY public.deposit_records.id;


--
-- Name: direct_tips_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.direct_tips_history (
    tip_id integer NOT NULL,
    charter_id integer,
    reserve_number character varying(50),
    driver_id character varying(50),
    employee_id integer,
    tip_date date NOT NULL,
    tip_amount numeric(12,2) NOT NULL,
    payment_method character varying(50),
    customer_name character varying(200),
    is_direct_tip boolean DEFAULT true,
    not_on_t4 boolean DEFAULT true,
    paid_by_customer_directly boolean DEFAULT true,
    not_employer_revenue boolean DEFAULT true,
    tax_year integer,
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    created_by character varying(100) DEFAULT 'direct_tips_migration'::character varying,
    source_system character varying(50) DEFAULT 'pre-2013_charter_migration'::character varying,
    documentation text DEFAULT 'Pre-2013 gratuity treated as direct tips per CRA guidelines. Not included in T4 employment income. Employee responsible for reporting on personal tax return.'::text
);


--
-- Name: direct_tips_history_tip_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.direct_tips_history_tip_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: direct_tips_history_tip_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.direct_tips_history_tip_id_seq OWNED BY public.direct_tips_history.tip_id;


--
-- Name: dispatch_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dispatch_events (
    dispatch_event_id integer NOT NULL,
    reserve_number character varying(50) NOT NULL,
    event_type character varying(50) NOT NULL,
    old_value jsonb,
    new_value jsonb,
    created_at timestamp with time zone DEFAULT now(),
    created_by character varying(100)
);


--
-- Name: dispatch_events_dispatch_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.dispatch_events_dispatch_event_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dispatch_events_dispatch_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.dispatch_events_dispatch_event_id_seq OWNED BY public.dispatch_events.dispatch_event_id;


--
-- Name: document_categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_categories (
    category_id integer NOT NULL,
    category_name character varying(100) NOT NULL,
    description text,
    is_required boolean DEFAULT false,
    red_deer_bylaw_required boolean DEFAULT false,
    expiry_tracking boolean DEFAULT false,
    renewal_days_notice integer DEFAULT 30,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: document_categories_category_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.document_categories_category_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: document_categories_category_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.document_categories_category_id_seq OWNED BY public.document_categories.category_id;


--
-- Name: documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documents (
    document_id integer NOT NULL,
    title text NOT NULL,
    category text NOT NULL,
    file_path text NOT NULL,
    file_size bigint,
    tags text,
    upload_date timestamp without time zone DEFAULT now()
);


--
-- Name: documents_document_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.documents_document_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: documents_document_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.documents_document_id_seq OWNED BY public.documents.document_id;


--
-- Name: donations_free_rides; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.donations_free_rides (
    id integer NOT NULL,
    charter_id integer,
    service_date date,
    service_type character varying(100),
    beneficiary character varying(200),
    estimated_value numeric(12,2),
    tax_receipt_issued boolean DEFAULT false,
    tax_receipt_number character varying(100),
    charity_registration character varying(100),
    business_expense boolean DEFAULT false,
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: donations_free_rides_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.donations_free_rides_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: donations_free_rides_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.donations_free_rides_id_seq OWNED BY public.donations_free_rides.id;


--
-- Name: driver_alias_map; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.driver_alias_map (
    driver_key text NOT NULL,
    canonical_name text NOT NULL,
    sources text[] DEFAULT '{}'::text[]
);


--
-- Name: driver_app_actions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.driver_app_actions (
    action_id integer NOT NULL,
    driver_id integer,
    charter_id integer,
    action_type character varying(50),
    action_timestamp timestamp without time zone NOT NULL,
    action_data jsonb,
    synced boolean DEFAULT false,
    synced_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: driver_app_actions_action_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.driver_app_actions_action_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: driver_app_actions_action_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.driver_app_actions_action_id_seq OWNED BY public.driver_app_actions.action_id;


--
-- Name: driver_app_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.driver_app_sessions (
    session_id integer NOT NULL,
    driver_id integer,
    device_id character varying(100),
    device_type character varying(50),
    device_name character varying(100),
    app_version character varying(20),
    os_version character varying(20),
    last_login timestamp without time zone,
    login_count integer DEFAULT 0,
    is_active boolean DEFAULT true,
    push_token character varying(255),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: driver_app_sessions_session_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.driver_app_sessions_session_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: driver_app_sessions_session_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.driver_app_sessions_session_id_seq OWNED BY public.driver_app_sessions.session_id;


--
-- Name: driver_comms_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.driver_comms_log (
    comm_id integer NOT NULL,
    reserve_number character varying(50),
    employee_id integer,
    method character varying(20),
    sent_at timestamp with time zone DEFAULT now(),
    acknowledged_at timestamp with time zone,
    message_summary text
);


--
-- Name: driver_comms_log_comm_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.driver_comms_log_comm_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: driver_comms_log_comm_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.driver_comms_log_comm_id_seq OWNED BY public.driver_comms_log.comm_id;


--
-- Name: driver_disciplinary_actions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.driver_disciplinary_actions (
    action_id integer NOT NULL,
    driver_id integer,
    action_date date NOT NULL,
    action_type character varying(50),
    reason text NOT NULL,
    duration_days integer,
    issued_by character varying(100),
    acknowledged_date date,
    acknowledged_by character varying(100),
    appeal_filed boolean DEFAULT false,
    appeal_notes text,
    appeal_resolved boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: driver_disciplinary_actions_action_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.driver_disciplinary_actions_action_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: driver_disciplinary_actions_action_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.driver_disciplinary_actions_action_id_seq OWNED BY public.driver_disciplinary_actions.action_id;


--
-- Name: driver_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.driver_documents (
    id integer NOT NULL,
    employee_id integer,
    document_type character varying(50) NOT NULL,
    document_name character varying(255) NOT NULL,
    file_path character varying(500),
    file_size integer,
    mime_type character varying(100),
    issued_date date,
    expiry_date date,
    issuing_authority character varying(255),
    document_number character varying(100),
    status character varying(20) DEFAULT 'active'::character varying,
    notes text,
    uploaded_by integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT driver_documents_document_type_check CHECK (((document_type)::text = ANY (ARRAY[('license'::character varying)::text, ('medical_certificate'::character varying)::text, ('chauffeur_permit'::character varying)::text, ('insurance'::character varying)::text, ('training_certificate'::character varying)::text, ('background_check'::character varying)::text, ('drug_test'::character varying)::text, ('other'::character varying)::text]))),
    CONSTRAINT driver_documents_status_check CHECK (((status)::text = ANY (ARRAY[('active'::character varying)::text, ('expired'::character varying)::text, ('revoked'::character varying)::text, ('pending'::character varying)::text])))
);


--
-- Name: driver_documents_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.driver_documents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: driver_documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.driver_documents_id_seq OWNED BY public.driver_documents.id;


--
-- Name: driver_employee_mapping; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.driver_employee_mapping (
    driver_id character varying(50) NOT NULL,
    employee_id integer,
    employee_number character varying(50),
    full_name character varying(200),
    confidence_score integer DEFAULT 100,
    mapping_source character varying(100) DEFAULT 'employee_number_match'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: driver_float_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.driver_float_summary AS
 SELECT cft.driver_id,
    cft.driver_name,
    e.full_name AS employee_name,
    e.employee_number,
    e.status AS employee_status,
    COALESCE(sum(
        CASE
            WHEN ((cft.reconciliation_status)::text = ANY ((ARRAY['pending'::character varying, 'partial'::character varying, 'overdue'::character varying, 'outstanding'::character varying])::text[])) THEN abs(cft.float_amount)
            ELSE (0)::numeric
        END), (0)::numeric) AS outstanding_amount,
    count(
        CASE
            WHEN ((cft.reconciliation_status)::text = ANY ((ARRAY['pending'::character varying, 'partial'::character varying, 'overdue'::character varying, 'outstanding'::character varying])::text[])) THEN 1
            ELSE NULL::integer
        END) AS outstanding_count,
    COALESCE(sum(
        CASE
            WHEN (cft.float_date >= date_trunc('month'::text, (CURRENT_DATE)::timestamp with time zone)) THEN abs(cft.float_amount)
            ELSE (0)::numeric
        END), (0)::numeric) AS monthly_floats,
    count(
        CASE
            WHEN (cft.float_date >= date_trunc('month'::text, (CURRENT_DATE)::timestamp with time zone)) THEN 1
            ELSE NULL::integer
        END) AS monthly_count,
    count(*) AS total_floats,
    avg(
        CASE
            WHEN (((cft.reconciliation_status)::text = 'reconciled'::text) AND (cft.updated_at IS NOT NULL) AND (cft.float_date IS NOT NULL)) THEN date_part('day'::text, (cft.updated_at - (cft.float_date)::timestamp without time zone))
            ELSE NULL::double precision
        END) AS avg_reconciliation_days,
    (((count(
        CASE
            WHEN ((cft.reconciliation_status)::text = 'reconciled'::text) THEN 1
            ELSE NULL::integer
        END))::numeric * 100.0) / (NULLIF(count(*), 0))::numeric) AS reconciliation_rate,
    max(cft.float_date) AS last_float_date,
    max(cft.updated_at) AS last_activity_date
   FROM (public.chauffeur_float_tracking cft
     LEFT JOIN public.employees e ON (((cft.driver_id)::text = (e.employee_number)::text)))
  WHERE (cft.float_date >= (CURRENT_DATE - '1 year'::interval))
  GROUP BY cft.driver_id, cft.driver_name, e.full_name, e.employee_number, e.status
  ORDER BY COALESCE(sum(
        CASE
            WHEN ((cft.reconciliation_status)::text = ANY ((ARRAY['pending'::character varying, 'partial'::character varying, 'overdue'::character varying, 'outstanding'::character varying])::text[])) THEN abs(cft.float_amount)
            ELSE (0)::numeric
        END), (0)::numeric) DESC, cft.driver_name;


--
-- Name: driver_floats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.driver_floats (
    float_id integer NOT NULL,
    employee_id integer NOT NULL,
    issued_date date NOT NULL,
    issued_amount numeric(12,2) NOT NULL,
    returned_date date,
    returned_amount numeric(12,2),
    spent_amount numeric(12,2) DEFAULT 0,
    outstanding_balance numeric(12,2),
    status character varying(20) DEFAULT 'active'::character varying,
    cash_box_transaction_id integer,
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT driver_floats_status_check CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'returned'::character varying, 'reconciled'::character varying, 'written_off'::character varying])::text[])))
);


--
-- Name: driver_floats_float_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.driver_floats_float_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: driver_floats_float_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.driver_floats_float_id_seq OWNED BY public.driver_floats.float_id;


--
-- Name: driver_location_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.driver_location_history (
    location_id integer NOT NULL,
    driver_id integer,
    charter_id integer,
    latitude numeric(10,8),
    longitude numeric(11,8),
    accuracy numeric(6,2),
    altitude numeric(8,2),
    speed numeric(6,2),
    heading numeric(5,2),
    "timestamp" timestamp without time zone NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: driver_location_history_location_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.driver_location_history_location_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: driver_location_history_location_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.driver_location_history_location_id_seq OWNED BY public.driver_location_history.location_id;


--
-- Name: driver_name_employee_map; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.driver_name_employee_map (
    id integer NOT NULL,
    source_name text NOT NULL,
    normalized_name text NOT NULL,
    candidate_employee_id integer,
    candidate_employee_name text,
    candidate_method text,
    confidence numeric(5,4),
    status text DEFAULT 'suggested'::text,
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: driver_name_employee_map_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.driver_name_employee_map_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: driver_name_employee_map_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.driver_name_employee_map_id_seq OWNED BY public.driver_name_employee_map.id;


--
-- Name: driver_pay_entries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.driver_pay_entries (
    entry_id integer NOT NULL,
    driver_id integer,
    driver_name character varying(255) NOT NULL,
    pay_date date NOT NULL,
    hours_worked numeric(5,2),
    hourly_rate numeric(8,2),
    total_pay numeric(10,2),
    charter_reference character varying(50),
    status character varying(50) DEFAULT 'pending'::character varying,
    notes text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    created_by integer
);


--
-- Name: TABLE driver_pay_entries; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.driver_pay_entries IS 'Accounting records for driver pay - separate from operational charter data';


--
-- Name: driver_pay_entries_entry_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.driver_pay_entries_entry_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: driver_pay_entries_entry_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.driver_pay_entries_entry_id_seq OWNED BY public.driver_pay_entries.entry_id;


--
-- Name: driver_payroll; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.driver_payroll (
    id integer NOT NULL,
    driver_id character varying(20),
    year integer,
    month integer,
    charter_id character varying(20),
    reserve_number character varying(20),
    pay_date date,
    gross_pay numeric(10,2),
    cpp numeric(10,2),
    ei numeric(10,2),
    tax numeric(10,2),
    total_deductions numeric(10,2),
    net_pay numeric(10,2),
    expenses numeric(10,2),
    wcb_payment numeric(10,2),
    wcb_rate numeric(10,4),
    source character varying(100),
    imported_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    t4_box_14 numeric(12,2),
    t4_box_16 numeric(12,2),
    t4_box_18 numeric(12,2),
    t4_box_22 numeric(12,2),
    t4_box_24 numeric(12,2),
    t4_box_26 numeric(12,2),
    t4_box_44 numeric(12,2),
    t4_box_46 numeric(12,2),
    t4_box_52 numeric(12,2),
    vacation_pay numeric(10,2),
    employee_id integer,
    quickbooks_source character varying(255),
    record_notes text,
    payroll_class character varying(50) DEFAULT 'WAGE'::character varying,
    base_wages numeric(12,2),
    gratuity_amount numeric(12,2),
    expense_reimbursement numeric(12,2),
    hours_worked numeric(8,2),
    t4_box_10 character varying(2)
);


--
-- Name: COLUMN driver_payroll.t4_box_14; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.driver_payroll.t4_box_14 IS 'T4 Box 14 - Employment income';


--
-- Name: COLUMN driver_payroll.t4_box_16; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.driver_payroll.t4_box_16 IS 'T4 Box 16 - CPP contributions';


--
-- Name: COLUMN driver_payroll.t4_box_18; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.driver_payroll.t4_box_18 IS 'T4 Box 18 - EI premiums';


--
-- Name: COLUMN driver_payroll.t4_box_22; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.driver_payroll.t4_box_22 IS 'T4 Box 22 - Income tax deducted';


--
-- Name: COLUMN driver_payroll.t4_box_24; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.driver_payroll.t4_box_24 IS 'T4 Box 24 - EI insurable earnings';


--
-- Name: COLUMN driver_payroll.t4_box_26; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.driver_payroll.t4_box_26 IS 'T4 Box 26 - CPP pensionable earnings';


--
-- Name: COLUMN driver_payroll.t4_box_44; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.driver_payroll.t4_box_44 IS 'T4 Box 44 - Union dues';


--
-- Name: COLUMN driver_payroll.t4_box_46; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.driver_payroll.t4_box_46 IS 'T4 Box 46 - Charitable donations';


--
-- Name: COLUMN driver_payroll.t4_box_52; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.driver_payroll.t4_box_52 IS 'T4 Box 52 - Pension adjustment';


--
-- Name: COLUMN driver_payroll.vacation_pay; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.driver_payroll.vacation_pay IS 'Vacation pay amount';


--
-- Name: COLUMN driver_payroll.employee_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.driver_payroll.employee_id IS 'Foreign key to employees table';


--
-- Name: COLUMN driver_payroll.quickbooks_source; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.driver_payroll.quickbooks_source IS 'Source QuickBooks file';


--
-- Name: COLUMN driver_payroll.payroll_class; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.driver_payroll.payroll_class IS 'WAGE (default) or ADJUSTMENT - filter WAGE for pure payroll analytics';


--
-- Name: COLUMN driver_payroll.t4_box_10; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.driver_payroll.t4_box_10 IS 'T4 Box 10: Province of employment (AB, BC, SK, etc.)';


--
-- Name: driver_payroll_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.driver_payroll_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: driver_payroll_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.driver_payroll_id_seq OWNED BY public.driver_payroll.id;


--
-- Name: duty_status_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.duty_status_types (
    status_id integer NOT NULL,
    status_code character varying(10) NOT NULL,
    status_name character varying(100) NOT NULL,
    description text,
    counts_as_driving boolean DEFAULT false,
    counts_as_on_duty boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: duty_status_types_status_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.duty_status_types_status_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: duty_status_types_status_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.duty_status_types_status_id_seq OWNED BY public.duty_status_types.status_id;


--
-- Name: email_financial_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.email_financial_events (
    id integer NOT NULL,
    source text NOT NULL,
    entity text,
    from_email text,
    subject text,
    email_date timestamp without time zone,
    event_type text,
    amount numeric(14,2),
    currency text,
    due_date date,
    status text,
    vin text,
    vehicle_name text,
    vehicle_id integer,
    lender_name text,
    loan_external_id text,
    policy_number text,
    notes text,
    banking_transaction_id integer,
    matched_account_number text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    license_plate text
);


--
-- Name: email_financial_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.email_financial_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: email_financial_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.email_financial_events_id_seq OWNED BY public.email_financial_events.id;


--
-- Name: email_processing_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.email_processing_stats (
    id integer NOT NULL,
    processing_date date NOT NULL,
    emails_processed integer DEFAULT 0,
    financial_emails_found integer DEFAULT 0,
    entries_created integer DEFAULT 0,
    total_amount numeric(12,2) DEFAULT 0,
    pending_review integer DEFAULT 0,
    auto_approved integer DEFAULT 0,
    processing_time_seconds integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: email_processing_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.email_processing_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: email_processing_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.email_processing_stats_id_seq OWNED BY public.email_processing_stats.id;


--
-- Name: employee_availability; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.employee_availability (
    availability_id integer NOT NULL,
    employee_id integer NOT NULL,
    day_of_week integer NOT NULL,
    available_start_time time without time zone,
    available_end_time time without time zone,
    is_available boolean DEFAULT true,
    max_hours_per_day numeric(4,2),
    preferred_work_types text[],
    notes text,
    effective_start_date date NOT NULL,
    effective_end_date date,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: TABLE employee_availability; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.employee_availability IS 'Tracks when employees are available for work and their preferences';


--
-- Name: employee_availability_availability_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.employee_availability_availability_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: employee_availability_availability_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.employee_availability_availability_id_seq OWNED BY public.employee_availability.availability_id;


--
-- Name: employee_expenses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.employee_expenses (
    expense_id integer NOT NULL,
    employee_id integer NOT NULL,
    receipt_id integer,
    expense_date date NOT NULL,
    amount numeric(10,2) NOT NULL,
    gst_amount numeric(8,2) DEFAULT 0,
    net_amount numeric(10,2),
    category character varying(50),
    subcategory character varying(50),
    vendor_name character varying(200),
    description text,
    work_assignment_id integer,
    is_business_expense boolean DEFAULT true,
    business_percentage numeric(5,2) DEFAULT 100.00,
    is_reimbursable boolean DEFAULT true,
    reimbursement_status character varying(20) DEFAULT 'pending'::character varying,
    reimbursed_amount numeric(10,2),
    reimbursed_date date,
    submitted_by integer,
    submitted_at timestamp without time zone,
    approved_by integer,
    approved_at timestamp without time zone,
    approval_notes text,
    receipt_image_path character varying(500),
    receipt_uploaded boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: TABLE employee_expenses; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.employee_expenses IS 'Expense tracking and reimbursement for all employees integrated with receipts system';


--
-- Name: employee_expenses_expense_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.employee_expenses_expense_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: employee_expenses_expense_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.employee_expenses_expense_id_seq OWNED BY public.employee_expenses.expense_id;


--
-- Name: employee_pay_entries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.employee_pay_entries (
    entry_id integer NOT NULL,
    employee_id integer,
    employee_name character varying(255) NOT NULL,
    employee_type character varying(50) DEFAULT 'chauffeur'::character varying,
    pay_date date NOT NULL,
    hours_worked numeric(5,2),
    hourly_rate numeric(8,2),
    total_pay numeric(10,2),
    reservation_reference character varying(50),
    status character varying(50) DEFAULT 'pending'::character varying,
    notes text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    created_by integer
);


--
-- Name: TABLE employee_pay_entries; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.employee_pay_entries IS 'Accounting records for employee pay - separate from operational reservation data';


--
-- Name: employee_pay_entries_entry_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.employee_pay_entries_entry_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: employee_pay_entries_entry_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.employee_pay_entries_entry_id_seq OWNED BY public.employee_pay_entries.entry_id;


--
-- Name: employee_pay_master; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.employee_pay_master (
    employee_pay_id integer NOT NULL,
    employee_id integer NOT NULL,
    pay_period_id integer NOT NULL,
    fiscal_year integer NOT NULL,
    charter_hours_sum numeric(10,2),
    approved_hours numeric(10,2),
    overtime_hours numeric(10,2),
    manual_hours_adjustment numeric(10,2),
    total_hours_worked numeric(10,2),
    hourly_rate numeric(10,2),
    rate_source text,
    base_pay numeric(12,2),
    gratuity_percent numeric(5,2),
    gratuity_amount numeric(12,2),
    float_draw numeric(12,2),
    reimbursements numeric(12,2),
    other_income numeric(12,2),
    gross_pay numeric(12,2),
    federal_tax numeric(12,2),
    provincial_tax numeric(12,2),
    cpp_employee numeric(12,2),
    ei_employee numeric(12,2),
    union_dues numeric(12,2),
    radio_dues numeric(12,2),
    voucher_deductions numeric(12,2),
    misc_deductions numeric(12,2),
    total_deductions numeric(12,2),
    net_pay numeric(12,2),
    data_completeness numeric(5,2),
    data_source text,
    confidence_level numeric(5,2),
    notes text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    created_by text DEFAULT 'system'::text,
    CONSTRAINT check_hours CHECK ((total_hours_worked >= (0)::numeric)),
    CONSTRAINT check_pay CHECK ((gross_pay >= (0)::numeric))
);


--
-- Name: employee_pay_master_employee_pay_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.employee_pay_master_employee_pay_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: employee_pay_master_employee_pay_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.employee_pay_master_employee_pay_id_seq OWNED BY public.employee_pay_master.employee_pay_id;


--
-- Name: employee_roe_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.employee_roe_records (
    id integer NOT NULL,
    employee_id integer,
    employee_name character varying(200),
    roe_number character varying(50),
    termination_date date,
    last_day_worked date,
    reason_code character varying(10),
    insurable_earnings numeric(12,2),
    insurable_hours integer,
    pay_period_type character varying(50),
    source_file character varying(500),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: employee_roe_records_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.employee_roe_records_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: employee_roe_records_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.employee_roe_records_id_seq OWNED BY public.employee_roe_records.id;


--
-- Name: employee_schedules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.employee_schedules (
    schedule_id integer NOT NULL,
    employee_id integer NOT NULL,
    work_date date NOT NULL,
    work_type character varying(50) NOT NULL,
    classification_type character varying(50) NOT NULL,
    scheduled_start_time time without time zone,
    scheduled_end_time time without time zone,
    actual_start_time time without time zone,
    actual_end_time time without time zone,
    break_duration_minutes integer DEFAULT 0,
    total_hours_scheduled numeric(5,2),
    total_hours_worked numeric(5,2),
    hourly_rate numeric(8,2),
    location character varying(200),
    description text,
    status character varying(20) DEFAULT 'scheduled'::character varying,
    approved_by integer,
    approved_at timestamp without time zone,
    created_by integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: TABLE employee_schedules; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.employee_schedules IS 'Tracks work schedules for non-charter employees with time tracking and approval';


--
-- Name: employee_schedules_schedule_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.employee_schedules_schedule_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: employee_schedules_schedule_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.employee_schedules_schedule_id_seq OWNED BY public.employee_schedules.schedule_id;


--
-- Name: employee_t4_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.employee_t4_records (
    t4_id integer NOT NULL,
    employee_id integer,
    tax_year integer NOT NULL,
    box_14_employment_income numeric(12,2) DEFAULT 0.00,
    box_16_cpp_contributions numeric(12,2) DEFAULT 0.00,
    box_18_ei_premiums numeric(12,2) DEFAULT 0.00,
    box_22_income_tax numeric(12,2) DEFAULT 0.00,
    box_24_ei_insurable_earnings numeric(12,2) DEFAULT 0.00,
    box_26_cpp_pensionable_earnings numeric(12,2) DEFAULT 0.00,
    box_44_union_dues numeric(12,2) DEFAULT 0.00,
    box_46_charitable_donations numeric(12,2) DEFAULT 0.00,
    box_52_pension_adjustment numeric(12,2) DEFAULT 0.00,
    notes text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    box_81_wcb_insurable_earnings numeric(12,2),
    box_82_charitable_tax_credit numeric(12,2),
    box_84_eligible_retiring_allowance numeric(12,2),
    box_85_non_eligible_retiring_allowance numeric(12,2),
    box_86_wcb_reportable_earnings numeric(12,2),
    box_12_taxable_benefits numeric(12,2),
    box_20_rpp_contributions numeric(12,2),
    box_28_exempt_cpp_cpp_pensionable numeric(12,2),
    box_29_exempt_ei_ei_insurable numeric(12,2),
    box_30_boarding_lodging numeric(12,2),
    box_32_travel_personal_vehicle numeric(12,2),
    box_34_travel_allowances numeric(12,2),
    box_36_medical_travel_assistance numeric(12,2),
    box_38_employer_paid_premiums_group_term_life numeric(12,2),
    box_40_other_taxable_allowances numeric(12,2),
    box_42_employment_commissions numeric(12,2),
    box_50_security_options_benefits numeric(12,2),
    box_56_labour_sponsored_funds numeric(12,2),
    box_66_eligible_retiring_allowance numeric(12,2),
    box_67_non_eligible_retiring_allowance numeric(12,2),
    box_68_fishers_gross_earnings numeric(12,2),
    box_69_fishers_net_partnership numeric(12,2),
    box_70_fishers_share_costs numeric(12,2),
    box_71_indian_employment_exempt numeric(12,2),
    box_78_non_cash_taxable_benefits numeric(12,2)
);


--
-- Name: TABLE employee_t4_records; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.employee_t4_records IS 'Manual T4 entry for historical or direct input of annual T4 box values';


--
-- Name: COLUMN employee_t4_records.box_81_wcb_insurable_earnings; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.employee_t4_records.box_81_wcb_insurable_earnings IS 'Provincial Box 81 - WCB insurable earnings';


--
-- Name: COLUMN employee_t4_records.box_82_charitable_tax_credit; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.employee_t4_records.box_82_charitable_tax_credit IS 'Provincial Box 82 - Charitable donations tax credit';


--
-- Name: COLUMN employee_t4_records.box_84_eligible_retiring_allowance; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.employee_t4_records.box_84_eligible_retiring_allowance IS 'Provincial Box 84 - Eligible retiring allowance';


--
-- Name: COLUMN employee_t4_records.box_85_non_eligible_retiring_allowance; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.employee_t4_records.box_85_non_eligible_retiring_allowance IS 'Provincial Box 85 - Non-eligible retiring allowance';


--
-- Name: COLUMN employee_t4_records.box_86_wcb_reportable_earnings; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.employee_t4_records.box_86_wcb_reportable_earnings IS 'Provincial Box 86 - WCB reportable earnings (another provincial code)';


--
-- Name: COLUMN employee_t4_records.box_12_taxable_benefits; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.employee_t4_records.box_12_taxable_benefits IS 'Box 12 - Taxable benefits';


--
-- Name: COLUMN employee_t4_records.box_20_rpp_contributions; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.employee_t4_records.box_20_rpp_contributions IS 'Box 20 - RPP contributions';


--
-- Name: COLUMN employee_t4_records.box_28_exempt_cpp_cpp_pensionable; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.employee_t4_records.box_28_exempt_cpp_cpp_pensionable IS 'Box 28 - Exempt from CPP/QPP - CPP/QPP pensionable';


--
-- Name: COLUMN employee_t4_records.box_29_exempt_ei_ei_insurable; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.employee_t4_records.box_29_exempt_ei_ei_insurable IS 'Box 29 - Exempt from EI - EI insurable';


--
-- Name: COLUMN employee_t4_records.box_30_boarding_lodging; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.employee_t4_records.box_30_boarding_lodging IS 'Box 30 - Boarding and lodging';


--
-- Name: employee_t4_records_t4_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.employee_t4_records_t4_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: employee_t4_records_t4_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.employee_t4_records_t4_id_seq OWNED BY public.employee_t4_records.t4_id;


--
-- Name: employee_t4_summary; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.employee_t4_summary (
    t4_id integer NOT NULL,
    employee_id integer NOT NULL,
    fiscal_year integer NOT NULL,
    t4_employment_income numeric(12,2),
    t4_federal_tax numeric(12,2),
    t4_provincial_tax numeric(12,2),
    t4_cpp_contributions numeric(12,2),
    t4_ei_contributions numeric(12,2),
    t4_union_dues numeric(12,2),
    t4_other_deductions numeric(12,2),
    source text,
    confidence_level numeric(5,2),
    is_verified boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    created_by text DEFAULT 'system'::text,
    notes text
);


--
-- Name: employee_t4_summary_t4_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.employee_t4_summary_t4_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: employee_t4_summary_t4_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.employee_t4_summary_t4_id_seq OWNED BY public.employee_t4_summary.t4_id;


--
-- Name: employee_time_off_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.employee_time_off_requests (
    request_id integer NOT NULL,
    employee_id integer NOT NULL,
    time_off_type character varying(30) NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    total_days_requested numeric(4,2),
    total_hours_requested numeric(6,2),
    reason text,
    is_paid boolean DEFAULT true,
    status character varying(20) DEFAULT 'pending'::character varying,
    requested_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    reviewed_by integer,
    reviewed_at timestamp without time zone,
    review_notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: TABLE employee_time_off_requests; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.employee_time_off_requests IS 'Manages vacation, sick time, and other time off requests with approval workflow';


--
-- Name: employee_time_off_requests_request_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.employee_time_off_requests_request_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: employee_time_off_requests_request_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.employee_time_off_requests_request_id_seq OWNED BY public.employee_time_off_requests.request_id;


--
-- Name: employee_work_classifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.employee_work_classifications (
    classification_id integer NOT NULL,
    employee_id integer NOT NULL,
    classification_type character varying(50) NOT NULL,
    pay_structure character varying(20) NOT NULL,
    hourly_rate numeric(8,2),
    monthly_salary numeric(10,2),
    annual_salary numeric(12,2),
    overtime_rate numeric(8,2),
    effective_start_date date NOT NULL,
    effective_end_date date,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    salary_deferred numeric(10,2) DEFAULT 0.00
);


--
-- Name: TABLE employee_work_classifications; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.employee_work_classifications IS 'Defines how employees are classified and paid - extends beyond just chauffeurs';


--
-- Name: employee_work_classifications_classification_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.employee_work_classifications_classification_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: employee_work_classifications_classification_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.employee_work_classifications_classification_id_seq OWNED BY public.employee_work_classifications.classification_id;


--
-- Name: employees_employee_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.employees_employee_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: employees_employee_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.employees_employee_id_seq OWNED BY public.employees.employee_id;


--
-- Name: epson_classifications_map; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.epson_classifications_map (
    epson_classification text NOT NULL,
    mapped_account_id integer,
    mapped_account_name text,
    mapped_cash_flow_category text,
    confidence numeric(5,2),
    alternatives text,
    status character varying(20) DEFAULT 'proposed'::character varying NOT NULL,
    notes text,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: epson_pay_accounts_map; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.epson_pay_accounts_map (
    epson_pay_account text NOT NULL,
    mapped_account_id integer,
    mapped_account_name text,
    confidence numeric(5,2),
    alternatives text,
    status character varying(20) DEFAULT 'proposed'::character varying NOT NULL,
    notes text,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: epson_pay_methods_map; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.epson_pay_methods_map (
    epson_pay_method text NOT NULL,
    canonical_method text,
    confidence numeric(5,2),
    alternatives text,
    status character varying(20) DEFAULT 'proposed'::character varying NOT NULL,
    notes text,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: etransfer_banking_reconciliation; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.etransfer_banking_reconciliation (
    id integer NOT NULL,
    etransfer_id integer NOT NULL,
    transaction_id integer,
    account_number text,
    transaction_date date,
    match_type text,
    match_score integer,
    amount numeric(12,2),
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: etransfer_banking_reconciliation_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.etransfer_banking_reconciliation_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: etransfer_banking_reconciliation_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.etransfer_banking_reconciliation_id_seq OWNED BY public.etransfer_banking_reconciliation.id;


--
-- Name: etransfer_transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.etransfer_transactions (
    etransfer_id integer NOT NULL,
    direction character varying(10) NOT NULL,
    amount numeric(12,2) NOT NULL,
    transaction_date date NOT NULL,
    sender_recipient_name character varying(200),
    sender_recipient_email character varying(200),
    reference_number character varying(100),
    status character varying(50),
    email_event_id integer,
    banking_transaction_id integer,
    matched_at timestamp without time zone,
    match_confidence character varying(20),
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    category character varying(50),
    category_description text
);


--
-- Name: etransfer_transactions_etransfer_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.etransfer_transactions_etransfer_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: etransfer_transactions_etransfer_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.etransfer_transactions_etransfer_id_seq OWNED BY public.etransfer_transactions.etransfer_id;


--
-- Name: etransfers_processed; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.etransfers_processed (
    id integer NOT NULL,
    etransfer_date date NOT NULL,
    amount numeric(12,2) NOT NULL,
    direction text,
    type_desc text,
    counterparty_role text,
    company text,
    reference_code text,
    gl_code text,
    category text,
    status text,
    source_email text,
    source_file text,
    source_hash text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: etransfers_processed_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.etransfers_processed_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: etransfers_processed_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.etransfers_processed_id_seq OWNED BY public.etransfers_processed.id;


--
-- Name: excluded_charters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.excluded_charters (
    id integer NOT NULL,
    charter_id integer,
    exclusion_reason character varying(100),
    excluded_date timestamp without time zone DEFAULT now()
);


--
-- Name: excluded_charters_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.excluded_charters_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: excluded_charters_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.excluded_charters_id_seq OWNED BY public.excluded_charters.id;


--
-- Name: federal_tax_brackets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.federal_tax_brackets (
    year integer NOT NULL,
    bracket_number integer NOT NULL,
    income_from numeric(12,2) NOT NULL,
    income_to numeric(12,2),
    tax_rate numeric(5,3) NOT NULL,
    marginal_rate_description text
);


--
-- Name: fee_tracking; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fee_tracking (
    fee_id integer NOT NULL,
    transaction_date date NOT NULL,
    fee_type character varying(100) NOT NULL,
    fee_amount numeric(15,2) NOT NULL,
    related_transaction_amount numeric(15,2),
    fee_description text,
    bank_reference character varying(200),
    gl_account_id integer,
    reconciled boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: fee_tracking_fee_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fee_tracking_fee_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fee_tracking_fee_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fee_tracking_fee_id_seq OWNED BY public.fee_tracking.fee_id;


--
-- Name: financial_adjustments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.financial_adjustments (
    adjustment_id integer NOT NULL,
    client_id integer,
    adjustment_type character varying(50) NOT NULL,
    amount numeric(10,2) NOT NULL,
    description text NOT NULL,
    fraud_case_id integer,
    created_by character varying(100) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    approved_by character varying(100),
    approved_at timestamp without time zone,
    status character varying(20) DEFAULT 'pending'::character varying
);


--
-- Name: TABLE financial_adjustments; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.financial_adjustments IS 'Financial adjustments made during fraud corrections';


--
-- Name: financial_adjustments_adjustment_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.financial_adjustments_adjustment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: financial_adjustments_adjustment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.financial_adjustments_adjustment_id_seq OWNED BY public.financial_adjustments.adjustment_id;


--
-- Name: financial_audit_trail; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.financial_audit_trail (
    audit_id integer NOT NULL,
    session_id character varying(32),
    user_name character varying(100),
    action_type character varying(50),
    table_name character varying(50),
    record_id character varying(50),
    old_values jsonb,
    new_values jsonb,
    filter_criteria jsonb,
    result_count integer,
    action_timestamp timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    client_ip character varying(45),
    details text
);


--
-- Name: financial_audit_trail_audit_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.financial_audit_trail_audit_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: financial_audit_trail_audit_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.financial_audit_trail_audit_id_seq OWNED BY public.financial_audit_trail.audit_id;


--
-- Name: financial_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.financial_documents (
    id integer NOT NULL,
    file_name character varying(255) NOT NULL,
    file_path text NOT NULL,
    file_size bigint,
    document_date date,
    document_type character varying(50),
    invoice_number character varying(50),
    reservation_number character varying(50),
    scan_number character varying(50),
    reference character varying(255),
    pattern character varying(50),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: financial_documents_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.financial_documents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: financial_documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.financial_documents_id_seq OWNED BY public.financial_documents.id;


--
-- Name: financial_statement_sections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.financial_statement_sections (
    section_id integer NOT NULL,
    statement_type_id integer,
    section_name character varying(100) NOT NULL,
    section_order integer NOT NULL,
    parent_section_id integer,
    is_subtotal boolean DEFAULT false
);


--
-- Name: financial_statement_sections_section_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.financial_statement_sections_section_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: financial_statement_sections_section_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.financial_statement_sections_section_id_seq OWNED BY public.financial_statement_sections.section_id;


--
-- Name: financial_statement_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.financial_statement_types (
    statement_type_id integer NOT NULL,
    statement_name character varying(100) NOT NULL,
    statement_code character varying(20) NOT NULL,
    description text,
    is_active boolean DEFAULT true
);


--
-- Name: financial_statement_types_statement_type_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.financial_statement_types_statement_type_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: financial_statement_types_statement_type_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.financial_statement_types_statement_type_id_seq OWNED BY public.financial_statement_types.statement_type_id;


--
-- Name: financial_transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.financial_transactions (
    id integer NOT NULL,
    source_file character varying(255),
    transaction_date date,
    record_type character varying(50),
    amount numeric,
    debit numeric,
    credit numeric,
    description text,
    memo text,
    account character varying(255),
    hash_id character varying(32),
    import_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: financial_transactions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.financial_transactions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: financial_transactions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.financial_transactions_id_seq OWNED BY public.financial_transactions.id;


--
-- Name: financing_sources; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.financing_sources (
    source_id integer NOT NULL,
    source_type character varying(50) NOT NULL,
    source_name character varying(255) NOT NULL,
    source_description text,
    principal_amount numeric(15,2) NOT NULL,
    interest_rate numeric(5,4) DEFAULT 0,
    term_months integer DEFAULT 0,
    date_received date NOT NULL,
    maturity_date date,
    lender_investor character varying(255),
    account_code character varying(20),
    status character varying(20) DEFAULT 'active'::character varying,
    terms_conditions text,
    collateral_description text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT financing_sources_source_type_check CHECK (((source_type)::text = ANY (ARRAY[('equity'::character varying)::text, ('debt'::character varying)::text, ('grant'::character varying)::text, ('retained_earnings'::character varying)::text, ('other'::character varying)::text]))),
    CONSTRAINT financing_sources_status_check CHECK (((status)::text = ANY (ARRAY[('active'::character varying)::text, ('paid_off'::character varying)::text, ('defaulted'::character varying)::text, ('refinanced'::character varying)::text])))
);


--
-- Name: TABLE financing_sources; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.financing_sources IS 'Tracks all sources of business financing following Microsoft Copilot flow';


--
-- Name: financing_sources_source_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.financing_sources_source_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: financing_sources_source_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.financing_sources_source_id_seq OWNED BY public.financing_sources.source_id;


--
-- Name: float_activity_log_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.float_activity_log_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: float_activity_log_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.float_activity_log_log_id_seq OWNED BY public.float_activity_log.log_id;


--
-- Name: float_dashboard_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.float_dashboard_summary AS
 SELECT COALESCE(sum(
        CASE
            WHEN ((reconciliation_status)::text = ANY ((ARRAY['pending'::character varying, 'partial'::character varying, 'overdue'::character varying, 'outstanding'::character varying])::text[])) THEN abs(float_amount)
            ELSE (0)::numeric
        END), (0)::numeric) AS outstanding_floats,
    count(
        CASE
            WHEN ((reconciliation_status)::text = ANY ((ARRAY['pending'::character varying, 'partial'::character varying, 'overdue'::character varying, 'outstanding'::character varying])::text[])) THEN 1
            ELSE NULL::integer
        END) AS outstanding_count,
    COALESCE(sum(
        CASE
            WHEN ((float_date = CURRENT_DATE) AND (float_amount < (0)::numeric)) THEN abs(float_amount)
            ELSE (0)::numeric
        END), (0)::numeric) AS issued_today,
    count(
        CASE
            WHEN ((float_date = CURRENT_DATE) AND (float_amount < (0)::numeric)) THEN 1
            ELSE NULL::integer
        END) AS issued_count_today,
    COALESCE(sum(
        CASE
            WHEN ((date(updated_at) = CURRENT_DATE) AND ((reconciliation_status)::text = 'reconciled'::text)) THEN collection_amount
            ELSE (0)::numeric
        END), (0)::numeric) AS reconciled_today,
    count(
        CASE
            WHEN ((date(updated_at) = CURRENT_DATE) AND ((reconciliation_status)::text = 'reconciled'::text)) THEN 1
            ELSE NULL::integer
        END) AS reconciled_count_today,
    COALESCE(sum(
        CASE
            WHEN ((collection_amount > abs(float_amount)) AND ((reconciliation_status)::text <> 'reimbursed'::text)) THEN (collection_amount - abs(float_amount))
            ELSE (0)::numeric
        END), (0)::numeric) AS pending_reimbursements,
    count(
        CASE
            WHEN ((collection_amount > abs(float_amount)) AND ((reconciliation_status)::text <> 'reimbursed'::text)) THEN 1
            ELSE NULL::integer
        END) AS pending_reimbursement_count,
    avg(
        CASE
            WHEN (((reconciliation_status)::text = 'reconciled'::text) AND (updated_at IS NOT NULL) AND (float_date IS NOT NULL)) THEN date_part('day'::text, (updated_at - (float_date)::timestamp without time zone))
            ELSE NULL::double precision
        END) AS avg_reconciliation_days,
    (((count(
        CASE
            WHEN ((reconciliation_status)::text = 'reconciled'::text) THEN 1
            ELSE NULL::integer
        END))::numeric * 100.0) / (NULLIF(count(*), 0))::numeric) AS reconciliation_rate
   FROM public.chauffeur_float_tracking
  WHERE (float_date >= (CURRENT_DATE - '1 year'::interval));


--
-- Name: fraud_cases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fraud_cases (
    case_id integer NOT NULL,
    case_number character varying(50) NOT NULL,
    case_type character varying(50) NOT NULL,
    source_client_id integer,
    target_client_id integer,
    amount_involved numeric(10,2) NOT NULL,
    investigator character varying(100) NOT NULL,
    reason text NOT NULL,
    supporting_documents jsonb DEFAULT '[]'::jsonb,
    authorization_level character varying(50) DEFAULT 'supervisor'::character varying,
    status character varying(20) DEFAULT 'pending'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    resolved_at timestamp without time zone,
    journal_reference character varying(50),
    accounting_status character varying(100) DEFAULT 'pending'::character varying,
    original_loss_date date,
    discovery_date date,
    accounting_treatment character varying(100)
);


--
-- Name: TABLE fraud_cases; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.fraud_cases IS 'Tracks fraud cases and corrections including debt transfers';


--
-- Name: fraud_cases_case_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fraud_cases_case_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fraud_cases_case_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fraud_cases_case_id_seq OWNED BY public.fraud_cases.case_id;


--
-- Name: fuel_expenses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fuel_expenses (
    id integer NOT NULL,
    expense_id integer,
    vehicle_id integer,
    vehicle_code text,
    expense_date date,
    merchant text,
    liters numeric(12,3),
    price_per_liter numeric(12,3),
    subtotal numeric(14,2),
    gst_amount numeric(14,2),
    total_amount numeric(14,2),
    source_key text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: fuel_expenses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fuel_expenses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fuel_expenses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fuel_expenses_id_seq OWNED BY public.fuel_expenses.id;


--
-- Name: general_ledger; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.general_ledger (
    id integer NOT NULL,
    date date,
    transaction_type text,
    num text,
    name text,
    memo_description text,
    account text,
    debit numeric,
    credit numeric,
    balance numeric,
    source_file text,
    imported_at timestamp without time zone,
    supplier text,
    account_name text,
    employee text,
    employee_billing_rate numeric,
    parent_distribution_account text,
    distribution_account_is_sub_account text
);


--
-- Name: general_ledger_headers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.general_ledger_headers (
    header_id integer NOT NULL,
    entry_date date NOT NULL,
    reference_number character varying(50) NOT NULL,
    description text NOT NULL,
    total_debits numeric(15,2) NOT NULL,
    total_credits numeric(15,2) NOT NULL,
    fraud_case_id integer,
    created_by character varying(100) NOT NULL,
    approved_by character varying(100),
    status character varying(20) DEFAULT 'draft'::character varying,
    reversal_reference character varying(50),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    posted_at timestamp without time zone,
    source_module character varying(50),
    source_reference character varying(100),
    period_key character varying(10),
    CONSTRAINT balanced_entry CHECK ((total_debits = total_credits))
);


--
-- Name: TABLE general_ledger_headers; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.general_ledger_headers IS 'Journal entry headers with fraud case tracking';


--
-- Name: general_ledger_headers_header_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.general_ledger_headers_header_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: general_ledger_headers_header_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.general_ledger_headers_header_id_seq OWNED BY public.general_ledger_headers.header_id;


--
-- Name: general_ledger_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.general_ledger_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: general_ledger_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.general_ledger_id_seq OWNED BY public.general_ledger.id;


--
-- Name: general_ledger_lines; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.general_ledger_lines (
    line_id integer NOT NULL,
    header_id integer,
    line_number integer NOT NULL,
    account_code character varying(20) NOT NULL,
    account_name character varying(255) NOT NULL,
    debit_amount numeric(15,2) DEFAULT 0.00,
    credit_amount numeric(15,2) DEFAULT 0.00,
    description text,
    fraud_case_id integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT single_amount CHECK ((((debit_amount > (0)::numeric) AND (credit_amount = (0)::numeric)) OR ((credit_amount > (0)::numeric) AND (debit_amount = (0)::numeric))))
);


--
-- Name: TABLE general_ledger_lines; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.general_ledger_lines IS 'Journal entry line items with detailed accounting';


--
-- Name: general_ledger_lines_line_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.general_ledger_lines_line_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: general_ledger_lines_line_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.general_ledger_lines_line_id_seq OWNED BY public.general_ledger_lines.line_id;


--
-- Name: receipts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.receipts (
    receipt_id bigint CONSTRAINT receipts_id_not_null NOT NULL,
    source_system text DEFAULT 'BANKING_IMPORT'::text,
    source_reference text DEFAULT 'BANKING_IMPORT'::text,
    receipt_date date NOT NULL,
    vendor_name text DEFAULT 'BANKING TRANSACTION'::text,
    description text,
    currency character(3) DEFAULT 'CAD'::bpchar NOT NULL,
    gross_amount numeric(14,2) DEFAULT 0,
    gst_amount numeric(14,2) DEFAULT 0 NOT NULL,
    expense_account text DEFAULT 'BANKING'::text,
    payment_method text,
    source_hash text DEFAULT 'AUTO_GENERATED'::text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    document_type character varying(50),
    type character varying(50),
    tax_category character varying(50),
    card_type character varying(50),
    card_number character varying(50),
    comment text,
    pay_method text,
    mapped_bank_account_id integer,
    canonical_pay_method text,
    category character varying(100),
    expense numeric(12,2),
    vehicle_id integer,
    vehicle_number character varying(50),
    fuel numeric(12,2),
    created_from_banking boolean DEFAULT false,
    revenue numeric DEFAULT 0 NOT NULL,
    gst_code text,
    split_key text,
    split_group_total numeric(12,2),
    fuel_amount numeric(12,2),
    deductible_status text,
    business_personal text,
    source_file text,
    gl_account_code character varying(10),
    gl_account_name character varying(200),
    gl_subcategory character varying(200),
    auto_categorized boolean DEFAULT false,
    net_amount numeric DEFAULT 0 NOT NULL,
    is_split_receipt boolean DEFAULT false,
    is_personal_purchase boolean DEFAULT false,
    owner_personal_amount numeric(12,2) DEFAULT 0,
    is_driver_reimbursement boolean DEFAULT false,
    banking_transaction_id integer,
    receipt_source character varying(50),
    display_color character varying(20),
    canonical_vendor character varying(255),
    is_transfer boolean DEFAULT false,
    verified_source text,
    is_verified_banking boolean DEFAULT false,
    potential_duplicate boolean DEFAULT false,
    duplicate_check_key text,
    is_nsf boolean DEFAULT false,
    is_voided boolean DEFAULT false,
    exclude_from_reports boolean DEFAULT false,
    vendor_account_id bigint,
    fiscal_year integer,
    invoice_date date,
    is_paper_verified boolean DEFAULT false,
    paper_verification_date timestamp without time zone,
    verified_by_user character varying(255) DEFAULT NULL::character varying,
    employee_id integer,
    charter_id integer,
    reserve_number character varying(20),
    gst_exempt boolean DEFAULT false,
    split_status character varying(50) DEFAULT 'single'::character varying,
    split_group_id integer,
    verified_by_edit boolean DEFAULT false,
    verified_at timestamp without time zone,
    verified boolean DEFAULT false,
    verified_date timestamp without time zone,
    verified_by character varying(100),
    gl_code character varying(20),
    gl_description text,
    receipt_review_status character varying(20) DEFAULT NULL::character varying,
    receipt_review_notes text,
    receipt_reviewed_at timestamp without time zone,
    receipt_reviewed_by character varying(100) DEFAULT NULL::character varying,
    CONSTRAINT chk_receipt_review_status CHECK (((receipt_review_status)::text = ANY ((ARRAY[NULL::character varying, 'verified'::character varying, 'missing'::character varying, 'unreadable'::character varying, 'data-error'::character varying])::text[]))),
    CONSTRAINT receipts_split_status_check CHECK (((split_status)::text = ANY ((ARRAY['single'::character varying, 'split_pending'::character varying, 'split_reconciled'::character varying])::text[])))
);


--
-- Name: COLUMN receipts.vendor_account_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.receipts.vendor_account_id IS 'Direct link to vendor account for payables tracking';


--
-- Name: COLUMN receipts.verified_by_user; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.receipts.verified_by_user IS 'Username or system that performed the verification';


--
-- Name: COLUMN receipts.verified_by_edit; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.receipts.verified_by_edit IS 'Auto-set to TRUE when receipt is manually edited, indicating it has been reviewed during audit';


--
-- Name: COLUMN receipts.verified_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.receipts.verified_at IS 'Timestamp when receipt was last edited/verified';


--
-- Name: COLUMN receipts.receipt_review_status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.receipts.receipt_review_status IS 'Manual review status: verified (confirmed correct), missing (lost/unavailable), unreadable (damaged/illegible), data-error (requires correction)';


--
-- Name: COLUMN receipts.receipt_review_notes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.receipts.receipt_review_notes IS 'Notes from manual review: reason for missing, description of damage, correction needed, etc.';


--
-- Name: COLUMN receipts.receipt_reviewed_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.receipts.receipt_reviewed_at IS 'Timestamp when receipt was manually reviewed';


--
-- Name: COLUMN receipts.receipt_reviewed_by; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.receipts.receipt_reviewed_by IS 'Username/identifier of person who reviewed the receipt';


--
-- Name: gl_account_year_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.gl_account_year_summary AS
 SELECT (EXTRACT(year FROM receipt_date))::integer AS fiscal_year,
    gl_account_code,
    count(*) AS transaction_count,
    sum(gross_amount) AS total_amount,
    min(receipt_date) AS first_transaction,
    max(receipt_date) AS last_transaction,
    count(DISTINCT vendor_name) AS unique_vendors
   FROM public.receipts
  WHERE ((receipt_date IS NOT NULL) AND (gl_account_code IS NOT NULL))
  GROUP BY (EXTRACT(year FROM receipt_date)), gl_account_code
  ORDER BY ((EXTRACT(year FROM receipt_date))::integer), gl_account_code;


--
-- Name: gl_transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.gl_transactions (
    gl_id integer NOT NULL,
    transaction_date date,
    transaction_type character varying(50),
    reference_number character varying(100),
    description text,
    account_name character varying(200),
    debit_amount numeric(15,2),
    credit_amount numeric(15,2),
    running_balance numeric(15,2),
    source_batch_id integer,
    natural_key text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: gl_transactions_gl_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.gl_transactions_gl_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: gl_transactions_gl_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.gl_transactions_gl_id_seq OWNED BY public.gl_transactions.gl_id;


--
-- Name: gratuity_income_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.gratuity_income_links (
    id integer NOT NULL,
    receipt_id integer NOT NULL,
    ugl_id integer,
    reserve_number character varying(20),
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: gratuity_income_links_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.gratuity_income_links_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: gratuity_income_links_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.gratuity_income_links_id_seq OWNED BY public.gratuity_income_links.id;


--
-- Name: gst_audit_trail; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.gst_audit_trail (
    gst_id integer NOT NULL,
    transaction_date date NOT NULL,
    transaction_type character varying(30) NOT NULL,
    gross_amount numeric(15,2) NOT NULL,
    gst_rate numeric(5,4) NOT NULL,
    gst_amount numeric(15,2) NOT NULL,
    net_amount numeric(15,2) NOT NULL,
    gst_account character varying(50),
    source_document character varying(200),
    charter_id integer,
    receipt_id integer,
    reconciled_to_filing boolean DEFAULT false,
    filing_period character varying(20),
    audit_notes text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: gst_audit_trail_gst_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.gst_audit_trail_gst_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: gst_audit_trail_gst_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.gst_audit_trail_gst_id_seq OWNED BY public.gst_audit_trail.gst_id;


--
-- Name: gst_rates_lookup; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.gst_rates_lookup (
    province_code character(2) NOT NULL,
    province_name text NOT NULL,
    gst_rate numeric(6,4) NOT NULL,
    pst_rate numeric(6,4) DEFAULT 0,
    hst_rate numeric(6,4) DEFAULT 0,
    total_rate numeric(6,4) NOT NULL,
    effective_date date NOT NULL,
    notes text
);


--
-- Name: hos_14day_summary; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hos_14day_summary (
    summary_id integer NOT NULL,
    employee_id integer,
    start_date date,
    end_date date,
    total_on_duty numeric(6,2),
    total_off_duty numeric(6,2),
    compliant boolean,
    violations text,
    generated_at timestamp with time zone DEFAULT now()
);


--
-- Name: hos_14day_summary_summary_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hos_14day_summary_summary_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hos_14day_summary_summary_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hos_14day_summary_summary_id_seq OWNED BY public.hos_14day_summary.summary_id;


--
-- Name: hos_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hos_log (
    hos_id integer NOT NULL,
    charter_id integer,
    reserve_number character varying(50),
    employee_id integer,
    hos_date date,
    on_duty_start timestamp with time zone,
    break_start timestamp with time zone,
    break_duration integer,
    break_end timestamp with time zone,
    off_duty_at timestamp with time zone,
    on_duty_hours numeric(5,2),
    off_duty_hours numeric(5,2),
    exemption_claimed boolean DEFAULT false,
    exemption_type character varying(100),
    hos_status character varying(20),
    logbook_required boolean DEFAULT false,
    logbook_submitted boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    created_by character varying(100),
    locked_at timestamp with time zone,
    locked_by character varying(100)
);


--
-- Name: hos_log_hos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hos_log_hos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hos_log_hos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hos_log_hos_id_seq OWNED BY public.hos_log.hos_id;


--
-- Name: incident_costs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.incident_costs (
    cost_id integer NOT NULL,
    incident_id integer,
    cost_type character varying(100),
    description text,
    amount numeric(10,2) NOT NULL,
    rebate_percentage numeric(5,2) DEFAULT 0,
    rebate_amount numeric(10,2),
    net_cost numeric(10,2),
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: incident_costs_cost_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.incident_costs_cost_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: incident_costs_cost_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.incident_costs_cost_id_seq OWNED BY public.incident_costs.cost_id;


--
-- Name: incident_damage_tracking; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.incident_damage_tracking (
    id integer NOT NULL,
    incident_date date,
    incident_type character varying(100),
    charter_id integer,
    vehicle_id integer,
    description text,
    cleanup_cost numeric(12,2),
    repair_cost numeric(12,2),
    insurance_claim numeric(12,2),
    deductible_paid numeric(12,2),
    net_cost numeric(12,2),
    receipt_id integer,
    status character varying(50),
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: incident_damage_tracking_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.incident_damage_tracking_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: incident_damage_tracking_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.incident_damage_tracking_id_seq OWNED BY public.incident_damage_tracking.id;


--
-- Name: incidents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.incidents (
    incident_id integer NOT NULL,
    incident_number character varying(50),
    incident_date date,
    incident_time time without time zone,
    location text,
    incident_type character varying(50),
    severity character varying(20),
    description text,
    involved_employee character varying(50),
    involved_vehicle character varying(50),
    involved_client character varying(50),
    witness_name character varying(100),
    witness_contact character varying(50),
    police_report_number character varying(50),
    insurance_claim_number character varying(50),
    medical_attention_required boolean DEFAULT false,
    property_damage boolean DEFAULT false,
    estimated_damage_cost numeric(10,2),
    status character varying(20) DEFAULT 'reported'::character varying,
    reported_by character varying(100),
    investigated_by character varying(100),
    resolution text,
    follow_up_required boolean DEFAULT false,
    follow_up_date date,
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    charter_id integer,
    incident_start_time timestamp without time zone,
    replacement_vehicle_id integer,
    replacement_arrival_time timestamp without time zone,
    downtime_minutes integer,
    total_incident_cost numeric(10,2),
    guest_compensation_flag boolean DEFAULT false,
    guest_compensation_amount numeric(10,2)
);


--
-- Name: incidents_incident_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.incidents_incident_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: incidents_incident_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.incidents_incident_id_seq OWNED BY public.incidents.incident_id;


--
-- Name: income_ledger; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.income_ledger (
    income_id integer NOT NULL,
    payment_id integer,
    source_system character varying(50) DEFAULT 'payments'::character varying,
    transaction_date date NOT NULL,
    fiscal_year integer GENERATED ALWAYS AS (EXTRACT(year FROM transaction_date)) STORED,
    fiscal_quarter integer GENERATED ALWAYS AS (EXTRACT(quarter FROM transaction_date)) STORED,
    revenue_category character varying(100) NOT NULL,
    revenue_subcategory character varying(100),
    gross_amount numeric(12,2) NOT NULL,
    gst_collected numeric(12,2) DEFAULT 0,
    net_amount numeric(12,2) GENERATED ALWAYS AS ((gross_amount - gst_collected)) STORED,
    is_taxable boolean DEFAULT true,
    tax_province character varying(2) DEFAULT 'AB'::character varying,
    client_id integer,
    charter_id integer,
    reserve_number character varying(50),
    payment_method character varying(100),
    payment_reference character varying(200),
    description text,
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    created_by character varying(100) DEFAULT 'create_income_ledger.py'::character varying,
    reconciled boolean DEFAULT false,
    reconciled_date date,
    reconciled_by character varying(100)
);


--
-- Name: TABLE income_ledger; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.income_ledger IS 'Revenue tracking ledger with QuickBooks-style categorization and GST extraction';


--
-- Name: COLUMN income_ledger.revenue_category; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.income_ledger.revenue_category IS 'Top-level revenue classification: Operating Revenue, Other Revenue, Contra Revenue';


--
-- Name: COLUMN income_ledger.revenue_subcategory; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.income_ledger.revenue_subcategory IS 'Detailed revenue type: Charter Services, Retainers, Miscellaneous, etc.';


--
-- Name: COLUMN income_ledger.gst_collected; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.income_ledger.gst_collected IS 'GST extracted from gross_amount using included-tax formula (AB: 5%)';


--
-- Name: income_ledger_income_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.income_ledger_income_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: income_ledger_income_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.income_ledger_income_id_seq OWNED BY public.income_ledger.income_id;


--
-- Name: interest_allocations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.interest_allocations (
    id integer NOT NULL,
    credit_line_id integer,
    month_year character varying(7) NOT NULL,
    total_interest numeric(10,2) NOT NULL,
    business_interest numeric(10,2) NOT NULL,
    personal_interest numeric(10,2) NOT NULL,
    business_percentage integer NOT NULL,
    average_balance numeric(10,2),
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT interest_allocations_business_percentage_check CHECK (((business_percentage >= 0) AND (business_percentage <= 100)))
);


--
-- Name: TABLE interest_allocations; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.interest_allocations IS 'Monthly interest allocation between business and personal';


--
-- Name: interest_allocations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.interest_allocations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: interest_allocations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.interest_allocations_id_seq OWNED BY public.interest_allocations.id;


--
-- Name: invoice_line_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invoice_line_items (
    line_item_id integer NOT NULL,
    invoice_id integer NOT NULL,
    reserve_number character varying(50),
    line_type character varying(50),
    description character varying(500),
    quantity numeric(8,2),
    unit_price numeric(12,2),
    line_total numeric(12,2),
    taxable boolean DEFAULT true,
    gst_amount numeric(12,2),
    display_order integer,
    notes text
);


--
-- Name: invoice_line_items_line_item_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.invoice_line_items_line_item_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: invoice_line_items_line_item_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.invoice_line_items_line_item_id_seq OWNED BY public.invoice_line_items.line_item_id;


--
-- Name: invoice_tracking; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invoice_tracking (
    id integer NOT NULL,
    invoice_number character varying(50) NOT NULL,
    invoice_date date,
    document_id integer,
    amount numeric(10,2),
    status character varying(20) DEFAULT 'pending'::character varying,
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: invoice_tracking_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.invoice_tracking_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: invoice_tracking_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.invoice_tracking_id_seq OWNED BY public.invoice_tracking.id;


--
-- Name: invoices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invoices (
    invoice_id integer NOT NULL,
    reserve_number character varying(50) NOT NULL,
    invoice_number character varying(50),
    invoice_date date,
    due_date date,
    subtotal_taxable numeric(12,2),
    gst_amount numeric(12,2),
    subtotal_non_taxable numeric(12,2),
    invoice_total numeric(12,2),
    total_payments numeric(12,2),
    balance_due numeric(12,2),
    paid boolean DEFAULT false,
    invoice_status character varying(20),
    manager_approved boolean DEFAULT false,
    manager_approved_by character varying(100),
    manager_approved_at timestamp with time zone,
    sent_at timestamp with time zone,
    sent_method character varying(20),
    sent_by character varying(100),
    finalized_at timestamp with time zone,
    finalized_by character varying(100),
    created_at timestamp with time zone DEFAULT now(),
    created_by character varying(100),
    notes text
);


--
-- Name: invoices_invoice_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.invoices_invoice_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: invoices_invoice_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.invoices_invoice_id_seq OWNED BY public.invoices.invoice_id;


--
-- Name: journal_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.journal_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: journal_journal_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.journal_journal_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: legacy_import_status; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.legacy_import_status (
    import_id integer NOT NULL,
    data_year integer NOT NULL,
    data_source character varying(100) NOT NULL,
    import_status character varying(30) DEFAULT 'pending'::character varying,
    records_imported integer DEFAULT 0,
    records_reconciled integer DEFAULT 0,
    reconciliation_rate numeric(5,2),
    import_date timestamp without time zone,
    validation_status character varying(30),
    audit_compliance_score numeric(5,2),
    issues_identified text[],
    resolution_notes text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: legacy_import_status_import_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.legacy_import_status_import_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: legacy_import_status_import_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.legacy_import_status_import_id_seq OWNED BY public.legacy_import_status.import_id;


--
-- Name: lender_statement_transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lender_statement_transactions (
    id integer NOT NULL,
    txn_date date NOT NULL,
    description text NOT NULL,
    amount numeric(12,2) NOT NULL,
    balance numeric(12,2),
    source_file text,
    desc_hash character varying(32) NOT NULL,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: lender_statement_transactions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lender_statement_transactions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lender_statement_transactions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lender_statement_transactions_id_seq OWNED BY public.lender_statement_transactions.id;


--
-- Name: lms2026_payment_matches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lms2026_payment_matches (
    match_id bigint NOT NULL,
    payment_id integer,
    lms_payment_id integer,
    reserve_no character varying(50),
    amount numeric,
    payment_date date,
    lms_date date,
    match_method character varying(100),
    confidence numeric(4,2),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: lms2026_payment_matches_match_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lms2026_payment_matches_match_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lms2026_payment_matches_match_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lms2026_payment_matches_match_id_seq OWNED BY public.lms2026_payment_matches.match_id;


--
-- Name: lms2026_payments_staging; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lms2026_payments_staging (
    payment_id integer,
    reserve_no character varying(50),
    account_no character varying(50),
    amount numeric,
    last_updated timestamp without time zone,
    key character varying(255),
    customer_name character varying(255),
    customer_email character varying(255),
    customer_phone character varying(50),
    reserve_name character varying(255),
    pu_date date,
    pu_time timestamp without time zone,
    drop_off timestamp without time zone,
    pymt_type character varying(50),
    card_type character varying(50),
    card_no character varying(50),
    card_appr character varying(50),
    invoice_no character varying(50),
    notes text
);


--
-- Name: loan_transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.loan_transactions (
    id integer NOT NULL,
    transaction_date date NOT NULL,
    amount numeric(10,2) NOT NULL,
    direction character varying(20) NOT NULL,
    lender_name character varying(200),
    lender_email character varying(200),
    borrower_name character varying(200),
    description text,
    payment_method character varying(50),
    reference_number character varying(100),
    is_business_expense boolean DEFAULT false,
    business_expense_type character varying(100),
    reconciliation_payment_id integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: loan_transactions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.loan_transactions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: loan_transactions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.loan_transactions_id_seq OWNED BY public.loan_transactions.id;


--
-- Name: maintenance_activity_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maintenance_activity_types (
    activity_type_id integer NOT NULL,
    activity_code character varying(20) NOT NULL,
    activity_name character varying(100) NOT NULL,
    category character varying(50) NOT NULL,
    requires_odometer boolean DEFAULT true,
    requires_parts boolean DEFAULT false,
    default_interval_km integer,
    default_interval_months integer,
    description text,
    is_inspection boolean DEFAULT false,
    is_regulatory boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: maintenance_activity_types_activity_type_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maintenance_activity_types_activity_type_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maintenance_activity_types_activity_type_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maintenance_activity_types_activity_type_id_seq OWNED BY public.maintenance_activity_types.activity_type_id;


--
-- Name: maintenance_alerts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maintenance_alerts (
    alert_id integer NOT NULL,
    vehicle_id integer,
    maintenance_type character varying(100),
    alert_date date,
    alert_level character varying(20),
    due_date date,
    days_overdue integer,
    recipient_email character varying(100),
    sent_date timestamp without time zone,
    acknowledged boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: maintenance_alerts_alert_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maintenance_alerts_alert_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maintenance_alerts_alert_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maintenance_alerts_alert_id_seq OWNED BY public.maintenance_alerts.alert_id;


--
-- Name: maintenance_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maintenance_records (
    record_id integer NOT NULL,
    vehicle_id integer NOT NULL,
    activity_type_id integer NOT NULL,
    service_date date NOT NULL,
    odometer_reading integer,
    odometer_type character varying(10) DEFAULT 'km'::character varying,
    performed_by character varying(100),
    service_location character varying(100),
    work_order_number character varying(50),
    labor_cost numeric(10,2),
    parts_cost numeric(10,2),
    total_cost numeric(10,2),
    next_service_km integer,
    next_service_date date,
    notes text,
    inspection_passed boolean,
    warranty_until date,
    status character varying(20) DEFAULT 'completed'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    receipt_id integer,
    cost numeric(10,2),
    scheduled_date date,
    maintenance_status character varying(50),
    alert_sent boolean DEFAULT false,
    alert_sent_date date,
    alert_days_before integer DEFAULT 14,
    recurring_interval_days integer,
    recurring_interval_km integer,
    required_by_regulation boolean,
    compliance_category character varying(50),
    estimated_cost numeric(10,2),
    actual_cost numeric(10,2),
    scheduled_with_vendor character varying(200),
    vendor_confirmed boolean DEFAULT false,
    service_order_number character varying(50)
);


--
-- Name: maintenance_records_record_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maintenance_records_record_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maintenance_records_record_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maintenance_records_record_id_seq OWNED BY public.maintenance_records.record_id;


--
-- Name: maintenance_schedules_auto; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maintenance_schedules_auto (
    schedule_id integer NOT NULL,
    vehicle_id integer,
    maintenance_type character varying(100),
    due_date date,
    due_mileage integer,
    days_until_due integer,
    km_until_due integer,
    status character varying(50),
    last_completed_date date,
    next_due_date date,
    alert_threshold_days integer DEFAULT 14,
    alert_threshold_km integer DEFAULT 500,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: maintenance_schedules_auto_schedule_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maintenance_schedules_auto_schedule_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maintenance_schedules_auto_schedule_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maintenance_schedules_auto_schedule_id_seq OWNED BY public.maintenance_schedules_auto.schedule_id;


--
-- Name: maintenance_service_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maintenance_service_types (
    service_type_id integer NOT NULL,
    service_code character varying(10) NOT NULL,
    service_name character varying(255) NOT NULL,
    description text,
    category character varying(100),
    estimated_duration_hours numeric(4,2),
    is_mandatory boolean DEFAULT false,
    frequency_km integer,
    frequency_months integer,
    requires_downtime boolean DEFAULT true,
    cost_estimate_min numeric(10,2),
    cost_estimate_max numeric(10,2),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: maintenance_service_types_service_type_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maintenance_service_types_service_type_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maintenance_service_types_service_type_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maintenance_service_types_service_type_id_seq OWNED BY public.maintenance_service_types.service_type_id;


--
-- Name: major_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.major_events (
    event_id integer NOT NULL,
    title character varying(255) NOT NULL,
    event_date date NOT NULL,
    description text NOT NULL,
    category character varying(100),
    severity character varying(20) DEFAULT 'medium'::character varying,
    impact character varying(255),
    financial_impact numeric(12,2),
    status character varying(50) DEFAULT 'active'::character varying,
    notes text,
    attachments jsonb,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    created_by integer
);


--
-- Name: TABLE major_events; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.major_events IS 'Document major business events with impact analysis and ongoing notes';


--
-- Name: major_events_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.major_events_event_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: major_events_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.major_events_event_id_seq OWNED BY public.major_events.event_id;


--
-- Name: manual_check_payees; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.manual_check_payees (
    id integer NOT NULL,
    cheque_no integer,
    check_date date,
    payee_name character varying(200),
    amount numeric(12,2),
    matched_banking_id integer,
    matched_on timestamp without time zone,
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: manual_check_payees_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.manual_check_payees_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: manual_check_payees_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.manual_check_payees_id_seq OWNED BY public.manual_check_payees.id;


--
-- Name: master_relationships; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.master_relationships (
    id integer NOT NULL,
    source_table character varying(100),
    source_id integer,
    target_table character varying(100),
    target_id integer,
    relationship_type character varying(100),
    match_confidence numeric(3,2),
    match_method character varying(200),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: master_relationships_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.master_relationships_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: master_relationships_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.master_relationships_id_seq OWNED BY public.master_relationships.id;


--
-- Name: migration_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.migration_log (
    log_id integer NOT NULL,
    table_name character varying(100),
    operation character varying(50),
    records_processed integer,
    records_successful integer,
    records_failed integer,
    start_time timestamp without time zone,
    end_time timestamp without time zone,
    duration_seconds integer,
    status character varying(20),
    error_message text,
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: migration_log_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.migration_log_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: migration_log_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.migration_log_log_id_seq OWNED BY public.migration_log.log_id;


--
-- Name: missing_receipt_tracking; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.missing_receipt_tracking (
    missing_id integer NOT NULL,
    transaction_date date NOT NULL,
    card_transaction_amount numeric(15,2) NOT NULL,
    merchant_name character varying(200),
    transaction_description text,
    estimated_gst numeric(15,2),
    estimated_net numeric(15,2),
    expense_category character varying(100),
    bank_reference character varying(200),
    recovery_status character varying(50) DEFAULT 'missing'::character varying,
    recovery_method character varying(100),
    audit_impact character varying(20) DEFAULT 'low'::character varying,
    notes text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: missing_receipt_tracking_missing_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.missing_receipt_tracking_missing_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: missing_receipt_tracking_missing_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.missing_receipt_tracking_missing_id_seq OWNED BY public.missing_receipt_tracking.missing_id;


--
-- Name: monthly_float_trends; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.monthly_float_trends AS
 SELECT date_trunc('month'::text, (float_date)::timestamp with time zone) AS month,
    to_char((float_date)::timestamp with time zone, 'YYYY-MM'::text) AS month_text,
    count(*) AS float_count,
    sum(abs(float_amount)) AS total_amount,
    avg(abs(float_amount)) AS avg_amount,
    count(
        CASE
            WHEN ((reconciliation_status)::text = 'reconciled'::text) THEN 1
            ELSE NULL::integer
        END) AS reconciled_count,
    (((count(
        CASE
            WHEN ((reconciliation_status)::text = 'reconciled'::text) THEN 1
            ELSE NULL::integer
        END))::numeric * 100.0) / (NULLIF(count(*), 0))::numeric) AS reconciliation_rate
   FROM public.chauffeur_float_tracking
  WHERE (float_date >= (CURRENT_DATE - '1 year'::interval))
  GROUP BY (date_trunc('month'::text, (float_date)::timestamp with time zone)), (to_char((float_date)::timestamp with time zone, 'YYYY-MM'::text))
  ORDER BY (date_trunc('month'::text, (float_date)::timestamp with time zone));


--
-- Name: monthly_work_assignments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.monthly_work_assignments (
    assignment_id integer NOT NULL,
    employee_id integer NOT NULL,
    work_month date NOT NULL,
    assignment_type character varying(50) NOT NULL,
    client_account_number character varying(20),
    project_name character varying(100),
    estimated_hours numeric(6,2),
    actual_hours numeric(6,2),
    hourly_rate numeric(8,2),
    fixed_amount numeric(10,2),
    status character varying(20) DEFAULT 'assigned'::character varying,
    start_date date,
    completion_date date,
    description text,
    notes text,
    assigned_by integer,
    assigned_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: TABLE monthly_work_assignments; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.monthly_work_assignments IS 'Tracks ongoing work assignments for bookkeeping, cleaning, and other non-charter work';


--
-- Name: monthly_work_assignments_assignment_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.monthly_work_assignments_assignment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: monthly_work_assignments_assignment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.monthly_work_assignments_assignment_id_seq OWNED BY public.monthly_work_assignments.assignment_id;


--
-- Name: owner_equity_accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.owner_equity_accounts (
    equity_account_id integer NOT NULL,
    owner_name character varying(100) NOT NULL,
    account_type character varying(30) NOT NULL,
    current_balance numeric(12,2) DEFAULT 0,
    ytd_business_expenses numeric(12,2) DEFAULT 0,
    ytd_personal_allocation numeric(12,2) DEFAULT 0,
    ytd_salary_equivalent numeric(12,2) DEFAULT 0,
    cibc_card_number character varying(20),
    card_nickname character varying(50),
    monthly_limit numeric(12,2),
    t4_reportable_income numeric(12,2) DEFAULT 0,
    t4_corrections_needed boolean DEFAULT false,
    correction_notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: TABLE owner_equity_accounts; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.owner_equity_accounts IS 'Owner (Paul) business expense vs personal allocation tracking';


--
-- Name: owner_equity_accounts_equity_account_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.owner_equity_accounts_equity_account_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: owner_equity_accounts_equity_account_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.owner_equity_accounts_equity_account_id_seq OWNED BY public.owner_equity_accounts.equity_account_id;


--
-- Name: owner_expense_transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.owner_expense_transactions (
    transaction_id integer NOT NULL,
    equity_account_id integer NOT NULL,
    transaction_date date NOT NULL,
    transaction_type character varying(30) NOT NULL,
    description text NOT NULL,
    gross_amount numeric(12,2) NOT NULL,
    business_portion numeric(12,2) DEFAULT 0,
    personal_portion numeric(12,2) DEFAULT 0,
    tax_implications text,
    expense_category character varying(50),
    vendor_name character varying(200),
    receipt_reference character varying(100),
    cibc_transaction_id character varying(50),
    banking_transaction_id integer,
    card_used character varying(20),
    requires_approval boolean DEFAULT true,
    approved_by character varying(100),
    approval_date timestamp without time zone,
    approval_notes text,
    journal_entry_id integer,
    qb_account character varying(100),
    cra_category character varying(50),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: TABLE owner_expense_transactions; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.owner_expense_transactions IS 'Detailed owner expense transactions with CIBC card integration';


--
-- Name: COLUMN owner_expense_transactions.business_portion; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.owner_expense_transactions.business_portion IS 'Business deductible portion of expense';


--
-- Name: COLUMN owner_expense_transactions.personal_portion; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.owner_expense_transactions.personal_portion IS 'Personal income portion (counted as owner income)';


--
-- Name: owner_expense_transactions_transaction_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.owner_expense_transactions_transaction_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: owner_expense_transactions_transaction_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.owner_expense_transactions_transaction_id_seq OWNED BY public.owner_expense_transactions.transaction_id;


--
-- Name: paul_pay_tracking; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.paul_pay_tracking (
    id integer NOT NULL,
    year integer,
    month integer,
    pay_period character varying(50),
    calculated_pay numeric(12,2),
    withheld_amount numeric(12,2),
    withhold_reason text,
    status character varying(50),
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: paul_pay_tracking_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.paul_pay_tracking_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: paul_pay_tracking_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.paul_pay_tracking_id_seq OWNED BY public.paul_pay_tracking.id;


--
-- Name: pay_periods; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pay_periods (
    pay_period_id integer NOT NULL,
    fiscal_year integer NOT NULL,
    period_number integer NOT NULL,
    period_start_date date NOT NULL,
    period_end_date date NOT NULL,
    pay_date date NOT NULL,
    is_closed boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    notes text
);


--
-- Name: pay_periods_pay_period_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pay_periods_pay_period_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pay_periods_pay_period_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pay_periods_pay_period_id_seq OWNED BY public.pay_periods.pay_period_id;


--
-- Name: payables; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payables (
    payable_id integer NOT NULL,
    vendor_name character varying(100),
    vendor_contact character varying(100),
    vendor_phone character varying(20),
    vendor_address text,
    invoice_number character varying(50),
    invoice_date date,
    due_date date,
    amount numeric(12,2) DEFAULT 0,
    tax_amount numeric(12,2) DEFAULT 0,
    total_amount numeric(12,2) DEFAULT 0,
    status character varying(20) DEFAULT 'pending'::character varying,
    payment_date date,
    payment_method character varying(50),
    check_number character varying(50),
    description text,
    category character varying(50),
    department character varying(50),
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    qb_txn_type character varying(50),
    qb_trans_num character varying(50),
    payment_status character varying(20) DEFAULT 'Open'::character varying,
    paid_amount numeric(15,2) DEFAULT 0,
    remaining_balance numeric(15,2),
    discount_amount numeric(15,2) DEFAULT 0,
    aging_days integer
);


--
-- Name: COLUMN payables.qb_txn_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.payables.qb_txn_type IS 'QuickBooks transaction type (Bill, VendorCredit, ItemReceipt, etc.)';


--
-- Name: COLUMN payables.payment_status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.payables.payment_status IS 'Payment status (Open, Paid, PartiallyPaid, Overdue)';


--
-- Name: COLUMN payables.aging_days; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.payables.aging_days IS 'Days overdue (negative = not due yet, positive = days past due)';


--
-- Name: payables_payable_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.payables_payable_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payables_payable_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.payables_payable_id_seq OWNED BY public.payables.payable_id;


--
-- Name: payday_loan_payments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payday_loan_payments (
    id integer NOT NULL,
    loan_id integer NOT NULL,
    due_date date NOT NULL,
    amount_due numeric(12,2) NOT NULL,
    status character varying(20) DEFAULT 'scheduled'::character varying,
    paid_date date,
    matched_amount numeric(12,2),
    match_confidence numeric(5,2),
    banking_transaction_id bigint,
    receipt_id bigint,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    match_method text
);


--
-- Name: payday_loan_payments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.payday_loan_payments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payday_loan_payments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.payday_loan_payments_id_seq OWNED BY public.payday_loan_payments.id;


--
-- Name: payday_loans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payday_loans (
    id integer NOT NULL,
    lender_name character varying(200),
    agreement_date date NOT NULL,
    principal numeric(12,2) NOT NULL,
    fee_total numeric(12,2) NOT NULL,
    apr_percent numeric(7,2),
    term_days integer,
    total_repay numeric(12,2) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    notes text,
    source_hash text
);


--
-- Name: payday_loans_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.payday_loans_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payday_loans_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.payday_loans_id_seq OWNED BY public.payday_loans.id;


--
-- Name: payment_customer_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_customer_links (
    payment_id integer NOT NULL,
    customer_account_no character varying(10),
    customer_name text,
    customer_email text,
    link_method character varying(50),
    confidence_score numeric(3,2),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: payment_matches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_matches (
    match_id integer NOT NULL,
    charter_id integer,
    square_payment_id text,
    match_type character varying(50),
    confidence_score numeric(5,2),
    amount_difference numeric(10,2),
    date_difference_days integer,
    match_details jsonb,
    created_at timestamp without time zone DEFAULT now(),
    status character varying(20) DEFAULT 'PENDING'::character varying,
    deposit_key character varying(30),
    hash_pattern character varying(30),
    verification_status character varying(20) DEFAULT 'PENDING'::character varying,
    locked boolean DEFAULT false
);


--
-- Name: payment_matches_match_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.payment_matches_match_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payment_matches_match_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.payment_matches_match_id_seq OWNED BY public.payment_matches.match_id;


--
-- Name: payments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payments (
    payment_id integer NOT NULL,
    account_number character varying(50),
    reserve_number character varying(50),
    amount numeric(12,2),
    payment_key character varying(100),
    last_updated timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    payment_method character varying(50),
    payment_date date,
    status character varying(20) DEFAULT 'pending'::character varying,
    notes text,
    payment_code_4char character varying(4),
    updated_at timestamp without time zone,
    reference_number character varying(50),
    is_deposited boolean DEFAULT false,
    payment_label character varying(50),
    verified boolean DEFAULT false,
    verified_date timestamp without time zone,
    verified_by character varying(100),
    square_fee_gl_code character varying(20),
    square_fee_gl_description text,
    CONSTRAINT chk_payment_method CHECK (((payment_method)::text = ANY ((ARRAY['cash'::character varying, 'check'::character varying, 'credit_card'::character varying, 'debit_card'::character varying, 'bank_transfer'::character varying, 'e_transfer'::character varying, 'trade_of_services'::character varying, 'unknown'::character varying, 'credit_adjustment'::character varying])::text[]))),
    CONSTRAINT chk_payment_status CHECK (((status)::text = ANY (ARRAY[('pending'::character varying)::text, ('paid'::character varying)::text, ('partial'::character varying)::text, ('failed'::character varying)::text, ('refunded'::character varying)::text, ('cancelled'::character varying)::text])))
);


--
-- Name: COLUMN payments.payment_method; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.payments.payment_method IS 'Method of payment: cash, check, credit_card, debit_card, bank_transfer';


--
-- Name: COLUMN payments.payment_date; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.payments.payment_date IS 'Date when payment was processed';


--
-- Name: COLUMN payments.status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.payments.status IS 'Payment status: pending, paid, partial, failed, refunded, cancelled';


--
-- Name: payments_payment_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.payments_payment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payments_payment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.payments_payment_id_seq OWNED BY public.payments.payment_id;


--
-- Name: payroll_adjustments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payroll_adjustments (
    adjustment_id integer NOT NULL,
    driver_payroll_id integer NOT NULL,
    adjustment_type character varying(50) NOT NULL,
    gross_amount numeric(12,2) NOT NULL,
    net_amount numeric(12,2),
    rationale text,
    source_reference text,
    original_pay_date date,
    year integer,
    month integer,
    has_charter_link boolean DEFAULT false,
    has_employee_link boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    created_by character varying(100)
);


--
-- Name: TABLE payroll_adjustments; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.payroll_adjustments IS 'Segregated payroll adjustments (reconciliations, corrections) excluded from wage KPIs';


--
-- Name: payroll_adjustments_adjustment_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.payroll_adjustments_adjustment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payroll_adjustments_adjustment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.payroll_adjustments_adjustment_id_seq OWNED BY public.payroll_adjustments.adjustment_id;


--
-- Name: payroll_comparison; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payroll_comparison (
    id integer NOT NULL,
    employee_number character varying(50),
    employee_name character varying(200),
    pay_period_start date,
    pay_period_end date,
    gross_pay numeric(10,2),
    deductions numeric(10,2),
    net_pay numeric(10,2),
    hours_paid numeric(8,2),
    hourly_rate numeric(6,2),
    overtime_hours numeric(8,2) DEFAULT 0,
    overtime_pay numeric(10,2) DEFAULT 0,
    regular_pay numeric(10,2) DEFAULT 0,
    bonus_pay numeric(10,2) DEFAULT 0,
    commission_pay numeric(10,2) DEFAULT 0,
    source_file character varying(500),
    import_notes text,
    imported_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: payroll_comparison_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.payroll_comparison_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payroll_comparison_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.payroll_comparison_id_seq OWNED BY public.payroll_comparison.id;


--
-- Name: payroll_fix_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payroll_fix_audit (
    id integer NOT NULL,
    driver_payroll_id integer NOT NULL,
    charter_id integer,
    reserve_number character varying(50),
    old_employee_id integer,
    old_driver_id character varying(50),
    new_employee_id integer,
    new_driver_id character varying(50),
    reason character varying(200),
    fixed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: payroll_fix_audit_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.payroll_fix_audit_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payroll_fix_audit_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.payroll_fix_audit_id_seq OWNED BY public.payroll_fix_audit.id;


--
-- Name: payroll_fix_rollback_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payroll_fix_rollback_audit (
    id integer NOT NULL,
    backup_table character varying(200) NOT NULL,
    restored_rows integer NOT NULL,
    rolled_back_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: payroll_fix_rollback_audit_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.payroll_fix_rollback_audit_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payroll_fix_rollback_audit_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.payroll_fix_rollback_audit_id_seq OWNED BY public.payroll_fix_rollback_audit.id;


--
-- Name: performance_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.performance_metrics (
    metric_id integer NOT NULL,
    metric_category character varying(50) NOT NULL,
    metric_name character varying(100) NOT NULL,
    metric_description text,
    current_value numeric(15,4),
    previous_value numeric(15,4),
    target_value numeric(15,4),
    unit_of_measure character varying(50),
    calculation_method text,
    data_source character varying(100),
    period_type character varying(20) DEFAULT 'monthly'::character varying,
    period_start_date date,
    period_end_date date,
    warning_threshold numeric(15,4),
    critical_threshold numeric(15,4),
    status character varying(20) DEFAULT 'active'::character varying,
    last_calculated timestamp without time zone,
    next_calculation timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    created_by character varying(100) DEFAULT 'system'::character varying
);


--
-- Name: performance_metrics_metric_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.performance_metrics_metric_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: performance_metrics_metric_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.performance_metrics_metric_id_seq OWNED BY public.performance_metrics.metric_id;


--
-- Name: permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.permissions (
    permission_id integer NOT NULL,
    module character varying(50) NOT NULL,
    action character varying(20) NOT NULL,
    description text
);


--
-- Name: permissions_permission_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.permissions_permission_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: permissions_permission_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.permissions_permission_id_seq OWNED BY public.permissions.permission_id;


--
-- Name: personal_expenses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.personal_expenses (
    id integer NOT NULL,
    date date NOT NULL,
    description text NOT NULL,
    amount numeric(10,2) NOT NULL,
    category character varying(50) DEFAULT 'uncategorized'::character varying,
    payment_method character varying(50) NOT NULL,
    credit_line character varying(100),
    business_percentage integer DEFAULT 100,
    interest_amount numeric(10,2) DEFAULT 0,
    receipt_url text,
    notes text,
    status character varying(20) DEFAULT 'pending'::character varying,
    reimbursement_date date,
    reimbursement_amount numeric(10,2),
    created_by character varying(100),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    source_txn_key text,
    import_source text,
    liters numeric(12,3),
    price_per_liter numeric(12,3),
    fuel_subtotal numeric(14,2),
    gst_amount numeric(14,2),
    vehicle_code text,
    vehicle_id text,
    tax_category character varying(100),
    cra_code character varying(50),
    is_tax_deductible boolean DEFAULT false,
    deduction_percentage integer DEFAULT 100,
    calculated_deduction numeric(10,2),
    tax_notes text,
    CONSTRAINT personal_expenses_business_percentage_check CHECK (((business_percentage >= 0) AND (business_percentage <= 100))),
    CONSTRAINT personal_expenses_status_check CHECK (((status)::text = ANY (ARRAY[('pending'::character varying)::text, ('approved'::character varying)::text, ('reimbursed'::character varying)::text, ('rejected'::character varying)::text])))
);


--
-- Name: TABLE personal_expenses; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.personal_expenses IS 'Tracks company expenses paid through personal accounts';


--
-- Name: personal_expenses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.personal_expenses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: personal_expenses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.personal_expenses_id_seq OWNED BY public.personal_expenses.id;


--
-- Name: personal_expenses_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.personal_expenses_summary AS
 SELECT date_trunc('month'::text, (date)::timestamp with time zone) AS month,
    category,
    payment_method,
    count(*) AS transaction_count,
    sum(amount) AS total_amount,
    sum(((amount * (business_percentage)::numeric) / (100)::numeric)) AS business_amount,
    sum(((amount * ((100 - business_percentage))::numeric) / (100)::numeric)) AS personal_amount,
    sum(((interest_amount * (business_percentage)::numeric) / (100)::numeric)) AS business_interest
   FROM public.personal_expenses
  WHERE ((status)::text <> 'rejected'::text)
  GROUP BY (date_trunc('month'::text, (date)::timestamp with time zone)), category, payment_method
  ORDER BY (date_trunc('month'::text, (date)::timestamp with time zone)) DESC, category;


--
-- Name: posting_queue; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.posting_queue (
    id bigint NOT NULL,
    event_type character varying(50) NOT NULL,
    event_reference character varying(100),
    payload jsonb NOT NULL,
    status character varying(20) DEFAULT 'PENDING'::character varying,
    error_message text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    processed_at timestamp without time zone
);


--
-- Name: posting_queue_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.posting_queue_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: posting_queue_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.posting_queue_id_seq OWNED BY public.posting_queue.id;


--
-- Name: posting_reversals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.posting_reversals (
    id bigint NOT NULL,
    original_batch_id bigint NOT NULL,
    reversal_batch_id bigint NOT NULL,
    reason text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: posting_reversals_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.posting_reversals_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: posting_reversals_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.posting_reversals_id_seq OWNED BY public.posting_reversals.id;


--
-- Name: pre_inspection_issues; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pre_inspection_issues (
    issue_id integer NOT NULL,
    inspection_id integer,
    category character varying(100),
    issue_description text NOT NULL,
    severity character varying(20),
    photo_url text,
    resolved boolean DEFAULT false,
    resolved_date date,
    resolved_by character varying(100),
    resolution_notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: pre_inspection_issues_issue_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pre_inspection_issues_issue_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pre_inspection_issues_issue_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pre_inspection_issues_issue_id_seq OWNED BY public.pre_inspection_issues.issue_id;


--
-- Name: quotations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.quotations (
    quote_id integer NOT NULL,
    charter_id integer,
    reserve_number character varying(20),
    client_id integer,
    quote_date date NOT NULL,
    pickup_location character varying(200),
    dropoff_location character varying(200),
    pax_count integer,
    hourly_hours numeric(8,2),
    hourly_rate numeric(10,2),
    hourly_total numeric(12,2),
    package_description character varying(200),
    package_price numeric(12,2),
    split_run_json text,
    split_run_total numeric(12,2),
    gst_rate numeric(5,4) DEFAULT 0.05,
    gratuity_rate numeric(5,4) DEFAULT 0.18,
    extra_charges_json text,
    selected_option character varying(20),
    total_quote numeric(12,2),
    status character varying(50) DEFAULT 'pending'::character varying,
    sent_to_client boolean DEFAULT false,
    sent_date timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: quotations_quote_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.quotations_quote_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: quotations_quote_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.quotations_quote_id_seq OWNED BY public.quotations.quote_id;


--
-- Name: raw_file_inventory; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.raw_file_inventory (
    id integer NOT NULL,
    scan_time timestamp without time zone DEFAULT now() NOT NULL,
    root_path text NOT NULL,
    rel_path text NOT NULL,
    file_name text NOT NULL,
    ext text,
    size_bytes bigint,
    md5 text,
    sha1 text,
    first_line text,
    last_line text,
    notes text
);


--
-- Name: raw_file_inventory_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.raw_file_inventory_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: raw_file_inventory_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.raw_file_inventory_id_seq OWNED BY public.raw_file_inventory.id;


--
-- Name: receipt_banking_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.receipt_banking_links (
    link_id integer NOT NULL,
    receipt_id integer NOT NULL,
    transaction_id integer NOT NULL,
    linked_amount numeric(12,2) NOT NULL,
    link_status character varying(50) DEFAULT 'matched'::character varying,
    linked_by integer,
    linked_at timestamp without time zone DEFAULT now(),
    notes text,
    CONSTRAINT receipt_banking_links_link_status_check CHECK (((link_status)::text = ANY ((ARRAY['matched'::character varying, 'partial'::character varying, 'unmatched'::character varying])::text[]))),
    CONSTRAINT receipt_banking_links_linked_amount_check CHECK ((linked_amount > (0)::numeric))
);


--
-- Name: receipt_banking_links_link_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.receipt_banking_links_link_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: receipt_banking_links_link_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.receipt_banking_links_link_id_seq OWNED BY public.receipt_banking_links.link_id;


--
-- Name: receipt_cashbox_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.receipt_cashbox_links (
    link_id integer NOT NULL,
    receipt_id integer NOT NULL,
    cashbox_amount numeric(12,2) NOT NULL,
    float_reimbursement_type character varying(50) DEFAULT 'other'::character varying,
    driver_id integer,
    driver_notes text,
    confirmed_by integer,
    confirmed_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now(),
    CONSTRAINT receipt_cashbox_links_cashbox_amount_check CHECK ((cashbox_amount > (0)::numeric)),
    CONSTRAINT receipt_cashbox_links_float_reimbursement_type_check CHECK (((float_reimbursement_type)::text = ANY ((ARRAY['float_out'::character varying, 'reimbursed'::character varying, 'cash_received'::character varying, 'other'::character varying])::text[])))
);


--
-- Name: receipt_cashbox_links_link_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.receipt_cashbox_links_link_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: receipt_cashbox_links_link_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.receipt_cashbox_links_link_id_seq OWNED BY public.receipt_cashbox_links.link_id;


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
    notes text
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
-- Name: receipt_deliveries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.receipt_deliveries (
    delivery_id integer NOT NULL,
    charter_id integer,
    client_email character varying(200),
    receipt_type character varying(50),
    delivery_method character varying(50),
    pdf_url text,
    sent_date timestamp without time zone,
    opened_date timestamp without time zone,
    downloaded_date timestamp without time zone,
    sent_by character varying(100),
    status character varying(50),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: receipt_deliveries_delivery_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.receipt_deliveries_delivery_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: receipt_deliveries_delivery_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.receipt_deliveries_delivery_id_seq OWNED BY public.receipt_deliveries.delivery_id;


--
-- Name: receipt_gst_adjustment_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.receipt_gst_adjustment_audit (
    id integer NOT NULL,
    receipt_id integer NOT NULL,
    before_gst numeric(12,2),
    after_gst numeric(12,2),
    before_category text,
    after_category text,
    rate_applied numeric(6,4) NOT NULL,
    reason text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: receipt_gst_adjustment_audit_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.receipt_gst_adjustment_audit_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: receipt_gst_adjustment_audit_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.receipt_gst_adjustment_audit_id_seq OWNED BY public.receipt_gst_adjustment_audit.id;


--
-- Name: receipt_line_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.receipt_line_items (
    line_item_id integer NOT NULL,
    receipt_id integer,
    line_number integer NOT NULL,
    item_description text,
    category character varying(100) NOT NULL,
    subcategory character varying(100),
    quantity numeric(10,2) DEFAULT 1,
    unit_price numeric(12,2),
    line_amount numeric(12,2) NOT NULL,
    gst_amount numeric(12,2) DEFAULT 0,
    is_personal boolean DEFAULT false,
    is_driver_reimbursable boolean DEFAULT false,
    employee_id integer,
    vehicle_id integer,
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: receipt_line_items_line_item_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.receipt_line_items_line_item_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: receipt_line_items_line_item_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.receipt_line_items_line_item_id_seq OWNED BY public.receipt_line_items.line_item_id;


--
-- Name: receipt_review_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.receipt_review_summary AS
 SELECT count(*) AS total_receipts,
    count(
        CASE
            WHEN ((receipt_review_status)::text = 'verified'::text) THEN 1
            ELSE NULL::integer
        END) AS verified_count,
    count(
        CASE
            WHEN ((receipt_review_status)::text = 'missing'::text) THEN 1
            ELSE NULL::integer
        END) AS missing_count,
    count(
        CASE
            WHEN ((receipt_review_status)::text = 'unreadable'::text) THEN 1
            ELSE NULL::integer
        END) AS unreadable_count,
    count(
        CASE
            WHEN ((receipt_review_status)::text = 'data-error'::text) THEN 1
            ELSE NULL::integer
        END) AS data_error_count,
    count(
        CASE
            WHEN (receipt_review_status IS NULL) THEN 1
            ELSE NULL::integer
        END) AS not_reviewed_count,
    round(((100.0 * (count(
        CASE
            WHEN ((receipt_review_status)::text = 'verified'::text) THEN 1
            ELSE NULL::integer
        END))::numeric) / (NULLIF(count(*), 0))::numeric), 1) AS verified_percentage,
    min(receipt_reviewed_at) AS first_review_date,
    max(receipt_reviewed_at) AS last_review_date
   FROM public.receipts
  WHERE ((exclude_from_reports = false) OR (exclude_from_reports IS NULL));


--
-- Name: receipt_verification_audit_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.receipt_verification_audit_summary AS
 SELECT count(*) AS total_receipts,
    sum(
        CASE
            WHEN verified_by_edit THEN 1
            ELSE 0
        END) AS verified_count,
    sum(
        CASE
            WHEN ((NOT verified_by_edit) OR (verified_by_edit IS NULL)) THEN 1
            ELSE 0
        END) AS unverified_count,
    round(((100.0 * (sum(
        CASE
            WHEN verified_by_edit THEN 1
            ELSE 0
        END))::numeric) / (NULLIF(count(*), 0))::numeric), 1) AS verification_percentage,
    min(verified_at) AS first_verification_date,
    max(verified_at) AS last_verification_date,
    count(DISTINCT verified_by_user) AS unique_verifiers
   FROM public.receipts
  WHERE ((business_personal <> 'personal'::text) OR (business_personal IS NULL));


--
-- Name: receipt_verification_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.receipt_verification_summary AS
 SELECT count(*) AS total_receipts,
    sum(
        CASE
            WHEN is_paper_verified THEN 1
            ELSE 0
        END) AS physically_verified_count,
    sum(
        CASE
            WHEN (NOT is_paper_verified) THEN 1
            ELSE 0
        END) AS unverified_count,
    round(((100.0 * (sum(
        CASE
            WHEN is_paper_verified THEN 1
            ELSE 0
        END))::numeric) / (NULLIF(count(*), 0))::numeric), 1) AS verification_percentage
   FROM public.receipts
  WHERE ((business_personal <> 'personal'::text) AND (is_personal_purchase = false));


--
-- Name: receipts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.receipts_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: receipts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.receipts_id_seq OWNED BY public.receipts.receipt_id;


--
-- Name: receipts_ingest_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.receipts_ingest_log (
    id integer NOT NULL,
    file_name text NOT NULL,
    file_hash text NOT NULL,
    started_at timestamp without time zone DEFAULT now(),
    finished_at timestamp without time zone,
    status text,
    rows_inserted integer DEFAULT 0,
    rows_updated integer DEFAULT 0,
    error text
);


--
-- Name: receipts_ingest_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.receipts_ingest_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: receipts_ingest_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.receipts_ingest_log_id_seq OWNED BY public.receipts_ingest_log.id;


--
-- Name: receipts_needing_attention; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.receipts_needing_attention AS
 SELECT receipt_id,
    receipt_date,
    vendor_name,
    gross_amount,
    category,
    banking_transaction_id,
    receipt_review_status,
    receipt_review_notes,
    receipt_reviewed_at,
    receipt_reviewed_by
   FROM public.receipts
  WHERE ((receipt_review_status)::text = ANY ((ARRAY['missing'::character varying, 'unreadable'::character varying, 'data-error'::character varying])::text[]))
  ORDER BY receipt_date DESC;


--
-- Name: receipts_square_dedupe_backup_20260201; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.receipts_square_dedupe_backup_20260201 (
    receipt_id bigint,
    source_system text,
    source_reference text,
    receipt_date date,
    vendor_name text,
    description text,
    currency character(3),
    gross_amount numeric(14,2),
    gst_amount numeric(14,2),
    expense_account text,
    payment_method text,
    source_hash text,
    created_at timestamp with time zone,
    document_type character varying(50),
    type character varying(50),
    tax_category character varying(50),
    card_type character varying(50),
    card_number character varying(50),
    comment text,
    pay_method text,
    mapped_bank_account_id integer,
    canonical_pay_method text,
    category character varying(100),
    expense numeric(12,2),
    vehicle_id integer,
    vehicle_number character varying(50),
    fuel numeric(12,2),
    created_from_banking boolean,
    revenue numeric,
    gst_code text,
    split_key text,
    split_group_total numeric(12,2),
    fuel_amount numeric(12,2),
    deductible_status text,
    business_personal text,
    source_file text,
    gl_account_code character varying(10),
    gl_account_name character varying(200),
    gl_subcategory character varying(200),
    auto_categorized boolean,
    net_amount numeric,
    is_split_receipt boolean,
    is_personal_purchase boolean,
    owner_personal_amount numeric(12,2),
    is_driver_reimbursement boolean,
    banking_transaction_id integer,
    receipt_source character varying(50),
    display_color character varying(20),
    canonical_vendor character varying(255),
    is_transfer boolean,
    verified_source text,
    is_verified_banking boolean,
    potential_duplicate boolean,
    duplicate_check_key text,
    is_nsf boolean,
    is_voided boolean,
    exclude_from_reports boolean,
    vendor_account_id bigint,
    fiscal_year integer,
    invoice_date date,
    is_paper_verified boolean,
    paper_verification_date timestamp without time zone,
    verified_by_user character varying(255),
    employee_id integer,
    charter_id integer,
    reserve_number character varying(20),
    gst_exempt boolean,
    split_status character varying(50),
    split_group_id integer,
    verified_by_edit boolean,
    verified_at timestamp without time zone,
    rn bigint
);


--
-- Name: receipts_square_final_backup_20260201; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.receipts_square_final_backup_20260201 (
    receipt_id bigint,
    source_system text,
    source_reference text,
    receipt_date date,
    vendor_name text,
    description text,
    currency character(3),
    gross_amount numeric(14,2),
    gst_amount numeric(14,2),
    expense_account text,
    payment_method text,
    source_hash text,
    created_at timestamp with time zone,
    document_type character varying(50),
    type character varying(50),
    tax_category character varying(50),
    card_type character varying(50),
    card_number character varying(50),
    comment text,
    pay_method text,
    mapped_bank_account_id integer,
    canonical_pay_method text,
    category character varying(100),
    expense numeric(12,2),
    vehicle_id integer,
    vehicle_number character varying(50),
    fuel numeric(12,2),
    created_from_banking boolean,
    revenue numeric,
    gst_code text,
    split_key text,
    split_group_total numeric(12,2),
    fuel_amount numeric(12,2),
    deductible_status text,
    business_personal text,
    source_file text,
    gl_account_code character varying(10),
    gl_account_name character varying(200),
    gl_subcategory character varying(200),
    auto_categorized boolean,
    net_amount numeric,
    is_split_receipt boolean,
    is_personal_purchase boolean,
    owner_personal_amount numeric(12,2),
    is_driver_reimbursement boolean,
    banking_transaction_id integer,
    receipt_source character varying(50),
    display_color character varying(20),
    canonical_vendor character varying(255),
    is_transfer boolean,
    verified_source text,
    is_verified_banking boolean,
    potential_duplicate boolean,
    duplicate_check_key text,
    is_nsf boolean,
    is_voided boolean,
    exclude_from_reports boolean,
    vendor_account_id bigint,
    fiscal_year integer,
    invoice_date date,
    is_paper_verified boolean,
    paper_verification_date timestamp without time zone,
    verified_by_user character varying(255),
    employee_id integer,
    charter_id integer,
    reserve_number character varying(20),
    gst_exempt boolean,
    split_status character varying(50),
    split_group_id integer,
    verified_by_edit boolean,
    verified_at timestamp without time zone
);


--
-- Name: recurring_invoices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recurring_invoices (
    id integer NOT NULL,
    vendor_name character varying(200) NOT NULL,
    invoice_type character varying(50) NOT NULL,
    charge_date date NOT NULL,
    description text,
    base_amount numeric(12,2) NOT NULL,
    gst_amount numeric(12,2) NOT NULL,
    total_amount numeric(12,2) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: recurring_invoices_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.recurring_invoices_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: recurring_invoices_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.recurring_invoices_id_seq OWNED BY public.recurring_invoices.id;


--
-- Name: refunds_cancellations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.refunds_cancellations (
    id integer NOT NULL,
    charter_id integer,
    original_amount numeric(12,2),
    refund_amount numeric(12,2),
    cancellation_fee numeric(12,2),
    refund_date date,
    reason character varying(200),
    refund_method character varying(50),
    payment_id integer,
    processing_cost numeric(12,2),
    net_loss numeric(12,2),
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: refunds_cancellations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.refunds_cancellations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: refunds_cancellations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.refunds_cancellations_id_seq OWNED BY public.refunds_cancellations.id;


--
-- Name: rent_debt_ledger; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rent_debt_ledger (
    id integer NOT NULL,
    transaction_date date NOT NULL,
    transaction_type character varying(20) NOT NULL,
    vendor_name character varying(200) NOT NULL,
    description text,
    charge_amount numeric(12,2) DEFAULT 0,
    payment_amount numeric(12,2) DEFAULT 0,
    running_balance numeric(12,2) NOT NULL,
    banking_transaction_id bigint,
    recurring_invoice_id integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: rent_debt_ledger_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.rent_debt_ledger_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: rent_debt_ledger_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.rent_debt_ledger_id_seq OWNED BY public.rent_debt_ledger.id;


--
-- Name: reserve_number_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.reserve_number_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    MAXVALUE 999999
    CACHE 1;


--
-- Name: route_event_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.route_event_types (
    event_type_id integer NOT NULL,
    event_code character varying(50) NOT NULL,
    event_name character varying(100) NOT NULL,
    description text,
    clock_action character varying(20) DEFAULT 'none'::character varying,
    affects_billing boolean DEFAULT true,
    is_active boolean DEFAULT true,
    display_order integer DEFAULT 100,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT route_event_types_clock_action_check CHECK (((clock_action)::text = ANY ((ARRAY['start'::character varying, 'stop'::character varying, 'pause'::character varying, 'resume'::character varying, 'none'::character varying])::text[])))
);


--
-- Name: TABLE route_event_types; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.route_event_types IS 'Standardized event types for charter routing timeline - used for accurate billing documentation';


--
-- Name: COLUMN route_event_types.clock_action; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.route_event_types.clock_action IS 'Billing clock action: start (begin billing), stop (end billing), pause (temporarily stop), resume (restart after pause), none (informational only)';


--
-- Name: COLUMN route_event_types.affects_billing; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.route_event_types.affects_billing IS 'Whether this event type impacts billable time calculations';


--
-- Name: route_event_types_event_type_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.route_event_types_event_type_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: route_event_types_event_type_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.route_event_types_event_type_id_seq OWNED BY public.route_event_types.event_type_id;


--
-- Name: run_type_default_charges; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.run_type_default_charges (
    run_type_id integer NOT NULL,
    charge_description character varying(255) NOT NULL,
    charge_type character varying(50),
    amount numeric(12,2),
    calc_type character varying(50),
    value numeric(12,2),
    is_taxable boolean DEFAULT true,
    sequence integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_migrations (
    id integer NOT NULL,
    filename text NOT NULL,
    executed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: schema_migrations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.schema_migrations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: schema_migrations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.schema_migrations_id_seq OWNED BY public.schema_migrations.id;


--
-- Name: security_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.security_audit (
    audit_id integer NOT NULL,
    user_id integer,
    action character varying(50) NOT NULL,
    details jsonb,
    ip_address inet,
    user_agent text,
    success boolean,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: security_audit_audit_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.security_audit_audit_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: security_audit_audit_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.security_audit_audit_id_seq OWNED BY public.security_audit.audit_id;


--
-- Name: security_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.security_events (
    event_id integer NOT NULL,
    event_type character varying(100) NOT NULL,
    ip_address inet,
    user_agent text,
    url character varying(500),
    method character varying(10),
    user_id integer,
    additional_data jsonb,
    "timestamp" timestamp without time zone DEFAULT now()
);


--
-- Name: security_events_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.security_events_event_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: security_events_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.security_events_event_id_seq OWNED BY public.security_events.event_id;


--
-- Name: square_api_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.square_api_audit (
    square_audit_id bigint NOT NULL,
    square_payment_id character varying(255) NOT NULL,
    square_customer_id character varying(255),
    square_refund_id character varying(255),
    square_dispute_id character varying(255),
    charter_reserve_number character varying(50),
    charter_id bigint,
    payment_id bigint,
    customer_name character varying(255),
    customer_email character varying(255),
    customer_phone character varying(20),
    customer_company character varying(255),
    transaction_amount_cents bigint NOT NULL,
    refund_amount_cents bigint DEFAULT 0,
    dispute_amount_cents bigint DEFAULT 0,
    square_fee_cents bigint DEFAULT 0,
    processing_fee_cents bigint DEFAULT 0,
    loan_fee_cents bigint DEFAULT 0,
    loan_payment_cents bigint DEFAULT 0,
    net_received_cents bigint GENERATED ALWAYS AS (((((transaction_amount_cents - refund_amount_cents) - dispute_amount_cents) - square_fee_cents) - processing_fee_cents)) STORED,
    payment_method character varying(50) NOT NULL,
    payment_source_type character varying(100),
    card_brand character varying(50),
    card_last_4 character varying(4),
    has_refund boolean DEFAULT false,
    refund_reason character varying(500),
    refund_date timestamp without time zone,
    refund_status character varying(50),
    has_dispute boolean DEFAULT false,
    dispute_reason character varying(255),
    dispute_amount_received numeric(10,2),
    dispute_status character varying(50),
    dispute_created_date timestamp without time zone,
    dispute_evidence_files_count integer DEFAULT 0,
    has_square_capital_loan boolean DEFAULT false,
    square_capital_loan_id character varying(255),
    banking_transaction_id character varying(255),
    banking_reference character varying(255),
    etransfer_transaction_id character varying(255),
    check_number character varying(50),
    cash_batch_id character varying(100),
    audit_status character varying(50) DEFAULT 'PENDING'::character varying,
    audit_notes text,
    merchant_notes text,
    customer_notes text,
    reconciliation_notes text,
    internal_reference_codes character varying(500),
    linked_payments_count integer DEFAULT 1,
    linked_refunds_count integer DEFAULT 0,
    linked_disputes_count integer DEFAULT 0,
    square_created_timestamp timestamp without time zone NOT NULL,
    square_updated_timestamp timestamp without time zone,
    square_risk_level character varying(50),
    square_receipt_url text,
    charter_match_confidence numeric(3,2) DEFAULT 0.00,
    match_method character varying(100),
    matched_by_user_id bigint,
    match_verified_date timestamp without time zone,
    synced_to_charter boolean DEFAULT false,
    synced_to_payments boolean DEFAULT false,
    synced_timestamp timestamp without time zone,
    last_audit_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    data_extraction_batch_id character varying(100),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT square_api_audit_dispute_amount_cents_check CHECK ((dispute_amount_cents >= 0)),
    CONSTRAINT square_api_audit_refund_amount_cents_check CHECK ((refund_amount_cents >= 0)),
    CONSTRAINT square_api_audit_transaction_amount_cents_check CHECK ((transaction_amount_cents >= 0)),
    CONSTRAINT valid_audit_status CHECK (((audit_status)::text = ANY ((ARRAY['PENDING'::character varying, 'VERIFIED'::character varying, 'MISMATCH'::character varying, 'ORPHANED'::character varying, 'DUPLICATE'::character varying, 'RESOLVED'::character varying])::text[])))
);


--
-- Name: square_api_audit_square_audit_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.square_api_audit_square_audit_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: square_api_audit_square_audit_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.square_api_audit_square_audit_id_seq OWNED BY public.square_api_audit.square_audit_id;


--
-- Name: square_audit_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.square_audit_summary AS
 SELECT count(*) AS total_transactions,
    (sum(transaction_amount_cents) / 100.0) AS total_amount,
    (sum(refund_amount_cents) / 100.0) AS total_refunded,
    (sum(dispute_amount_cents) / 100.0) AS total_disputed,
    (sum(square_fee_cents) / 100.0) AS total_square_fees,
    (sum(net_received_cents) / 100.0) AS net_received,
    count(
        CASE
            WHEN has_refund THEN 1
            ELSE NULL::integer
        END) AS refund_count,
    count(
        CASE
            WHEN has_dispute THEN 1
            ELSE NULL::integer
        END) AS dispute_count,
    count(
        CASE
            WHEN (charter_id IS NULL) THEN 1
            ELSE NULL::integer
        END) AS orphaned_count,
    count(
        CASE
            WHEN ((audit_status)::text = 'VERIFIED'::text) THEN 1
            ELSE NULL::integer
        END) AS verified_count,
    count(
        CASE
            WHEN ((audit_status)::text = 'MISMATCH'::text) THEN 1
            ELSE NULL::integer
        END) AS mismatch_count,
    count(
        CASE
            WHEN ((dispute_status)::text = 'LOST'::text) THEN 1
            ELSE NULL::integer
        END) AS lost_disputes
   FROM public.square_api_audit
  WHERE ((data_extraction_batch_id)::text = '20260203_115106'::text);


--
-- Name: square_capital_activity; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.square_capital_activity (
    id integer NOT NULL,
    activity_date date NOT NULL,
    description text NOT NULL,
    amount numeric(12,2) NOT NULL,
    source_file text NOT NULL,
    row_hash character(32) NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: square_capital_activity_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.square_capital_activity_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: square_capital_activity_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.square_capital_activity_id_seq OWNED BY public.square_capital_activity.id;


--
-- Name: square_capital_loans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.square_capital_loans (
    loan_id integer NOT NULL,
    square_loan_id text,
    loan_amount numeric(12,2),
    received_date date,
    status text,
    banking_transaction_id integer,
    description text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: square_capital_loans_loan_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.square_capital_loans_loan_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: square_capital_loans_loan_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.square_capital_loans_loan_id_seq OWNED BY public.square_capital_loans.loan_id;


--
-- Name: square_capital_monthly_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.square_capital_monthly_summary AS
 WITH sc AS (
         SELECT square_capital_activity.activity_date,
            square_capital_activity.description,
            (square_capital_activity.amount)::numeric AS amount,
                CASE
                    WHEN (square_capital_activity.description ~~* '%automatic payment%'::text) THEN 'repayment'::text
                    ELSE 'credit'::text
                END AS kind
           FROM public.square_capital_activity
        ), agg AS (
         SELECT (date_trunc('month'::text, (sc.activity_date)::timestamp with time zone))::date AS month,
            sum(
                CASE
                    WHEN (sc.kind = 'credit'::text) THEN sc.amount
                    ELSE (0)::numeric
                END) AS credits_total,
            sum(
                CASE
                    WHEN (sc.kind = 'repayment'::text) THEN (- abs(sc.amount))
                    ELSE (0)::numeric
                END) AS repayments_total,
            count(*) FILTER (WHERE (sc.kind = 'credit'::text)) AS credits_count,
            count(*) FILTER (WHERE (sc.kind = 'repayment'::text)) AS repayments_count
           FROM sc
          GROUP BY ((date_trunc('month'::text, (sc.activity_date)::timestamp with time zone))::date)
        )
 SELECT month,
    credits_total,
    repayments_total,
    credits_count,
    repayments_count
   FROM agg
  ORDER BY month;


--
-- Name: square_cc_staging; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.square_cc_staging (
    payment_id text NOT NULL,
    type text,
    status text,
    card_brand text,
    last_4 text,
    amount_total numeric,
    tip_amount numeric,
    fee_amount numeric,
    net_amount numeric,
    currency text,
    created_at timestamp with time zone,
    receipt_number text,
    reference_id text,
    order_id text,
    customer_id text,
    note text
);


--
-- Name: square_charter_linkage; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.square_charter_linkage AS
 SELECT charter_reserve_number,
    count(*) AS payment_count,
    count(DISTINCT square_payment_id) AS square_transactions,
    (sum(transaction_amount_cents) / 100.0) AS total_billed,
    (sum(refund_amount_cents) / 100.0) AS total_refunded,
    (sum(net_received_cents) / 100.0) AS net_received,
    count(
        CASE
            WHEN ((audit_status)::text = 'VERIFIED'::text) THEN 1
            ELSE NULL::integer
        END) AS verified_count,
    count(
        CASE
            WHEN ((audit_status)::text = 'MISMATCH'::text) THEN 1
            ELSE NULL::integer
        END) AS mismatch_count,
    string_agg(DISTINCT (customer_name)::text, ', '::text) AS customers,
    string_agg(DISTINCT (audit_status)::text, ', '::text) AS statuses
   FROM public.square_api_audit
  WHERE (charter_reserve_number IS NOT NULL)
  GROUP BY charter_reserve_number
  ORDER BY (sum(transaction_amount_cents) / 100.0) DESC;


--
-- Name: square_customer_payment_history; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.square_customer_payment_history AS
 SELECT square_customer_id,
    customer_name,
    customer_email,
    customer_company,
    count(DISTINCT square_payment_id) AS total_transactions,
    (sum(transaction_amount_cents) / 100.0) AS lifetime_value,
    (sum(refund_amount_cents) / 100.0) AS total_refunded,
    count(
        CASE
            WHEN has_refund THEN 1
            ELSE NULL::integer
        END) AS refund_count,
    count(
        CASE
            WHEN has_dispute THEN 1
            ELSE NULL::integer
        END) AS dispute_count,
    count(DISTINCT charter_reserve_number) AS charter_count,
    max(square_created_timestamp) AS last_transaction_date,
    min(square_created_timestamp) AS first_transaction_date
   FROM public.square_api_audit
  GROUP BY square_customer_id, customer_name, customer_email, customer_company
  ORDER BY (sum(transaction_amount_cents) / 100.0) DESC;


--
-- Name: square_customers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.square_customers (
    id integer NOT NULL,
    reference_id character varying(100),
    first_name character varying(100),
    surname character varying(100),
    email_address character varying(200),
    phone_number character varying(50),
    nickname character varying(100),
    company_name character varying(200),
    street_address_1 character varying(200),
    street_address_2 character varying(200),
    city character varying(100),
    state character varying(50),
    postal_code character varying(20),
    birthday character varying(50),
    memo text,
    square_customer_id character varying(100),
    creation_source character varying(100),
    first_visit date,
    last_visit date,
    transaction_count integer,
    lifetime_spend character varying(50),
    email_subscription_status character varying(50),
    instant_profile character varying(10),
    import_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    import_batch character varying(100)
);


--
-- Name: TABLE square_customers; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.square_customers IS 'Square customer data for matching with transactions and charters';


--
-- Name: COLUMN square_customers.email_address; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.square_customers.email_address IS 'Customer email for matching with charter clients';


--
-- Name: COLUMN square_customers.company_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.square_customers.company_name IS 'Company name for matching with business charters';


--
-- Name: COLUMN square_customers.square_customer_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.square_customers.square_customer_id IS 'Unique Square Customer ID for linking with transactions';


--
-- Name: square_customers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.square_customers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: square_customers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.square_customers_id_seq OWNED BY public.square_customers.id;


--
-- Name: square_customers_staging; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.square_customers_staging (
    customer_id character varying(255) NOT NULL,
    given_name character varying(255),
    family_name character varying(255),
    email_address character varying(255)
);


--
-- Name: square_disputes_tracking; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.square_disputes_tracking AS
 SELECT square_audit_id,
    square_dispute_id,
    charter_reserve_number,
    customer_name,
    ((dispute_amount_cents)::numeric / 100.0) AS dispute_amount,
    dispute_reason,
    dispute_status,
    dispute_evidence_files_count,
    dispute_created_date,
    audit_status,
    reconciliation_notes
   FROM public.square_api_audit
  WHERE (has_dispute = true)
  ORDER BY dispute_created_date DESC;


--
-- Name: square_etransfer_reconciliation; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.square_etransfer_reconciliation (
    reconciliation_id integer NOT NULL,
    payment_code_4char character varying(4) NOT NULL,
    square_payment_id integer,
    square_payment_key character varying(100),
    square_amount numeric(10,2),
    square_date date,
    charter_id integer,
    banking_transaction_id integer,
    etransfer_reference_number character varying(50),
    etransfer_amount numeric(10,2),
    etransfer_date date,
    etransfer_sender_name character varying(200),
    interac_email_reference character varying(50),
    interac_code_4char character varying(4),
    etransfer_assessment_id integer,
    etransfer_analysis_id integer,
    reconciliation_status character varying(50) DEFAULT 'pending'::character varying,
    reconciliation_method character varying(50),
    amount_variance numeric(10,2),
    date_variance integer,
    almsdata_entry_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    almsdata_entered_by character varying(100),
    almsdata_notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    reconciled_at timestamp without time zone,
    reconciled_by character varying(100)
);


--
-- Name: square_etransfer_reconciliation_reconciliation_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.square_etransfer_reconciliation_reconciliation_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: square_etransfer_reconciliation_reconciliation_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.square_etransfer_reconciliation_reconciliation_id_seq OWNED BY public.square_etransfer_reconciliation.reconciliation_id;


--
-- Name: square_processing_fees; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.square_processing_fees (
    fee_id integer NOT NULL,
    payment_id text NOT NULL,
    square_payment_id text,
    transaction_date timestamp with time zone,
    gross_amount numeric(12,2),
    processing_fee_amount numeric(12,2),
    net_amount numeric(12,2),
    card_brand text,
    card_last4 text,
    entry_method text,
    fee_type text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: square_fee_by_card_brand; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.square_fee_by_card_brand AS
 SELECT card_brand,
    count(*) AS transaction_count,
    sum(gross_amount) AS total_gross,
    sum(processing_fee_amount) AS total_fees,
    sum(net_amount) AS total_net,
    round(((sum(processing_fee_amount) / NULLIF(sum(gross_amount), (0)::numeric)) * (100)::numeric), 2) AS avg_fee_percentage
   FROM public.square_processing_fees
  GROUP BY card_brand
  ORDER BY (sum(gross_amount)) DESC;


--
-- Name: square_fees_staging; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.square_fees_staging (
    payment_id text,
    fee_date date,
    amount_total numeric,
    fee_amount numeric,
    fee_percent numeric,
    net_amount numeric,
    card_brand text,
    receipt_number text,
    status text
);


--
-- Name: square_lms_matches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.square_lms_matches (
    match_id bigint NOT NULL,
    square_payment_id character varying(255),
    lms_payment_id integer,
    reserve_no character varying(50),
    amount numeric,
    square_date date,
    lms_date date,
    match_method character varying(100),
    confidence numeric(4,2),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: square_lms_matches_match_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.square_lms_matches_match_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: square_lms_matches_match_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.square_lms_matches_match_id_seq OWNED BY public.square_lms_matches.match_id;


--
-- Name: square_monthly_fee_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.square_monthly_fee_summary AS
 SELECT date_trunc('month'::text, transaction_date) AS month,
    count(*) AS transaction_count,
    sum(gross_amount) AS total_gross,
    sum(processing_fee_amount) AS total_fees,
    sum(net_amount) AS total_net,
    round(((sum(processing_fee_amount) / NULLIF(sum(gross_amount), (0)::numeric)) * (100)::numeric), 2) AS avg_fee_percentage
   FROM public.square_processing_fees
  GROUP BY (date_trunc('month'::text, transaction_date))
  ORDER BY (date_trunc('month'::text, transaction_date)) DESC;


--
-- Name: square_monthly_fees_verification; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.square_monthly_fees_verification AS
SELECT
    NULL::integer AS payment_id,
    NULL::numeric(12,2) AS fee_amount,
    NULL::date AS payment_date,
    NULL::character varying(50) AS reserve_number,
    NULL::bigint AS receipt_count,
    NULL::numeric AS receipt_total,
    NULL::boolean AS verified,
    NULL::character varying AS gl_code,
    NULL::text AS status;


--
-- Name: square_orphaned_transactions; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.square_orphaned_transactions AS
 SELECT square_audit_id,
    square_payment_id,
    customer_name,
    customer_email,
    ((transaction_amount_cents)::numeric / 100.0) AS amount,
    charter_reserve_number,
    charter_id,
    payment_id,
    audit_status,
    audit_notes,
    square_created_timestamp
   FROM public.square_api_audit
  WHERE ((charter_id IS NULL) OR ((audit_status)::text = ANY ((ARRAY['ORPHANED'::character varying, 'MISMATCH'::character varying, 'DUPLICATE'::character varying])::text[])))
  ORDER BY transaction_amount_cents DESC;


--
-- Name: square_payment_categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.square_payment_categories (
    id integer NOT NULL,
    square_payment_id integer,
    category character varying(50) NOT NULL,
    subcategory character varying(100),
    original_payment_id integer,
    categorized_by character varying(100) DEFAULT 'system'::character varying,
    categorized_date timestamp without time zone DEFAULT now(),
    notes text
);


--
-- Name: TABLE square_payment_categories; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.square_payment_categories IS 'Categorizes Square payments by type (normal, refund, chargeback, etc.)';


--
-- Name: square_payment_categories_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.square_payment_categories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: square_payment_categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.square_payment_categories_id_seq OWNED BY public.square_payment_categories.id;


--
-- Name: square_payments_pending_receipt_verification; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.square_payments_pending_receipt_verification AS
 SELECT p.payment_id,
    p.reserve_number,
    p.amount,
    p.payment_date,
    p.payment_method,
    c.status AS charter_status,
    count(r.receipt_id) AS receipt_count,
    sum(r.gross_amount) AS receipt_total,
    p.verified,
        CASE
            WHEN (count(r.receipt_id) = 0) THEN 'NO_RECEIPTS'::text
            WHEN (p.amount <> sum(r.gross_amount)) THEN 'AMOUNT_MISMATCH'::text
            WHEN (count(r.receipt_id) > 1) THEN 'SPLIT_RECEIPT'::text
            WHEN p.verified THEN 'VERIFIED'::text
            ELSE 'NEEDS_VERIFICATION'::text
        END AS status
   FROM ((public.payments p
     LEFT JOIN public.charters c ON (((c.reserve_number)::text = (p.reserve_number)::text)))
     LEFT JOIN public.receipts r ON ((r.source_reference = (p.payment_id)::text)))
  WHERE ((p.payment_method)::text = 'square'::text)
  GROUP BY p.payment_id, p.reserve_number, p.amount, p.payment_date, p.payment_method, c.status, p.verified;


--
-- Name: square_payouts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.square_payouts (
    id text NOT NULL,
    status text,
    location_id text,
    arrival_date date,
    amount numeric(12,2),
    currency text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);


--
-- Name: square_processing_fees_fee_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.square_processing_fees_fee_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: square_processing_fees_fee_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.square_processing_fees_fee_id_seq OWNED BY public.square_processing_fees.fee_id;


--
-- Name: square_raw_imports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.square_raw_imports (
    import_id integer NOT NULL,
    source text NOT NULL,
    file_name text NOT NULL,
    imported_at timestamp without time zone DEFAULT now() NOT NULL,
    row_count integer DEFAULT 0
);


--
-- Name: square_raw_imports_import_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.square_raw_imports_import_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: square_raw_imports_import_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.square_raw_imports_import_id_seq OWNED BY public.square_raw_imports.import_id;


--
-- Name: square_raw_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.square_raw_records (
    record_pk bigint NOT NULL,
    import_id integer NOT NULL,
    record_type text NOT NULL,
    record_id text,
    record_date date,
    amount numeric(12,2),
    currency text,
    customer_id text,
    card_last4 text,
    row_hash text NOT NULL,
    raw jsonb NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: square_raw_records_record_pk_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.square_raw_records_record_pk_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: square_raw_records_record_pk_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.square_raw_records_record_pk_seq OWNED BY public.square_raw_records.record_pk;


--
-- Name: square_refunds_tracking; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.square_refunds_tracking AS
 SELECT square_audit_id,
    square_refund_id,
    square_payment_id,
    charter_reserve_number,
    customer_name,
    ((transaction_amount_cents)::numeric / 100.0) AS original_amount,
    ((refund_amount_cents)::numeric / 100.0) AS refund_amount,
    refund_reason,
    refund_status,
    refund_date,
    audit_status
   FROM public.square_api_audit
  WHERE (has_refund = true)
  ORDER BY refund_date DESC;


--
-- Name: square_review_status; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.square_review_status (
    id integer NOT NULL,
    square_payment_id integer,
    review_status character varying(50) NOT NULL,
    assigned_to character varying(100),
    priority character varying(20) DEFAULT 'normal'::character varying,
    created_date timestamp without time zone DEFAULT now(),
    reviewed_date timestamp without time zone,
    resolution text,
    reviewer_notes text
);


--
-- Name: TABLE square_review_status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.square_review_status IS 'Tracks manual review status for problematic Square payments';


--
-- Name: square_review_status_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.square_review_status_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: square_review_status_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.square_review_status_id_seq OWNED BY public.square_review_status.id;


--
-- Name: staging_driver_pay_files; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.staging_driver_pay_files (
    id bigint NOT NULL,
    file_path text NOT NULL,
    file_name text NOT NULL,
    file_type text NOT NULL,
    source_hash text,
    rows_parsed integer DEFAULT 0,
    status text DEFAULT 'pending'::text,
    error_message text,
    first_txn_date date,
    last_txn_date date,
    processed_at timestamp with time zone DEFAULT now()
);


--
-- Name: staging_driver_pay_files_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.staging_driver_pay_files_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: staging_driver_pay_files_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.staging_driver_pay_files_id_seq OWNED BY public.staging_driver_pay_files.id;


--
-- Name: staging_driver_pay_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.staging_driver_pay_links (
    staging_id integer NOT NULL,
    employee_id integer NOT NULL,
    method text,
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: staging_employee_reference_data; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.staging_employee_reference_data (
    id integer NOT NULL,
    employee_id character varying(20),
    employee_name character varying(255),
    hire_date date,
    sin character varying(20),
    birth_date date,
    additional_amount numeric(10,2),
    main_phone character varying(50),
    street1 character varying(255),
    city character varying(100),
    postal_code character varying(20),
    source_file character varying(500),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: staging_employee_reference_data_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.staging_employee_reference_data_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: staging_employee_reference_data_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.staging_employee_reference_data_id_seq OWNED BY public.staging_employee_reference_data.id;


--
-- Name: staging_pd7a_year_end_summary; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.staging_pd7a_year_end_summary (
    id integer NOT NULL,
    year integer,
    period_start date,
    period_end date,
    gross_payroll numeric(12,2),
    num_employees_paid integer,
    tax_deductions numeric(12,2),
    cpp_employee numeric(12,2),
    cpp_company numeric(12,2),
    total_cpp numeric(12,2),
    ei_employee numeric(12,2),
    ei_company numeric(12,2),
    total_ei numeric(12,2),
    total_remittance numeric(12,2),
    source_file character varying(500),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: staging_pd7a_year_end_summary_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.staging_pd7a_year_end_summary_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: staging_pd7a_year_end_summary_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.staging_pd7a_year_end_summary_id_seq OWNED BY public.staging_pd7a_year_end_summary.id;


--
-- Name: system_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.system_config (
    config_id integer NOT NULL,
    config_category character varying(50) NOT NULL,
    config_key character varying(100) NOT NULL,
    config_value text,
    data_type character varying(20) DEFAULT 'string'::character varying,
    description text,
    is_encrypted boolean DEFAULT false,
    is_user_configurable boolean DEFAULT true,
    default_value text,
    validation_rules text,
    last_modified timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    modified_by character varying(100)
);


--
-- Name: system_config_config_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.system_config_config_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: system_config_config_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.system_config_config_id_seq OWNED BY public.system_config.config_id;


--
-- Name: system_locked_years; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.system_locked_years (
    year integer NOT NULL,
    locked boolean DEFAULT true NOT NULL,
    locked_at timestamp with time zone DEFAULT now() NOT NULL,
    locked_by text
);


--
-- Name: t4_compliance_corrections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.t4_compliance_corrections (
    correction_id integer NOT NULL,
    employee_id integer NOT NULL,
    tax_year integer NOT NULL,
    correction_type character varying(30) NOT NULL,
    correction_reason text,
    original_t4_issued boolean DEFAULT false,
    original_employment_income numeric(12,2),
    original_cpp_contributions numeric(10,2),
    original_ei_contributions numeric(10,2),
    original_income_tax numeric(10,2),
    corrected_employment_income numeric(12,2),
    corrected_cpp_contributions numeric(10,2),
    corrected_ei_contributions numeric(10,2),
    corrected_income_tax numeric(10,2),
    income_variance numeric(12,2),
    cpp_variance numeric(10,2),
    ei_variance numeric(10,2),
    tax_variance numeric(10,2),
    correction_status character varying(30) DEFAULT 'pending'::character varying,
    cra_reference_number character varying(50),
    filed_date date,
    cra_response_date date,
    cra_notes text,
    impacts_deferred_wages boolean DEFAULT false,
    deferred_wage_adjustment numeric(12,2),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    prepared_by integer
);


--
-- Name: TABLE t4_compliance_corrections; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.t4_compliance_corrections IS 'T4 corrections tracking including 2013 owner salary issue';


--
-- Name: COLUMN t4_compliance_corrections.correction_reason; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.t4_compliance_corrections.correction_reason IS 'Reason for T4 correction (e.g., 2013 owner salary issue)';


--
-- Name: t4_compliance_corrections_correction_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.t4_compliance_corrections_correction_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: t4_compliance_corrections_correction_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.t4_compliance_corrections_correction_id_seq OWNED BY public.t4_compliance_corrections.correction_id;


--
-- Name: tax_overrides; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tax_overrides (
    id integer NOT NULL,
    entity_type text NOT NULL,
    entity_id text,
    field text NOT NULL,
    override_data jsonb NOT NULL,
    reason text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: tax_overrides_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tax_overrides_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tax_overrides_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tax_overrides_id_seq OWNED BY public.tax_overrides.id;


--
-- Name: tax_periods; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tax_periods (
    id integer NOT NULL,
    label text NOT NULL,
    period_type text DEFAULT 'gst'::text NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    year integer NOT NULL,
    quarter integer,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: tax_periods_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tax_periods_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tax_periods_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tax_periods_id_seq OWNED BY public.tax_periods.id;


--
-- Name: tax_remittances; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tax_remittances (
    id integer NOT NULL,
    tax_return_id integer NOT NULL,
    kind text DEFAULT 'gst'::text NOT NULL,
    amount numeric(14,2) DEFAULT 0 NOT NULL,
    paid_at date,
    reference text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: tax_remittances_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tax_remittances_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tax_remittances_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tax_remittances_id_seq OWNED BY public.tax_remittances.id;


--
-- Name: tax_returns; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tax_returns (
    id integer NOT NULL,
    period_id integer NOT NULL,
    form_type text NOT NULL,
    status text DEFAULT 'draft'::text NOT NULL,
    calculated_amount numeric(14,2) DEFAULT 0,
    filed_amount numeric(14,2),
    filed_at timestamp without time zone,
    reference text,
    notes text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: tax_returns_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tax_returns_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tax_returns_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tax_returns_id_seq OWNED BY public.tax_returns.id;


--
-- Name: tax_rollovers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tax_rollovers (
    id integer NOT NULL,
    rollover_type text NOT NULL,
    from_year integer,
    to_year integer,
    amount numeric(14,2) DEFAULT 0 NOT NULL,
    expires_year integer,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: tax_rollovers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tax_rollovers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tax_rollovers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tax_rollovers_id_seq OWNED BY public.tax_rollovers.id;


--
-- Name: tax_variances; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tax_variances (
    id integer NOT NULL,
    tax_return_id integer NOT NULL,
    field text NOT NULL,
    actual numeric(14,2),
    expected numeric(14,2),
    severity text DEFAULT 'info'::text,
    message text,
    recommendation text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: tax_variances_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tax_variances_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tax_variances_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tax_variances_id_seq OWNED BY public.tax_variances.id;


--
-- Name: tax_year_reference; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tax_year_reference (
    year integer NOT NULL,
    federal_basic_personal_amount numeric(10,2),
    alberta_basic_personal_amount numeric(10,2),
    federal_small_business_limit numeric(12,2),
    federal_small_business_rate numeric(5,3),
    federal_general_corporate_rate numeric(5,3),
    ab_corp_small_business_rate numeric(5,3),
    ab_corp_general_rate numeric(5,3),
    gst_rate numeric(4,2),
    cpp_contribution_rate_employee numeric(5,4),
    cpp_contribution_rate_employer numeric(5,4),
    cpp_max_pensionable_earnings numeric(10,2),
    cpp_basic_exemption numeric(10,2),
    cpp_max_employee_contribution numeric(10,2),
    cpp_max_employer_contribution numeric(10,2),
    cpp2_contribution_rate_employee numeric(5,4),
    cpp2_contribution_rate_employer numeric(5,4),
    cpp2_upper_pensionable_earnings numeric(10,2),
    cpp2_max_employee_contribution numeric(10,2),
    cpp2_max_employer_contribution numeric(10,2),
    ei_rate numeric(5,4),
    ei_max_insurable_earnings numeric(10,2),
    ei_max_employee_contribution numeric(10,2),
    ei_max_employer_contribution numeric(10,2),
    wcb_ab_max_insurable_earnings numeric(10,2),
    federal_dividend_gross_up_eligible numeric(5,3),
    federal_dividend_gross_up_non_eligible numeric(5,3),
    low_income_tax_threshold_federal numeric(10,2),
    low_income_tax_threshold_alberta numeric(10,2),
    vacation_minimum_percent numeric(4,2),
    capital_gains_inclusion_rate_percent numeric(5,2),
    auto_allowance_first_rate_cents_km numeric(5,2),
    auto_allowance_additional_rate_cents_km numeric(5,2),
    meal_deduction_percent_general numeric(5,2),
    meal_deduction_percent_longhaul numeric(5,2),
    notes text,
    federal_tax_free_threshold numeric(10,2),
    alberta_tax_free_threshold numeric(10,2),
    minimum_taxable_income_federal numeric(10,2),
    minimum_taxable_income_alberta numeric(10,2)
);


--
-- Name: TABLE tax_year_reference; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.tax_year_reference IS 'Complete Canadian tax reference data 2008-2025. 
Tax-free thresholds represent the basic personal amount - the income level where no federal or provincial tax is owed.
These are the LOWEST amounts to use for payroll calculations to avoid over-withholding.
Note: Actual tax owing may be less due to additional credits (spousal, disability, tuition, etc.) but these are the safe minimums for payroll withholding.';


--
-- Name: COLUMN tax_year_reference.federal_tax_free_threshold; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.tax_year_reference.federal_tax_free_threshold IS 'Annual income where federal tax owing becomes $0 (basic personal amount converted to income threshold)';


--
-- Name: COLUMN tax_year_reference.alberta_tax_free_threshold; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.tax_year_reference.alberta_tax_free_threshold IS 'Annual income where Alberta provincial tax owing becomes $0 (basic personal amount converted to income threshold)';


--
-- Name: COLUMN tax_year_reference.minimum_taxable_income_federal; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.tax_year_reference.minimum_taxable_income_federal IS 'Minimum income to be required to file federal tax return (typically matches federal_tax_free_threshold)';


--
-- Name: COLUMN tax_year_reference.minimum_taxable_income_alberta; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.tax_year_reference.minimum_taxable_income_alberta IS 'Minimum income where Alberta tax is owed (typically matches alberta_tax_free_threshold)';


--
-- Name: training_checklist_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.training_checklist_items (
    item_id integer NOT NULL,
    program_id integer,
    item_name character varying(255) NOT NULL,
    description text,
    is_required boolean DEFAULT true,
    sort_order integer DEFAULT 0,
    completion_verification_required boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: training_checklist_items_item_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.training_checklist_items_item_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: training_checklist_items_item_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.training_checklist_items_item_id_seq OWNED BY public.training_checklist_items.item_id;


--
-- Name: training_programs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.training_programs (
    program_id integer NOT NULL,
    program_name character varying(255) NOT NULL,
    description text,
    is_mandatory boolean DEFAULT false,
    red_deer_required boolean DEFAULT false,
    duration_hours numeric(4,2),
    expiry_months integer,
    sort_order integer DEFAULT 0,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: training_programs_program_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.training_programs_program_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: training_programs_program_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.training_programs_program_id_seq OWNED BY public.training_programs.program_id;


--
-- Name: transaction_categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transaction_categories (
    id integer NOT NULL,
    category_name character varying(50) NOT NULL,
    description text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: transaction_categories_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transaction_categories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transaction_categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transaction_categories_id_seq OWNED BY public.transaction_categories.id;


--
-- Name: transaction_chain; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transaction_chain (
    chain_id integer NOT NULL,
    transaction_date date NOT NULL,
    transaction_type character varying(50) NOT NULL,
    source_account character varying(100),
    destination_account character varying(100),
    gross_amount numeric(15,2) NOT NULL,
    fees_charged numeric(15,2) DEFAULT 0,
    net_amount numeric(15,2) NOT NULL,
    reference_number character varying(100),
    description text,
    supporting_documents text[],
    charter_id integer,
    receipt_id integer,
    square_transaction_id character varying(100),
    reconciliation_status character varying(50) DEFAULT 'unmatched'::character varying,
    gst_component numeric(15,2) DEFAULT 0,
    audit_notes text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: transaction_chain_chain_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transaction_chain_chain_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transaction_chain_chain_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transaction_chain_chain_id_seq OWNED BY public.transaction_chain.chain_id;


--
-- Name: transaction_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transaction_log (
    transaction_id integer NOT NULL,
    transaction_type character varying(50) NOT NULL,
    source_client_id integer,
    target_client_id integer,
    amount numeric(10,2) NOT NULL,
    description text NOT NULL,
    fraud_case_id integer,
    created_by character varying(100) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    metadata jsonb DEFAULT '{}'::jsonb,
    reference_number character varying(100),
    status character varying(20) DEFAULT 'completed'::character varying
);


--
-- Name: TABLE transaction_log; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.transaction_log IS 'Detailed transaction log for fraud case operations';


--
-- Name: transaction_log_transaction_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transaction_log_transaction_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transaction_log_transaction_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transaction_log_transaction_id_seq OWNED BY public.transaction_log.transaction_id;


--
-- Name: transaction_subcategories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transaction_subcategories (
    id integer NOT NULL,
    category_id integer,
    subcategory_name character varying(100) NOT NULL,
    pattern_keywords text[],
    description text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: transaction_subcategories_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transaction_subcategories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transaction_subcategories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transaction_subcategories_id_seq OWNED BY public.transaction_subcategories.id;


--
-- Name: unified_charge_lookup; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.unified_charge_lookup (
    lookup_id integer NOT NULL,
    charge_code character varying(50) NOT NULL,
    standard_description character varying(200) NOT NULL,
    category character varying(100) NOT NULL,
    usage_frequency integer DEFAULT 0,
    avg_amount numeric(10,2),
    min_amount numeric(10,2),
    max_amount numeric(10,2),
    total_amount numeric(15,2),
    search_patterns text[],
    alternative_descriptions text[],
    is_taxable boolean DEFAULT true,
    is_active boolean DEFAULT true,
    lms_source boolean DEFAULT false,
    charter_charges_source boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: unified_charge_lookup_lookup_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.unified_charge_lookup_lookup_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: unified_charge_lookup_lookup_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.unified_charge_lookup_lookup_id_seq OWNED BY public.unified_charge_lookup.lookup_id;


--
-- Name: unified_general_ledger; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.unified_general_ledger (
    id integer NOT NULL,
    transaction_date date NOT NULL,
    account_code character varying(100),
    account_name character varying(200),
    description text,
    debit_amount numeric(15,2) DEFAULT 0,
    credit_amount numeric(15,2) DEFAULT 0,
    source_system character varying(50),
    source_transaction_id character varying(100),
    transaction_type character varying(50),
    transaction_number character varying(50),
    entity_name character varying(200),
    row_hash character varying(64),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: unified_general_ledger_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.unified_general_ledger_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: unified_general_ledger_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.unified_general_ledger_id_seq OWNED BY public.unified_general_ledger.id;


--
-- Name: unmatched_etransfers_almsdata; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.unmatched_etransfers_almsdata AS
 SELECT bt.transaction_id,
    bt.description,
    bt.credit_amount AS etransfer_amount,
    bt.transaction_date AS etransfer_date,
    bt.account_number,
    public.extract_etransfer_reference(bt.description) AS etransfer_reference,
    public.extract_etransfer_sender(bt.description) AS etransfer_sender,
    public.derive_code4_from_banking(bt.description) AS banking_code4_suggestion,
        CASE
            WHEN ((CURRENT_DATE - bt.transaction_date) <= 3) THEN 'URGENT'::text
            WHEN ((CURRENT_DATE - bt.transaction_date) <= 7) THEN 'HIGH'::text
            WHEN ((CURRENT_DATE - bt.transaction_date) <= 30) THEN 'MEDIUM'::text
            ELSE 'LOW'::text
        END AS matching_priority,
    (CURRENT_DATE - bt.transaction_date) AS days_old
   FROM (public.banking_transactions bt
     LEFT JOIN public.square_etransfer_reconciliation ser ON ((bt.transaction_id = ser.banking_transaction_id)))
  WHERE (((bt.description ~~* '%E-TRANSFER%'::text) OR (bt.description ~~* '%INTERAC%'::text)) AND (bt.credit_amount > (0)::numeric) AND (ser.reconciliation_id IS NULL))
  ORDER BY bt.transaction_date DESC;


--
-- Name: unmatched_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.unmatched_items (
    id integer NOT NULL,
    table_name character varying(100),
    record_id integer,
    item_type character varying(100),
    description text,
    amount numeric(12,2),
    item_date date,
    flag_reason text,
    review_priority character varying(20),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: unmatched_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.unmatched_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: unmatched_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.unmatched_items_id_seq OWNED BY public.unmatched_items.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    user_id integer NOT NULL,
    username character varying(100) NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    role character varying(50) DEFAULT 'user'::character varying,
    status character varying(20) DEFAULT 'active'::character varying,
    permissions jsonb DEFAULT '[]'::jsonb,
    last_login timestamp without time zone,
    last_activity timestamp without time zone,
    last_ip inet,
    failed_login_attempts integer DEFAULT 0,
    locked_until timestamp without time zone,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    mfa_enabled boolean DEFAULT false,
    mfa_secret character varying(255),
    session_version integer DEFAULT 1
);


--
-- Name: users_user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_user_id_seq OWNED BY public.users.user_id;


--
-- Name: v_banking_potential_duplicates; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_banking_potential_duplicates AS
 SELECT source_hash,
    count(*) AS occurrence_count,
    array_agg(transaction_id ORDER BY transaction_id) AS transaction_ids,
    min(transaction_date) AS first_date,
    max(created_at) AS last_import_time
   FROM public.banking_transactions
  WHERE (source_hash IS NOT NULL)
  GROUP BY source_hash
 HAVING (count(*) > 1)
  ORDER BY (count(*)) DESC;


--
-- Name: v_banking_reconciliation_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_banking_reconciliation_summary AS
 SELECT account_number,
    EXTRACT(year FROM transaction_date) AS year,
    EXTRACT(month FROM transaction_date) AS month,
    count(*) AS total_transactions,
    sum(
        CASE
            WHEN (((reconciliation_status)::text = 'unreconciled'::text) OR (reconciliation_status IS NULL)) THEN 1
            ELSE 0
        END) AS unreconciled_count,
    sum(
        CASE
            WHEN ((reconciliation_status)::text = 'matched'::text) THEN 1
            ELSE 0
        END) AS matched_count,
    sum(debit_amount) AS total_debits,
    sum(credit_amount) AS total_credits
   FROM public.banking_transactions
  GROUP BY account_number, (EXTRACT(year FROM transaction_date)), (EXTRACT(month FROM transaction_date))
  ORDER BY account_number, (EXTRACT(year FROM transaction_date)), (EXTRACT(month FROM transaction_date));


--
-- Name: v_banking_transactions_with_aliases; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_banking_transactions_with_aliases AS
SELECT
    NULL::integer AS transaction_id,
    NULL::character varying(20) AS account_number,
    NULL::date AS transaction_date,
    NULL::date AS posted_date,
    NULL::text AS description,
    NULL::numeric(12,2) AS debit_amount,
    NULL::numeric(12,2) AS credit_amount,
    NULL::numeric(12,2) AS balance,
    NULL::character varying(200) AS vendor_extracted,
    NULL::boolean AS vendor_truncated,
    NULL::character varying(4) AS card_last4_detected,
    NULL::character varying(100) AS category,
    NULL::character varying(200) AS source_file,
    NULL::character varying(50) AS import_batch,
    NULL::timestamp without time zone AS created_at,
    NULL::integer AS bank_id,
    NULL::character varying(64) AS transaction_hash,
    NULL::timestamp without time zone AS updated_at,
    NULL::integer AS receipt_id,
    NULL::character varying(64) AS source_hash,
    NULL::character varying(20) AS reconciliation_status,
    NULL::integer AS reconciled_receipt_id,
    NULL::integer AS reconciled_payment_id,
    NULL::integer AS reconciled_charter_id,
    NULL::text AS reconciliation_notes,
    NULL::timestamp without time zone AS reconciled_at,
    NULL::character varying(100) AS reconciled_by,
    NULL::character varying[] AS known_aliases;


--
-- Name: v_cibc_card_utilization; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_cibc_card_utilization AS
 SELECT card_id,
    card_name,
    card_type,
    credit_limit,
    current_balance,
    available_credit,
    round(((current_balance / credit_limit) * (100)::numeric), 2) AS utilization_percentage,
        CASE
            WHEN ((current_balance / credit_limit) > 0.9) THEN 'High Risk'::text
            WHEN ((current_balance / credit_limit) > 0.7) THEN 'Medium Risk'::text
            ELSE 'Normal'::text
        END AS risk_level
   FROM public.cibc_business_cards c
  WHERE (is_active = true);


--
-- Name: VIEW v_cibc_card_utilization; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON VIEW public.v_cibc_card_utilization IS 'Credit utilization tracking for risk management';


--
-- Name: v_cibc_monthly_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_cibc_monthly_summary AS
 SELECT c.card_id,
    c.card_name,
    c.card_type,
    date_trunc('month'::text, (t.transaction_date)::timestamp with time zone) AS month_year,
    count(t.transaction_id) AS transaction_count,
    sum(t.amount) AS total_amount,
    sum(
        CASE
            WHEN t.auto_categorized THEN t.amount
            ELSE (0)::numeric
        END) AS auto_categorized_amount,
    sum(
        CASE
            WHEN t.manual_review_required THEN t.amount
            ELSE (0)::numeric
        END) AS review_required_amount,
    sum(
        CASE
            WHEN t.reconciled THEN t.amount
            ELSE (0)::numeric
        END) AS reconciled_amount,
    count(
        CASE
            WHEN (t.receipt_required AND (NOT t.receipt_uploaded)) THEN 1
            ELSE NULL::integer
        END) AS missing_receipts
   FROM (public.cibc_business_cards c
     LEFT JOIN public.cibc_card_transactions t ON ((c.card_id = t.card_id)))
  GROUP BY c.card_id, c.card_name, c.card_type, (date_trunc('month'::text, (t.transaction_date)::timestamp with time zone))
  ORDER BY c.card_id, (date_trunc('month'::text, (t.transaction_date)::timestamp with time zone)) DESC;


--
-- Name: VIEW v_cibc_monthly_summary; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON VIEW public.v_cibc_monthly_summary IS 'Monthly transaction summary by card';


--
-- Name: v_cibc_reconciliation_status; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_cibc_reconciliation_status AS
 SELECT c.card_id,
    c.card_name,
    count(t.transaction_id) AS total_transactions,
    count(
        CASE
            WHEN t.reconciled THEN 1
            ELSE NULL::integer
        END) AS reconciled_transactions,
    count(
        CASE
            WHEN (NOT t.reconciled) THEN 1
            ELSE NULL::integer
        END) AS unreconciled_transactions,
    sum(
        CASE
            WHEN (NOT t.reconciled) THEN t.amount
            ELSE (0)::numeric
        END) AS unreconciled_amount,
    count(
        CASE
            WHEN t.manual_review_required THEN 1
            ELSE NULL::integer
        END) AS review_required_count,
    count(
        CASE
            WHEN (t.receipt_required AND (NOT t.receipt_uploaded)) THEN 1
            ELSE NULL::integer
        END) AS missing_receipt_count
   FROM (public.cibc_business_cards c
     LEFT JOIN public.cibc_card_transactions t ON ((c.card_id = t.card_id)))
  WHERE (c.is_active = true)
  GROUP BY c.card_id, c.card_name;


--
-- Name: VIEW v_cibc_reconciliation_status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON VIEW public.v_cibc_reconciliation_status IS 'Banking reconciliation status by card';


--
-- Name: v_current_tax_thresholds; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_current_tax_thresholds AS
 SELECT year,
    federal_tax_free_threshold,
    alberta_tax_free_threshold,
    (federal_tax_free_threshold + alberta_tax_free_threshold) AS total_tax_free,
    round((federal_tax_free_threshold / (52)::numeric), 2) AS fed_weekly_exempt,
    round((federal_tax_free_threshold / (26)::numeric), 2) AS fed_biweekly_exempt,
    round((federal_tax_free_threshold / (24)::numeric), 2) AS fed_semimonthly_exempt,
    round((federal_tax_free_threshold / (12)::numeric), 2) AS fed_monthly_exempt,
    round((alberta_tax_free_threshold / (52)::numeric), 2) AS ab_weekly_exempt,
    round((alberta_tax_free_threshold / (26)::numeric), 2) AS ab_biweekly_exempt,
    round((alberta_tax_free_threshold / (24)::numeric), 2) AS ab_semimonthly_exempt,
    round((alberta_tax_free_threshold / (12)::numeric), 2) AS ab_monthly_exempt
   FROM public.tax_year_reference
  WHERE ((year)::numeric = EXTRACT(year FROM CURRENT_DATE));


--
-- Name: VIEW v_current_tax_thresholds; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON VIEW public.v_current_tax_thresholds IS 'Current year tax-free thresholds broken down by pay period frequency for easy payroll calculations';


--
-- Name: vehicles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vehicles (
    vehicle_id integer NOT NULL,
    vehicle_number character varying(50),
    make character varying(100),
    model character varying(100),
    year integer,
    license_plate character varying(50),
    passenger_capacity integer,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    operational_status character varying(20) DEFAULT 'active'::character varying,
    last_service_date date,
    next_service_due date,
    vin_number character varying(17),
    description text,
    ext_color character varying(50),
    int_color character varying(50),
    length numeric(8,2),
    width numeric(8,2),
    height numeric(8,2),
    odometer integer,
    odometer_type character varying(2) DEFAULT 'mi'::character varying NOT NULL,
    type character varying(50),
    engine_oil_type character varying,
    fuel_filter_number character varying,
    fuel_type character varying,
    transmission_fluid_type character varying,
    transmission_fluid_quantity character varying,
    fuel_filter_interval_km integer DEFAULT 60000,
    transmission_service_interval_km integer DEFAULT 80000,
    curb_weight integer,
    gross_vehicle_weight integer,
    fuel_efficiency_data jsonb DEFAULT '{}'::jsonb,
    oil_quantity character varying,
    oil_filter_number character varying,
    coolant_type character varying,
    coolant_quantity character varying,
    belt_size character varying,
    tire_size character varying,
    tire_pressure character varying,
    brake_fluid_type character varying,
    power_steering_fluid_type character varying,
    oil_change_interval_km integer DEFAULT 8000,
    oil_change_interval_months integer DEFAULT 6,
    air_filter_interval_km integer DEFAULT 30000,
    coolant_change_interval_km integer DEFAULT 150000,
    brake_fluid_change_interval_months integer DEFAULT 24,
    air_filter_part_number character varying,
    cabin_filter_part_number character varying,
    serpentine_belt_part_number character varying,
    return_to_service_date date,
    maintenance_schedule jsonb DEFAULT '{}'::jsonb,
    service_history jsonb DEFAULT '[]'::jsonb,
    parts_replacement_history jsonb DEFAULT '[]'::jsonb,
    vehicle_type character varying(100),
    fleet_number character varying(10),
    vehicle_category character varying(50),
    vehicle_class character varying(50),
    fleet_position integer,
    vehicle_history_id character varying(50),
    commission_date date DEFAULT CURRENT_DATE,
    decommission_date date,
    is_active boolean DEFAULT true,
    unit_number character varying(50),
    status character varying(50),
    cvip_expiry_date date,
    cvip_inspection_number character varying(50),
    last_cvip_date date,
    next_cvip_due date,
    cvip_compliance_status character varying(50),
    purchase_date date,
    purchase_price numeric(12,2),
    purchase_vendor character varying(200),
    finance_partner character varying(200),
    financing_amount numeric(12,2),
    monthly_payment numeric(10,2),
    sale_date date,
    sale_price numeric(12,2),
    writeoff_date date,
    writeoff_reason character varying(200),
    repossession_date date,
    lifecycle_status character varying(50),
    tier_id integer,
    maintenance_start_date date,
    maintenance_end_date date,
    is_in_maintenance boolean DEFAULT false,
    red_deer_compliant boolean DEFAULT false
);


--
-- Name: v_cvip_compliance; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_cvip_compliance AS
 SELECT vehicle_id,
    vehicle_number,
    make,
    model,
    year,
    license_plate,
    cvip_expiry_date,
    cvip_inspection_number,
    cvip_compliance_status,
        CASE
            WHEN (cvip_expiry_date IS NULL) THEN 'NO_RECORD'::text
            WHEN (cvip_expiry_date < CURRENT_DATE) THEN 'EXPIRED'::text
            WHEN (cvip_expiry_date < (CURRENT_DATE + '30 days'::interval)) THEN 'EXPIRING_SOON'::text
            ELSE 'CURRENT'::text
        END AS alert_status,
    (cvip_expiry_date - CURRENT_DATE) AS days_remaining
   FROM public.vehicles v
  WHERE (is_active = true)
  ORDER BY cvip_expiry_date NULLS FIRST;


--
-- Name: v_deferred_wage_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_deferred_wage_summary AS
 SELECT e.employee_id,
    e.full_name,
    dwa.account_id,
    dwa.account_name,
    dwa.current_balance,
    dwa.ytd_deferred_amount,
    dwa.ytd_paid_amount,
    dwa.lifetime_deferred,
    dwa.lifetime_paid,
    dwa.accumulated_interest,
    dwa.account_status,
    dwa.last_interest_calculation,
    count(dwt.transaction_id) AS total_transactions,
    max(dwt.transaction_date) AS last_transaction_date
   FROM ((public.employees e
     JOIN public.deferred_wage_accounts dwa ON ((e.employee_id = dwa.employee_id)))
     LEFT JOIN public.deferred_wage_transactions dwt ON ((dwa.account_id = dwt.account_id)))
  GROUP BY e.employee_id, e.full_name, dwa.account_id, dwa.account_name, dwa.current_balance, dwa.ytd_deferred_amount, dwa.ytd_paid_amount, dwa.lifetime_deferred, dwa.lifetime_paid, dwa.accumulated_interest, dwa.account_status, dwa.last_interest_calculation;


--
-- Name: v_driver_pay_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_driver_pay_summary AS
 SELECT e.employee_id,
    e.first_name,
    e.last_name,
    date_trunc('month'::text, (dp.pay_date)::timestamp with time zone) AS pay_period,
    count(DISTINCT dp.reserve_number) AS total_charters,
    sum(dp.hours_worked) AS total_hours,
    sum(dp.gross_pay) AS total_pay,
    avg((dp.gross_pay / NULLIF(dp.hours_worked, (0)::numeric))) AS avg_effective_hourly
   FROM (public.driver_payroll dp
     JOIN public.employees e ON ((dp.employee_id = e.employee_id)))
  WHERE (dp.hours_worked > (0)::numeric)
  GROUP BY e.employee_id, e.first_name, e.last_name, (date_trunc('month'::text, (dp.pay_date)::timestamp with time zone));


--
-- Name: v_hos_compliance_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_hos_compliance_summary AS
 SELECT e.employee_id,
    e.first_name,
    e.last_name,
    date_trunc('month'::text, (hl.hos_date)::timestamp with time zone) AS compliance_period,
    count(*) AS total_shifts,
    sum(
        CASE
            WHEN ((hl.hos_status)::text = 'compliant'::text) THEN 1
            ELSE 0
        END) AS compliant_shifts,
    sum(
        CASE
            WHEN ((hl.hos_status)::text = 'warning'::text) THEN 1
            ELSE 0
        END) AS warning_shifts,
    sum(
        CASE
            WHEN ((hl.hos_status)::text = 'violation'::text) THEN 1
            ELSE 0
        END) AS violation_shifts,
    sum(
        CASE
            WHEN hl.logbook_required THEN 1
            ELSE 0
        END) AS logbook_required_shifts
   FROM (public.hos_log hl
     JOIN public.employees e ON ((hl.employee_id = e.employee_id)))
  GROUP BY e.employee_id, e.first_name, e.last_name, (date_trunc('month'::text, (hl.hos_date)::timestamp with time zone))
  ORDER BY (date_trunc('month'::text, (hl.hos_date)::timestamp with time zone)) DESC, (sum(
        CASE
            WHEN ((hl.hos_status)::text = 'violation'::text) THEN 1
            ELSE 0
        END)) DESC;


--
-- Name: v_incident_trends; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_incident_trends AS
 SELECT date_trunc('month'::text, occurred_at) AS month,
    incident_type,
    incident_severity,
    count(*) AS total_incidents,
    sum(
        CASE
            WHEN gratuity_impact THEN 1
            ELSE 0
        END) AS gratuity_forfeitures,
    sum(poor_service_reimbursement) AS total_reimbursements
   FROM public.charter_incidents
  GROUP BY (date_trunc('month'::text, occurred_at)), incident_type, incident_severity
  ORDER BY (date_trunc('month'::text, occurred_at)) DESC, (count(*)) DESC;


--
-- Name: v_maintenance_due; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_maintenance_due AS
 SELECT v.vehicle_id,
    v.vehicle_number,
    v.make,
    v.model,
    ms.maintenance_type,
    ms.due_date,
    ms.due_mileage,
    v.odometer AS current_mileage,
    ms.days_until_due,
    ms.km_until_due,
    ms.status,
        CASE
            WHEN ((ms.status)::text = 'OVERDUE'::text) THEN 'CRITICAL'::text
            WHEN (ms.days_until_due < 7) THEN 'WARNING'::text
            WHEN (ms.days_until_due < 30) THEN 'INFO'::text
            ELSE 'OK'::text
        END AS alert_level
   FROM (public.vehicles v
     LEFT JOIN public.maintenance_schedules_auto ms ON ((v.vehicle_id = ms.vehicle_id)))
  WHERE ((v.is_active = true) AND (((ms.status)::text = 'OVERDUE'::text) OR (ms.days_until_due < 30)))
  ORDER BY ms.days_until_due NULLS FIRST;


--
-- Name: v_outstanding_receivables; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_outstanding_receivables AS
 SELECT i.reserve_number,
    c.charter_date,
    COALESCE(c.client_display_name, 'Unknown Customer'::text) AS customer_name,
    i.invoice_number,
    i.invoice_date,
    i.due_date,
    (CURRENT_DATE - i.due_date) AS days_overdue,
    i.invoice_total,
    i.total_payments,
    i.balance_due,
    i.invoice_status
   FROM (public.invoices i
     JOIN public.charters c ON (((i.reserve_number)::text = (c.reserve_number)::text)))
  WHERE ((i.balance_due > (0)::numeric) AND ((i.invoice_status)::text <> 'credited'::text))
  ORDER BY i.due_date;


--
-- Name: v_owner_expense_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_owner_expense_summary AS
 SELECT oea.owner_name,
    oea.account_type,
    oea.current_balance,
    oea.ytd_business_expenses,
    oea.ytd_personal_allocation,
    oea.t4_reportable_income,
    count(oet.transaction_id) AS total_transactions,
    sum(
        CASE
            WHEN ((oet.transaction_type)::text = 'business_expense'::text) THEN oet.business_portion
            ELSE (0)::numeric
        END) AS total_business_expenses,
    sum(
        CASE
            WHEN ((oet.transaction_type)::text = 'personal_allocation'::text) THEN oet.personal_portion
            ELSE (0)::numeric
        END) AS total_personal_allocations,
    max(oet.transaction_date) AS last_transaction_date
   FROM (public.owner_equity_accounts oea
     LEFT JOIN public.owner_expense_transactions oet ON ((oea.equity_account_id = oet.equity_account_id)))
  GROUP BY oea.owner_name, oea.account_type, oea.current_balance, oea.ytd_business_expenses, oea.ytd_personal_allocation, oea.t4_reportable_income;


--
-- Name: v_revenue_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_revenue_summary AS
 SELECT date_trunc('month'::text, (c.charter_date)::timestamp with time zone) AS month,
    count(DISTINCT c.reserve_number) AS total_charters,
    sum(i.invoice_total) AS total_invoiced,
    sum(i.total_payments) AS total_paid,
    sum(i.balance_due) AS total_outstanding
   FROM (public.charters c
     LEFT JOIN public.invoices i ON (((c.reserve_number)::text = (i.reserve_number)::text)))
  WHERE ((c.status IS NULL) OR ((c.status)::text <> 'Cancelled'::text))
  GROUP BY (date_trunc('month'::text, (c.charter_date)::timestamp with time zone))
  ORDER BY (date_trunc('month'::text, (c.charter_date)::timestamp with time zone)) DESC;


--
-- Name: vehicle_mileage_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vehicle_mileage_log (
    log_id integer NOT NULL,
    vehicle_id integer,
    charter_id integer,
    recorded_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    odometer_reading integer NOT NULL,
    odometer_type character varying(2) DEFAULT 'km'::character varying,
    recorded_by character varying(100),
    reading_type character varying(50),
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: v_vehicle_latest_mileage; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_vehicle_latest_mileage AS
 WITH latest_readings AS (
         SELECT vehicle_mileage_log.vehicle_id,
            vehicle_mileage_log.odometer_reading,
            vehicle_mileage_log.recorded_at,
            vehicle_mileage_log.reading_type,
            row_number() OVER (PARTITION BY vehicle_mileage_log.vehicle_id ORDER BY vehicle_mileage_log.recorded_at DESC) AS rn
           FROM public.vehicle_mileage_log
        )
 SELECT v.vehicle_id,
    v.unit_number,
    v.make,
    v.model,
    v.year,
    v.vehicle_type,
    v.odometer AS vehicle_odometer,
    lr.odometer_reading AS latest_logged_mileage,
    lr.recorded_at AS last_reading_date,
    lr.reading_type AS last_reading_type,
    COALESCE(lr.odometer_reading, v.odometer, 0) AS current_mileage
   FROM (public.vehicles v
     LEFT JOIN latest_readings lr ON (((v.vehicle_id = lr.vehicle_id) AND (lr.rn = 1))));


--
-- Name: vacation_pay_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vacation_pay_records (
    id integer NOT NULL,
    employee_id integer,
    employee_name character varying(200),
    pay_period character varying(50),
    vacation_amount numeric(12,2),
    payout_date date,
    accumulated_hours numeric(8,2),
    hourly_rate numeric(8,2),
    source_file character varying(500),
    record_notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: vacation_pay_records_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vacation_pay_records_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vacation_pay_records_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vacation_pay_records_id_seq OWNED BY public.vacation_pay_records.id;


--
-- Name: vehicle_capacity_tiers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vehicle_capacity_tiers (
    tier_id integer NOT NULL,
    tier_name character varying(50) NOT NULL,
    min_capacity integer,
    max_capacity integer,
    tier_group integer,
    display_order integer
);


--
-- Name: vehicle_capacity_tiers_tier_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vehicle_capacity_tiers_tier_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vehicle_capacity_tiers_tier_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vehicle_capacity_tiers_tier_id_seq OWNED BY public.vehicle_capacity_tiers.tier_id;


--
-- Name: vehicle_document_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vehicle_document_types (
    doc_type_id integer NOT NULL,
    type_code character varying(20) NOT NULL,
    type_name character varying(100) NOT NULL,
    category character varying(50) NOT NULL,
    is_mandatory boolean DEFAULT false,
    requires_renewal boolean DEFAULT false,
    default_validity_months integer,
    renewal_notice_days integer DEFAULT 30,
    regulatory_authority character varying(100),
    description text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: vehicle_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vehicle_documents (
    document_id integer NOT NULL,
    vehicle_id integer NOT NULL,
    doc_type_id integer NOT NULL,
    document_number character varying(100),
    document_title character varying(200),
    issuing_authority character varying(100),
    issue_date date,
    effective_date date,
    expiry_date date,
    renewal_date date,
    file_name character varying(255),
    file_path character varying(500),
    file_size_bytes integer,
    file_type character varying(20),
    file_hash character varying(64),
    status character varying(20) DEFAULT 'active'::character varying,
    is_expired boolean DEFAULT false,
    renewal_notice_sent boolean DEFAULT false,
    last_verified_date date,
    cost_amount numeric(10,2),
    renewal_cost numeric(10,2),
    notes text,
    tags character varying(500),
    uploaded_by character varying(100),
    verified_by character varying(100),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: vehicle_compliance_dashboard; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vehicle_compliance_dashboard AS
 SELECT vehicle_id,
    vehicle_number,
    make,
    model,
    operational_status,
    ( SELECT count(*) AS count
           FROM (public.vehicle_documents vd
             JOIN public.vehicle_document_types vdt ON ((vd.doc_type_id = vdt.doc_type_id)))
          WHERE ((vd.vehicle_id = v.vehicle_id) AND ((vdt.category)::text = 'Registration'::text) AND ((vd.status)::text = 'active'::text))) AS registration_docs,
    ( SELECT count(*) AS count
           FROM (public.vehicle_documents vd
             JOIN public.vehicle_document_types vdt ON ((vd.doc_type_id = vdt.doc_type_id)))
          WHERE ((vd.vehicle_id = v.vehicle_id) AND ((vdt.category)::text = 'Insurance'::text) AND ((vd.status)::text = 'active'::text))) AS insurance_docs,
    ( SELECT count(*) AS count
           FROM (public.vehicle_documents vd
             JOIN public.vehicle_document_types vdt ON ((vd.doc_type_id = vdt.doc_type_id)))
          WHERE ((vd.vehicle_id = v.vehicle_id) AND ((vdt.category)::text = 'Inspection'::text) AND ((vd.status)::text = 'active'::text))) AS inspection_docs,
    ( SELECT count(*) AS count
           FROM (public.vehicle_documents vd
             JOIN public.vehicle_document_types vdt ON ((vd.doc_type_id = vdt.doc_type_id)))
          WHERE ((vd.vehicle_id = v.vehicle_id) AND ((vdt.category)::text = 'License'::text) AND ((vd.status)::text = 'active'::text))) AS license_docs,
    ( SELECT count(*) AS count
           FROM public.vehicle_documents vd
          WHERE ((vd.vehicle_id = v.vehicle_id) AND (vd.expiry_date < CURRENT_DATE) AND ((vd.status)::text = 'active'::text))) AS expired_docs_info,
    ( SELECT count(*) AS count
           FROM public.vehicle_documents vd
          WHERE ((vd.vehicle_id = v.vehicle_id) AND ((vd.expiry_date >= CURRENT_DATE) AND (vd.expiry_date <= (CURRENT_DATE + '30 days'::interval))) AND ((vd.status)::text = 'active'::text))) AS expiring_soon_info,
        CASE
            WHEN (( SELECT count(*) AS count
               FROM public.vehicle_documents vd
              WHERE ((vd.vehicle_id = v.vehicle_id) AND (vd.expiry_date < CURRENT_DATE) AND ((vd.status)::text = 'active'::text))) > 0) THEN 'ALERTS_INFO_ONLY'::text
            WHEN (( SELECT count(*) AS count
               FROM public.vehicle_documents vd
              WHERE ((vd.vehicle_id = v.vehicle_id) AND (vd.expiry_date <= (CURRENT_DATE + '7 days'::interval)) AND ((vd.status)::text = 'active'::text))) > 0) THEN 'EXPIRING_INFO_ONLY'::text
            WHEN (( SELECT count(*) AS count
               FROM public.vehicle_documents vd
              WHERE ((vd.vehicle_id = v.vehicle_id) AND (vd.expiry_date <= (CURRENT_DATE + '30 days'::interval)) AND ((vd.status)::text = 'active'::text))) > 0) THEN 'RENEWAL_INFO_ONLY'::text
            ELSE 'COMPLIANT_INFO'::text
        END AS compliance_status,
    'ALWAYS_OPERATIONAL'::text AS usage_policy,
    'Vehicle usage never restricted by alerts or compliance status'::text AS policy_description
   FROM public.vehicles v
  WHERE (is_active = true)
  ORDER BY fleet_position;


--
-- Name: vehicle_document_alerts; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vehicle_document_alerts AS
 SELECT v.vehicle_id,
    v.vehicle_number,
    v.make,
    v.model,
    v.operational_status,
    vdt.type_name,
    vdt.category,
    vd.document_number,
    vd.expiry_date,
    vd.status,
        CASE
            WHEN (vd.expiry_date IS NOT NULL) THEN (vd.expiry_date - CURRENT_DATE)
            ELSE NULL::integer
        END AS days_until_expiry,
        CASE
            WHEN (vd.expiry_date < CURRENT_DATE) THEN 'EXPIRED_INFO'::text
            WHEN (vd.expiry_date <= (CURRENT_DATE + '7 days'::interval)) THEN 'CRITICAL_INFO'::text
            WHEN (vd.expiry_date <= (CURRENT_DATE + '30 days'::interval)) THEN 'WARNING_INFO'::text
            WHEN (vd.expiry_date <= (CURRENT_DATE + '60 days'::interval)) THEN 'NOTICE_INFO'::text
            ELSE 'OK'::text
        END AS alert_level,
        CASE
            WHEN (vd.expiry_date < CURRENT_DATE) THEN 'EXPIRED - INFORMATIONAL ALERT ONLY'::text
            WHEN (vd.expiry_date <= (CURRENT_DATE + '7 days'::interval)) THEN 'EXPIRING SOON - INFORMATIONAL ONLY'::text
            WHEN (vd.expiry_date <= (CURRENT_DATE + '30 days'::interval)) THEN 'RENEWAL REMINDER - INFORMATIONAL'::text
            ELSE 'DOCUMENT OK'::text
        END AS alert_message,
    'USAGE_ALWAYS_ALLOWED'::text AS vehicle_usage_status,
    'Vehicle remains operational regardless of document status'::text AS usage_policy,
    vd.file_path,
    vd.last_verified_date
   FROM ((public.vehicles v
     JOIN public.vehicle_documents vd ON ((v.vehicle_id = vd.vehicle_id)))
     JOIN public.vehicle_document_types vdt ON ((vd.doc_type_id = vdt.doc_type_id)))
  WHERE ((v.is_active = true) AND ((vd.status)::text = 'active'::text) AND (vdt.requires_renewal = true))
  ORDER BY
        CASE
            WHEN (vd.expiry_date < CURRENT_DATE) THEN 1
            WHEN (vd.expiry_date <= (CURRENT_DATE + '7 days'::interval)) THEN 2
            WHEN (vd.expiry_date <= (CURRENT_DATE + '30 days'::interval)) THEN 3
            ELSE 4
        END, vd.expiry_date;


--
-- Name: vehicle_document_types_doc_type_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vehicle_document_types_doc_type_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vehicle_document_types_doc_type_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vehicle_document_types_doc_type_id_seq OWNED BY public.vehicle_document_types.doc_type_id;


--
-- Name: vehicle_documents_document_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vehicle_documents_document_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vehicle_documents_document_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vehicle_documents_document_id_seq OWNED BY public.vehicle_documents.document_id;


--
-- Name: vehicle_financing; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vehicle_financing (
    financing_id integer NOT NULL,
    vehicle_id integer,
    financing_type character varying(20) DEFAULT 'purchase'::character varying,
    status character varying(20) DEFAULT 'active'::character varying,
    purchase_price numeric(12,2),
    purchase_date date,
    purchase_vendor character varying(100),
    purchase_contact character varying(100),
    purchase_phone character varying(20),
    purchase_down_payment numeric(12,2),
    financed_amount numeric(12,2),
    lender_name character varying(100),
    loan_number character varying(50),
    loan_amount numeric(12,2),
    monthly_payment numeric(10,2),
    interest_rate numeric(5,4),
    loan_start_date date,
    loan_end_date date,
    remaining_balance numeric(12,2),
    lease_company character varying(100),
    lease_contract_number character varying(50),
    lease_monthly_payment numeric(10,2),
    lease_start_date date,
    lease_end_date date,
    lease_mileage_limit integer,
    lease_excess_mileage_fee numeric(6,2),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    notes text
);


--
-- Name: vehicle_financing_complete; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vehicle_financing_complete (
    id integer NOT NULL,
    vehicle_id integer,
    vehicle_description character varying(300),
    original_purchase_price numeric(12,2),
    original_purchase_date date,
    financing_partner character varying(200),
    refinance_date date,
    refinance_partner character varying(200),
    total_payments_made numeric(12,2),
    final_payment_date date,
    release_date date,
    actual_total_paid numeric(12,2),
    purchase_vs_paid_difference numeric(12,2),
    financing_cost numeric(12,2),
    status character varying(50),
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: vehicle_financing_complete_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vehicle_financing_complete_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vehicle_financing_complete_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vehicle_financing_complete_id_seq OWNED BY public.vehicle_financing_complete.id;


--
-- Name: vehicle_financing_financing_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vehicle_financing_financing_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vehicle_financing_financing_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vehicle_financing_financing_id_seq OWNED BY public.vehicle_financing.financing_id;


--
-- Name: vehicle_fuel_expenses; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vehicle_fuel_expenses AS
 SELECT v.vehicle_id,
    v.make,
    v.model,
    v.year,
    v.vin_number,
    v.license_plate,
    count(r.receipt_id) AS fuel_receipt_count,
    sum(r.gross_amount) AS total_fuel_cost,
    avg(r.gross_amount) AS avg_fuel_cost,
    min(r.receipt_date) AS first_fuel_date,
    max(r.receipt_date) AS last_fuel_date
   FROM (public.vehicles v
     LEFT JOIN public.receipts r ON ((v.vehicle_id = r.vehicle_id)))
  WHERE ((lower(r.description) ~~ '%fuel%'::text) OR (lower(r.description) ~~ '%gas%'::text) OR (lower(r.description) ~~ '%diesel%'::text))
  GROUP BY v.vehicle_id, v.make, v.model, v.year, v.vin_number, v.license_plate
  ORDER BY (sum(r.gross_amount)) DESC;


--
-- Name: vehicle_fuel_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vehicle_fuel_log (
    id integer NOT NULL,
    vehicle_id text NOT NULL,
    amount numeric(10,2) NOT NULL,
    charter_id integer,
    receipt_id integer,
    recorded_at timestamp without time zone DEFAULT now() NOT NULL,
    recorded_by text,
    log_id integer NOT NULL,
    liters numeric(8,2) DEFAULT 0,
    odometer_reading integer DEFAULT 0
);


--
-- Name: vehicle_fuel_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vehicle_fuel_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vehicle_fuel_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vehicle_fuel_log_id_seq OWNED BY public.vehicle_fuel_log.id;


--
-- Name: vehicle_fuel_log_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vehicle_fuel_log_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vehicle_fuel_log_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vehicle_fuel_log_log_id_seq OWNED BY public.vehicle_fuel_log.log_id;


--
-- Name: vehicle_identification; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vehicle_identification AS
 SELECT vehicle_id,
    vehicle_number,
    vin_number,
    vehicle_type AS vehicle_code,
    fleet_number,
    license_plate,
    make,
    model,
    year,
    type,
    vehicle_category,
    vehicle_class,
    passenger_capacity,
    operational_status,
    description
   FROM public.vehicles
  ORDER BY vehicle_number;


--
-- Name: vehicle_insurance; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vehicle_insurance (
    insurance_id integer NOT NULL,
    vehicle_id integer,
    carrier character varying(100) NOT NULL,
    agency character varying(100),
    agent_name character varying(100),
    agent_phone character varying(20),
    agent_email character varying(100),
    policy_number character varying(50) NOT NULL,
    policy_type character varying(30) DEFAULT 'comprehensive'::character varying,
    coverage_amount numeric(12,2),
    annual_premium numeric(10,2),
    monthly_premium numeric(8,2),
    deductible_collision numeric(8,2),
    deductible_comprehensive numeric(8,2),
    policy_start_date date NOT NULL,
    policy_end_date date NOT NULL,
    renewal_date date,
    has_claims boolean DEFAULT false,
    total_claims_amount numeric(12,2) DEFAULT 0,
    claims_count integer DEFAULT 0,
    last_claim_date date,
    status character varying(20) DEFAULT 'active'::character varying,
    auto_renew boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    notes text
);


--
-- Name: vehicle_insurance_expenses; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vehicle_insurance_expenses AS
 SELECT v.vehicle_id,
    v.make,
    v.model,
    v.year,
    count(r.receipt_id) AS insurance_receipt_count,
    sum(r.gross_amount) AS total_insurance_cost,
    min(r.receipt_date) AS first_insurance_date,
    max(r.receipt_date) AS last_insurance_date
   FROM (public.vehicles v
     LEFT JOIN public.receipts r ON ((v.vehicle_id = r.vehicle_id)))
  WHERE ((lower(r.description) ~~ '%insurance%'::text) OR (lower(r.description) ~~ '%premium%'::text))
  GROUP BY v.vehicle_id, v.make, v.model, v.year
  ORDER BY (sum(r.gross_amount)) DESC;


--
-- Name: vehicle_insurance_insurance_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vehicle_insurance_insurance_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vehicle_insurance_insurance_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vehicle_insurance_insurance_id_seq OWNED BY public.vehicle_insurance.insurance_id;


--
-- Name: vehicle_loan_payments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vehicle_loan_payments (
    id integer NOT NULL,
    vehicle_id integer,
    vehicle_vin character varying(50),
    vehicle_description text,
    lender_name character varying(200),
    banking_transaction_id integer,
    payment_date date NOT NULL,
    payment_type character varying(50),
    gross_amount numeric(12,2),
    gst_amount numeric(12,2),
    net_amount numeric(12,2),
    gst_rate numeric(5,4) DEFAULT 0.05,
    nsf_related boolean DEFAULT false,
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: vehicle_loan_payments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vehicle_loan_payments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vehicle_loan_payments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vehicle_loan_payments_id_seq OWNED BY public.vehicle_loan_payments.id;


--
-- Name: vehicle_loan_reconciliation_allocations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vehicle_loan_reconciliation_allocations (
    id integer NOT NULL,
    lender_id integer NOT NULL,
    bank_txn_id integer,
    bank_txn_id_2 integer,
    lender_date date,
    bank_date date,
    lender_amount numeric(14,2),
    bank_net numeric(14,2),
    principal_amount numeric(14,2),
    interest_amount numeric(14,2),
    fee_amount numeric(14,2),
    notes text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: vehicle_loan_reconciliation_allocations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vehicle_loan_reconciliation_allocations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vehicle_loan_reconciliation_allocations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vehicle_loan_reconciliation_allocations_id_seq OWNED BY public.vehicle_loan_reconciliation_allocations.id;


--
-- Name: vehicle_loans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vehicle_loans (
    id integer NOT NULL,
    vehicle_id integer NOT NULL,
    vehicle_name text NOT NULL,
    lender text NOT NULL,
    paid_by text NOT NULL,
    opening_balance numeric(14,2),
    closing_balance numeric(14,2),
    total_paid numeric(14,2),
    total_interest numeric(14,2),
    total_fees numeric(14,2),
    total_penalties numeric(14,2),
    total_sold_for numeric(14,2),
    loan_start_date date,
    loan_end_date date,
    notes text
);


--
-- Name: vehicle_loans_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vehicle_loans_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vehicle_loans_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vehicle_loans_id_seq OWNED BY public.vehicle_loans.id;


--
-- Name: vehicle_maintenance_dashboard; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vehicle_maintenance_dashboard AS
 SELECT vehicle_id,
    vehicle_number,
    make,
    model,
    year,
    odometer,
    last_service_date,
    ( SELECT count(*) AS count
           FROM public.maintenance_records mr
          WHERE ((mr.vehicle_id = v.vehicle_id) AND (mr.service_date >= (CURRENT_DATE - '30 days'::interval)))) AS recent_services_30d,
    ( SELECT count(*) AS count
           FROM public.maintenance_records mr
          WHERE (mr.vehicle_id = v.vehicle_id)) AS total_services,
    ( SELECT max(mr.service_date) AS max
           FROM (public.maintenance_records mr
             JOIN public.maintenance_activity_types mat ON ((mr.activity_type_id = mat.activity_type_id)))
          WHERE ((mr.vehicle_id = v.vehicle_id) AND ((mat.activity_code)::text = 'OIL001'::text))) AS last_oil_change,
    ( SELECT max(mr.service_date) AS max
           FROM (public.maintenance_records mr
             JOIN public.maintenance_activity_types mat ON ((mr.activity_type_id = mat.activity_type_id)))
          WHERE ((mr.vehicle_id = v.vehicle_id) AND ((mat.activity_code)::text = 'CVIP'::text))) AS last_cvip_date,
    ( SELECT max(mr.service_date) AS max
           FROM (public.maintenance_records mr
             JOIN public.maintenance_activity_types mat ON ((mr.activity_type_id = mat.activity_type_id)))
          WHERE ((mr.vehicle_id = v.vehicle_id) AND ((mat.category)::text = 'Tires'::text))) AS last_tire_service,
    ( SELECT COALESCE(sum(mr.total_cost), (0)::numeric) AS "coalesce"
           FROM public.maintenance_records mr
          WHERE ((mr.vehicle_id = v.vehicle_id) AND (mr.service_date >= (CURRENT_DATE - '1 year'::interval)))) AS cost_12_months,
    ( SELECT count(*) AS count
           FROM public.get_maintenance_due(v.vehicle_id) get_maintenance_due(activity_name, category, last_service_date, last_service_km, next_due_date, next_due_km, days_overdue, km_overdue, priority)
          WHERE ((get_maintenance_due.days_overdue > 0) OR (get_maintenance_due.km_overdue > 0))) AS overdue_services
   FROM public.vehicles v
  WHERE (is_active = true)
  ORDER BY fleet_position;


--
-- Name: vehicle_maintenance_expenses; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vehicle_maintenance_expenses AS
 SELECT v.vehicle_id,
    v.make,
    v.model,
    v.year,
    v.vin_number,
    count(r.receipt_id) AS maintenance_receipt_count,
    sum(r.gross_amount) AS total_maintenance_cost,
    avg(r.gross_amount) AS avg_maintenance_cost,
    min(r.receipt_date) AS first_maintenance_date,
    max(r.receipt_date) AS last_maintenance_date
   FROM (public.vehicles v
     LEFT JOIN public.receipts r ON ((v.vehicle_id = r.vehicle_id)))
  WHERE ((lower(r.description) ~~ '%repair%'::text) OR (lower(r.description) ~~ '%service%'::text) OR (lower(r.description) ~~ '%maintenance%'::text))
  GROUP BY v.vehicle_id, v.make, v.model, v.year, v.vin_number
  ORDER BY (sum(r.gross_amount)) DESC;


--
-- Name: vehicle_mileage_log_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vehicle_mileage_log_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vehicle_mileage_log_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vehicle_mileage_log_log_id_seq OWNED BY public.vehicle_mileage_log.log_id;


--
-- Name: vehicle_pre_inspections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vehicle_pre_inspections (
    inspection_id integer NOT NULL,
    charter_id integer,
    vehicle_id integer,
    driver_id integer,
    inspection_date date NOT NULL,
    inspection_time time without time zone,
    inspection_type character varying(50),
    completed boolean DEFAULT false,
    completed_time timestamp without time zone,
    pass_fail character varying(20),
    issues_found integer DEFAULT 0,
    critical_issues integer DEFAULT 0,
    issues_json jsonb,
    cleared_to_operate boolean DEFAULT false,
    clearance_time timestamp without time zone,
    clearance_notes text,
    previous_inspection_id integer,
    carryover_issues text,
    notes text,
    signature character varying(200),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: vehicle_pre_inspections_inspection_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vehicle_pre_inspections_inspection_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vehicle_pre_inspections_inspection_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vehicle_pre_inspections_inspection_id_seq OWNED BY public.vehicle_pre_inspections.inspection_id;


--
-- Name: vehicle_pricing_defaults; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vehicle_pricing_defaults (
    pricing_id integer NOT NULL,
    vehicle_type character varying(50) NOT NULL,
    charter_type_code character varying(50) NOT NULL,
    hourly_rate numeric(10,2) DEFAULT 0.00,
    package_rate numeric(10,2) DEFAULT 0.00,
    package_hours numeric(5,2) DEFAULT 0.00,
    minimum_hours numeric(5,2) DEFAULT 0.00,
    extra_time_rate numeric(10,2) DEFAULT 0.00,
    standby_rate numeric(10,2) DEFAULT 25.00,
    split_run_before_hours numeric(5,2) DEFAULT 1.5,
    split_run_after_hours numeric(5,2) DEFAULT 1.5,
    is_active boolean DEFAULT true,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: vehicle_pricing_defaults_pricing_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vehicle_pricing_defaults_pricing_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vehicle_pricing_defaults_pricing_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vehicle_pricing_defaults_pricing_id_seq OWNED BY public.vehicle_pricing_defaults.pricing_id;


--
-- Name: vehicle_purchases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vehicle_purchases (
    purchase_id integer NOT NULL,
    vehicle_id integer,
    purchase_date date NOT NULL,
    vendor_name character varying(200),
    purchase_price numeric(12,2),
    down_payment numeric(12,2),
    financing_partner character varying(200),
    financing_amount numeric(12,2),
    financing_term_months integer,
    interest_rate numeric(5,4),
    monthly_payment numeric(10,2),
    invoice_number character varying(50),
    po_number character varying(50),
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: vehicle_purchases_purchase_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vehicle_purchases_purchase_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vehicle_purchases_purchase_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vehicle_purchases_purchase_id_seq OWNED BY public.vehicle_purchases.purchase_id;


--
-- Name: vehicle_repossessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vehicle_repossessions (
    repossession_id integer NOT NULL,
    vehicle_id integer,
    repossession_date date NOT NULL,
    lender_name character varying(200),
    reason character varying(200),
    recovery_location character varying(200),
    recovery_cost numeric(10,2),
    sold_to_lender boolean,
    auction_date date,
    final_amount_owed numeric(12,2),
    reportable_event boolean DEFAULT true,
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: vehicle_repossessions_repossession_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vehicle_repossessions_repossession_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vehicle_repossessions_repossession_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vehicle_repossessions_repossession_id_seq OWNED BY public.vehicle_repossessions.repossession_id;


--
-- Name: vehicle_sales; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vehicle_sales (
    sale_id integer NOT NULL,
    vehicle_id integer,
    sale_date date NOT NULL,
    buyer_name character varying(200),
    sale_price numeric(12,2),
    sale_status character varying(50),
    auction_company character varying(200),
    auction_date date,
    lot_number character varying(50),
    hammer_price numeric(12,2),
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: vehicle_sales_sale_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vehicle_sales_sale_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vehicle_sales_sale_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vehicle_sales_sale_id_seq OWNED BY public.vehicle_sales.sale_id;


--
-- Name: vehicle_writeoffs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vehicle_writeoffs (
    writeoff_id integer NOT NULL,
    vehicle_id integer,
    writeoff_date date NOT NULL,
    writeoff_reason character varying(100),
    insurance_claim_number character varying(50),
    insurance_company character varying(200),
    claim_amount numeric(12,2),
    claim_status character varying(50),
    book_value numeric(12,2),
    salvage_value numeric(12,2),
    loss_amount numeric(12,2),
    deduction_claimed boolean,
    deduction_amount numeric(12,2),
    cra_class character varying(20),
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: vehicle_writeoffs_writeoff_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vehicle_writeoffs_writeoff_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vehicle_writeoffs_writeoff_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vehicle_writeoffs_writeoff_id_seq OWNED BY public.vehicle_writeoffs.writeoff_id;


--
-- Name: vehicles_vehicle_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vehicles_vehicle_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vehicles_vehicle_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vehicles_vehicle_id_seq OWNED BY public.vehicles.vehicle_id;


--
-- Name: vendor_account_ledger; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vendor_account_ledger (
    ledger_id bigint NOT NULL,
    account_id bigint NOT NULL,
    entry_date date NOT NULL,
    entry_type character varying(20) NOT NULL,
    amount numeric(14,2) NOT NULL,
    balance_after numeric(14,2),
    source_table character varying(50),
    source_id character varying(100),
    external_ref character varying(100),
    match_confidence numeric(4,2),
    notes text,
    created_at timestamp without time zone DEFAULT now(),
    payment_method character varying(50),
    CONSTRAINT entry_type_ck CHECK (((entry_type)::text = ANY ((ARRAY['INVOICE'::character varying, 'PAYMENT'::character varying, 'ADJUSTMENT'::character varying])::text[]))),
    CONSTRAINT vendor_account_ledger_payment_method_check CHECK (((payment_method IS NULL) OR ((payment_method)::text = ANY (ARRAY['cash'::text, 'check'::text, 'credit_card'::text, 'debit_card'::text, 'bank_transfer'::text, 'trade_of_services'::text, 'unknown'::text, 'credit_adjustment'::text]))))
);


--
-- Name: vendor_account_ledger_ledger_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vendor_account_ledger_ledger_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vendor_account_ledger_ledger_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vendor_account_ledger_ledger_id_seq OWNED BY public.vendor_account_ledger.ledger_id;


--
-- Name: vendor_accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vendor_accounts (
    account_id bigint NOT NULL,
    canonical_vendor character varying(255) NOT NULL,
    display_name character varying(255),
    created_at timestamp without time zone DEFAULT now(),
    payment_terms character varying(20),
    contact_email character varying(255),
    notes text,
    status character varying(20) DEFAULT 'active'::character varying,
    CONSTRAINT status_ck CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'inactive'::character varying, 'archived'::character varying])::text[])))
);


--
-- Name: COLUMN vendor_accounts.payment_terms; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vendor_accounts.payment_terms IS 'Payment terms (NET30, NET60, etc.)';


--
-- Name: COLUMN vendor_accounts.contact_email; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vendor_accounts.contact_email IS 'Email for sending statement requests';


--
-- Name: vendor_accounts_account_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vendor_accounts_account_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vendor_accounts_account_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vendor_accounts_account_id_seq OWNED BY public.vendor_accounts.account_id;


--
-- Name: vendor_default_categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vendor_default_categories (
    id integer NOT NULL,
    vendor_canonical_name character varying(200) NOT NULL,
    default_category character varying(100) NOT NULL,
    default_subcategory character varying(100),
    allows_splits boolean DEFAULT true,
    common_split_categories text[],
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: vendor_default_categories_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vendor_default_categories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vendor_default_categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vendor_default_categories_id_seq OWNED BY public.vendor_default_categories.id;


--
-- Name: vendor_name_mapping; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vendor_name_mapping (
    id integer NOT NULL,
    raw_vendor_name character varying(500) NOT NULL,
    normalized_vendor_name character varying(200) NOT NULL,
    canonical_vendor_name character varying(200) NOT NULL,
    confidence_score integer DEFAULT 100,
    transaction_count integer DEFAULT 0,
    total_amount numeric(12,2) DEFAULT 0,
    source_systems text[],
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    notes text
);


--
-- Name: vendor_name_mapping_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vendor_name_mapping_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vendor_name_mapping_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vendor_name_mapping_id_seq OWNED BY public.vendor_name_mapping.id;


--
-- Name: vendor_standardization; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vendor_standardization (
    id integer NOT NULL,
    original_name character varying(300),
    standardized_name character varying(300),
    category character varying(100),
    consolidation_reason text,
    quickbooks_match boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: vendor_standardization_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vendor_standardization_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vendor_standardization_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vendor_standardization_id_seq OWNED BY public.vendor_standardization.id;


--
-- Name: vendor_synonyms; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vendor_synonyms (
    synonym_id bigint NOT NULL,
    account_id bigint NOT NULL,
    synonym character varying(255) NOT NULL,
    match_type character varying(20) DEFAULT 'exact'::character varying NOT NULL,
    confidence numeric(4,2) DEFAULT 0.95 NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    CONSTRAINT match_type_ck CHECK (((match_type)::text = ANY ((ARRAY['exact'::character varying, 'contains'::character varying, 'regex'::character varying])::text[])))
);


--
-- Name: TABLE vendor_synonyms; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.vendor_synonyms IS 'Dynamic vendor name synonym mapping for canonicalization';


--
-- Name: vendor_synonyms_synonym_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vendor_synonyms_synonym_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vendor_synonyms_synonym_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vendor_synonyms_synonym_id_seq OWNED BY public.vendor_synonyms.synonym_id;


--
-- Name: vendor_year_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vendor_year_summary AS
 SELECT (EXTRACT(year FROM receipt_date))::integer AS fiscal_year,
    vendor_name,
    count(*) AS transaction_count,
    sum(gross_amount) AS total_spent,
    min(receipt_date) AS first_purchase,
    max(receipt_date) AS last_purchase,
    count(DISTINCT gl_account_code) AS gl_codes_used
   FROM public.receipts
  WHERE ((receipt_date IS NOT NULL) AND (vendor_name IS NOT NULL))
  GROUP BY (EXTRACT(year FROM receipt_date)), vendor_name
 HAVING (sum(gross_amount) > (0)::numeric)
  ORDER BY ((EXTRACT(year FROM receipt_date))::integer), (sum(gross_amount)) DESC;


--
-- Name: vendors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vendors (
    id integer NOT NULL,
    quickbooks_id character varying(50),
    vendor_name character varying(255),
    company_name character varying(255),
    account_number character varying(50),
    email character varying(255),
    phone character varying(50),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    qb_vendor_type character varying(50),
    payment_terms character varying(50) DEFAULT 'Net 30'::character varying,
    credit_limit numeric(15,2),
    tax_id character varying(50),
    vendor_account_number character varying(50),
    billing_rate_level character varying(50),
    is_1099_contractor boolean DEFAULT false,
    default_expense_account character varying(50),
    is_sales_tax_vendor boolean DEFAULT false
);


--
-- Name: COLUMN vendors.qb_vendor_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vendors.qb_vendor_type IS 'Vendor classification (Supplier, Service, Fuel, Insurance, Financial, Government, etc.)';


--
-- Name: COLUMN vendors.payment_terms; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vendors.payment_terms IS 'Payment terms with this vendor (Net 30, Net 15, Due on Receipt, etc.)';


--
-- Name: COLUMN vendors.is_1099_contractor; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vendors.is_1099_contractor IS 'US tax form 1099 contractor status';


--
-- Name: vendors_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vendors_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vendors_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vendors_id_seq OWNED BY public.vendors.id;


--
-- Name: verification_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.verification_audit (
    audit_id integer NOT NULL,
    table_name character varying(50) NOT NULL,
    record_id bigint NOT NULL,
    record_type character varying(50),
    verified boolean NOT NULL,
    verified_date timestamp without time zone DEFAULT now() NOT NULL,
    verified_by character varying(100) NOT NULL,
    gl_code character varying(20),
    notes text,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: verification_audit_audit_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.verification_audit_audit_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: verification_audit_audit_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.verification_audit_audit_id_seq OWNED BY public.verification_audit.audit_id;


--
-- Name: verification_queue; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.verification_queue (
    id integer NOT NULL,
    source_table character varying(50) NOT NULL,
    source_id integer NOT NULL,
    title character varying(255) NOT NULL,
    description text,
    amount numeric(10,2),
    source_data jsonb,
    priority character varying(10) DEFAULT 'medium'::character varying,
    status character varying(30) DEFAULT 'pending_verification'::character varying,
    verification_notes text,
    duplicate_matches jsonb,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    reviewed_at timestamp without time zone,
    reviewed_by character varying(100),
    source character varying(20) DEFAULT 'manual'::character varying,
    CONSTRAINT verification_queue_priority_check CHECK (((priority)::text = ANY (ARRAY[('low'::character varying)::text, ('medium'::character varying)::text, ('high'::character varying)::text]))),
    CONSTRAINT verification_queue_source_check CHECK (((source)::text = ANY (ARRAY[('manual'::character varying)::text, ('email'::character varying)::text, ('bank'::character varying)::text, ('bulk_upload'::character varying)::text]))),
    CONSTRAINT verification_queue_source_table_check CHECK (((source_table)::text = ANY (ARRAY[('email_scanner_staging'::character varying)::text, ('bank_transactions_staging'::character varying)::text, ('personal_expenses'::character varying)::text]))),
    CONSTRAINT verification_queue_status_check CHECK (((status)::text = ANY (ARRAY[('pending_verification'::character varying)::text, ('approved'::character varying)::text, ('rejected'::character varying)::text, ('needs_clarification'::character varying)::text])))
);


--
-- Name: TABLE verification_queue; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.verification_queue IS 'Queue for manual verification of imported data';


--
-- Name: verification_queue_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.verification_queue_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: verification_queue_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.verification_queue_id_seq OWNED BY public.verification_queue.id;


--
-- Name: verification_queue_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.verification_queue_summary AS
 SELECT status,
    priority,
    source,
    count(*) AS count,
    sum(COALESCE(amount, (0)::numeric)) AS total_amount
   FROM public.verification_queue
  GROUP BY status, priority, source
  ORDER BY
        CASE priority
            WHEN 'high'::text THEN 1
            WHEN 'medium'::text THEN 2
            WHEN 'low'::text THEN 3
            ELSE NULL::integer
        END, status;


--
-- Name: verified_receipts_audit_detail; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.verified_receipts_audit_detail AS
 SELECT receipt_id,
    receipt_date,
    vendor_name,
    gross_amount,
    category,
    gl_account_code,
    verified_by_edit,
    verified_at,
    verified_by_user,
    created_at,
        CASE
            WHEN verified_by_edit THEN 'Manually Verified'::text
            WHEN (banking_transaction_id IS NOT NULL) THEN 'Banking Linked'::text
            ELSE 'Unverified'::text
        END AS verification_status
   FROM public.receipts r
  WHERE ((business_personal <> 'personal'::text) OR (business_personal IS NULL))
  ORDER BY verified_at DESC NULLS LAST, receipt_date DESC;


--
-- Name: verified_receipts_detail; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.verified_receipts_detail AS
 SELECT r.receipt_id,
    r.receipt_date,
    r.vendor_name,
    r.gross_amount,
    r.category,
    r.is_paper_verified,
    r.paper_verification_date,
    bt.transaction_id AS banking_id,
    bt.transaction_date AS banking_date,
    bt.description AS banking_description
   FROM (public.receipts r
     LEFT JOIN public.banking_transactions bt ON ((r.banking_transaction_id = bt.transaction_id)))
  WHERE (r.is_paper_verified = true)
  ORDER BY r.receipt_date DESC;


--
-- Name: wage_allocation_pool; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wage_allocation_pool (
    pool_id integer NOT NULL,
    pool_name character varying(100) NOT NULL,
    pool_type character varying(30) NOT NULL,
    total_available numeric(12,2) NOT NULL,
    allocated_amount numeric(12,2) DEFAULT 0,
    remaining_balance numeric(12,2) DEFAULT 0,
    allocation_period_start date NOT NULL,
    allocation_period_end date NOT NULL,
    allocation_frequency character varying(20),
    priority_employees text,
    minimum_allocation_per_employee numeric(10,2) DEFAULT 0,
    maximum_allocation_per_employee numeric(10,2),
    emergency_reserve_percentage numeric(5,2) DEFAULT 10,
    pool_status character varying(20) DEFAULT 'active'::character varying,
    allocation_complete boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    created_by integer
);


--
-- Name: TABLE wage_allocation_pool; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.wage_allocation_pool IS 'Available funds pool for strategic wage allocation decisions';


--
-- Name: wage_allocation_pool_pool_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.wage_allocation_pool_pool_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: wage_allocation_pool_pool_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.wage_allocation_pool_pool_id_seq OWNED BY public.wage_allocation_pool.pool_id;


--
-- Name: wcb_ab_industry_rates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wcb_ab_industry_rates (
    year integer NOT NULL,
    industry_code character varying(20) NOT NULL,
    industry_description text,
    premium_rate numeric(6,3) NOT NULL,
    max_assessable_earnings numeric(10,2),
    notes text
);


--
-- Name: wcb_ab_premium_rates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wcb_ab_premium_rates (
    year integer NOT NULL,
    industry_code character varying(32) NOT NULL,
    description text,
    base_premium_rate_per_100 numeric(7,4),
    experience_adjusted_rate_per_100 numeric(7,4)
);


--
-- Name: wcb_debt_ledger; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wcb_debt_ledger (
    id integer NOT NULL,
    transaction_date date NOT NULL,
    transaction_type character varying(20) NOT NULL,
    description text,
    charge_amount numeric(12,2) DEFAULT 0,
    payment_amount numeric(12,2) DEFAULT 0,
    running_balance numeric(12,2) NOT NULL,
    wcb_charge_id integer,
    email_event_id integer,
    banking_transaction_id bigint,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: wcb_debt_ledger_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.wcb_debt_ledger_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: wcb_debt_ledger_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.wcb_debt_ledger_id_seq OWNED BY public.wcb_debt_ledger.id;


--
-- Name: wcb_recurring_charges; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wcb_recurring_charges (
    id integer NOT NULL,
    charge_month date NOT NULL,
    gross_payroll numeric(12,2) DEFAULT 0 NOT NULL,
    wcb_rate numeric(7,4) NOT NULL,
    wcb_premium numeric(12,2) NOT NULL,
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: wcb_recurring_charges_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.wcb_recurring_charges_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: wcb_recurring_charges_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.wcb_recurring_charges_id_seq OWNED BY public.wcb_recurring_charges.id;


--
-- Name: wcb_summary; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wcb_summary (
    id integer NOT NULL,
    driver_id character varying(20),
    year integer,
    month integer,
    wcb_payment numeric(10,2),
    wcb_rate numeric(10,4),
    total_gross_pay numeric(10,2),
    source character varying(100),
    imported_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: wcb_summary_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.wcb_summary_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: wcb_summary_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.wcb_summary_id_seq OWNED BY public.wcb_summary.id;


--
-- Name: zero_payment_resolutions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.zero_payment_resolutions (
    payment_id integer NOT NULL,
    payment_square_id text,
    payment_amount numeric(12,2),
    payment_date date,
    refund_square_id integer,
    resolution_type character varying(50),
    resolution_subtype character varying(100),
    original_payment_id integer,
    resolution_notes text,
    status text,
    resolved_date timestamp with time zone
);


--
-- Name: zero_payment_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.zero_payment_summary AS
 SELECT 'ZERO PAYMENT RESOLUTION COMPLETE'::text AS status,
    count(*) AS total_payments,
    count(
        CASE
            WHEN ((resolution_type)::text = 'refund'::text) THEN 1
            ELSE NULL::integer
        END) AS confirmed_refunds,
    count(
        CASE
            WHEN ((resolution_type)::text = 'probable_refund'::text) THEN 1
            ELSE NULL::integer
        END) AS probable_refunds,
    'All zero-amount Square payments have been identified as transaction reversals'::text AS conclusion
   FROM public.zero_payment_resolutions;


--
-- Name: account_categories category_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_categories ALTER COLUMN category_id SET DEFAULT nextval('public.account_categories_category_id_seq'::regclass);


--
-- Name: account_number_aliases alias_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_number_aliases ALTER COLUMN alias_id SET DEFAULT nextval('public.account_number_aliases_alias_id_seq'::regclass);


--
-- Name: accounting_entries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounting_entries ALTER COLUMN id SET DEFAULT nextval('public.accounting_entries_id_seq'::regclass);


--
-- Name: accounting_periods period_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounting_periods ALTER COLUMN period_id SET DEFAULT nextval('public.accounting_periods_period_id_seq'::regclass);


--
-- Name: accounting_records id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounting_records ALTER COLUMN id SET DEFAULT nextval('public.accounting_records_id_seq'::regclass);


--
-- Name: agreement_terms term_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agreement_terms ALTER COLUMN term_id SET DEFAULT nextval('public.agreement_terms_term_id_seq'::regclass);


--
-- Name: alcohol_business_tracking id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alcohol_business_tracking ALTER COLUMN id SET DEFAULT nextval('public.alcohol_business_tracking_id_seq'::regclass);


--
-- Name: alert_policy policy_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alert_policy ALTER COLUMN policy_id SET DEFAULT nextval('public.alert_policy_policy_id_seq'::regclass);


--
-- Name: app_errors error_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_errors ALTER COLUMN error_id SET DEFAULT nextval('public.app_errors_error_id_seq'::regclass);


--
-- Name: asset_depreciation_schedule schedule_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset_depreciation_schedule ALTER COLUMN schedule_id SET DEFAULT nextval('public.asset_depreciation_schedule_schedule_id_seq'::regclass);


--
-- Name: asset_documentation doc_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset_documentation ALTER COLUMN doc_id SET DEFAULT nextval('public.asset_documentation_doc_id_seq'::regclass);


--
-- Name: assets asset_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assets ALTER COLUMN asset_id SET DEFAULT nextval('public.assets_asset_id_seq'::regclass);


--
-- Name: audit_log audit_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log ALTER COLUMN audit_id SET DEFAULT nextval('public.audit_log_audit_id_seq'::regclass);


--
-- Name: bank_accounts bank_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bank_accounts ALTER COLUMN bank_id SET DEFAULT nextval('public.bank_accounts_bank_id_seq'::regclass);


--
-- Name: bank_reconciliation reconciliation_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bank_reconciliation ALTER COLUMN reconciliation_id SET DEFAULT nextval('public.bank_reconciliation_reconciliation_id_seq'::regclass);


--
-- Name: banking_inter_account_transfers transfer_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.banking_inter_account_transfers ALTER COLUMN transfer_id SET DEFAULT nextval('public.banking_inter_account_transfers_transfer_id_seq'::regclass);


--
-- Name: banking_receipt_matching_ledger id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.banking_receipt_matching_ledger ALTER COLUMN id SET DEFAULT nextval('public.banking_receipt_matching_ledger_id_seq'::regclass);


--
-- Name: banking_transactions transaction_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.banking_transactions ALTER COLUMN transaction_id SET DEFAULT nextval('public.banking_transactions_transaction_id_seq'::regclass);


--
-- Name: batch_deposit_allocations allocation_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.batch_deposit_allocations ALTER COLUMN allocation_id SET DEFAULT nextval('public.batch_deposit_allocations_allocation_id_seq'::regclass);


--
-- Name: beverage_cart cart_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverage_cart ALTER COLUMN cart_id SET DEFAULT nextval('public.beverage_cart_cart_id_seq'::regclass);


--
-- Name: beverage_menu beverage_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverage_menu ALTER COLUMN beverage_id SET DEFAULT nextval('public.beverage_menu_beverage_id_seq'::regclass);


--
-- Name: beverage_order_items item_line_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverage_order_items ALTER COLUMN item_line_id SET DEFAULT nextval('public.beverage_order_items_item_line_id_seq'::regclass);


--
-- Name: beverage_orders order_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverage_orders ALTER COLUMN order_id SET DEFAULT nextval('public.beverage_orders_order_id_seq'::regclass);


--
-- Name: beverage_products item_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverage_products ALTER COLUMN item_id SET DEFAULT nextval('public.beverage_products_item_id_seq'::regclass);


--
-- Name: beverages beverage_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverages ALTER COLUMN beverage_id SET DEFAULT nextval('public.beverages_beverage_id_seq'::regclass);


--
-- Name: billing_audit_issues id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_audit_issues ALTER COLUMN id SET DEFAULT nextval('public.billing_audit_issues_id_seq'::regclass);


--
-- Name: billing_audit_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_audit_log ALTER COLUMN id SET DEFAULT nextval('public.billing_audit_log_id_seq'::regclass);


--
-- Name: business_expenses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_expenses ALTER COLUMN id SET DEFAULT nextval('public.business_expenses_id_seq'::regclass);


--
-- Name: business_losses loss_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_losses ALTER COLUMN loss_id SET DEFAULT nextval('public.business_losses_loss_id_seq'::regclass);


--
-- Name: cash_box_transactions transaction_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cash_box_transactions ALTER COLUMN transaction_id SET DEFAULT nextval('public.cash_box_transactions_transaction_id_seq'::regclass);


--
-- Name: cash_flow_categories category_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cash_flow_categories ALTER COLUMN category_id SET DEFAULT nextval('public.cash_flow_categories_category_id_seq'::regclass);


--
-- Name: cash_flow_tracking flow_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cash_flow_tracking ALTER COLUMN flow_id SET DEFAULT nextval('public.cash_flow_tracking_flow_id_seq'::regclass);


--
-- Name: categorization_rules rule_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categorization_rules ALTER COLUMN rule_id SET DEFAULT nextval('public.categorization_rules_rule_id_seq'::regclass);


--
-- Name: category_mappings mapping_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.category_mappings ALTER COLUMN mapping_id SET DEFAULT nextval('public.category_mappings_mapping_id_seq'::regclass);


--
-- Name: category_to_account_map mapping_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.category_to_account_map ALTER COLUMN mapping_id SET DEFAULT nextval('public.category_to_account_map_mapping_id_seq'::regclass);


--
-- Name: charge_catalog catalog_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charge_catalog ALTER COLUMN catalog_id SET DEFAULT nextval('public.charge_catalog_catalog_id_seq'::regclass);


--
-- Name: charges charge_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charges ALTER COLUMN charge_id SET DEFAULT nextval('public.charges_charge_id_seq'::regclass);


--
-- Name: charity_trade_charters id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charity_trade_charters ALTER COLUMN id SET DEFAULT nextval('public.charity_trade_charters_id_seq'::regclass);


--
-- Name: charter_beverage_items beverage_item_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_beverage_items ALTER COLUMN beverage_item_id SET DEFAULT nextval('public.charter_beverage_items_beverage_item_id_seq'::regclass);


--
-- Name: charter_beverage_orders beverage_order_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_beverage_orders ALTER COLUMN beverage_order_id SET DEFAULT nextval('public.charter_beverage_orders_beverage_order_id_seq'::regclass);


--
-- Name: charter_beverages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_beverages ALTER COLUMN id SET DEFAULT nextval('public.charter_beverages_id_seq'::regclass);


--
-- Name: charter_charges charge_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_charges ALTER COLUMN charge_id SET DEFAULT nextval('public.charter_charges_charge_id_seq'::regclass);


--
-- Name: charter_credit_ledger credit_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_credit_ledger ALTER COLUMN credit_id SET DEFAULT nextval('public.charter_credit_ledger_credit_id_seq'::regclass);


--
-- Name: charter_gst_details_2010_2012 id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_gst_details_2010_2012 ALTER COLUMN id SET DEFAULT nextval('public.charter_gst_details_2010_2012_id_seq'::regclass);


--
-- Name: charter_incidents incident_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_incidents ALTER COLUMN incident_id SET DEFAULT nextval('public.charter_incidents_incident_id_seq'::regclass);


--
-- Name: charter_payments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_payments ALTER COLUMN id SET DEFAULT nextval('public.charter_payments_id_seq'::regclass);


--
-- Name: charter_receipts receipt_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_receipts ALTER COLUMN receipt_id SET DEFAULT nextval('public.charter_receipts_receipt_id_seq'::regclass);


--
-- Name: charter_refunds id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_refunds ALTER COLUMN id SET DEFAULT nextval('public.charter_refunds_id_seq'::regclass);


--
-- Name: charter_routes route_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_routes ALTER COLUMN route_id SET DEFAULT nextval('public.charter_routes_route_id_seq'::regclass);


--
-- Name: charter_run_types run_type_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_run_types ALTER COLUMN run_type_id SET DEFAULT nextval('public.charter_run_types_run_type_id_seq'::regclass);


--
-- Name: charter_time_updates update_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_time_updates ALTER COLUMN update_id SET DEFAULT nextval('public.charter_time_updates_update_id_seq'::regclass);


--
-- Name: charter_types charter_type_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_types ALTER COLUMN charter_type_id SET DEFAULT nextval('public.charter_types_charter_type_id_seq'::regclass);


--
-- Name: charters charter_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charters ALTER COLUMN charter_id SET DEFAULT nextval('public.charters_charter_id_seq'::regclass);


--
-- Name: charters_routing_times routing_time_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charters_routing_times ALTER COLUMN routing_time_id SET DEFAULT nextval('public.charters_routing_times_routing_time_id_seq'::regclass);


--
-- Name: chauffeur_float_tracking id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chauffeur_float_tracking ALTER COLUMN id SET DEFAULT nextval('public.chauffeur_float_tracking_id_seq'::regclass);


--
-- Name: chauffeur_pay_entries entry_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chauffeur_pay_entries ALTER COLUMN entry_id SET DEFAULT nextval('public.chauffeur_pay_entries_entry_id_seq'::regclass);


--
-- Name: cheque_register id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cheque_register ALTER COLUMN id SET DEFAULT nextval('public.cheque_register_id_seq'::regclass);


--
-- Name: cibc_accounts account_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cibc_accounts ALTER COLUMN account_id SET DEFAULT nextval('public.cibc_accounts_account_id_seq'::regclass);


--
-- Name: cibc_auto_categorization_rules rule_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cibc_auto_categorization_rules ALTER COLUMN rule_id SET DEFAULT nextval('public.cibc_auto_categorization_rules_rule_id_seq'::regclass);


--
-- Name: cibc_business_cards card_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cibc_business_cards ALTER COLUMN card_id SET DEFAULT nextval('public.cibc_business_cards_card_id_seq'::regclass);


--
-- Name: cibc_card_transactions transaction_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cibc_card_transactions ALTER COLUMN transaction_id SET DEFAULT nextval('public.cibc_card_transactions_transaction_id_seq'::regclass);


--
-- Name: clients client_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clients ALTER COLUMN client_id SET DEFAULT nextval('public.clients_client_id_seq'::regclass);


--
-- Name: comprehensive_payment_reconciliation id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comprehensive_payment_reconciliation ALTER COLUMN id SET DEFAULT nextval('public.comprehensive_payment_reconciliation_id_seq'::regclass);


--
-- Name: cra_vehicle_events event_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cra_vehicle_events ALTER COLUMN event_id SET DEFAULT nextval('public.cra_vehicle_events_event_id_seq'::regclass);


--
-- Name: customer_comms_log comm_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_comms_log ALTER COLUMN comm_id SET DEFAULT nextval('public.customer_comms_log_comm_id_seq'::regclass);


--
-- Name: customer_feedback feedback_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_feedback ALTER COLUMN feedback_id SET DEFAULT nextval('public.customer_feedback_feedback_id_seq'::regclass);


--
-- Name: customer_name_mapping id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_name_mapping ALTER COLUMN id SET DEFAULT nextval('public.customer_name_mapping_id_seq'::regclass);


--
-- Name: cvip_compliance_alerts alert_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cvip_compliance_alerts ALTER COLUMN alert_id SET DEFAULT nextval('public.cvip_compliance_alerts_alert_id_seq'::regclass);


--
-- Name: cvip_defects defect_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cvip_defects ALTER COLUMN defect_id SET DEFAULT nextval('public.cvip_defects_defect_id_seq'::regclass);


--
-- Name: cvip_inspections inspection_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cvip_inspections ALTER COLUMN inspection_id SET DEFAULT nextval('public.cvip_inspections_inspection_id_seq'::regclass);


--
-- Name: david_account_tracking id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.david_account_tracking ALTER COLUMN id SET DEFAULT nextval('public.david_account_tracking_id_seq'::regclass);


--
-- Name: david_richard_vehicle_loans id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.david_richard_vehicle_loans ALTER COLUMN id SET DEFAULT nextval('public.david_richard_vehicle_loans_id_seq'::regclass);


--
-- Name: deferred_wage_accounts account_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deferred_wage_accounts ALTER COLUMN account_id SET DEFAULT nextval('public.deferred_wage_accounts_account_id_seq'::regclass);


--
-- Name: deferred_wage_transactions transaction_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deferred_wage_transactions ALTER COLUMN transaction_id SET DEFAULT nextval('public.deferred_wage_transactions_transaction_id_seq'::regclass);


--
-- Name: deposit_records id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deposit_records ALTER COLUMN id SET DEFAULT nextval('public.deposit_records_id_seq'::regclass);


--
-- Name: direct_tips_history tip_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.direct_tips_history ALTER COLUMN tip_id SET DEFAULT nextval('public.direct_tips_history_tip_id_seq'::regclass);


--
-- Name: dispatch_events dispatch_event_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispatch_events ALTER COLUMN dispatch_event_id SET DEFAULT nextval('public.dispatch_events_dispatch_event_id_seq'::regclass);


--
-- Name: document_categories category_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_categories ALTER COLUMN category_id SET DEFAULT nextval('public.document_categories_category_id_seq'::regclass);


--
-- Name: documents document_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents ALTER COLUMN document_id SET DEFAULT nextval('public.documents_document_id_seq'::regclass);


--
-- Name: donations_free_rides id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.donations_free_rides ALTER COLUMN id SET DEFAULT nextval('public.donations_free_rides_id_seq'::regclass);


--
-- Name: driver_app_actions action_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_app_actions ALTER COLUMN action_id SET DEFAULT nextval('public.driver_app_actions_action_id_seq'::regclass);


--
-- Name: driver_app_sessions session_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_app_sessions ALTER COLUMN session_id SET DEFAULT nextval('public.driver_app_sessions_session_id_seq'::regclass);


--
-- Name: driver_comms_log comm_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_comms_log ALTER COLUMN comm_id SET DEFAULT nextval('public.driver_comms_log_comm_id_seq'::regclass);


--
-- Name: driver_disciplinary_actions action_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_disciplinary_actions ALTER COLUMN action_id SET DEFAULT nextval('public.driver_disciplinary_actions_action_id_seq'::regclass);


--
-- Name: driver_documents id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_documents ALTER COLUMN id SET DEFAULT nextval('public.driver_documents_id_seq'::regclass);


--
-- Name: driver_floats float_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_floats ALTER COLUMN float_id SET DEFAULT nextval('public.driver_floats_float_id_seq'::regclass);


--
-- Name: driver_location_history location_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_location_history ALTER COLUMN location_id SET DEFAULT nextval('public.driver_location_history_location_id_seq'::regclass);


--
-- Name: driver_name_employee_map id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_name_employee_map ALTER COLUMN id SET DEFAULT nextval('public.driver_name_employee_map_id_seq'::regclass);


--
-- Name: driver_pay_entries entry_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_pay_entries ALTER COLUMN entry_id SET DEFAULT nextval('public.driver_pay_entries_entry_id_seq'::regclass);


--
-- Name: driver_payroll id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_payroll ALTER COLUMN id SET DEFAULT nextval('public.driver_payroll_id_seq'::regclass);


--
-- Name: duty_status_types status_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.duty_status_types ALTER COLUMN status_id SET DEFAULT nextval('public.duty_status_types_status_id_seq'::regclass);


--
-- Name: email_financial_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.email_financial_events ALTER COLUMN id SET DEFAULT nextval('public.email_financial_events_id_seq'::regclass);


--
-- Name: email_processing_stats id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.email_processing_stats ALTER COLUMN id SET DEFAULT nextval('public.email_processing_stats_id_seq'::regclass);


--
-- Name: employee_availability availability_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_availability ALTER COLUMN availability_id SET DEFAULT nextval('public.employee_availability_availability_id_seq'::regclass);


--
-- Name: employee_expenses expense_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_expenses ALTER COLUMN expense_id SET DEFAULT nextval('public.employee_expenses_expense_id_seq'::regclass);


--
-- Name: employee_pay_entries entry_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_pay_entries ALTER COLUMN entry_id SET DEFAULT nextval('public.employee_pay_entries_entry_id_seq'::regclass);


--
-- Name: employee_pay_master employee_pay_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_pay_master ALTER COLUMN employee_pay_id SET DEFAULT nextval('public.employee_pay_master_employee_pay_id_seq'::regclass);


--
-- Name: employee_roe_records id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_roe_records ALTER COLUMN id SET DEFAULT nextval('public.employee_roe_records_id_seq'::regclass);


--
-- Name: employee_schedules schedule_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_schedules ALTER COLUMN schedule_id SET DEFAULT nextval('public.employee_schedules_schedule_id_seq'::regclass);


--
-- Name: employee_t4_records t4_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_t4_records ALTER COLUMN t4_id SET DEFAULT nextval('public.employee_t4_records_t4_id_seq'::regclass);


--
-- Name: employee_t4_summary t4_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_t4_summary ALTER COLUMN t4_id SET DEFAULT nextval('public.employee_t4_summary_t4_id_seq'::regclass);


--
-- Name: employee_time_off_requests request_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_time_off_requests ALTER COLUMN request_id SET DEFAULT nextval('public.employee_time_off_requests_request_id_seq'::regclass);


--
-- Name: employee_work_classifications classification_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_work_classifications ALTER COLUMN classification_id SET DEFAULT nextval('public.employee_work_classifications_classification_id_seq'::regclass);


--
-- Name: employees employee_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employees ALTER COLUMN employee_id SET DEFAULT nextval('public.employees_employee_id_seq'::regclass);


--
-- Name: etransfer_banking_reconciliation id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.etransfer_banking_reconciliation ALTER COLUMN id SET DEFAULT nextval('public.etransfer_banking_reconciliation_id_seq'::regclass);


--
-- Name: etransfer_transactions etransfer_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.etransfer_transactions ALTER COLUMN etransfer_id SET DEFAULT nextval('public.etransfer_transactions_etransfer_id_seq'::regclass);


--
-- Name: etransfers_processed id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.etransfers_processed ALTER COLUMN id SET DEFAULT nextval('public.etransfers_processed_id_seq'::regclass);


--
-- Name: excluded_charters id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.excluded_charters ALTER COLUMN id SET DEFAULT nextval('public.excluded_charters_id_seq'::regclass);


--
-- Name: fee_tracking fee_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fee_tracking ALTER COLUMN fee_id SET DEFAULT nextval('public.fee_tracking_fee_id_seq'::regclass);


--
-- Name: financial_adjustments adjustment_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_adjustments ALTER COLUMN adjustment_id SET DEFAULT nextval('public.financial_adjustments_adjustment_id_seq'::regclass);


--
-- Name: financial_audit_trail audit_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_audit_trail ALTER COLUMN audit_id SET DEFAULT nextval('public.financial_audit_trail_audit_id_seq'::regclass);


--
-- Name: financial_documents id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_documents ALTER COLUMN id SET DEFAULT nextval('public.financial_documents_id_seq'::regclass);


--
-- Name: financial_statement_sections section_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_statement_sections ALTER COLUMN section_id SET DEFAULT nextval('public.financial_statement_sections_section_id_seq'::regclass);


--
-- Name: financial_statement_types statement_type_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_statement_types ALTER COLUMN statement_type_id SET DEFAULT nextval('public.financial_statement_types_statement_type_id_seq'::regclass);


--
-- Name: financial_transactions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_transactions ALTER COLUMN id SET DEFAULT nextval('public.financial_transactions_id_seq'::regclass);


--
-- Name: financing_sources source_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financing_sources ALTER COLUMN source_id SET DEFAULT nextval('public.financing_sources_source_id_seq'::regclass);


--
-- Name: float_activity_log log_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.float_activity_log ALTER COLUMN log_id SET DEFAULT nextval('public.float_activity_log_log_id_seq'::regclass);


--
-- Name: fraud_cases case_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fraud_cases ALTER COLUMN case_id SET DEFAULT nextval('public.fraud_cases_case_id_seq'::regclass);


--
-- Name: fuel_expenses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fuel_expenses ALTER COLUMN id SET DEFAULT nextval('public.fuel_expenses_id_seq'::regclass);


--
-- Name: general_ledger id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.general_ledger ALTER COLUMN id SET DEFAULT nextval('public.general_ledger_id_seq'::regclass);


--
-- Name: general_ledger_headers header_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.general_ledger_headers ALTER COLUMN header_id SET DEFAULT nextval('public.general_ledger_headers_header_id_seq'::regclass);


--
-- Name: general_ledger_lines line_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.general_ledger_lines ALTER COLUMN line_id SET DEFAULT nextval('public.general_ledger_lines_line_id_seq'::regclass);


--
-- Name: gl_transactions gl_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gl_transactions ALTER COLUMN gl_id SET DEFAULT nextval('public.gl_transactions_gl_id_seq'::regclass);


--
-- Name: gratuity_income_links id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gratuity_income_links ALTER COLUMN id SET DEFAULT nextval('public.gratuity_income_links_id_seq'::regclass);


--
-- Name: gst_audit_trail gst_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gst_audit_trail ALTER COLUMN gst_id SET DEFAULT nextval('public.gst_audit_trail_gst_id_seq'::regclass);


--
-- Name: hos_14day_summary summary_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hos_14day_summary ALTER COLUMN summary_id SET DEFAULT nextval('public.hos_14day_summary_summary_id_seq'::regclass);


--
-- Name: hos_log hos_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hos_log ALTER COLUMN hos_id SET DEFAULT nextval('public.hos_log_hos_id_seq'::regclass);


--
-- Name: incident_costs cost_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incident_costs ALTER COLUMN cost_id SET DEFAULT nextval('public.incident_costs_cost_id_seq'::regclass);


--
-- Name: incident_damage_tracking id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incident_damage_tracking ALTER COLUMN id SET DEFAULT nextval('public.incident_damage_tracking_id_seq'::regclass);


--
-- Name: incidents incident_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incidents ALTER COLUMN incident_id SET DEFAULT nextval('public.incidents_incident_id_seq'::regclass);


--
-- Name: income_ledger income_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.income_ledger ALTER COLUMN income_id SET DEFAULT nextval('public.income_ledger_income_id_seq'::regclass);


--
-- Name: interest_allocations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interest_allocations ALTER COLUMN id SET DEFAULT nextval('public.interest_allocations_id_seq'::regclass);


--
-- Name: invoice_line_items line_item_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_line_items ALTER COLUMN line_item_id SET DEFAULT nextval('public.invoice_line_items_line_item_id_seq'::regclass);


--
-- Name: invoice_tracking id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_tracking ALTER COLUMN id SET DEFAULT nextval('public.invoice_tracking_id_seq'::regclass);


--
-- Name: invoices invoice_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices ALTER COLUMN invoice_id SET DEFAULT nextval('public.invoices_invoice_id_seq'::regclass);


--
-- Name: legacy_import_status import_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legacy_import_status ALTER COLUMN import_id SET DEFAULT nextval('public.legacy_import_status_import_id_seq'::regclass);


--
-- Name: lender_statement_transactions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lender_statement_transactions ALTER COLUMN id SET DEFAULT nextval('public.lender_statement_transactions_id_seq'::regclass);


--
-- Name: lms2026_payment_matches match_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lms2026_payment_matches ALTER COLUMN match_id SET DEFAULT nextval('public.lms2026_payment_matches_match_id_seq'::regclass);


--
-- Name: loan_transactions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.loan_transactions ALTER COLUMN id SET DEFAULT nextval('public.loan_transactions_id_seq'::regclass);


--
-- Name: maintenance_activity_types activity_type_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maintenance_activity_types ALTER COLUMN activity_type_id SET DEFAULT nextval('public.maintenance_activity_types_activity_type_id_seq'::regclass);


--
-- Name: maintenance_alerts alert_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maintenance_alerts ALTER COLUMN alert_id SET DEFAULT nextval('public.maintenance_alerts_alert_id_seq'::regclass);


--
-- Name: maintenance_records record_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maintenance_records ALTER COLUMN record_id SET DEFAULT nextval('public.maintenance_records_record_id_seq'::regclass);


--
-- Name: maintenance_schedules_auto schedule_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maintenance_schedules_auto ALTER COLUMN schedule_id SET DEFAULT nextval('public.maintenance_schedules_auto_schedule_id_seq'::regclass);


--
-- Name: maintenance_service_types service_type_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maintenance_service_types ALTER COLUMN service_type_id SET DEFAULT nextval('public.maintenance_service_types_service_type_id_seq'::regclass);


--
-- Name: major_events event_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.major_events ALTER COLUMN event_id SET DEFAULT nextval('public.major_events_event_id_seq'::regclass);


--
-- Name: manual_check_payees id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_check_payees ALTER COLUMN id SET DEFAULT nextval('public.manual_check_payees_id_seq'::regclass);


--
-- Name: master_relationships id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.master_relationships ALTER COLUMN id SET DEFAULT nextval('public.master_relationships_id_seq'::regclass);


--
-- Name: migration_log log_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.migration_log ALTER COLUMN log_id SET DEFAULT nextval('public.migration_log_log_id_seq'::regclass);


--
-- Name: missing_receipt_tracking missing_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.missing_receipt_tracking ALTER COLUMN missing_id SET DEFAULT nextval('public.missing_receipt_tracking_missing_id_seq'::regclass);


--
-- Name: monthly_work_assignments assignment_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.monthly_work_assignments ALTER COLUMN assignment_id SET DEFAULT nextval('public.monthly_work_assignments_assignment_id_seq'::regclass);


--
-- Name: owner_equity_accounts equity_account_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.owner_equity_accounts ALTER COLUMN equity_account_id SET DEFAULT nextval('public.owner_equity_accounts_equity_account_id_seq'::regclass);


--
-- Name: owner_expense_transactions transaction_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.owner_expense_transactions ALTER COLUMN transaction_id SET DEFAULT nextval('public.owner_expense_transactions_transaction_id_seq'::regclass);


--
-- Name: paul_pay_tracking id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paul_pay_tracking ALTER COLUMN id SET DEFAULT nextval('public.paul_pay_tracking_id_seq'::regclass);


--
-- Name: pay_periods pay_period_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_periods ALTER COLUMN pay_period_id SET DEFAULT nextval('public.pay_periods_pay_period_id_seq'::regclass);


--
-- Name: payables payable_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payables ALTER COLUMN payable_id SET DEFAULT nextval('public.payables_payable_id_seq'::regclass);


--
-- Name: payday_loan_payments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payday_loan_payments ALTER COLUMN id SET DEFAULT nextval('public.payday_loan_payments_id_seq'::regclass);


--
-- Name: payday_loans id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payday_loans ALTER COLUMN id SET DEFAULT nextval('public.payday_loans_id_seq'::regclass);


--
-- Name: payment_matches match_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_matches ALTER COLUMN match_id SET DEFAULT nextval('public.payment_matches_match_id_seq'::regclass);


--
-- Name: payments payment_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments ALTER COLUMN payment_id SET DEFAULT nextval('public.payments_payment_id_seq'::regclass);


--
-- Name: payroll_adjustments adjustment_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_adjustments ALTER COLUMN adjustment_id SET DEFAULT nextval('public.payroll_adjustments_adjustment_id_seq'::regclass);


--
-- Name: payroll_comparison id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_comparison ALTER COLUMN id SET DEFAULT nextval('public.payroll_comparison_id_seq'::regclass);


--
-- Name: payroll_fix_audit id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_fix_audit ALTER COLUMN id SET DEFAULT nextval('public.payroll_fix_audit_id_seq'::regclass);


--
-- Name: payroll_fix_rollback_audit id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_fix_rollback_audit ALTER COLUMN id SET DEFAULT nextval('public.payroll_fix_rollback_audit_id_seq'::regclass);


--
-- Name: performance_metrics metric_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.performance_metrics ALTER COLUMN metric_id SET DEFAULT nextval('public.performance_metrics_metric_id_seq'::regclass);


--
-- Name: permissions permission_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.permissions ALTER COLUMN permission_id SET DEFAULT nextval('public.permissions_permission_id_seq'::regclass);


--
-- Name: personal_expenses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personal_expenses ALTER COLUMN id SET DEFAULT nextval('public.personal_expenses_id_seq'::regclass);


--
-- Name: posting_queue id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.posting_queue ALTER COLUMN id SET DEFAULT nextval('public.posting_queue_id_seq'::regclass);


--
-- Name: posting_reversals id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.posting_reversals ALTER COLUMN id SET DEFAULT nextval('public.posting_reversals_id_seq'::regclass);


--
-- Name: pre_inspection_issues issue_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pre_inspection_issues ALTER COLUMN issue_id SET DEFAULT nextval('public.pre_inspection_issues_issue_id_seq'::regclass);


--
-- Name: quotations quote_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quotations ALTER COLUMN quote_id SET DEFAULT nextval('public.quotations_quote_id_seq'::regclass);


--
-- Name: raw_file_inventory id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.raw_file_inventory ALTER COLUMN id SET DEFAULT nextval('public.raw_file_inventory_id_seq'::regclass);


--
-- Name: receipt_banking_links link_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_banking_links ALTER COLUMN link_id SET DEFAULT nextval('public.receipt_banking_links_link_id_seq'::regclass);


--
-- Name: receipt_cashbox_links link_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_cashbox_links ALTER COLUMN link_id SET DEFAULT nextval('public.receipt_cashbox_links_link_id_seq'::regclass);


--
-- Name: receipt_categories category_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_categories ALTER COLUMN category_id SET DEFAULT nextval('public.receipt_categories_category_id_seq'::regclass);


--
-- Name: receipt_deliveries delivery_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_deliveries ALTER COLUMN delivery_id SET DEFAULT nextval('public.receipt_deliveries_delivery_id_seq'::regclass);


--
-- Name: receipt_gst_adjustment_audit id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_gst_adjustment_audit ALTER COLUMN id SET DEFAULT nextval('public.receipt_gst_adjustment_audit_id_seq'::regclass);


--
-- Name: receipt_line_items line_item_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_line_items ALTER COLUMN line_item_id SET DEFAULT nextval('public.receipt_line_items_line_item_id_seq'::regclass);


--
-- Name: receipts receipt_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts ALTER COLUMN receipt_id SET DEFAULT nextval('public.receipts_id_seq'::regclass);


--
-- Name: receipts_ingest_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts_ingest_log ALTER COLUMN id SET DEFAULT nextval('public.receipts_ingest_log_id_seq'::regclass);


--
-- Name: recurring_invoices id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recurring_invoices ALTER COLUMN id SET DEFAULT nextval('public.recurring_invoices_id_seq'::regclass);


--
-- Name: refunds_cancellations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refunds_cancellations ALTER COLUMN id SET DEFAULT nextval('public.refunds_cancellations_id_seq'::regclass);


--
-- Name: rent_debt_ledger id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rent_debt_ledger ALTER COLUMN id SET DEFAULT nextval('public.rent_debt_ledger_id_seq'::regclass);


--
-- Name: route_event_types event_type_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.route_event_types ALTER COLUMN event_type_id SET DEFAULT nextval('public.route_event_types_event_type_id_seq'::regclass);


--
-- Name: schema_migrations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations ALTER COLUMN id SET DEFAULT nextval('public.schema_migrations_id_seq'::regclass);


--
-- Name: security_audit audit_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_audit ALTER COLUMN audit_id SET DEFAULT nextval('public.security_audit_audit_id_seq'::regclass);


--
-- Name: security_events event_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_events ALTER COLUMN event_id SET DEFAULT nextval('public.security_events_event_id_seq'::regclass);


--
-- Name: square_api_audit square_audit_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_api_audit ALTER COLUMN square_audit_id SET DEFAULT nextval('public.square_api_audit_square_audit_id_seq'::regclass);


--
-- Name: square_capital_activity id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_capital_activity ALTER COLUMN id SET DEFAULT nextval('public.square_capital_activity_id_seq'::regclass);


--
-- Name: square_capital_loans loan_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_capital_loans ALTER COLUMN loan_id SET DEFAULT nextval('public.square_capital_loans_loan_id_seq'::regclass);


--
-- Name: square_customers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_customers ALTER COLUMN id SET DEFAULT nextval('public.square_customers_id_seq'::regclass);


--
-- Name: square_etransfer_reconciliation reconciliation_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_etransfer_reconciliation ALTER COLUMN reconciliation_id SET DEFAULT nextval('public.square_etransfer_reconciliation_reconciliation_id_seq'::regclass);


--
-- Name: square_lms_matches match_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_lms_matches ALTER COLUMN match_id SET DEFAULT nextval('public.square_lms_matches_match_id_seq'::regclass);


--
-- Name: square_payment_categories id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_payment_categories ALTER COLUMN id SET DEFAULT nextval('public.square_payment_categories_id_seq'::regclass);


--
-- Name: square_processing_fees fee_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_processing_fees ALTER COLUMN fee_id SET DEFAULT nextval('public.square_processing_fees_fee_id_seq'::regclass);


--
-- Name: square_raw_imports import_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_raw_imports ALTER COLUMN import_id SET DEFAULT nextval('public.square_raw_imports_import_id_seq'::regclass);


--
-- Name: square_raw_records record_pk; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_raw_records ALTER COLUMN record_pk SET DEFAULT nextval('public.square_raw_records_record_pk_seq'::regclass);


--
-- Name: square_review_status id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_review_status ALTER COLUMN id SET DEFAULT nextval('public.square_review_status_id_seq'::regclass);


--
-- Name: staging_driver_pay_files id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_driver_pay_files ALTER COLUMN id SET DEFAULT nextval('public.staging_driver_pay_files_id_seq'::regclass);


--
-- Name: staging_employee_reference_data id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_employee_reference_data ALTER COLUMN id SET DEFAULT nextval('public.staging_employee_reference_data_id_seq'::regclass);


--
-- Name: staging_pd7a_year_end_summary id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_pd7a_year_end_summary ALTER COLUMN id SET DEFAULT nextval('public.staging_pd7a_year_end_summary_id_seq'::regclass);


--
-- Name: system_config config_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_config ALTER COLUMN config_id SET DEFAULT nextval('public.system_config_config_id_seq'::regclass);


--
-- Name: t4_compliance_corrections correction_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.t4_compliance_corrections ALTER COLUMN correction_id SET DEFAULT nextval('public.t4_compliance_corrections_correction_id_seq'::regclass);


--
-- Name: tax_overrides id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_overrides ALTER COLUMN id SET DEFAULT nextval('public.tax_overrides_id_seq'::regclass);


--
-- Name: tax_periods id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_periods ALTER COLUMN id SET DEFAULT nextval('public.tax_periods_id_seq'::regclass);


--
-- Name: tax_remittances id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_remittances ALTER COLUMN id SET DEFAULT nextval('public.tax_remittances_id_seq'::regclass);


--
-- Name: tax_returns id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_returns ALTER COLUMN id SET DEFAULT nextval('public.tax_returns_id_seq'::regclass);


--
-- Name: tax_rollovers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_rollovers ALTER COLUMN id SET DEFAULT nextval('public.tax_rollovers_id_seq'::regclass);


--
-- Name: tax_variances id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_variances ALTER COLUMN id SET DEFAULT nextval('public.tax_variances_id_seq'::regclass);


--
-- Name: training_checklist_items item_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.training_checklist_items ALTER COLUMN item_id SET DEFAULT nextval('public.training_checklist_items_item_id_seq'::regclass);


--
-- Name: training_programs program_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.training_programs ALTER COLUMN program_id SET DEFAULT nextval('public.training_programs_program_id_seq'::regclass);


--
-- Name: transaction_categories id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transaction_categories ALTER COLUMN id SET DEFAULT nextval('public.transaction_categories_id_seq'::regclass);


--
-- Name: transaction_chain chain_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transaction_chain ALTER COLUMN chain_id SET DEFAULT nextval('public.transaction_chain_chain_id_seq'::regclass);


--
-- Name: transaction_log transaction_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transaction_log ALTER COLUMN transaction_id SET DEFAULT nextval('public.transaction_log_transaction_id_seq'::regclass);


--
-- Name: transaction_subcategories id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transaction_subcategories ALTER COLUMN id SET DEFAULT nextval('public.transaction_subcategories_id_seq'::regclass);


--
-- Name: unified_charge_lookup lookup_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unified_charge_lookup ALTER COLUMN lookup_id SET DEFAULT nextval('public.unified_charge_lookup_lookup_id_seq'::regclass);


--
-- Name: unified_general_ledger id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unified_general_ledger ALTER COLUMN id SET DEFAULT nextval('public.unified_general_ledger_id_seq'::regclass);


--
-- Name: unmatched_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unmatched_items ALTER COLUMN id SET DEFAULT nextval('public.unmatched_items_id_seq'::regclass);


--
-- Name: users user_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN user_id SET DEFAULT nextval('public.users_user_id_seq'::regclass);


--
-- Name: vacation_pay_records id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vacation_pay_records ALTER COLUMN id SET DEFAULT nextval('public.vacation_pay_records_id_seq'::regclass);


--
-- Name: vehicle_capacity_tiers tier_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_capacity_tiers ALTER COLUMN tier_id SET DEFAULT nextval('public.vehicle_capacity_tiers_tier_id_seq'::regclass);


--
-- Name: vehicle_document_types doc_type_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_document_types ALTER COLUMN doc_type_id SET DEFAULT nextval('public.vehicle_document_types_doc_type_id_seq'::regclass);


--
-- Name: vehicle_documents document_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_documents ALTER COLUMN document_id SET DEFAULT nextval('public.vehicle_documents_document_id_seq'::regclass);


--
-- Name: vehicle_financing financing_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_financing ALTER COLUMN financing_id SET DEFAULT nextval('public.vehicle_financing_financing_id_seq'::regclass);


--
-- Name: vehicle_financing_complete id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_financing_complete ALTER COLUMN id SET DEFAULT nextval('public.vehicle_financing_complete_id_seq'::regclass);


--
-- Name: vehicle_fuel_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_fuel_log ALTER COLUMN id SET DEFAULT nextval('public.vehicle_fuel_log_id_seq'::regclass);


--
-- Name: vehicle_fuel_log log_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_fuel_log ALTER COLUMN log_id SET DEFAULT nextval('public.vehicle_fuel_log_log_id_seq'::regclass);


--
-- Name: vehicle_insurance insurance_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_insurance ALTER COLUMN insurance_id SET DEFAULT nextval('public.vehicle_insurance_insurance_id_seq'::regclass);


--
-- Name: vehicle_loan_payments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_loan_payments ALTER COLUMN id SET DEFAULT nextval('public.vehicle_loan_payments_id_seq'::regclass);


--
-- Name: vehicle_loan_reconciliation_allocations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_loan_reconciliation_allocations ALTER COLUMN id SET DEFAULT nextval('public.vehicle_loan_reconciliation_allocations_id_seq'::regclass);


--
-- Name: vehicle_loans id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_loans ALTER COLUMN id SET DEFAULT nextval('public.vehicle_loans_id_seq'::regclass);


--
-- Name: vehicle_mileage_log log_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_mileage_log ALTER COLUMN log_id SET DEFAULT nextval('public.vehicle_mileage_log_log_id_seq'::regclass);


--
-- Name: vehicle_pre_inspections inspection_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_pre_inspections ALTER COLUMN inspection_id SET DEFAULT nextval('public.vehicle_pre_inspections_inspection_id_seq'::regclass);


--
-- Name: vehicle_pricing_defaults pricing_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_pricing_defaults ALTER COLUMN pricing_id SET DEFAULT nextval('public.vehicle_pricing_defaults_pricing_id_seq'::regclass);


--
-- Name: vehicle_purchases purchase_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_purchases ALTER COLUMN purchase_id SET DEFAULT nextval('public.vehicle_purchases_purchase_id_seq'::regclass);


--
-- Name: vehicle_repossessions repossession_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_repossessions ALTER COLUMN repossession_id SET DEFAULT nextval('public.vehicle_repossessions_repossession_id_seq'::regclass);


--
-- Name: vehicle_sales sale_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_sales ALTER COLUMN sale_id SET DEFAULT nextval('public.vehicle_sales_sale_id_seq'::regclass);


--
-- Name: vehicle_writeoffs writeoff_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_writeoffs ALTER COLUMN writeoff_id SET DEFAULT nextval('public.vehicle_writeoffs_writeoff_id_seq'::regclass);


--
-- Name: vehicles vehicle_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicles ALTER COLUMN vehicle_id SET DEFAULT nextval('public.vehicles_vehicle_id_seq'::regclass);


--
-- Name: vendor_account_ledger ledger_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_account_ledger ALTER COLUMN ledger_id SET DEFAULT nextval('public.vendor_account_ledger_ledger_id_seq'::regclass);


--
-- Name: vendor_accounts account_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_accounts ALTER COLUMN account_id SET DEFAULT nextval('public.vendor_accounts_account_id_seq'::regclass);


--
-- Name: vendor_default_categories id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_default_categories ALTER COLUMN id SET DEFAULT nextval('public.vendor_default_categories_id_seq'::regclass);


--
-- Name: vendor_name_mapping id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_name_mapping ALTER COLUMN id SET DEFAULT nextval('public.vendor_name_mapping_id_seq'::regclass);


--
-- Name: vendor_standardization id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_standardization ALTER COLUMN id SET DEFAULT nextval('public.vendor_standardization_id_seq'::regclass);


--
-- Name: vendor_synonyms synonym_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_synonyms ALTER COLUMN synonym_id SET DEFAULT nextval('public.vendor_synonyms_synonym_id_seq'::regclass);


--
-- Name: vendors id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendors ALTER COLUMN id SET DEFAULT nextval('public.vendors_id_seq'::regclass);


--
-- Name: verification_audit audit_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.verification_audit ALTER COLUMN audit_id SET DEFAULT nextval('public.verification_audit_audit_id_seq'::regclass);


--
-- Name: verification_queue id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.verification_queue ALTER COLUMN id SET DEFAULT nextval('public.verification_queue_id_seq'::regclass);


--
-- Name: wage_allocation_pool pool_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wage_allocation_pool ALTER COLUMN pool_id SET DEFAULT nextval('public.wage_allocation_pool_pool_id_seq'::regclass);


--
-- Name: wcb_debt_ledger id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wcb_debt_ledger ALTER COLUMN id SET DEFAULT nextval('public.wcb_debt_ledger_id_seq'::regclass);


--
-- Name: wcb_recurring_charges id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wcb_recurring_charges ALTER COLUMN id SET DEFAULT nextval('public.wcb_recurring_charges_id_seq'::regclass);


--
-- Name: wcb_summary id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wcb_summary ALTER COLUMN id SET DEFAULT nextval('public.wcb_summary_id_seq'::regclass);


--
-- Name: account_categories account_categories_category_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_categories
    ADD CONSTRAINT account_categories_category_code_key UNIQUE (category_code);


--
-- Name: account_categories account_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_categories
    ADD CONSTRAINT account_categories_pkey PRIMARY KEY (category_id);


--
-- Name: account_number_aliases account_number_aliases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_number_aliases
    ADD CONSTRAINT account_number_aliases_pkey PRIMARY KEY (alias_id);


--
-- Name: account_number_aliases account_number_aliases_statement_format_canonical_account_n_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_number_aliases
    ADD CONSTRAINT account_number_aliases_statement_format_canonical_account_n_key UNIQUE (statement_format, canonical_account_number);


--
-- Name: accounting_entries accounting_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounting_entries
    ADD CONSTRAINT accounting_entries_pkey PRIMARY KEY (id);


--
-- Name: accounting_periods accounting_periods_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounting_periods
    ADD CONSTRAINT accounting_periods_pkey PRIMARY KEY (period_id);


--
-- Name: accounting_records accounting_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounting_records
    ADD CONSTRAINT accounting_records_pkey PRIMARY KEY (id);


--
-- Name: agreement_terms agreement_terms_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agreement_terms
    ADD CONSTRAINT agreement_terms_pkey PRIMARY KEY (term_id);


--
-- Name: alberta_tax_brackets alberta_tax_brackets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alberta_tax_brackets
    ADD CONSTRAINT alberta_tax_brackets_pkey PRIMARY KEY (year, bracket_number);


--
-- Name: alcohol_business_tracking alcohol_business_tracking_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alcohol_business_tracking
    ADD CONSTRAINT alcohol_business_tracking_pkey PRIMARY KEY (id);


--
-- Name: alert_policy alert_policy_alert_type_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alert_policy
    ADD CONSTRAINT alert_policy_alert_type_key UNIQUE (alert_type);


--
-- Name: alert_policy alert_policy_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alert_policy
    ADD CONSTRAINT alert_policy_pkey PRIMARY KEY (policy_id);


--
-- Name: app_errors app_errors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_errors
    ADD CONSTRAINT app_errors_pkey PRIMARY KEY (error_id);


--
-- Name: asset_depreciation_schedule asset_depreciation_schedule_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset_depreciation_schedule
    ADD CONSTRAINT asset_depreciation_schedule_pkey PRIMARY KEY (schedule_id);


--
-- Name: asset_documentation asset_documentation_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset_documentation
    ADD CONSTRAINT asset_documentation_pkey PRIMARY KEY (doc_id);


--
-- Name: assets assets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assets
    ADD CONSTRAINT assets_pkey PRIMARY KEY (asset_id);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (audit_id);


--
-- Name: bank_accounts bank_accounts_institution_name_account_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bank_accounts
    ADD CONSTRAINT bank_accounts_institution_name_account_number_key UNIQUE (institution_name, account_number);


--
-- Name: bank_accounts bank_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bank_accounts
    ADD CONSTRAINT bank_accounts_pkey PRIMARY KEY (bank_id);


--
-- Name: bank_reconciliation bank_reconciliation_bank_account_name_statement_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bank_reconciliation
    ADD CONSTRAINT bank_reconciliation_bank_account_name_statement_date_key UNIQUE (bank_account_name, statement_date);


--
-- Name: bank_reconciliation bank_reconciliation_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bank_reconciliation
    ADD CONSTRAINT bank_reconciliation_pkey PRIMARY KEY (reconciliation_id);


--
-- Name: banking_inter_account_transfers banking_inter_account_transfe_from_transaction_id_to_transa_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.banking_inter_account_transfers
    ADD CONSTRAINT banking_inter_account_transfe_from_transaction_id_to_transa_key UNIQUE (from_transaction_id, to_transaction_id);


--
-- Name: banking_inter_account_transfers banking_inter_account_transfers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.banking_inter_account_transfers
    ADD CONSTRAINT banking_inter_account_transfers_pkey PRIMARY KEY (transfer_id);


--
-- Name: banking_receipt_matching_ledger banking_receipt_matching_ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.banking_receipt_matching_ledger
    ADD CONSTRAINT banking_receipt_matching_ledger_pkey PRIMARY KEY (id);


--
-- Name: banking_transactions banking_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.banking_transactions
    ADD CONSTRAINT banking_transactions_pkey PRIMARY KEY (transaction_id);


--
-- Name: banking_transactions banking_transactions_transaction_uid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.banking_transactions
    ADD CONSTRAINT banking_transactions_transaction_uid_key UNIQUE (transaction_uid);


--
-- Name: batch_deposit_allocations batch_deposit_allocations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.batch_deposit_allocations
    ADD CONSTRAINT batch_deposit_allocations_pkey PRIMARY KEY (allocation_id);


--
-- Name: beverage_cart beverage_cart_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverage_cart
    ADD CONSTRAINT beverage_cart_pkey PRIMARY KEY (cart_id);


--
-- Name: beverage_menu beverage_menu_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverage_menu
    ADD CONSTRAINT beverage_menu_pkey PRIMARY KEY (beverage_id);


--
-- Name: beverage_order_items beverage_order_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverage_order_items
    ADD CONSTRAINT beverage_order_items_pkey PRIMARY KEY (item_line_id);


--
-- Name: beverage_orders beverage_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverage_orders
    ADD CONSTRAINT beverage_orders_pkey PRIMARY KEY (order_id);


--
-- Name: beverage_products beverage_products_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverage_products
    ADD CONSTRAINT beverage_products_pkey PRIMARY KEY (item_id);


--
-- Name: beverages beverages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverages
    ADD CONSTRAINT beverages_pkey PRIMARY KEY (beverage_id);


--
-- Name: billing_audit_issues billing_audit_issues_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_audit_issues
    ADD CONSTRAINT billing_audit_issues_pkey PRIMARY KEY (id);


--
-- Name: billing_audit_log billing_audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_audit_log
    ADD CONSTRAINT billing_audit_log_pkey PRIMARY KEY (id);


--
-- Name: business_expenses business_expenses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_expenses
    ADD CONSTRAINT business_expenses_pkey PRIMARY KEY (id);


--
-- Name: business_losses business_losses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_losses
    ADD CONSTRAINT business_losses_pkey PRIMARY KEY (loss_id);


--
-- Name: cash_box_transactions cash_box_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cash_box_transactions
    ADD CONSTRAINT cash_box_transactions_pkey PRIMARY KEY (transaction_id);


--
-- Name: cash_flow_categories cash_flow_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cash_flow_categories
    ADD CONSTRAINT cash_flow_categories_pkey PRIMARY KEY (category_id);


--
-- Name: cash_flow_tracking cash_flow_tracking_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cash_flow_tracking
    ADD CONSTRAINT cash_flow_tracking_pkey PRIMARY KEY (flow_id);


--
-- Name: categorization_rules categorization_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categorization_rules
    ADD CONSTRAINT categorization_rules_pkey PRIMARY KEY (rule_id);


--
-- Name: category_mappings category_mappings_old_category_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.category_mappings
    ADD CONSTRAINT category_mappings_old_category_key UNIQUE (old_category);


--
-- Name: category_mappings category_mappings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.category_mappings
    ADD CONSTRAINT category_mappings_pkey PRIMARY KEY (mapping_id);


--
-- Name: category_to_account_map category_to_account_map_category_code_gl_account_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.category_to_account_map
    ADD CONSTRAINT category_to_account_map_category_code_gl_account_code_key UNIQUE (category_code, gl_account_code);


--
-- Name: category_to_account_map category_to_account_map_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.category_to_account_map
    ADD CONSTRAINT category_to_account_map_pkey PRIMARY KEY (mapping_id);


--
-- Name: charge_catalog charge_catalog_charge_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charge_catalog
    ADD CONSTRAINT charge_catalog_charge_code_key UNIQUE (charge_code);


--
-- Name: charge_catalog charge_catalog_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charge_catalog
    ADD CONSTRAINT charge_catalog_pkey PRIMARY KEY (catalog_id);


--
-- Name: charges charges_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charges
    ADD CONSTRAINT charges_pkey PRIMARY KEY (charge_id);


--
-- Name: charity_trade_charters charity_trade_charters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charity_trade_charters
    ADD CONSTRAINT charity_trade_charters_pkey PRIMARY KEY (id);


--
-- Name: chart_of_accounts chart_of_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chart_of_accounts
    ADD CONSTRAINT chart_of_accounts_pkey PRIMARY KEY (account_code);


--
-- Name: charter_beverage_items charter_beverage_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_beverage_items
    ADD CONSTRAINT charter_beverage_items_pkey PRIMARY KEY (beverage_item_id);


--
-- Name: charter_beverage_orders charter_beverage_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_beverage_orders
    ADD CONSTRAINT charter_beverage_orders_pkey PRIMARY KEY (beverage_order_id);


--
-- Name: charter_beverages charter_beverages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_beverages
    ADD CONSTRAINT charter_beverages_pkey PRIMARY KEY (id);


--
-- Name: charter_charges charter_charges_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_charges
    ADD CONSTRAINT charter_charges_pkey PRIMARY KEY (charge_id);


--
-- Name: charter_credit_ledger charter_credit_ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_credit_ledger
    ADD CONSTRAINT charter_credit_ledger_pkey PRIMARY KEY (credit_id);


--
-- Name: charter_gst_details_2010_2012 charter_gst_details_2010_2012_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_gst_details_2010_2012
    ADD CONSTRAINT charter_gst_details_2010_2012_pkey PRIMARY KEY (id);


--
-- Name: charter_gst_details_2010_2012 charter_gst_details_2010_2012_source_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_gst_details_2010_2012
    ADD CONSTRAINT charter_gst_details_2010_2012_source_hash_key UNIQUE (source_hash);


--
-- Name: charter_incidents charter_incidents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_incidents
    ADD CONSTRAINT charter_incidents_pkey PRIMARY KEY (incident_id);


--
-- Name: charter_payments charter_payments_payment_id_charter_id_payment_date_amount_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_payments
    ADD CONSTRAINT charter_payments_payment_id_charter_id_payment_date_amount_key UNIQUE (payment_id, charter_id, payment_date, amount);


--
-- Name: charter_payments charter_payments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_payments
    ADD CONSTRAINT charter_payments_pkey PRIMARY KEY (id);


--
-- Name: charter_receipts charter_receipts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_receipts
    ADD CONSTRAINT charter_receipts_pkey PRIMARY KEY (receipt_id);


--
-- Name: charter_reconciliation_status charter_reconciliation_status_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_reconciliation_status
    ADD CONSTRAINT charter_reconciliation_status_pkey PRIMARY KEY (charter_id);


--
-- Name: charter_refunds charter_refunds_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_refunds
    ADD CONSTRAINT charter_refunds_pkey PRIMARY KEY (id);


--
-- Name: charter_routes charter_routes_charter_id_route_sequence_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_routes
    ADD CONSTRAINT charter_routes_charter_id_route_sequence_key UNIQUE (charter_id, route_sequence);


--
-- Name: charter_routes charter_routes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_routes
    ADD CONSTRAINT charter_routes_pkey PRIMARY KEY (route_id);


--
-- Name: charter_run_types charter_run_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_run_types
    ADD CONSTRAINT charter_run_types_pkey PRIMARY KEY (run_type_id);


--
-- Name: charter_run_types charter_run_types_run_type_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_run_types
    ADD CONSTRAINT charter_run_types_run_type_name_key UNIQUE (run_type_name);


--
-- Name: charter_time_updates charter_time_updates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_time_updates
    ADD CONSTRAINT charter_time_updates_pkey PRIMARY KEY (update_id);


--
-- Name: charter_types charter_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_types
    ADD CONSTRAINT charter_types_pkey PRIMARY KEY (charter_type_id);


--
-- Name: charter_types charter_types_type_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_types
    ADD CONSTRAINT charter_types_type_code_key UNIQUE (type_code);


--
-- Name: charters charters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charters
    ADD CONSTRAINT charters_pkey PRIMARY KEY (charter_id);


--
-- Name: charters charters_reserve_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charters
    ADD CONSTRAINT charters_reserve_number_key UNIQUE (reserve_number);


--
-- Name: charters_routing_times charters_routing_times_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charters_routing_times
    ADD CONSTRAINT charters_routing_times_pkey PRIMARY KEY (routing_time_id);


--
-- Name: chauffeur_float_tracking chauffeur_float_tracking_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chauffeur_float_tracking
    ADD CONSTRAINT chauffeur_float_tracking_pkey PRIMARY KEY (id);


--
-- Name: chauffeur_pay_entries chauffeur_pay_entries_charter_reference_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chauffeur_pay_entries
    ADD CONSTRAINT chauffeur_pay_entries_charter_reference_key UNIQUE (charter_reference);


--
-- Name: chauffeur_pay_entries chauffeur_pay_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chauffeur_pay_entries
    ADD CONSTRAINT chauffeur_pay_entries_pkey PRIMARY KEY (entry_id);


--
-- Name: cheque_register cheque_register_cheque_number_account_number_cleared_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cheque_register
    ADD CONSTRAINT cheque_register_cheque_number_account_number_cleared_date_key UNIQUE (cheque_number, account_number, cleared_date);


--
-- Name: cheque_register cheque_register_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cheque_register
    ADD CONSTRAINT cheque_register_pkey PRIMARY KEY (id);


--
-- Name: cibc_accounts cibc_accounts_account_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cibc_accounts
    ADD CONSTRAINT cibc_accounts_account_number_key UNIQUE (account_number);


--
-- Name: cibc_accounts cibc_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cibc_accounts
    ADD CONSTRAINT cibc_accounts_pkey PRIMARY KEY (account_id);


--
-- Name: cibc_auto_categorization_rules cibc_auto_categorization_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cibc_auto_categorization_rules
    ADD CONSTRAINT cibc_auto_categorization_rules_pkey PRIMARY KEY (rule_id);


--
-- Name: cibc_business_cards cibc_business_cards_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cibc_business_cards
    ADD CONSTRAINT cibc_business_cards_pkey PRIMARY KEY (card_id);


--
-- Name: cibc_card_transactions cibc_card_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cibc_card_transactions
    ADD CONSTRAINT cibc_card_transactions_pkey PRIMARY KEY (transaction_id);


--
-- Name: clients clients_account_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clients
    ADD CONSTRAINT clients_account_number_key UNIQUE (account_number);


--
-- Name: clients clients_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clients
    ADD CONSTRAINT clients_pkey PRIMARY KEY (client_id);


--
-- Name: comprehensive_payment_reconciliation comprehensive_payment_reconciliation_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comprehensive_payment_reconciliation
    ADD CONSTRAINT comprehensive_payment_reconciliation_pkey PRIMARY KEY (id);


--
-- Name: cra_vehicle_events cra_vehicle_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cra_vehicle_events
    ADD CONSTRAINT cra_vehicle_events_pkey PRIMARY KEY (event_id);


--
-- Name: customer_comms_log customer_comms_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_comms_log
    ADD CONSTRAINT customer_comms_log_pkey PRIMARY KEY (comm_id);


--
-- Name: customer_feedback customer_feedback_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_feedback
    ADD CONSTRAINT customer_feedback_pkey PRIMARY KEY (feedback_id);


--
-- Name: customer_name_mapping customer_name_mapping_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_name_mapping
    ADD CONSTRAINT customer_name_mapping_pkey PRIMARY KEY (id);


--
-- Name: cvip_compliance_alerts cvip_compliance_alerts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cvip_compliance_alerts
    ADD CONSTRAINT cvip_compliance_alerts_pkey PRIMARY KEY (alert_id);


--
-- Name: cvip_defects cvip_defects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cvip_defects
    ADD CONSTRAINT cvip_defects_pkey PRIMARY KEY (defect_id);


--
-- Name: cvip_inspections cvip_inspections_inspection_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cvip_inspections
    ADD CONSTRAINT cvip_inspections_inspection_number_key UNIQUE (inspection_number);


--
-- Name: cvip_inspections cvip_inspections_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cvip_inspections
    ADD CONSTRAINT cvip_inspections_pkey PRIMARY KEY (inspection_id);


--
-- Name: david_account_tracking david_account_tracking_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.david_account_tracking
    ADD CONSTRAINT david_account_tracking_pkey PRIMARY KEY (id);


--
-- Name: david_richard_vehicle_loans david_richard_vehicle_loans_payment_date_amount_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.david_richard_vehicle_loans
    ADD CONSTRAINT david_richard_vehicle_loans_payment_date_amount_key UNIQUE (payment_date, amount);


--
-- Name: david_richard_vehicle_loans david_richard_vehicle_loans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.david_richard_vehicle_loans
    ADD CONSTRAINT david_richard_vehicle_loans_pkey PRIMARY KEY (id);


--
-- Name: deferred_wage_accounts deferred_wage_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deferred_wage_accounts
    ADD CONSTRAINT deferred_wage_accounts_pkey PRIMARY KEY (account_id);


--
-- Name: deferred_wage_transactions deferred_wage_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deferred_wage_transactions
    ADD CONSTRAINT deferred_wage_transactions_pkey PRIMARY KEY (transaction_id);


--
-- Name: deposit_records deposit_records_deposit_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deposit_records
    ADD CONSTRAINT deposit_records_deposit_key_key UNIQUE (deposit_key);


--
-- Name: deposit_records deposit_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deposit_records
    ADD CONSTRAINT deposit_records_pkey PRIMARY KEY (id);


--
-- Name: direct_tips_history direct_tips_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.direct_tips_history
    ADD CONSTRAINT direct_tips_history_pkey PRIMARY KEY (tip_id);


--
-- Name: dispatch_events dispatch_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispatch_events
    ADD CONSTRAINT dispatch_events_pkey PRIMARY KEY (dispatch_event_id);


--
-- Name: document_categories document_categories_category_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_categories
    ADD CONSTRAINT document_categories_category_name_key UNIQUE (category_name);


--
-- Name: document_categories document_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_categories
    ADD CONSTRAINT document_categories_pkey PRIMARY KEY (category_id);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (document_id);


--
-- Name: donations_free_rides donations_free_rides_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.donations_free_rides
    ADD CONSTRAINT donations_free_rides_pkey PRIMARY KEY (id);


--
-- Name: driver_alias_map driver_alias_map_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_alias_map
    ADD CONSTRAINT driver_alias_map_pkey PRIMARY KEY (driver_key);


--
-- Name: driver_app_actions driver_app_actions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_app_actions
    ADD CONSTRAINT driver_app_actions_pkey PRIMARY KEY (action_id);


--
-- Name: driver_app_sessions driver_app_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_app_sessions
    ADD CONSTRAINT driver_app_sessions_pkey PRIMARY KEY (session_id);


--
-- Name: driver_comms_log driver_comms_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_comms_log
    ADD CONSTRAINT driver_comms_log_pkey PRIMARY KEY (comm_id);


--
-- Name: driver_disciplinary_actions driver_disciplinary_actions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_disciplinary_actions
    ADD CONSTRAINT driver_disciplinary_actions_pkey PRIMARY KEY (action_id);


--
-- Name: driver_documents driver_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_documents
    ADD CONSTRAINT driver_documents_pkey PRIMARY KEY (id);


--
-- Name: driver_employee_mapping driver_employee_mapping_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_employee_mapping
    ADD CONSTRAINT driver_employee_mapping_pkey PRIMARY KEY (driver_id);


--
-- Name: driver_floats driver_floats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_floats
    ADD CONSTRAINT driver_floats_pkey PRIMARY KEY (float_id);


--
-- Name: driver_location_history driver_location_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_location_history
    ADD CONSTRAINT driver_location_history_pkey PRIMARY KEY (location_id);


--
-- Name: driver_name_employee_map driver_name_employee_map_normalized_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_name_employee_map
    ADD CONSTRAINT driver_name_employee_map_normalized_name_key UNIQUE (normalized_name);


--
-- Name: driver_name_employee_map driver_name_employee_map_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_name_employee_map
    ADD CONSTRAINT driver_name_employee_map_pkey PRIMARY KEY (id);


--
-- Name: driver_pay_entries driver_pay_entries_charter_reference_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_pay_entries
    ADD CONSTRAINT driver_pay_entries_charter_reference_key UNIQUE (charter_reference);


--
-- Name: driver_pay_entries driver_pay_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_pay_entries
    ADD CONSTRAINT driver_pay_entries_pkey PRIMARY KEY (entry_id);


--
-- Name: driver_payroll driver_payroll_driver_id_year_month_charter_id_reserve_numb_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_payroll
    ADD CONSTRAINT driver_payroll_driver_id_year_month_charter_id_reserve_numb_key UNIQUE (driver_id, year, month, charter_id, reserve_number, pay_date);


--
-- Name: driver_payroll driver_payroll_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_payroll
    ADD CONSTRAINT driver_payroll_pkey PRIMARY KEY (id);


--
-- Name: duty_status_types duty_status_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.duty_status_types
    ADD CONSTRAINT duty_status_types_pkey PRIMARY KEY (status_id);


--
-- Name: duty_status_types duty_status_types_status_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.duty_status_types
    ADD CONSTRAINT duty_status_types_status_code_key UNIQUE (status_code);


--
-- Name: email_financial_events email_financial_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.email_financial_events
    ADD CONSTRAINT email_financial_events_pkey PRIMARY KEY (id);


--
-- Name: email_processing_stats email_processing_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.email_processing_stats
    ADD CONSTRAINT email_processing_stats_pkey PRIMARY KEY (id);


--
-- Name: employee_availability employee_availability_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_availability
    ADD CONSTRAINT employee_availability_pkey PRIMARY KEY (availability_id);


--
-- Name: employee_expenses employee_expenses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_expenses
    ADD CONSTRAINT employee_expenses_pkey PRIMARY KEY (expense_id);


--
-- Name: employee_pay_entries employee_pay_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_pay_entries
    ADD CONSTRAINT employee_pay_entries_pkey PRIMARY KEY (entry_id);


--
-- Name: employee_pay_entries employee_pay_entries_reservation_reference_employee_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_pay_entries
    ADD CONSTRAINT employee_pay_entries_reservation_reference_employee_id_key UNIQUE (reservation_reference, employee_id);


--
-- Name: employee_pay_master employee_pay_master_employee_id_pay_period_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_pay_master
    ADD CONSTRAINT employee_pay_master_employee_id_pay_period_id_key UNIQUE (employee_id, pay_period_id);


--
-- Name: employee_pay_master employee_pay_master_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_pay_master
    ADD CONSTRAINT employee_pay_master_pkey PRIMARY KEY (employee_pay_id);


--
-- Name: employee_roe_records employee_roe_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_roe_records
    ADD CONSTRAINT employee_roe_records_pkey PRIMARY KEY (id);


--
-- Name: employee_schedules employee_schedules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_schedules
    ADD CONSTRAINT employee_schedules_pkey PRIMARY KEY (schedule_id);


--
-- Name: employee_t4_records employee_t4_records_employee_id_tax_year_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_t4_records
    ADD CONSTRAINT employee_t4_records_employee_id_tax_year_key UNIQUE (employee_id, tax_year);


--
-- Name: employee_t4_records employee_t4_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_t4_records
    ADD CONSTRAINT employee_t4_records_pkey PRIMARY KEY (t4_id);


--
-- Name: employee_t4_summary employee_t4_summary_employee_id_fiscal_year_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_t4_summary
    ADD CONSTRAINT employee_t4_summary_employee_id_fiscal_year_key UNIQUE (employee_id, fiscal_year);


--
-- Name: employee_t4_summary employee_t4_summary_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_t4_summary
    ADD CONSTRAINT employee_t4_summary_pkey PRIMARY KEY (t4_id);


--
-- Name: employee_time_off_requests employee_time_off_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_time_off_requests
    ADD CONSTRAINT employee_time_off_requests_pkey PRIMARY KEY (request_id);


--
-- Name: employee_work_classifications employee_work_classifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_work_classifications
    ADD CONSTRAINT employee_work_classifications_pkey PRIMARY KEY (classification_id);


--
-- Name: employees employees_employee_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT employees_employee_number_key UNIQUE (employee_number);


--
-- Name: employees employees_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT employees_pkey PRIMARY KEY (employee_id);


--
-- Name: employees employees_quickbooks_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT employees_quickbooks_id_key UNIQUE (quickbooks_id);


--
-- Name: epson_classifications_map epson_classifications_map_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.epson_classifications_map
    ADD CONSTRAINT epson_classifications_map_pkey PRIMARY KEY (epson_classification);


--
-- Name: epson_pay_accounts_map epson_pay_accounts_map_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.epson_pay_accounts_map
    ADD CONSTRAINT epson_pay_accounts_map_pkey PRIMARY KEY (epson_pay_account);


--
-- Name: epson_pay_methods_map epson_pay_methods_map_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.epson_pay_methods_map
    ADD CONSTRAINT epson_pay_methods_map_pkey PRIMARY KEY (epson_pay_method);


--
-- Name: etransfer_banking_reconciliation etransfer_banking_reconciliation_etransfer_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.etransfer_banking_reconciliation
    ADD CONSTRAINT etransfer_banking_reconciliation_etransfer_id_key UNIQUE (etransfer_id);


--
-- Name: etransfer_banking_reconciliation etransfer_banking_reconciliation_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.etransfer_banking_reconciliation
    ADD CONSTRAINT etransfer_banking_reconciliation_pkey PRIMARY KEY (id);


--
-- Name: etransfer_transactions etransfer_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.etransfer_transactions
    ADD CONSTRAINT etransfer_transactions_pkey PRIMARY KEY (etransfer_id);


--
-- Name: etransfers_processed etransfers_processed_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.etransfers_processed
    ADD CONSTRAINT etransfers_processed_pkey PRIMARY KEY (id);


--
-- Name: etransfers_processed etransfers_processed_source_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.etransfers_processed
    ADD CONSTRAINT etransfers_processed_source_hash_key UNIQUE (source_hash);


--
-- Name: excluded_charters excluded_charters_charter_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.excluded_charters
    ADD CONSTRAINT excluded_charters_charter_id_key UNIQUE (charter_id);


--
-- Name: excluded_charters excluded_charters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.excluded_charters
    ADD CONSTRAINT excluded_charters_pkey PRIMARY KEY (id);


--
-- Name: federal_tax_brackets federal_tax_brackets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.federal_tax_brackets
    ADD CONSTRAINT federal_tax_brackets_pkey PRIMARY KEY (year, bracket_number);


--
-- Name: fee_tracking fee_tracking_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fee_tracking
    ADD CONSTRAINT fee_tracking_pkey PRIMARY KEY (fee_id);


--
-- Name: financial_adjustments financial_adjustments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_adjustments
    ADD CONSTRAINT financial_adjustments_pkey PRIMARY KEY (adjustment_id);


--
-- Name: financial_audit_trail financial_audit_trail_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_audit_trail
    ADD CONSTRAINT financial_audit_trail_pkey PRIMARY KEY (audit_id);


--
-- Name: financial_documents financial_documents_file_path_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_documents
    ADD CONSTRAINT financial_documents_file_path_key UNIQUE (file_path);


--
-- Name: financial_documents financial_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_documents
    ADD CONSTRAINT financial_documents_pkey PRIMARY KEY (id);


--
-- Name: financial_statement_sections financial_statement_sections_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_statement_sections
    ADD CONSTRAINT financial_statement_sections_pkey PRIMARY KEY (section_id);


--
-- Name: financial_statement_types financial_statement_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_statement_types
    ADD CONSTRAINT financial_statement_types_pkey PRIMARY KEY (statement_type_id);


--
-- Name: financial_statement_types financial_statement_types_statement_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_statement_types
    ADD CONSTRAINT financial_statement_types_statement_code_key UNIQUE (statement_code);


--
-- Name: financial_transactions financial_transactions_hash_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_transactions
    ADD CONSTRAINT financial_transactions_hash_id_key UNIQUE (hash_id);


--
-- Name: financial_transactions financial_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_transactions
    ADD CONSTRAINT financial_transactions_pkey PRIMARY KEY (id);


--
-- Name: financing_sources financing_sources_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financing_sources
    ADD CONSTRAINT financing_sources_pkey PRIMARY KEY (source_id);


--
-- Name: float_activity_log float_activity_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.float_activity_log
    ADD CONSTRAINT float_activity_log_pkey PRIMARY KEY (log_id);


--
-- Name: fraud_cases fraud_cases_case_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fraud_cases
    ADD CONSTRAINT fraud_cases_case_number_key UNIQUE (case_number);


--
-- Name: fraud_cases fraud_cases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fraud_cases
    ADD CONSTRAINT fraud_cases_pkey PRIMARY KEY (case_id);


--
-- Name: fuel_expenses fuel_expenses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fuel_expenses
    ADD CONSTRAINT fuel_expenses_pkey PRIMARY KEY (id);


--
-- Name: fuel_expenses fuel_expenses_source_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fuel_expenses
    ADD CONSTRAINT fuel_expenses_source_key_key UNIQUE (source_key);


--
-- Name: general_ledger_headers general_ledger_headers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.general_ledger_headers
    ADD CONSTRAINT general_ledger_headers_pkey PRIMARY KEY (header_id);


--
-- Name: general_ledger_headers general_ledger_headers_reference_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.general_ledger_headers
    ADD CONSTRAINT general_ledger_headers_reference_number_key UNIQUE (reference_number);


--
-- Name: general_ledger_lines general_ledger_lines_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.general_ledger_lines
    ADD CONSTRAINT general_ledger_lines_pkey PRIMARY KEY (line_id);


--
-- Name: general_ledger general_ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.general_ledger
    ADD CONSTRAINT general_ledger_pkey PRIMARY KEY (id);


--
-- Name: gl_transactions gl_transactions_natural_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gl_transactions
    ADD CONSTRAINT gl_transactions_natural_key_key UNIQUE (natural_key);


--
-- Name: gl_transactions gl_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gl_transactions
    ADD CONSTRAINT gl_transactions_pkey PRIMARY KEY (gl_id);


--
-- Name: gratuity_income_links gratuity_income_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gratuity_income_links
    ADD CONSTRAINT gratuity_income_links_pkey PRIMARY KEY (id);


--
-- Name: gst_audit_trail gst_audit_trail_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gst_audit_trail
    ADD CONSTRAINT gst_audit_trail_pkey PRIMARY KEY (gst_id);


--
-- Name: gst_rates_lookup gst_rates_lookup_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gst_rates_lookup
    ADD CONSTRAINT gst_rates_lookup_pkey PRIMARY KEY (province_code);


--
-- Name: hos_14day_summary hos_14day_summary_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hos_14day_summary
    ADD CONSTRAINT hos_14day_summary_pkey PRIMARY KEY (summary_id);


--
-- Name: hos_log hos_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hos_log
    ADD CONSTRAINT hos_log_pkey PRIMARY KEY (hos_id);


--
-- Name: incident_costs incident_costs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incident_costs
    ADD CONSTRAINT incident_costs_pkey PRIMARY KEY (cost_id);


--
-- Name: incident_damage_tracking incident_damage_tracking_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incident_damage_tracking
    ADD CONSTRAINT incident_damage_tracking_pkey PRIMARY KEY (id);


--
-- Name: incidents incidents_incident_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incidents
    ADD CONSTRAINT incidents_incident_number_key UNIQUE (incident_number);


--
-- Name: incidents incidents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incidents
    ADD CONSTRAINT incidents_pkey PRIMARY KEY (incident_id);


--
-- Name: income_ledger income_ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.income_ledger
    ADD CONSTRAINT income_ledger_pkey PRIMARY KEY (income_id);


--
-- Name: interest_allocations interest_allocations_credit_line_id_month_year_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interest_allocations
    ADD CONSTRAINT interest_allocations_credit_line_id_month_year_key UNIQUE (credit_line_id, month_year);


--
-- Name: interest_allocations interest_allocations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interest_allocations
    ADD CONSTRAINT interest_allocations_pkey PRIMARY KEY (id);


--
-- Name: invoice_line_items invoice_line_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_line_items
    ADD CONSTRAINT invoice_line_items_pkey PRIMARY KEY (line_item_id);


--
-- Name: invoice_tracking invoice_tracking_invoice_number_invoice_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_tracking
    ADD CONSTRAINT invoice_tracking_invoice_number_invoice_date_key UNIQUE (invoice_number, invoice_date);


--
-- Name: invoice_tracking invoice_tracking_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_tracking
    ADD CONSTRAINT invoice_tracking_pkey PRIMARY KEY (id);


--
-- Name: invoices invoices_invoice_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_invoice_number_key UNIQUE (invoice_number);


--
-- Name: invoices invoices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_pkey PRIMARY KEY (invoice_id);


--
-- Name: invoices invoices_reserve_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_reserve_number_key UNIQUE (reserve_number);


--
-- Name: legacy_import_status legacy_import_status_data_year_data_source_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legacy_import_status
    ADD CONSTRAINT legacy_import_status_data_year_data_source_key UNIQUE (data_year, data_source);


--
-- Name: legacy_import_status legacy_import_status_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legacy_import_status
    ADD CONSTRAINT legacy_import_status_pkey PRIMARY KEY (import_id);


--
-- Name: lender_statement_transactions lender_statement_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lender_statement_transactions
    ADD CONSTRAINT lender_statement_transactions_pkey PRIMARY KEY (id);


--
-- Name: lender_statement_transactions lender_statement_transactions_txn_date_amount_desc_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lender_statement_transactions
    ADD CONSTRAINT lender_statement_transactions_txn_date_amount_desc_hash_key UNIQUE (txn_date, amount, desc_hash);


--
-- Name: lms2026_payment_matches lms2026_payment_matches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lms2026_payment_matches
    ADD CONSTRAINT lms2026_payment_matches_pkey PRIMARY KEY (match_id);


--
-- Name: loan_transactions loan_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.loan_transactions
    ADD CONSTRAINT loan_transactions_pkey PRIMARY KEY (id);


--
-- Name: maintenance_activity_types maintenance_activity_types_activity_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maintenance_activity_types
    ADD CONSTRAINT maintenance_activity_types_activity_code_key UNIQUE (activity_code);


--
-- Name: maintenance_activity_types maintenance_activity_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maintenance_activity_types
    ADD CONSTRAINT maintenance_activity_types_pkey PRIMARY KEY (activity_type_id);


--
-- Name: maintenance_alerts maintenance_alerts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maintenance_alerts
    ADD CONSTRAINT maintenance_alerts_pkey PRIMARY KEY (alert_id);


--
-- Name: maintenance_records maintenance_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maintenance_records
    ADD CONSTRAINT maintenance_records_pkey PRIMARY KEY (record_id);


--
-- Name: maintenance_schedules_auto maintenance_schedules_auto_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maintenance_schedules_auto
    ADD CONSTRAINT maintenance_schedules_auto_pkey PRIMARY KEY (schedule_id);


--
-- Name: maintenance_service_types maintenance_service_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maintenance_service_types
    ADD CONSTRAINT maintenance_service_types_pkey PRIMARY KEY (service_type_id);


--
-- Name: maintenance_service_types maintenance_service_types_service_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maintenance_service_types
    ADD CONSTRAINT maintenance_service_types_service_code_key UNIQUE (service_code);


--
-- Name: major_events major_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.major_events
    ADD CONSTRAINT major_events_pkey PRIMARY KEY (event_id);


--
-- Name: manual_check_payees manual_check_payees_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.manual_check_payees
    ADD CONSTRAINT manual_check_payees_pkey PRIMARY KEY (id);


--
-- Name: master_relationships master_relationships_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.master_relationships
    ADD CONSTRAINT master_relationships_pkey PRIMARY KEY (id);


--
-- Name: migration_log migration_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.migration_log
    ADD CONSTRAINT migration_log_pkey PRIMARY KEY (log_id);


--
-- Name: missing_receipt_tracking missing_receipt_tracking_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.missing_receipt_tracking
    ADD CONSTRAINT missing_receipt_tracking_pkey PRIMARY KEY (missing_id);


--
-- Name: monthly_work_assignments monthly_work_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.monthly_work_assignments
    ADD CONSTRAINT monthly_work_assignments_pkey PRIMARY KEY (assignment_id);


--
-- Name: owner_equity_accounts owner_equity_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.owner_equity_accounts
    ADD CONSTRAINT owner_equity_accounts_pkey PRIMARY KEY (equity_account_id);


--
-- Name: owner_expense_transactions owner_expense_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.owner_expense_transactions
    ADD CONSTRAINT owner_expense_transactions_pkey PRIMARY KEY (transaction_id);


--
-- Name: paul_pay_tracking paul_pay_tracking_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paul_pay_tracking
    ADD CONSTRAINT paul_pay_tracking_pkey PRIMARY KEY (id);


--
-- Name: pay_periods pay_periods_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pay_periods
    ADD CONSTRAINT pay_periods_pkey PRIMARY KEY (pay_period_id);


--
-- Name: payables payables_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payables
    ADD CONSTRAINT payables_pkey PRIMARY KEY (payable_id);


--
-- Name: payday_loan_payments payday_loan_payments_loan_id_due_date_amount_due_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payday_loan_payments
    ADD CONSTRAINT payday_loan_payments_loan_id_due_date_amount_due_key UNIQUE (loan_id, due_date, amount_due);


--
-- Name: payday_loan_payments payday_loan_payments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payday_loan_payments
    ADD CONSTRAINT payday_loan_payments_pkey PRIMARY KEY (id);


--
-- Name: payday_loans payday_loans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payday_loans
    ADD CONSTRAINT payday_loans_pkey PRIMARY KEY (id);


--
-- Name: payday_loans payday_loans_source_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payday_loans
    ADD CONSTRAINT payday_loans_source_hash_key UNIQUE (source_hash);


--
-- Name: payment_customer_links payment_customer_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_customer_links
    ADD CONSTRAINT payment_customer_links_pkey PRIMARY KEY (payment_id);


--
-- Name: payment_matches payment_matches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_matches
    ADD CONSTRAINT payment_matches_pkey PRIMARY KEY (match_id);


--
-- Name: payments payments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_pkey PRIMARY KEY (payment_id);


--
-- Name: payroll_adjustments payroll_adjustments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_adjustments
    ADD CONSTRAINT payroll_adjustments_pkey PRIMARY KEY (adjustment_id);


--
-- Name: payroll_comparison payroll_comparison_employee_number_pay_period_start_pay_per_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_comparison
    ADD CONSTRAINT payroll_comparison_employee_number_pay_period_start_pay_per_key UNIQUE (employee_number, pay_period_start, pay_period_end, source_file);


--
-- Name: payroll_comparison payroll_comparison_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_comparison
    ADD CONSTRAINT payroll_comparison_pkey PRIMARY KEY (id);


--
-- Name: payroll_fix_audit payroll_fix_audit_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_fix_audit
    ADD CONSTRAINT payroll_fix_audit_pkey PRIMARY KEY (id);


--
-- Name: payroll_fix_rollback_audit payroll_fix_rollback_audit_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_fix_rollback_audit
    ADD CONSTRAINT payroll_fix_rollback_audit_pkey PRIMARY KEY (id);


--
-- Name: performance_metrics performance_metrics_metric_category_metric_name_period_type_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.performance_metrics
    ADD CONSTRAINT performance_metrics_metric_category_metric_name_period_type_key UNIQUE (metric_category, metric_name, period_type);


--
-- Name: performance_metrics performance_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.performance_metrics
    ADD CONSTRAINT performance_metrics_pkey PRIMARY KEY (metric_id);


--
-- Name: permissions permissions_module_action_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.permissions
    ADD CONSTRAINT permissions_module_action_key UNIQUE (module, action);


--
-- Name: permissions permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.permissions
    ADD CONSTRAINT permissions_pkey PRIMARY KEY (permission_id);


--
-- Name: personal_expenses personal_expenses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personal_expenses
    ADD CONSTRAINT personal_expenses_pkey PRIMARY KEY (id);


--
-- Name: posting_queue posting_queue_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.posting_queue
    ADD CONSTRAINT posting_queue_pkey PRIMARY KEY (id);


--
-- Name: posting_reversals posting_reversals_original_batch_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.posting_reversals
    ADD CONSTRAINT posting_reversals_original_batch_id_key UNIQUE (original_batch_id);


--
-- Name: posting_reversals posting_reversals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.posting_reversals
    ADD CONSTRAINT posting_reversals_pkey PRIMARY KEY (id);


--
-- Name: pre_inspection_issues pre_inspection_issues_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pre_inspection_issues
    ADD CONSTRAINT pre_inspection_issues_pkey PRIMARY KEY (issue_id);


--
-- Name: quotations quotations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quotations
    ADD CONSTRAINT quotations_pkey PRIMARY KEY (quote_id);


--
-- Name: raw_file_inventory raw_file_inventory_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.raw_file_inventory
    ADD CONSTRAINT raw_file_inventory_pkey PRIMARY KEY (id);


--
-- Name: receipt_banking_links receipt_banking_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_banking_links
    ADD CONSTRAINT receipt_banking_links_pkey PRIMARY KEY (link_id);


--
-- Name: receipt_banking_links receipt_banking_links_receipt_id_transaction_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_banking_links
    ADD CONSTRAINT receipt_banking_links_receipt_id_transaction_id_key UNIQUE (receipt_id, transaction_id);


--
-- Name: receipt_cashbox_links receipt_cashbox_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_cashbox_links
    ADD CONSTRAINT receipt_cashbox_links_pkey PRIMARY KEY (link_id);


--
-- Name: receipt_cashbox_links receipt_cashbox_links_receipt_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_cashbox_links
    ADD CONSTRAINT receipt_cashbox_links_receipt_id_key UNIQUE (receipt_id);


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
-- Name: receipt_deliveries receipt_deliveries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_deliveries
    ADD CONSTRAINT receipt_deliveries_pkey PRIMARY KEY (delivery_id);


--
-- Name: receipt_gst_adjustment_audit receipt_gst_adjustment_audit_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_gst_adjustment_audit
    ADD CONSTRAINT receipt_gst_adjustment_audit_pkey PRIMARY KEY (id);


--
-- Name: receipt_line_items receipt_line_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_line_items
    ADD CONSTRAINT receipt_line_items_pkey PRIMARY KEY (line_item_id);


--
-- Name: receipts_ingest_log receipts_ingest_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts_ingest_log
    ADD CONSTRAINT receipts_ingest_log_pkey PRIMARY KEY (id);


--
-- Name: receipts receipts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT receipts_pkey PRIMARY KEY (receipt_id);


--
-- Name: recurring_invoices recurring_invoices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recurring_invoices
    ADD CONSTRAINT recurring_invoices_pkey PRIMARY KEY (id);


--
-- Name: recurring_invoices recurring_invoices_vendor_name_invoice_type_charge_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recurring_invoices
    ADD CONSTRAINT recurring_invoices_vendor_name_invoice_type_charge_date_key UNIQUE (vendor_name, invoice_type, charge_date);


--
-- Name: refunds_cancellations refunds_cancellations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refunds_cancellations
    ADD CONSTRAINT refunds_cancellations_pkey PRIMARY KEY (id);


--
-- Name: rent_debt_ledger rent_debt_ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rent_debt_ledger
    ADD CONSTRAINT rent_debt_ledger_pkey PRIMARY KEY (id);


--
-- Name: route_event_types route_event_types_event_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.route_event_types
    ADD CONSTRAINT route_event_types_event_code_key UNIQUE (event_code);


--
-- Name: route_event_types route_event_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.route_event_types
    ADD CONSTRAINT route_event_types_pkey PRIMARY KEY (event_type_id);


--
-- Name: run_type_default_charges run_type_default_charges_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.run_type_default_charges
    ADD CONSTRAINT run_type_default_charges_pkey PRIMARY KEY (run_type_id, charge_description);


--
-- Name: schema_migrations schema_migrations_filename_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_filename_key UNIQUE (filename);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (id);


--
-- Name: security_audit security_audit_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_audit
    ADD CONSTRAINT security_audit_pkey PRIMARY KEY (audit_id);


--
-- Name: security_events security_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_events
    ADD CONSTRAINT security_events_pkey PRIMARY KEY (event_id);


--
-- Name: square_api_audit square_api_audit_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_api_audit
    ADD CONSTRAINT square_api_audit_pkey PRIMARY KEY (square_audit_id);


--
-- Name: square_api_audit square_api_audit_square_payment_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_api_audit
    ADD CONSTRAINT square_api_audit_square_payment_id_key UNIQUE (square_payment_id);


--
-- Name: square_capital_activity square_capital_activity_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_capital_activity
    ADD CONSTRAINT square_capital_activity_pkey PRIMARY KEY (id);


--
-- Name: square_capital_activity square_capital_activity_row_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_capital_activity
    ADD CONSTRAINT square_capital_activity_row_hash_key UNIQUE (row_hash);


--
-- Name: square_capital_loans square_capital_loans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_capital_loans
    ADD CONSTRAINT square_capital_loans_pkey PRIMARY KEY (loan_id);


--
-- Name: square_capital_loans square_capital_loans_square_loan_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_capital_loans
    ADD CONSTRAINT square_capital_loans_square_loan_id_key UNIQUE (square_loan_id);


--
-- Name: square_cc_staging square_cc_staging_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_cc_staging
    ADD CONSTRAINT square_cc_staging_pkey PRIMARY KEY (payment_id);


--
-- Name: square_customers square_customers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_customers
    ADD CONSTRAINT square_customers_pkey PRIMARY KEY (id);


--
-- Name: square_customers square_customers_square_customer_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_customers
    ADD CONSTRAINT square_customers_square_customer_id_key UNIQUE (square_customer_id);


--
-- Name: square_customers_staging square_customers_staging_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_customers_staging
    ADD CONSTRAINT square_customers_staging_pkey PRIMARY KEY (customer_id);


--
-- Name: square_etransfer_reconciliation square_etransfer_reconciliati_payment_code_4char_square_pay_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_etransfer_reconciliation
    ADD CONSTRAINT square_etransfer_reconciliati_payment_code_4char_square_pay_key UNIQUE (payment_code_4char, square_payment_id);


--
-- Name: square_etransfer_reconciliation square_etransfer_reconciliation_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_etransfer_reconciliation
    ADD CONSTRAINT square_etransfer_reconciliation_pkey PRIMARY KEY (reconciliation_id);


--
-- Name: square_lms_matches square_lms_matches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_lms_matches
    ADD CONSTRAINT square_lms_matches_pkey PRIMARY KEY (match_id);


--
-- Name: square_payment_categories square_payment_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_payment_categories
    ADD CONSTRAINT square_payment_categories_pkey PRIMARY KEY (id);


--
-- Name: square_payment_categories square_payment_categories_square_payment_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_payment_categories
    ADD CONSTRAINT square_payment_categories_square_payment_unique UNIQUE (square_payment_id);


--
-- Name: square_payouts square_payouts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_payouts
    ADD CONSTRAINT square_payouts_pkey PRIMARY KEY (id);


--
-- Name: square_processing_fees square_processing_fees_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_processing_fees
    ADD CONSTRAINT square_processing_fees_pkey PRIMARY KEY (fee_id);


--
-- Name: square_raw_imports square_raw_imports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_raw_imports
    ADD CONSTRAINT square_raw_imports_pkey PRIMARY KEY (import_id);


--
-- Name: square_raw_records square_raw_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_raw_records
    ADD CONSTRAINT square_raw_records_pkey PRIMARY KEY (record_pk);


--
-- Name: square_review_status square_review_status_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_review_status
    ADD CONSTRAINT square_review_status_pkey PRIMARY KEY (id);


--
-- Name: square_review_status square_review_status_square_payment_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_review_status
    ADD CONSTRAINT square_review_status_square_payment_unique UNIQUE (square_payment_id);


--
-- Name: staging_driver_pay_files staging_driver_pay_files_file_path_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_driver_pay_files
    ADD CONSTRAINT staging_driver_pay_files_file_path_key UNIQUE (file_path);


--
-- Name: staging_driver_pay_files staging_driver_pay_files_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_driver_pay_files
    ADD CONSTRAINT staging_driver_pay_files_pkey PRIMARY KEY (id);


--
-- Name: staging_driver_pay_links staging_driver_pay_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_driver_pay_links
    ADD CONSTRAINT staging_driver_pay_links_pkey PRIMARY KEY (staging_id);


--
-- Name: staging_employee_reference_data staging_employee_reference_data_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_employee_reference_data
    ADD CONSTRAINT staging_employee_reference_data_pkey PRIMARY KEY (id);


--
-- Name: staging_pd7a_year_end_summary staging_pd7a_year_end_summary_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.staging_pd7a_year_end_summary
    ADD CONSTRAINT staging_pd7a_year_end_summary_pkey PRIMARY KEY (id);


--
-- Name: system_config system_config_config_category_config_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_config
    ADD CONSTRAINT system_config_config_category_config_key_key UNIQUE (config_category, config_key);


--
-- Name: system_config system_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_config
    ADD CONSTRAINT system_config_pkey PRIMARY KEY (config_id);


--
-- Name: system_locked_years system_locked_years_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_locked_years
    ADD CONSTRAINT system_locked_years_pkey PRIMARY KEY (year);


--
-- Name: t4_compliance_corrections t4_compliance_corrections_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.t4_compliance_corrections
    ADD CONSTRAINT t4_compliance_corrections_pkey PRIMARY KEY (correction_id);


--
-- Name: tax_overrides tax_overrides_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_overrides
    ADD CONSTRAINT tax_overrides_pkey PRIMARY KEY (id);


--
-- Name: tax_periods tax_periods_label_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_periods
    ADD CONSTRAINT tax_periods_label_key UNIQUE (label);


--
-- Name: tax_periods tax_periods_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_periods
    ADD CONSTRAINT tax_periods_pkey PRIMARY KEY (id);


--
-- Name: tax_remittances tax_remittances_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_remittances
    ADD CONSTRAINT tax_remittances_pkey PRIMARY KEY (id);


--
-- Name: tax_returns tax_returns_period_id_form_type_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_returns
    ADD CONSTRAINT tax_returns_period_id_form_type_key UNIQUE (period_id, form_type);


--
-- Name: tax_returns tax_returns_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_returns
    ADD CONSTRAINT tax_returns_pkey PRIMARY KEY (id);


--
-- Name: tax_rollovers tax_rollovers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_rollovers
    ADD CONSTRAINT tax_rollovers_pkey PRIMARY KEY (id);


--
-- Name: tax_variances tax_variances_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_variances
    ADD CONSTRAINT tax_variances_pkey PRIMARY KEY (id);


--
-- Name: tax_year_reference tax_year_reference_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_year_reference
    ADD CONSTRAINT tax_year_reference_pkey PRIMARY KEY (year);


--
-- Name: training_checklist_items training_checklist_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.training_checklist_items
    ADD CONSTRAINT training_checklist_items_pkey PRIMARY KEY (item_id);


--
-- Name: training_programs training_programs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.training_programs
    ADD CONSTRAINT training_programs_pkey PRIMARY KEY (program_id);


--
-- Name: transaction_categories transaction_categories_category_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transaction_categories
    ADD CONSTRAINT transaction_categories_category_name_key UNIQUE (category_name);


--
-- Name: transaction_categories transaction_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transaction_categories
    ADD CONSTRAINT transaction_categories_pkey PRIMARY KEY (id);


--
-- Name: transaction_chain transaction_chain_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transaction_chain
    ADD CONSTRAINT transaction_chain_pkey PRIMARY KEY (chain_id);


--
-- Name: transaction_log transaction_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transaction_log
    ADD CONSTRAINT transaction_log_pkey PRIMARY KEY (transaction_id);


--
-- Name: transaction_subcategories transaction_subcategories_category_id_subcategory_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transaction_subcategories
    ADD CONSTRAINT transaction_subcategories_category_id_subcategory_name_key UNIQUE (category_id, subcategory_name);


--
-- Name: transaction_subcategories transaction_subcategories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transaction_subcategories
    ADD CONSTRAINT transaction_subcategories_pkey PRIMARY KEY (id);


--
-- Name: unified_charge_lookup unified_charge_lookup_charge_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unified_charge_lookup
    ADD CONSTRAINT unified_charge_lookup_charge_code_key UNIQUE (charge_code);


--
-- Name: unified_charge_lookup unified_charge_lookup_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unified_charge_lookup
    ADD CONSTRAINT unified_charge_lookup_pkey PRIMARY KEY (lookup_id);


--
-- Name: unified_general_ledger unified_general_ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unified_general_ledger
    ADD CONSTRAINT unified_general_ledger_pkey PRIMARY KEY (id);


--
-- Name: unified_general_ledger unified_general_ledger_row_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unified_general_ledger
    ADD CONSTRAINT unified_general_ledger_row_hash_key UNIQUE (row_hash);


--
-- Name: asset_depreciation_schedule unique_asset_year; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset_depreciation_schedule
    ADD CONSTRAINT unique_asset_year UNIQUE (asset_id, fiscal_year);


--
-- Name: payroll_adjustments unique_driver_payroll_adjustment; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_adjustments
    ADD CONSTRAINT unique_driver_payroll_adjustment UNIQUE (driver_payroll_id);


--
-- Name: receipt_line_items unique_receipt_line; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_line_items
    ADD CONSTRAINT unique_receipt_line UNIQUE (receipt_id, line_number);


--
-- Name: charity_trade_charters unique_reserve_charity; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charity_trade_charters
    ADD CONSTRAINT unique_reserve_charity UNIQUE (reserve_number);


--
-- Name: charter_gst_details_2010_2012 unique_reserve_source; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_gst_details_2010_2012
    ADD CONSTRAINT unique_reserve_source UNIQUE (reserve_number, source_sheet);


--
-- Name: vendor_default_categories unique_vendor_category; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_default_categories
    ADD CONSTRAINT unique_vendor_category UNIQUE (vendor_canonical_name);


--
-- Name: unmatched_items unmatched_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unmatched_items
    ADD CONSTRAINT unmatched_items_pkey PRIMARY KEY (id);


--
-- Name: personal_expenses uq_personal_expenses_source_txn_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.personal_expenses
    ADD CONSTRAINT uq_personal_expenses_source_txn_key UNIQUE (source_txn_key);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: vacation_pay_records vacation_pay_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vacation_pay_records
    ADD CONSTRAINT vacation_pay_records_pkey PRIMARY KEY (id);


--
-- Name: vehicle_capacity_tiers vehicle_capacity_tiers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_capacity_tiers
    ADD CONSTRAINT vehicle_capacity_tiers_pkey PRIMARY KEY (tier_id);


--
-- Name: vehicle_capacity_tiers vehicle_capacity_tiers_tier_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_capacity_tiers
    ADD CONSTRAINT vehicle_capacity_tiers_tier_name_key UNIQUE (tier_name);


--
-- Name: vehicle_document_types vehicle_document_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_document_types
    ADD CONSTRAINT vehicle_document_types_pkey PRIMARY KEY (doc_type_id);


--
-- Name: vehicle_document_types vehicle_document_types_type_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_document_types
    ADD CONSTRAINT vehicle_document_types_type_code_key UNIQUE (type_code);


--
-- Name: vehicle_documents vehicle_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_documents
    ADD CONSTRAINT vehicle_documents_pkey PRIMARY KEY (document_id);


--
-- Name: vehicle_financing_complete vehicle_financing_complete_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_financing_complete
    ADD CONSTRAINT vehicle_financing_complete_pkey PRIMARY KEY (id);


--
-- Name: vehicle_financing vehicle_financing_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_financing
    ADD CONSTRAINT vehicle_financing_pkey PRIMARY KEY (financing_id);


--
-- Name: vehicle_fuel_log vehicle_fuel_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_fuel_log
    ADD CONSTRAINT vehicle_fuel_log_pkey PRIMARY KEY (id);


--
-- Name: vehicle_insurance vehicle_insurance_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_insurance
    ADD CONSTRAINT vehicle_insurance_pkey PRIMARY KEY (insurance_id);


--
-- Name: vehicle_loan_payments vehicle_loan_payments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_loan_payments
    ADD CONSTRAINT vehicle_loan_payments_pkey PRIMARY KEY (id);


--
-- Name: vehicle_loan_reconciliation_allocations vehicle_loan_reconciliation_allocations_lender_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_loan_reconciliation_allocations
    ADD CONSTRAINT vehicle_loan_reconciliation_allocations_lender_id_key UNIQUE (lender_id);


--
-- Name: vehicle_loan_reconciliation_allocations vehicle_loan_reconciliation_allocations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_loan_reconciliation_allocations
    ADD CONSTRAINT vehicle_loan_reconciliation_allocations_pkey PRIMARY KEY (id);


--
-- Name: vehicle_loans vehicle_loans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_loans
    ADD CONSTRAINT vehicle_loans_pkey PRIMARY KEY (id);


--
-- Name: vehicle_mileage_log vehicle_mileage_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_mileage_log
    ADD CONSTRAINT vehicle_mileage_log_pkey PRIMARY KEY (log_id);


--
-- Name: vehicle_pre_inspections vehicle_pre_inspections_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_pre_inspections
    ADD CONSTRAINT vehicle_pre_inspections_pkey PRIMARY KEY (inspection_id);


--
-- Name: vehicle_pricing_defaults vehicle_pricing_defaults_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_pricing_defaults
    ADD CONSTRAINT vehicle_pricing_defaults_pkey PRIMARY KEY (pricing_id);


--
-- Name: vehicle_pricing_defaults vehicle_pricing_defaults_vehicle_type_charter_type_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_pricing_defaults
    ADD CONSTRAINT vehicle_pricing_defaults_vehicle_type_charter_type_code_key UNIQUE (vehicle_type, charter_type_code);


--
-- Name: vehicle_purchases vehicle_purchases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_purchases
    ADD CONSTRAINT vehicle_purchases_pkey PRIMARY KEY (purchase_id);


--
-- Name: vehicle_repossessions vehicle_repossessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_repossessions
    ADD CONSTRAINT vehicle_repossessions_pkey PRIMARY KEY (repossession_id);


--
-- Name: vehicle_sales vehicle_sales_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_sales
    ADD CONSTRAINT vehicle_sales_pkey PRIMARY KEY (sale_id);


--
-- Name: vehicle_writeoffs vehicle_writeoffs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_writeoffs
    ADD CONSTRAINT vehicle_writeoffs_pkey PRIMARY KEY (writeoff_id);


--
-- Name: vehicles vehicles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicles
    ADD CONSTRAINT vehicles_pkey PRIMARY KEY (vehicle_id);


--
-- Name: vendor_account_ledger vendor_account_ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_account_ledger
    ADD CONSTRAINT vendor_account_ledger_pkey PRIMARY KEY (ledger_id);


--
-- Name: vendor_accounts vendor_accounts_canonical_vendor_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_accounts
    ADD CONSTRAINT vendor_accounts_canonical_vendor_key UNIQUE (canonical_vendor);


--
-- Name: vendor_accounts vendor_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_accounts
    ADD CONSTRAINT vendor_accounts_pkey PRIMARY KEY (account_id);


--
-- Name: vendor_default_categories vendor_default_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_default_categories
    ADD CONSTRAINT vendor_default_categories_pkey PRIMARY KEY (id);


--
-- Name: vendor_name_mapping vendor_name_mapping_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_name_mapping
    ADD CONSTRAINT vendor_name_mapping_pkey PRIMARY KEY (id);


--
-- Name: vendor_standardization vendor_standardization_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_standardization
    ADD CONSTRAINT vendor_standardization_pkey PRIMARY KEY (id);


--
-- Name: vendor_synonyms vendor_synonyms_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_synonyms
    ADD CONSTRAINT vendor_synonyms_pkey PRIMARY KEY (synonym_id);


--
-- Name: vendors vendors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendors
    ADD CONSTRAINT vendors_pkey PRIMARY KEY (id);


--
-- Name: vendors vendors_quickbooks_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendors
    ADD CONSTRAINT vendors_quickbooks_id_key UNIQUE (quickbooks_id);


--
-- Name: verification_audit verification_audit_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.verification_audit
    ADD CONSTRAINT verification_audit_pkey PRIMARY KEY (audit_id);


--
-- Name: verification_queue verification_queue_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.verification_queue
    ADD CONSTRAINT verification_queue_pkey PRIMARY KEY (id);


--
-- Name: wage_allocation_pool wage_allocation_pool_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wage_allocation_pool
    ADD CONSTRAINT wage_allocation_pool_pkey PRIMARY KEY (pool_id);


--
-- Name: wcb_ab_industry_rates wcb_ab_industry_rates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wcb_ab_industry_rates
    ADD CONSTRAINT wcb_ab_industry_rates_pkey PRIMARY KEY (year, industry_code);


--
-- Name: wcb_ab_premium_rates wcb_ab_premium_rates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wcb_ab_premium_rates
    ADD CONSTRAINT wcb_ab_premium_rates_pkey PRIMARY KEY (year, industry_code);


--
-- Name: wcb_debt_ledger wcb_debt_ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wcb_debt_ledger
    ADD CONSTRAINT wcb_debt_ledger_pkey PRIMARY KEY (id);


--
-- Name: wcb_recurring_charges wcb_recurring_charges_charge_month_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wcb_recurring_charges
    ADD CONSTRAINT wcb_recurring_charges_charge_month_key UNIQUE (charge_month);


--
-- Name: wcb_recurring_charges wcb_recurring_charges_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wcb_recurring_charges
    ADD CONSTRAINT wcb_recurring_charges_pkey PRIMARY KEY (id);


--
-- Name: wcb_summary wcb_summary_driver_id_year_month_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wcb_summary
    ADD CONSTRAINT wcb_summary_driver_id_year_month_key UNIQUE (driver_id, year, month);


--
-- Name: wcb_summary wcb_summary_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wcb_summary
    ADD CONSTRAINT wcb_summary_pkey PRIMARY KEY (id);


--
-- Name: zero_payment_resolutions zero_payment_resolutions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zero_payment_resolutions
    ADD CONSTRAINT zero_payment_resolutions_pkey PRIMARY KEY (payment_id);


--
-- Name: gl_lines_account_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX gl_lines_account_idx ON public.general_ledger_lines USING btree (account_code);


--
-- Name: gl_lines_header_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX gl_lines_header_idx ON public.general_ledger_lines USING btree (header_id);


--
-- Name: idx_account_aliases_canonical; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_account_aliases_canonical ON public.account_number_aliases USING btree (canonical_account_number);


--
-- Name: idx_account_aliases_statement; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_account_aliases_statement ON public.account_number_aliases USING btree (statement_format);


--
-- Name: idx_accounting_entries_account; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_accounting_entries_account ON public.accounting_entries USING btree (account_code);


--
-- Name: idx_accounting_entries_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_accounting_entries_date ON public.accounting_entries USING btree (entry_date);


--
-- Name: idx_activity_types_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activity_types_category ON public.maintenance_activity_types USING btree (category);


--
-- Name: idx_asset_docs_asset; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_asset_docs_asset ON public.asset_documentation USING btree (asset_id);


--
-- Name: idx_assets_acquisition_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_assets_acquisition_date ON public.assets USING btree (acquisition_date);


--
-- Name: idx_assets_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_assets_category ON public.assets USING btree (asset_category);


--
-- Name: idx_assets_ownership; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_assets_ownership ON public.assets USING btree (ownership_status);


--
-- Name: idx_assets_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_assets_status ON public.assets USING btree (status);


--
-- Name: idx_audit_log_changed_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_log_changed_at ON public.audit_log USING btree (changed_at);


--
-- Name: idx_audit_log_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_log_entity ON public.audit_log USING btree (entity_type, entity_id);


--
-- Name: idx_bank_accounts_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bank_accounts_active ON public.bank_accounts USING btree (is_active, account_type);


--
-- Name: idx_banking_account_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_banking_account_date ON public.banking_transactions USING btree (account_number, transaction_date);


--
-- Name: idx_banking_etransfer_pattern; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_banking_etransfer_pattern ON public.banking_transactions USING btree (description) WHERE (description ~~* '%E-TRANSFER%'::text);


--
-- Name: idx_banking_receipt_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_banking_receipt_id ON public.banking_transactions USING btree (receipt_id);


--
-- Name: idx_banking_reconciliation_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_banking_reconciliation_status ON public.banking_transactions USING btree (reconciliation_status);


--
-- Name: idx_banking_source_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_banking_source_hash ON public.banking_transactions USING btree (source_hash);


--
-- Name: idx_banking_trans_account; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_banking_trans_account ON public.banking_transactions USING btree (account_number);


--
-- Name: idx_banking_trans_amount; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_banking_trans_amount ON public.banking_transactions USING btree (debit_amount, credit_amount);


--
-- Name: idx_banking_trans_bank_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_banking_trans_bank_id ON public.banking_transactions USING btree (bank_id);


--
-- Name: idx_banking_trans_card; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_banking_trans_card ON public.banking_transactions USING btree (card_last4_detected);


--
-- Name: idx_banking_trans_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_banking_trans_category ON public.banking_transactions USING btree (category);


--
-- Name: idx_banking_trans_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_banking_trans_date ON public.banking_transactions USING btree (transaction_date);


--
-- Name: idx_banking_trans_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_banking_trans_hash ON public.banking_transactions USING btree (transaction_hash);


--
-- Name: idx_banking_trans_updated_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_banking_trans_updated_at ON public.banking_transactions USING btree (updated_at);


--
-- Name: idx_banking_trans_vendor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_banking_trans_vendor ON public.banking_transactions USING btree (vendor_extracted);


--
-- Name: idx_banking_transactions_date_amounts; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_banking_transactions_date_amounts ON public.banking_transactions USING btree (transaction_date, debit_amount, credit_amount);


--
-- Name: idx_banking_transactions_description; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_banking_transactions_description ON public.banking_transactions USING gin (to_tsvector('english'::regconfig, description));


--
-- Name: idx_banking_transactions_uid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_banking_transactions_uid ON public.banking_transactions USING btree (transaction_uid);


--
-- Name: idx_banking_verified; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_banking_verified ON public.banking_transactions USING btree (verified, verified_date);


--
-- Name: idx_beverage_orders_reserve; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_beverage_orders_reserve ON public.charter_beverage_orders USING btree (reserve_number);


--
-- Name: idx_business_expenses_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_business_expenses_date ON public.business_expenses USING btree (expense_date);


--
-- Name: idx_business_expenses_vendor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_business_expenses_vendor ON public.business_expenses USING btree (vendor);


--
-- Name: idx_business_losses_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_business_losses_category ON public.business_losses USING btree (category);


--
-- Name: idx_business_losses_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_business_losses_date ON public.business_losses USING btree (loss_date);


--
-- Name: idx_cashbox_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cashbox_date ON public.cash_box_transactions USING btree (transaction_date);


--
-- Name: idx_cashbox_employee; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cashbox_employee ON public.cash_box_transactions USING btree (employee_id);


--
-- Name: idx_cashbox_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cashbox_type ON public.cash_box_transactions USING btree (transaction_type);


--
-- Name: idx_categorization_rules_pattern; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_categorization_rules_pattern ON public.categorization_rules USING btree (rule_pattern);


--
-- Name: idx_charge_catalog_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charge_catalog_active ON public.charge_catalog USING btree (is_active);


--
-- Name: idx_charge_catalog_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charge_catalog_code ON public.charge_catalog USING btree (charge_code);


--
-- Name: idx_charges_account; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charges_account ON public.charter_charges USING btree (account_number);


--
-- Name: idx_charges_charge_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charges_charge_type ON public.charges USING btree (charge_type);


--
-- Name: idx_charges_charter; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charges_charter ON public.charter_charges USING btree (charter_id);


--
-- Name: idx_charges_reserve; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charges_reserve ON public.charter_charges USING btree (reserve_number);


--
-- Name: idx_charges_reserve_number; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charges_reserve_number ON public.charges USING btree (reserve_number);


--
-- Name: idx_charity_classification; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charity_classification ON public.charity_trade_charters USING btree (classification);


--
-- Name: idx_charity_reserve; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charity_reserve ON public.charity_trade_charters USING btree (reserve_number);


--
-- Name: idx_charity_tax_locked; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charity_tax_locked ON public.charity_trade_charters USING btree (is_tax_locked);


--
-- Name: idx_chart_accounts_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chart_accounts_active ON public.chart_of_accounts USING btree (is_active);


--
-- Name: idx_chart_accounts_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chart_accounts_code ON public.chart_of_accounts USING btree (account_code);


--
-- Name: idx_chart_accounts_parent; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chart_accounts_parent ON public.chart_of_accounts USING btree (parent_account);


--
-- Name: idx_chart_accounts_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chart_accounts_type ON public.chart_of_accounts USING btree (account_type);


--
-- Name: idx_charter_beverages_beverage_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charter_beverages_beverage_item_id ON public.charter_beverages USING btree (beverage_item_id);


--
-- Name: idx_charter_beverages_charter_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charter_beverages_charter_id ON public.charter_beverages USING btree (charter_id);


--
-- Name: idx_charter_beverages_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charter_beverages_created_at ON public.charter_beverages USING btree (created_at);


--
-- Name: idx_charter_charges_charter_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charter_charges_charter_id ON public.charter_charges USING btree (charter_id);


--
-- Name: idx_charter_payments_charter_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charter_payments_charter_id ON public.charter_payments USING btree (charter_id);


--
-- Name: idx_charter_payments_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charter_payments_date ON public.charter_payments USING btree (payment_date);


--
-- Name: idx_charter_payments_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charter_payments_key ON public.charter_payments USING btree (payment_key);


--
-- Name: idx_charter_payments_payment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charter_payments_payment_id ON public.charter_payments USING btree (payment_id);


--
-- Name: idx_charter_receipts_reserve; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charter_receipts_reserve ON public.charter_receipts USING btree (reserve_number);


--
-- Name: idx_charter_receipts_vehicle; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charter_receipts_vehicle ON public.charter_receipts USING btree (vehicle_id);


--
-- Name: idx_charter_refunds_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charter_refunds_date ON public.charter_refunds USING btree (refund_date);


--
-- Name: idx_charter_refunds_reserve; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charter_refunds_reserve ON public.charter_refunds USING btree (reserve_number);


--
-- Name: idx_charter_routes_charter_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charter_routes_charter_id ON public.charter_routes USING btree (charter_id);


--
-- Name: idx_charter_routes_sequence; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charter_routes_sequence ON public.charter_routes USING btree (charter_id, route_sequence);


--
-- Name: idx_charter_routes_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charter_routes_status ON public.charter_routes USING btree (route_status);


--
-- Name: idx_charters_charter_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charters_charter_type ON public.charters USING btree (charter_type);


--
-- Name: idx_charters_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charters_date ON public.charters USING btree (charter_date);


--
-- Name: idx_charters_employee_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charters_employee_id ON public.charters USING btree (employee_id);


--
-- Name: idx_charters_is_placeholder_true; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charters_is_placeholder_true ON public.charters USING btree (charter_id) WHERE (is_placeholder = true);


--
-- Name: idx_charters_locked; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charters_locked ON public.charters USING btree (locked) WHERE (locked = true);


--
-- Name: idx_charters_out_of_town; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charters_out_of_town ON public.charters USING btree (is_out_of_town) WHERE (is_out_of_town = false);


--
-- Name: idx_charters_reserve; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charters_reserve ON public.charters USING btree (reserve_number);


--
-- Name: idx_charters_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charters_status ON public.charters USING btree (status);


--
-- Name: idx_charters_vehicle_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_charters_vehicle_id ON public.charters USING btree (vehicle_id);


--
-- Name: idx_chauffeur_float_banking_transaction; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chauffeur_float_banking_transaction ON public.chauffeur_float_tracking USING btree (banking_transaction_id);


--
-- Name: idx_chauffeur_pay_entries_charter_ref; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chauffeur_pay_entries_charter_ref ON public.chauffeur_pay_entries USING btree (charter_reference);


--
-- Name: idx_chauffeur_pay_entries_chauffeur_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chauffeur_pay_entries_chauffeur_id ON public.chauffeur_pay_entries USING btree (chauffeur_id);


--
-- Name: idx_chauffeur_pay_entries_pay_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_chauffeur_pay_entries_pay_date ON public.chauffeur_pay_entries USING btree (pay_date);


--
-- Name: idx_cibc_cards_equity_account; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cibc_cards_equity_account ON public.cibc_business_cards USING btree (owner_equity_account_id);


--
-- Name: idx_cibc_transactions_banking; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cibc_transactions_banking ON public.cibc_card_transactions USING btree (banking_transaction_id);


--
-- Name: idx_cibc_transactions_card; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cibc_transactions_card ON public.cibc_card_transactions USING btree (card_id);


--
-- Name: idx_cibc_transactions_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cibc_transactions_category ON public.cibc_card_transactions USING btree (expense_category);


--
-- Name: idx_cibc_transactions_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cibc_transactions_date ON public.cibc_card_transactions USING btree (transaction_date);


--
-- Name: idx_clients_account; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clients_account ON public.clients USING btree (account_number);


--
-- Name: idx_clients_balance; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clients_balance ON public.clients USING btree (balance);


--
-- Name: idx_clients_corporate_hierarchy; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clients_corporate_hierarchy ON public.clients USING btree (corporate_parent_id, corporate_role);


--
-- Name: idx_clients_corporate_parent_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clients_corporate_parent_id ON public.clients USING btree (corporate_parent_id);


--
-- Name: idx_clients_corporate_role; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clients_corporate_role ON public.clients USING btree (corporate_role);


--
-- Name: idx_clients_exemption_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clients_exemption_type ON public.clients USING btree (exemption_type);


--
-- Name: idx_clients_fraud_case_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clients_fraud_case_id ON public.clients USING btree (fraud_case_id);


--
-- Name: idx_clients_gst_exempt; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clients_gst_exempt ON public.clients USING btree (is_gst_exempt);


--
-- Name: idx_clients_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clients_name ON public.clients USING btree (company_name);


--
-- Name: idx_clients_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clients_status ON public.clients USING btree (status);


--
-- Name: idx_credit_ledger_applied_reserve; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_credit_ledger_applied_reserve ON public.charter_credit_ledger USING btree (applied_to_reserve_number);


--
-- Name: idx_credit_ledger_client; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_credit_ledger_client ON public.charter_credit_ledger USING btree (client_id);


--
-- Name: idx_credit_ledger_remaining; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_credit_ledger_remaining ON public.charter_credit_ledger USING btree (remaining_balance) WHERE (remaining_balance > (0)::numeric);


--
-- Name: idx_credit_ledger_source_reserve; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_credit_ledger_source_reserve ON public.charter_credit_ledger USING btree (source_reserve_number);


--
-- Name: idx_customer_comms_reserve; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_customer_comms_reserve ON public.customer_comms_log USING btree (reserve_number);


--
-- Name: idx_customer_comms_sent_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_customer_comms_sent_at ON public.customer_comms_log USING btree (sent_at DESC);


--
-- Name: idx_customer_feedback_follow_up; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_customer_feedback_follow_up ON public.customer_feedback USING btree (requires_follow_up, follow_up_completed);


--
-- Name: idx_customer_feedback_reserve; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_customer_feedback_reserve ON public.customer_feedback USING btree (reserve_number);


--
-- Name: idx_customer_feedback_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_customer_feedback_type ON public.customer_feedback USING btree (feedback_type);


--
-- Name: idx_deferred_wage_accounts_balance; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deferred_wage_accounts_balance ON public.deferred_wage_accounts USING btree (current_balance);


--
-- Name: idx_deferred_wage_accounts_employee_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deferred_wage_accounts_employee_id ON public.deferred_wage_accounts USING btree (employee_id);


--
-- Name: idx_deferred_wage_accounts_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deferred_wage_accounts_status ON public.deferred_wage_accounts USING btree (account_status);


--
-- Name: idx_deferred_wage_transactions_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deferred_wage_transactions_account_id ON public.deferred_wage_transactions USING btree (account_id);


--
-- Name: idx_deferred_wage_transactions_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deferred_wage_transactions_date ON public.deferred_wage_transactions USING btree (transaction_date);


--
-- Name: idx_deferred_wage_transactions_employee_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deferred_wage_transactions_employee_id ON public.deferred_wage_transactions USING btree (employee_id);


--
-- Name: idx_deferred_wage_transactions_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_deferred_wage_transactions_type ON public.deferred_wage_transactions USING btree (transaction_type);


--
-- Name: idx_depreciation_asset; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_depreciation_asset ON public.asset_depreciation_schedule USING btree (asset_id);


--
-- Name: idx_depreciation_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_depreciation_year ON public.asset_depreciation_schedule USING btree (fiscal_year);


--
-- Name: idx_dispatch_events_reserve; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dispatch_events_reserve ON public.dispatch_events USING btree (reserve_number);


--
-- Name: idx_dispatch_events_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dispatch_events_type ON public.dispatch_events USING btree (event_type);


--
-- Name: idx_doc_types_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_doc_types_category ON public.vehicle_document_types USING btree (category);


--
-- Name: idx_documents_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_category ON public.documents USING btree (category);


--
-- Name: idx_documents_upload_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_upload_date ON public.documents USING btree (upload_date);


--
-- Name: idx_driver_comms_ack; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_driver_comms_ack ON public.driver_comms_log USING btree (acknowledged_at);


--
-- Name: idx_driver_comms_reserve; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_driver_comms_reserve ON public.driver_comms_log USING btree (reserve_number);


--
-- Name: idx_driver_documents_employee; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_driver_documents_employee ON public.driver_documents USING btree (employee_id);


--
-- Name: idx_driver_documents_expiry; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_driver_documents_expiry ON public.driver_documents USING btree (expiry_date) WHERE (expiry_date IS NOT NULL);


--
-- Name: idx_driver_documents_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_driver_documents_status ON public.driver_documents USING btree (status);


--
-- Name: idx_driver_documents_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_driver_documents_type ON public.driver_documents USING btree (document_type);


--
-- Name: idx_driver_pay_entries_charter_ref; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_driver_pay_entries_charter_ref ON public.driver_pay_entries USING btree (charter_reference);


--
-- Name: idx_driver_pay_entries_driver_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_driver_pay_entries_driver_id ON public.driver_pay_entries USING btree (driver_id);


--
-- Name: idx_driver_pay_entries_pay_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_driver_pay_entries_pay_date ON public.driver_pay_entries USING btree (pay_date);


--
-- Name: idx_driver_payroll_charter; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_driver_payroll_charter ON public.driver_payroll USING btree (charter_id);


--
-- Name: idx_driver_payroll_class; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_driver_payroll_class ON public.driver_payroll USING btree (payroll_class);


--
-- Name: idx_driver_payroll_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_driver_payroll_date ON public.driver_payroll USING btree (pay_date);


--
-- Name: idx_driver_payroll_driver; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_driver_payroll_driver ON public.driver_payroll USING btree (driver_id);


--
-- Name: idx_email_events_amount; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_email_events_amount ON public.email_financial_events USING btree (amount);


--
-- Name: idx_email_events_email_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_email_events_email_date ON public.email_financial_events USING btree (email_date);


--
-- Name: idx_email_events_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_email_events_entity ON public.email_financial_events USING btree (entity);


--
-- Name: idx_email_events_event_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_email_events_event_type ON public.email_financial_events USING btree (event_type);


--
-- Name: idx_emp_pay_completeness; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_emp_pay_completeness ON public.employee_pay_master USING btree (data_completeness);


--
-- Name: idx_emp_pay_employee; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_emp_pay_employee ON public.employee_pay_master USING btree (employee_id);


--
-- Name: idx_emp_pay_employee_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_emp_pay_employee_year ON public.employee_pay_master USING btree (employee_id, fiscal_year);


--
-- Name: idx_emp_pay_period; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_emp_pay_period ON public.employee_pay_master USING btree (pay_period_id);


--
-- Name: idx_emp_pay_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_emp_pay_year ON public.employee_pay_master USING btree (fiscal_year);


--
-- Name: idx_employee_availability_day; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_employee_availability_day ON public.employee_availability USING btree (day_of_week, is_available);


--
-- Name: idx_employee_availability_employee_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_employee_availability_employee_id ON public.employee_availability USING btree (employee_id);


--
-- Name: idx_employee_expenses_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_employee_expenses_date ON public.employee_expenses USING btree (expense_date);


--
-- Name: idx_employee_expenses_employee_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_employee_expenses_employee_id ON public.employee_expenses USING btree (employee_id);


--
-- Name: idx_employee_expenses_reimbursement; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_employee_expenses_reimbursement ON public.employee_expenses USING btree (reimbursement_status);


--
-- Name: idx_employee_pay_entries_employee_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_employee_pay_entries_employee_id ON public.employee_pay_entries USING btree (employee_id);


--
-- Name: idx_employee_pay_entries_employee_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_employee_pay_entries_employee_type ON public.employee_pay_entries USING btree (employee_type);


--
-- Name: idx_employee_pay_entries_pay_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_employee_pay_entries_pay_date ON public.employee_pay_entries USING btree (pay_date);


--
-- Name: idx_employee_pay_entries_reservation_ref; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_employee_pay_entries_reservation_ref ON public.employee_pay_entries USING btree (reservation_reference);


--
-- Name: idx_employee_schedules_approval; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_employee_schedules_approval ON public.employee_schedules USING btree (approved_by, approved_at);


--
-- Name: idx_employee_schedules_employee_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_employee_schedules_employee_id ON public.employee_schedules USING btree (employee_id);


--
-- Name: idx_employee_schedules_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_employee_schedules_status ON public.employee_schedules USING btree (status);


--
-- Name: idx_employee_schedules_work_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_employee_schedules_work_date ON public.employee_schedules USING btree (work_date);


--
-- Name: idx_employee_work_classifications_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_employee_work_classifications_active ON public.employee_work_classifications USING btree (is_active, effective_start_date, effective_end_date);


--
-- Name: idx_employee_work_classifications_employee_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_employee_work_classifications_employee_id ON public.employee_work_classifications USING btree (employee_id);


--
-- Name: idx_employees_chauffeur; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_employees_chauffeur ON public.employees USING btree (is_chauffeur);


--
-- Name: idx_employees_chauffeur_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_employees_chauffeur_status ON public.employees USING btree (is_chauffeur, employment_status) WHERE (is_chauffeur = true);


--
-- Name: idx_employees_legacy_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_employees_legacy_name ON public.employees USING btree (legacy_name);


--
-- Name: idx_employees_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_employees_name ON public.employees USING btree (full_name);


--
-- Name: idx_employees_number; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_employees_number ON public.employees USING btree (employee_number);


--
-- Name: idx_employees_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_employees_status ON public.employees USING btree (status);


--
-- Name: idx_etransfer_banking; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_etransfer_banking ON public.etransfer_transactions USING btree (banking_transaction_id);


--
-- Name: idx_etransfer_date_amount; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_etransfer_date_amount ON public.etransfer_transactions USING btree (transaction_date, amount);


--
-- Name: idx_etransfer_direction; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_etransfer_direction ON public.etransfer_transactions USING btree (direction, status);


--
-- Name: idx_financial_adjustments_client_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_financial_adjustments_client_id ON public.financial_adjustments USING btree (client_id);


--
-- Name: idx_financial_adjustments_fraud_case_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_financial_adjustments_fraud_case_id ON public.financial_adjustments USING btree (fraud_case_id);


--
-- Name: idx_financial_docs_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_financial_docs_date ON public.financial_documents USING btree (document_date);


--
-- Name: idx_financial_docs_invoice; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_financial_docs_invoice ON public.financial_documents USING btree (invoice_number);


--
-- Name: idx_financial_docs_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_financial_docs_type ON public.financial_documents USING btree (document_type);


--
-- Name: idx_financing_sources_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_financing_sources_status ON public.financing_sources USING btree (status);


--
-- Name: idx_financing_sources_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_financing_sources_type ON public.financing_sources USING btree (source_type);


--
-- Name: idx_float_activity_log_activity_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_float_activity_log_activity_type ON public.float_activity_log USING btree (activity_type);


--
-- Name: idx_float_activity_log_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_float_activity_log_created_at ON public.float_activity_log USING btree (created_at);


--
-- Name: idx_float_activity_log_float_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_float_activity_log_float_id ON public.float_activity_log USING btree (float_id);


--
-- Name: idx_floats_employee; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_floats_employee ON public.driver_floats USING btree (employee_id);


--
-- Name: idx_floats_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_floats_status ON public.driver_floats USING btree (status);


--
-- Name: idx_fraud_cases_case_number; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fraud_cases_case_number ON public.fraud_cases USING btree (case_number);


--
-- Name: idx_fraud_cases_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fraud_cases_created_at ON public.fraud_cases USING btree (created_at);


--
-- Name: idx_fraud_cases_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fraud_cases_status ON public.fraud_cases USING btree (status);


--
-- Name: idx_fuel_log_vehicle; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fuel_log_vehicle ON public.vehicle_fuel_log USING btree (vehicle_id, recorded_at DESC);


--
-- Name: idx_general_ledger_account; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_general_ledger_account ON public.general_ledger USING btree (account, date);


--
-- Name: idx_general_ledger_account_balance; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_general_ledger_account_balance ON public.general_ledger USING btree (account, date, balance);


--
-- Name: idx_general_ledger_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_general_ledger_date ON public.general_ledger USING btree (date);


--
-- Name: idx_general_ledger_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_general_ledger_name ON public.general_ledger USING btree (name, date);


--
-- Name: idx_general_ledger_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_general_ledger_type ON public.general_ledger USING btree (transaction_type, date);


--
-- Name: idx_gl_account; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_gl_account ON public.gl_transactions USING btree (account_name);


--
-- Name: idx_gl_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_gl_date ON public.gl_transactions USING btree (transaction_date);


--
-- Name: idx_gl_headers_entry_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_gl_headers_entry_date ON public.general_ledger_headers USING btree (entry_date);


--
-- Name: idx_gl_headers_fraud_case; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_gl_headers_fraud_case ON public.general_ledger_headers USING btree (fraud_case_id);


--
-- Name: idx_gl_headers_reference; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_gl_headers_reference ON public.general_ledger_headers USING btree (reference_number);


--
-- Name: idx_gl_lines_account_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_gl_lines_account_code ON public.general_ledger_lines USING btree (account_code);


--
-- Name: idx_gl_lines_fraud_case; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_gl_lines_fraud_case ON public.general_ledger_lines USING btree (fraud_case_id);


--
-- Name: idx_gl_lines_header_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_gl_lines_header_id ON public.general_ledger_lines USING btree (header_id);


--
-- Name: idx_gst_details_charter; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_gst_details_charter ON public.charter_gst_details_2010_2012 USING btree (charter_id);


--
-- Name: idx_gst_details_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_gst_details_date ON public.charter_gst_details_2010_2012 USING btree (reserve_date);


--
-- Name: idx_gst_details_reserve; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_gst_details_reserve ON public.charter_gst_details_2010_2012 USING btree (reserve_number);


--
-- Name: idx_hos_14day_employee; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_hos_14day_employee ON public.hos_14day_summary USING btree (employee_id, end_date DESC);


--
-- Name: idx_hos_log_employee_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_hos_log_employee_date ON public.hos_log USING btree (employee_id, hos_date DESC);


--
-- Name: idx_hos_log_reserve; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_hos_log_reserve ON public.hos_log USING btree (reserve_number);


--
-- Name: idx_incidents_manager_review; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_incidents_manager_review ON public.charter_incidents USING btree (requires_manager_review, manager_reviewed_at);


--
-- Name: idx_incidents_reserve; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_incidents_reserve ON public.charter_incidents USING btree (reserve_number);


--
-- Name: idx_incidents_type_severity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_incidents_type_severity ON public.charter_incidents USING btree (incident_type, incident_severity);


--
-- Name: idx_income_ledger_charter_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_income_ledger_charter_id ON public.income_ledger USING btree (charter_id);


--
-- Name: idx_income_ledger_client_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_income_ledger_client_id ON public.income_ledger USING btree (client_id);


--
-- Name: idx_income_ledger_fiscal_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_income_ledger_fiscal_year ON public.income_ledger USING btree (fiscal_year);


--
-- Name: idx_income_ledger_payment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_income_ledger_payment_id ON public.income_ledger USING btree (payment_id);


--
-- Name: idx_income_ledger_revenue_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_income_ledger_revenue_category ON public.income_ledger USING btree (revenue_category);


--
-- Name: idx_income_ledger_transaction_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_income_ledger_transaction_date ON public.income_ledger USING btree (transaction_date);


--
-- Name: idx_interest_allocations_month; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_interest_allocations_month ON public.interest_allocations USING btree (month_year);


--
-- Name: idx_invoice_line_items_invoice; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_invoice_line_items_invoice ON public.invoice_line_items USING btree (invoice_id);


--
-- Name: idx_invoice_line_items_reserve; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_invoice_line_items_reserve ON public.invoice_line_items USING btree (reserve_number);


--
-- Name: idx_invoice_line_items_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_invoice_line_items_type ON public.invoice_line_items USING btree (line_type);


--
-- Name: idx_invoice_tracking_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_invoice_tracking_date ON public.invoice_tracking USING btree (invoice_date);


--
-- Name: idx_invoice_tracking_number; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_invoice_tracking_number ON public.invoice_tracking USING btree (invoice_number);


--
-- Name: idx_invoices_balance_due; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_invoices_balance_due ON public.invoices USING btree (balance_due) WHERE (balance_due > (0)::numeric);


--
-- Name: idx_invoices_due_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_invoices_due_date ON public.invoices USING btree (due_date);


--
-- Name: idx_invoices_reserve; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_invoices_reserve ON public.invoices USING btree (reserve_number);


--
-- Name: idx_invoices_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_invoices_status ON public.invoices USING btree (invoice_status);


--
-- Name: idx_line_items_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_line_items_category ON public.receipt_line_items USING btree (category);


--
-- Name: idx_line_items_employee; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_line_items_employee ON public.receipt_line_items USING btree (employee_id);


--
-- Name: idx_line_items_receipt; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_line_items_receipt ON public.receipt_line_items USING btree (receipt_id);


--
-- Name: idx_line_items_vehicle; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_line_items_vehicle ON public.receipt_line_items USING btree (vehicle_id);


--
-- Name: idx_maint_records_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_maint_records_date ON public.maintenance_records USING btree (service_date);


--
-- Name: idx_maint_records_odometer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_maint_records_odometer ON public.maintenance_records USING btree (odometer_reading);


--
-- Name: idx_maint_records_vehicle; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_maint_records_vehicle ON public.maintenance_records USING btree (vehicle_id);


--
-- Name: idx_maintenance_records_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_maintenance_records_date ON public.maintenance_records USING btree (service_date);


--
-- Name: idx_maintenance_records_odometer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_maintenance_records_odometer ON public.maintenance_records USING btree (odometer_reading);


--
-- Name: idx_maintenance_records_vehicle; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_maintenance_records_vehicle ON public.maintenance_records USING btree (vehicle_id);


--
-- Name: idx_major_events_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_major_events_date ON public.major_events USING btree (event_date);


--
-- Name: idx_major_events_severity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_major_events_severity ON public.major_events USING btree (severity);


--
-- Name: idx_mileage_log_charter; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mileage_log_charter ON public.vehicle_mileage_log USING btree (charter_id);


--
-- Name: idx_mileage_log_vehicle; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_mileage_log_vehicle ON public.vehicle_mileage_log USING btree (vehicle_id, recorded_at DESC);


--
-- Name: idx_monthly_work_assignments_employee_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_monthly_work_assignments_employee_id ON public.monthly_work_assignments USING btree (employee_id);


--
-- Name: idx_monthly_work_assignments_month; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_monthly_work_assignments_month ON public.monthly_work_assignments USING btree (work_month);


--
-- Name: idx_monthly_work_assignments_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_monthly_work_assignments_status ON public.monthly_work_assignments USING btree (status);


--
-- Name: idx_owner_equity_accounts_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_owner_equity_accounts_owner ON public.owner_equity_accounts USING btree (owner_name);


--
-- Name: idx_owner_equity_accounts_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_owner_equity_accounts_type ON public.owner_equity_accounts USING btree (account_type);


--
-- Name: idx_owner_expense_transactions_approval; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_owner_expense_transactions_approval ON public.owner_expense_transactions USING btree (approved_by, approval_date);


--
-- Name: idx_owner_expense_transactions_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_owner_expense_transactions_date ON public.owner_expense_transactions USING btree (transaction_date);


--
-- Name: idx_owner_expense_transactions_equity_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_owner_expense_transactions_equity_id ON public.owner_expense_transactions USING btree (equity_account_id);


--
-- Name: idx_owner_expense_transactions_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_owner_expense_transactions_type ON public.owner_expense_transactions USING btree (transaction_type);


--
-- Name: idx_pay_periods_dates; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pay_periods_dates ON public.pay_periods USING btree (period_start_date, period_end_date);


--
-- Name: idx_pay_periods_year_period; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pay_periods_year_period ON public.pay_periods USING btree (fiscal_year, period_number);


--
-- Name: idx_payments_account; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payments_account ON public.payments USING btree (account_number);


--
-- Name: idx_payments_code_4char; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payments_code_4char ON public.payments USING btree (payment_code_4char);


--
-- Name: idx_payments_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payments_date ON public.payments USING btree (payment_date);


--
-- Name: idx_payments_method; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payments_method ON public.payments USING btree (payment_method);


--
-- Name: idx_payments_payment_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payments_payment_key ON public.payments USING btree (payment_key) WHERE (payment_key IS NOT NULL);


--
-- Name: idx_payments_reserve; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payments_reserve ON public.payments USING btree (reserve_number);


--
-- Name: idx_payments_reserve_label; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payments_reserve_label ON public.payments USING btree (reserve_number, payment_label);


--
-- Name: idx_payments_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payments_status ON public.payments USING btree (status);


--
-- Name: idx_payments_verified; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payments_verified ON public.payments USING btree (verified, verified_date);


--
-- Name: idx_payroll_adjustments_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payroll_adjustments_date ON public.payroll_adjustments USING btree (original_pay_date);


--
-- Name: idx_payroll_adjustments_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payroll_adjustments_type ON public.payroll_adjustments USING btree (adjustment_type);


--
-- Name: idx_payroll_comparison_date_range; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payroll_comparison_date_range ON public.payroll_comparison USING btree (pay_period_start, pay_period_end, employee_number);


--
-- Name: idx_payroll_comparison_employee; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payroll_comparison_employee ON public.payroll_comparison USING btree (employee_number);


--
-- Name: idx_payroll_comparison_period; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payroll_comparison_period ON public.payroll_comparison USING btree (pay_period_start, pay_period_end);


--
-- Name: idx_personal_expenses_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_personal_expenses_category ON public.personal_expenses USING btree (category);


--
-- Name: idx_personal_expenses_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_personal_expenses_date ON public.personal_expenses USING btree (date);


--
-- Name: idx_personal_expenses_payment_method; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_personal_expenses_payment_method ON public.personal_expenses USING btree (payment_method);


--
-- Name: idx_personal_expenses_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_personal_expenses_status ON public.personal_expenses USING btree (status);


--
-- Name: idx_receipt_banking_links_receipt_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_receipt_banking_links_receipt_id ON public.receipt_banking_links USING btree (receipt_id);


--
-- Name: idx_receipt_banking_links_transaction_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_receipt_banking_links_transaction_id ON public.receipt_banking_links USING btree (transaction_id);


--
-- Name: idx_receipt_cashbox_links_driver_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_receipt_cashbox_links_driver_id ON public.receipt_cashbox_links USING btree (driver_id);


--
-- Name: idx_receipt_cashbox_links_receipt_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_receipt_cashbox_links_receipt_id ON public.receipt_cashbox_links USING btree (receipt_id);


--
-- Name: idx_receipts_banking_txn; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_receipts_banking_txn ON public.receipts USING btree (banking_transaction_id);


--
-- Name: idx_receipts_canonical_vendor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_receipts_canonical_vendor ON public.receipts USING btree (canonical_vendor);


--
-- Name: idx_receipts_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_receipts_date ON public.receipts USING btree (receipt_date);


--
-- Name: idx_receipts_fiscal_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_receipts_fiscal_year ON public.receipts USING btree (fiscal_year);


--
-- Name: idx_receipts_gl_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_receipts_gl_code ON public.receipts USING btree (gl_code);


--
-- Name: idx_receipts_ingest_log_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_receipts_ingest_log_hash ON public.receipts_ingest_log USING btree (file_hash);


--
-- Name: idx_receipts_invoice_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_receipts_invoice_date ON public.receipts USING btree (invoice_date);


--
-- Name: idx_receipts_paper_verified; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_receipts_paper_verified ON public.receipts USING btree (is_paper_verified, paper_verification_date);


--
-- Name: idx_receipts_review_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_receipts_review_status ON public.receipts USING btree (receipt_review_status, receipt_reviewed_at);


--
-- Name: idx_receipts_source_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_receipts_source_hash ON public.receipts USING btree (source_hash);


--
-- Name: idx_receipts_vendor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_receipts_vendor ON public.receipts USING btree (lower(vendor_name));


--
-- Name: idx_receipts_vendor_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_receipts_vendor_account_id ON public.receipts USING btree (vendor_account_id);


--
-- Name: idx_receipts_vendor_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_receipts_vendor_date ON public.receipts USING btree (vendor_name, receipt_date);


--
-- Name: idx_receipts_vendor_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_receipts_vendor_name ON public.receipts USING btree (vendor_name);


--
-- Name: idx_receipts_verified; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_receipts_verified ON public.receipts USING btree (verified, verified_date);


--
-- Name: idx_receipts_verified_by_edit; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_receipts_verified_by_edit ON public.receipts USING btree (verified_by_edit, verified_at);


--
-- Name: idx_rent_debt_ledger_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rent_debt_ledger_date ON public.rent_debt_ledger USING btree (transaction_date);


--
-- Name: idx_rent_debt_ledger_vendor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rent_debt_ledger_vendor ON public.rent_debt_ledger USING btree (vendor_name);


--
-- Name: idx_route_event_types_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_route_event_types_active ON public.route_event_types USING btree (is_active, display_order) WHERE (is_active = true);


--
-- Name: idx_routing_times_reserve; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_routing_times_reserve ON public.charters_routing_times USING btree (reserve_number);


--
-- Name: idx_sca_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sca_date ON public.square_capital_activity USING btree (activity_date);


--
-- Name: idx_sca_desc; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sca_desc ON public.square_capital_activity USING btree (description);


--
-- Name: idx_security_events_ip; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_security_events_ip ON public.security_events USING btree (ip_address);


--
-- Name: idx_security_events_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_security_events_timestamp ON public.security_events USING btree ("timestamp");


--
-- Name: idx_security_events_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_security_events_user_id ON public.security_events USING btree (user_id);


--
-- Name: idx_square_audit_amounts; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_audit_amounts ON public.square_api_audit USING btree (transaction_amount_cents, refund_amount_cents, net_received_cents);


--
-- Name: idx_square_audit_charter; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_audit_charter ON public.square_api_audit USING btree (charter_reserve_number, charter_id);


--
-- Name: idx_square_audit_customer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_audit_customer ON public.square_api_audit USING btree (square_customer_id, customer_email);


--
-- Name: idx_square_audit_dates; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_audit_dates ON public.square_api_audit USING btree (square_created_timestamp, data_extraction_batch_id);


--
-- Name: idx_square_audit_payment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_audit_payment ON public.square_api_audit USING btree (payment_id, square_payment_id);


--
-- Name: idx_square_audit_reconciliation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_audit_reconciliation ON public.square_api_audit USING btree (has_refund, has_dispute, audit_status);


--
-- Name: idx_square_audit_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_audit_status ON public.square_api_audit USING btree (audit_status, match_verified_date);


--
-- Name: idx_square_categories_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_categories_category ON public.square_payment_categories USING btree (category);


--
-- Name: idx_square_categories_payment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_categories_payment_id ON public.square_payment_categories USING btree (square_payment_id);


--
-- Name: idx_square_customers_company; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_customers_company ON public.square_customers USING btree (company_name);


--
-- Name: idx_square_customers_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_customers_email ON public.square_customers USING btree (email_address);


--
-- Name: idx_square_customers_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_customers_name ON public.square_customers USING btree (first_name, surname);


--
-- Name: idx_square_customers_phone; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_customers_phone ON public.square_customers USING btree (phone_number);


--
-- Name: idx_square_customers_square_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_customers_square_id ON public.square_customers USING btree (square_customer_id);


--
-- Name: idx_square_etransfer_reconcil_banking; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_etransfer_reconcil_banking ON public.square_etransfer_reconciliation USING btree (banking_transaction_id);


--
-- Name: idx_square_etransfer_reconcil_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_etransfer_reconcil_code ON public.square_etransfer_reconciliation USING btree (payment_code_4char);


--
-- Name: idx_square_etransfer_reconcil_interac_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_etransfer_reconcil_interac_code ON public.square_etransfer_reconciliation USING btree (interac_code_4char);


--
-- Name: idx_square_etransfer_reconcil_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_etransfer_reconcil_status ON public.square_etransfer_reconciliation USING btree (reconciliation_status);


--
-- Name: idx_square_fees_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_fees_date ON public.square_processing_fees USING btree (transaction_date);


--
-- Name: idx_square_fees_payment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_fees_payment ON public.square_processing_fees USING btree (square_payment_id);


--
-- Name: idx_square_loans_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_loans_date ON public.square_capital_loans USING btree (received_date);


--
-- Name: idx_square_review_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_review_status ON public.square_review_status USING btree (review_status);


--
-- Name: idx_square_review_status_payment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_review_status_payment_id ON public.square_review_status USING btree (square_payment_id);


--
-- Name: idx_t4_compliance_corrections_employee_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_t4_compliance_corrections_employee_id ON public.t4_compliance_corrections USING btree (employee_id);


--
-- Name: idx_t4_compliance_corrections_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_t4_compliance_corrections_status ON public.t4_compliance_corrections USING btree (correction_status);


--
-- Name: idx_t4_compliance_corrections_tax_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_t4_compliance_corrections_tax_year ON public.t4_compliance_corrections USING btree (tax_year);


--
-- Name: idx_t4_confidence; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_t4_confidence ON public.employee_t4_summary USING btree (confidence_level);


--
-- Name: idx_t4_employee_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_t4_employee_year ON public.employee_t4_summary USING btree (employee_id, fiscal_year);


--
-- Name: idx_t4_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_t4_year ON public.employee_t4_summary USING btree (fiscal_year);


--
-- Name: idx_tax_periods_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tax_periods_year ON public.tax_periods USING btree (year);


--
-- Name: idx_tax_remittances_return; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tax_remittances_return ON public.tax_remittances USING btree (tax_return_id);


--
-- Name: idx_tax_returns_form; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tax_returns_form ON public.tax_returns USING btree (form_type);


--
-- Name: idx_tax_variances_return; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tax_variances_return ON public.tax_variances USING btree (tax_return_id);


--
-- Name: idx_time_off_requests_dates; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_time_off_requests_dates ON public.employee_time_off_requests USING btree (start_date, end_date);


--
-- Name: idx_time_off_requests_employee_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_time_off_requests_employee_id ON public.employee_time_off_requests USING btree (employee_id);


--
-- Name: idx_time_off_requests_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_time_off_requests_status ON public.employee_time_off_requests USING btree (status);


--
-- Name: idx_transaction_log_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transaction_log_created_at ON public.transaction_log USING btree (created_at);


--
-- Name: idx_transaction_log_fraud_case_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transaction_log_fraud_case_id ON public.transaction_log USING btree (fraud_case_id);


--
-- Name: idx_transfers_from_tx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transfers_from_tx ON public.banking_inter_account_transfers USING btree (from_transaction_id);


--
-- Name: idx_transfers_to_tx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transfers_to_tx ON public.banking_inter_account_transfers USING btree (to_transaction_id);


--
-- Name: idx_ugl_account; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ugl_account ON public.unified_general_ledger USING btree (account_code);


--
-- Name: idx_ugl_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ugl_date ON public.unified_general_ledger USING btree (transaction_date);


--
-- Name: idx_unified_charge_lookup_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_unified_charge_lookup_category ON public.unified_charge_lookup USING btree (category);


--
-- Name: idx_unified_charge_lookup_description; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_unified_charge_lookup_description ON public.unified_charge_lookup USING btree (standard_description);


--
-- Name: idx_unified_charge_lookup_patterns; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_unified_charge_lookup_patterns ON public.unified_charge_lookup USING gin (search_patterns);


--
-- Name: idx_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_email ON public.users USING btree (email);


--
-- Name: idx_users_username; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_username ON public.users USING btree (username);


--
-- Name: idx_vehicle_docs_expiry; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vehicle_docs_expiry ON public.vehicle_documents USING btree (expiry_date);


--
-- Name: idx_vehicle_docs_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vehicle_docs_status ON public.vehicle_documents USING btree (status);


--
-- Name: idx_vehicle_docs_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vehicle_docs_type ON public.vehicle_documents USING btree (doc_type_id);


--
-- Name: idx_vehicle_docs_vehicle; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vehicle_docs_vehicle ON public.vehicle_documents USING btree (vehicle_id);


--
-- Name: idx_vehicle_loan_payments_banking; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vehicle_loan_payments_banking ON public.vehicle_loan_payments USING btree (banking_transaction_id);


--
-- Name: idx_vehicle_loan_payments_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vehicle_loan_payments_date ON public.vehicle_loan_payments USING btree (payment_date);


--
-- Name: idx_vehicle_loan_payments_vehicle; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vehicle_loan_payments_vehicle ON public.vehicle_loan_payments USING btree (vehicle_id);


--
-- Name: idx_vehicle_loans_vehicle_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vehicle_loans_vehicle_id ON public.vehicle_loans USING btree (vehicle_id);


--
-- Name: idx_vehicle_pricing_charter_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vehicle_pricing_charter_type ON public.vehicle_pricing_defaults USING btree (charter_type_code);


--
-- Name: idx_vehicle_pricing_vehicle_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vehicle_pricing_vehicle_type ON public.vehicle_pricing_defaults USING btree (vehicle_type);


--
-- Name: idx_vehicles_fleet_position_active; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_vehicles_fleet_position_active ON public.vehicles USING btree (fleet_position) WHERE (is_active = true);


--
-- Name: idx_vehicles_number; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vehicles_number ON public.vehicles USING btree (vehicle_number);


--
-- Name: idx_vehicles_plate; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vehicles_plate ON public.vehicles USING btree (license_plate);


--
-- Name: idx_vendor_categories; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vendor_categories ON public.vendor_default_categories USING btree (vendor_canonical_name);


--
-- Name: idx_vendor_ledger_account_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vendor_ledger_account_date ON public.vendor_account_ledger USING btree (account_id, entry_date);


--
-- Name: idx_vendor_ledger_payment_method; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vendor_ledger_payment_method ON public.vendor_account_ledger USING btree (payment_method) WHERE (payment_method IS NOT NULL);


--
-- Name: idx_vendor_ledger_source; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vendor_ledger_source ON public.vendor_account_ledger USING btree (source_table, source_id);


--
-- Name: idx_vendor_mapping_canonical; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vendor_mapping_canonical ON public.vendor_name_mapping USING btree (canonical_vendor_name);


--
-- Name: idx_vendor_mapping_raw; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vendor_mapping_raw ON public.vendor_name_mapping USING btree (raw_vendor_name);


--
-- Name: idx_vendor_synonyms_account; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vendor_synonyms_account ON public.vendor_synonyms USING btree (account_id);


--
-- Name: idx_verification_audit_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_verification_audit_date ON public.verification_audit USING btree (verified_date);


--
-- Name: idx_verification_audit_table; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_verification_audit_table ON public.verification_audit USING btree (table_name, record_id);


--
-- Name: idx_verification_queue_priority; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_verification_queue_priority ON public.verification_queue USING btree (priority);


--
-- Name: idx_verification_queue_source; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_verification_queue_source ON public.verification_queue USING btree (source_table);


--
-- Name: idx_verification_queue_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_verification_queue_status ON public.verification_queue USING btree (status);


--
-- Name: idx_wage_allocation_pool_period; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_wage_allocation_pool_period ON public.wage_allocation_pool USING btree (allocation_period_start, allocation_period_end);


--
-- Name: idx_wage_allocation_pool_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_wage_allocation_pool_status ON public.wage_allocation_pool USING btree (pool_status);


--
-- Name: idx_wcb_debt_ledger_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_wcb_debt_ledger_date ON public.wcb_debt_ledger USING btree (transaction_date);


--
-- Name: idx_wcb_summary_driver; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_wcb_summary_driver ON public.wcb_summary USING btree (driver_id);


--
-- Name: idx_wcb_summary_year_month; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_wcb_summary_year_month ON public.wcb_summary USING btree (year, month);


--
-- Name: ix_email_events_src_from_subj_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_email_events_src_from_subj_date ON public.email_financial_events USING btree (source, from_email, subject, email_date);


--
-- Name: payment_matches_charter_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX payment_matches_charter_idx ON public.payment_matches USING btree (charter_id);


--
-- Name: payment_matches_deposit_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX payment_matches_deposit_idx ON public.payment_matches USING btree (deposit_key);


--
-- Name: posting_queue_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX posting_queue_status_idx ON public.posting_queue USING btree (status);


--
-- Name: square_raw_records_customer_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX square_raw_records_customer_idx ON public.square_raw_records USING btree (customer_id);


--
-- Name: square_raw_records_date_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX square_raw_records_date_idx ON public.square_raw_records USING btree (record_date);


--
-- Name: square_raw_records_id_uniq; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX square_raw_records_id_uniq ON public.square_raw_records USING btree (record_type, record_id) WHERE (record_id IS NOT NULL);


--
-- Name: square_raw_records_row_hash_uniq; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX square_raw_records_row_hash_uniq ON public.square_raw_records USING btree (record_type, row_hash);


--
-- Name: uniq_vendor_ledger_source; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uniq_vendor_ledger_source ON public.vendor_account_ledger USING btree (account_id, source_table, source_id);


--
-- Name: uniq_vendor_synonym; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uniq_vendor_synonym ON public.vendor_synonyms USING btree (upper((synonym)::text));


--
-- Name: ux_personal_expenses_source_txn; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_personal_expenses_source_txn ON public.personal_expenses USING btree (source_txn_key) WHERE (source_txn_key IS NOT NULL);


--
-- Name: square_monthly_fees_verification _RETURN; Type: RULE; Schema: public; Owner: -
--

CREATE OR REPLACE VIEW public.square_monthly_fees_verification AS
 SELECT p.payment_id,
    p.amount AS fee_amount,
    p.payment_date,
    p.reserve_number,
    count(r.receipt_id) AS receipt_count,
    sum(r.gross_amount) AS receipt_total,
    p.verified,
    COALESCE(p.square_fee_gl_code, 'PENDING'::character varying) AS gl_code,
        CASE
            WHEN ((p.payment_method)::text !~~ '%fee%'::text) THEN 'NOT_MARKED_FEE'::text
            WHEN (count(r.receipt_id) = 0) THEN 'NO_RECEIPT'::text
            WHEN p.verified THEN 'VERIFIED'::text
            ELSE 'NEEDS_VERIFICATION'::text
        END AS status
   FROM (public.payments p
     LEFT JOIN public.receipts r ON ((r.source_reference = (p.payment_id)::text)))
  WHERE (((p.payment_method)::text ~~ '%fee%'::text) OR (p.notes ~~ '%square%fee%'::text))
  GROUP BY p.payment_id, p.amount, p.payment_date, p.reserve_number, p.verified, p.square_fee_gl_code;


--
-- Name: v_banking_transactions_with_aliases _RETURN; Type: RULE; Schema: public; Owner: -
--

CREATE OR REPLACE VIEW public.v_banking_transactions_with_aliases AS
 SELECT bt.transaction_id,
    bt.account_number,
    bt.transaction_date,
    bt.posted_date,
    bt.description,
    bt.debit_amount,
    bt.credit_amount,
    bt.balance,
    bt.vendor_extracted,
    bt.vendor_truncated,
    bt.card_last4_detected,
    bt.category,
    bt.source_file,
    bt.import_batch,
    bt.created_at,
    bt.bank_id,
    bt.transaction_hash,
    bt.updated_at,
    bt.receipt_id,
    bt.source_hash,
    bt.reconciliation_status,
    bt.reconciled_receipt_id,
    bt.reconciled_payment_id,
    bt.reconciled_charter_id,
    bt.reconciliation_notes,
    bt.reconciled_at,
    bt.reconciled_by,
    array_agg(DISTINCT ana.statement_format) AS known_aliases
   FROM (public.banking_transactions bt
     LEFT JOIN public.account_number_aliases ana ON (((bt.account_number)::text = (ana.canonical_account_number)::text)))
  GROUP BY bt.transaction_id, bt.account_number, bt.transaction_date, bt.description, bt.debit_amount, bt.credit_amount, bt.balance, bt.posted_date, bt.vendor_extracted, bt.vendor_truncated, bt.card_last4_detected, bt.category, bt.source_file, bt.import_batch, bt.created_at, bt.source_hash, bt.reconciliation_status, bt.reconciled_receipt_id, bt.reconciled_payment_id, bt.reconciled_charter_id, bt.reconciliation_notes, bt.reconciled_at, bt.reconciled_by;


--
-- Name: charter_routes charter_routes_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER charter_routes_updated_at BEFORE UPDATE ON public.charter_routes FOR EACH ROW EXECUTE FUNCTION public.update_charter_routes_timestamp();


--
-- Name: receipts receipts_banking_link_consistency; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER receipts_banking_link_consistency AFTER INSERT OR UPDATE OF banking_transaction_id ON public.receipts FOR EACH ROW EXECUTE FUNCTION public.ensure_ledger_on_receipts_update();


--
-- Name: charter_charges round_charter_charges_amount; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER round_charter_charges_amount BEFORE INSERT OR UPDATE ON public.charter_charges FOR EACH ROW EXECUTE FUNCTION public.round_amounts();


--
-- Name: bank_accounts trg_bank_accounts_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_bank_accounts_updated_at BEFORE UPDATE ON public.bank_accounts FOR EACH ROW EXECUTE FUNCTION public.update_banking_updated_at();


--
-- Name: banking_transactions trg_banking_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_banking_updated_at BEFORE UPDATE ON public.banking_transactions FOR EACH ROW EXECUTE FUNCTION public.update_banking_updated_at();


--
-- Name: charters trg_charters_set_display_name; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_charters_set_display_name BEFORE INSERT OR UPDATE ON public.charters FOR EACH ROW EXECUTE FUNCTION public.trg_sync_charter_client_display_name();


--
-- Name: clients trg_clients_propagate_display_name; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_clients_propagate_display_name AFTER UPDATE OF client_name ON public.clients FOR EACH ROW EXECUTE FUNCTION public.trg_sync_charter_client_display_name();


--
-- Name: charters trg_mark_placeholder; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_mark_placeholder BEFORE INSERT OR UPDATE ON public.charters FOR EACH ROW EXECUTE FUNCTION public.mark_charter_placeholder();


--
-- Name: vehicle_mileage_log trg_update_vehicle_odometer; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_update_vehicle_odometer AFTER INSERT ON public.vehicle_mileage_log FOR EACH ROW EXECUTE FUNCTION public.update_vehicle_odometer();


--
-- Name: employees trigger_auto_driver_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trigger_auto_driver_code BEFORE INSERT OR UPDATE ON public.employees FOR EACH ROW EXECUTE FUNCTION public.auto_assign_driver_code();


--
-- Name: payments trigger_auto_payment_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trigger_auto_payment_code BEFORE INSERT OR UPDATE ON public.payments FOR EACH ROW EXECUTE FUNCTION public.auto_populate_payment_code();


--
-- Name: deferred_wage_transactions trigger_update_deferred_wage_balance; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trigger_update_deferred_wage_balance AFTER INSERT ON public.deferred_wage_transactions FOR EACH ROW EXECUTE FUNCTION public.update_deferred_wage_balance();


--
-- Name: cibc_business_cards update_cibc_cards_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_cibc_cards_updated_at BEFORE UPDATE ON public.cibc_business_cards FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: cibc_card_transactions update_cibc_transactions_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_cibc_transactions_updated_at BEFORE UPDATE ON public.cibc_card_transactions FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: employee_availability update_employee_availability_timestamp; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_employee_availability_timestamp BEFORE UPDATE ON public.employee_availability FOR EACH ROW EXECUTE FUNCTION public.update_timestamp();


--
-- Name: employee_expenses update_employee_expenses_timestamp; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_employee_expenses_timestamp BEFORE UPDATE ON public.employee_expenses FOR EACH ROW EXECUTE FUNCTION public.update_timestamp();


--
-- Name: employee_schedules update_employee_schedules_timestamp; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_employee_schedules_timestamp BEFORE UPDATE ON public.employee_schedules FOR EACH ROW EXECUTE FUNCTION public.update_timestamp();


--
-- Name: employee_work_classifications update_employee_work_classifications_timestamp; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_employee_work_classifications_timestamp BEFORE UPDATE ON public.employee_work_classifications FOR EACH ROW EXECUTE FUNCTION public.update_timestamp();


--
-- Name: fraud_cases update_fraud_cases_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_fraud_cases_updated_at BEFORE UPDATE ON public.fraud_cases FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: monthly_work_assignments update_monthly_work_assignments_timestamp; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_monthly_work_assignments_timestamp BEFORE UPDATE ON public.monthly_work_assignments FOR EACH ROW EXECUTE FUNCTION public.update_timestamp();


--
-- Name: personal_expenses update_personal_expenses_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_personal_expenses_updated_at BEFORE UPDATE ON public.personal_expenses FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: employee_time_off_requests update_time_off_requests_timestamp; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_time_off_requests_timestamp BEFORE UPDATE ON public.employee_time_off_requests FOR EACH ROW EXECUTE FUNCTION public.update_timestamp();


--
-- Name: accounting_entries accounting_entries_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounting_entries
    ADD CONSTRAINT accounting_entries_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id);


--
-- Name: accounting_periods accounting_periods_closed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounting_periods
    ADD CONSTRAINT accounting_periods_closed_by_fkey FOREIGN KEY (closed_by) REFERENCES public.employees(employee_id);


--
-- Name: asset_depreciation_schedule asset_depreciation_schedule_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset_depreciation_schedule
    ADD CONSTRAINT asset_depreciation_schedule_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(asset_id) ON DELETE CASCADE;


--
-- Name: asset_documentation asset_documentation_asset_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.asset_documentation
    ADD CONSTRAINT asset_documentation_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(asset_id) ON DELETE CASCADE;


--
-- Name: assets assets_purchase_receipt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assets
    ADD CONSTRAINT assets_purchase_receipt_id_fkey FOREIGN KEY (purchase_receipt_id) REFERENCES public.receipts(receipt_id);


--
-- Name: audit_log audit_log_changed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_changed_by_fkey FOREIGN KEY (changed_by) REFERENCES public.employees(employee_id);


--
-- Name: banking_transactions banking_transactions_receipt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.banking_transactions
    ADD CONSTRAINT banking_transactions_receipt_id_fkey FOREIGN KEY (receipt_id) REFERENCES public.receipts(receipt_id);


--
-- Name: beverage_cart beverage_cart_beverage_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverage_cart
    ADD CONSTRAINT beverage_cart_beverage_id_fkey FOREIGN KEY (beverage_id) REFERENCES public.beverages(beverage_id);


--
-- Name: beverage_order_items beverage_order_items_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverage_order_items
    ADD CONSTRAINT beverage_order_items_order_id_fkey FOREIGN KEY (order_id) REFERENCES public.beverage_orders(order_id) ON DELETE CASCADE;


--
-- Name: business_losses business_losses_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.business_losses
    ADD CONSTRAINT business_losses_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.employees(employee_id);


--
-- Name: cash_box_transactions cash_box_transactions_banking_transaction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cash_box_transactions
    ADD CONSTRAINT cash_box_transactions_banking_transaction_id_fkey FOREIGN KEY (banking_transaction_id) REFERENCES public.banking_transactions(transaction_id);


--
-- Name: cash_box_transactions cash_box_transactions_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cash_box_transactions
    ADD CONSTRAINT cash_box_transactions_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- Name: cash_box_transactions cash_box_transactions_receipt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cash_box_transactions
    ADD CONSTRAINT cash_box_transactions_receipt_id_fkey FOREIGN KEY (receipt_id) REFERENCES public.receipts(receipt_id);


--
-- Name: categorization_rules categorization_rules_category_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categorization_rules
    ADD CONSTRAINT categorization_rules_category_code_fkey FOREIGN KEY (category_code) REFERENCES public.account_categories(category_code);


--
-- Name: category_mappings category_mappings_new_account_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.category_mappings
    ADD CONSTRAINT category_mappings_new_account_code_fkey FOREIGN KEY (new_account_code) REFERENCES public.chart_of_accounts(account_code);


--
-- Name: category_to_account_map category_to_account_map_gl_account_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.category_to_account_map
    ADD CONSTRAINT category_to_account_map_gl_account_code_fkey FOREIGN KEY (gl_account_code) REFERENCES public.chart_of_accounts(account_code);


--
-- Name: charity_trade_charters charity_trade_charters_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charity_trade_charters
    ADD CONSTRAINT charity_trade_charters_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id);


--
-- Name: charter_beverage_items charter_beverage_items_beverage_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_beverage_items
    ADD CONSTRAINT charter_beverage_items_beverage_order_id_fkey FOREIGN KEY (beverage_order_id) REFERENCES public.charter_beverage_orders(beverage_order_id) ON DELETE CASCADE;


--
-- Name: charter_beverage_orders charter_beverage_orders_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_beverage_orders
    ADD CONSTRAINT charter_beverage_orders_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id);


--
-- Name: charter_beverages charter_beverages_beverage_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_beverages
    ADD CONSTRAINT charter_beverages_beverage_item_id_fkey FOREIGN KEY (beverage_item_id) REFERENCES public.beverage_products(item_id);


--
-- Name: charter_beverages charter_beverages_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_beverages
    ADD CONSTRAINT charter_beverages_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id) ON DELETE CASCADE;


--
-- Name: charter_charges charter_charges_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_charges
    ADD CONSTRAINT charter_charges_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id);


--
-- Name: charter_credit_ledger charter_credit_ledger_applied_to_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_credit_ledger
    ADD CONSTRAINT charter_credit_ledger_applied_to_charter_id_fkey FOREIGN KEY (applied_to_charter_id) REFERENCES public.charters(charter_id) ON DELETE SET NULL;


--
-- Name: charter_credit_ledger charter_credit_ledger_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_credit_ledger
    ADD CONSTRAINT charter_credit_ledger_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(client_id) ON DELETE CASCADE;


--
-- Name: charter_credit_ledger charter_credit_ledger_source_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_credit_ledger
    ADD CONSTRAINT charter_credit_ledger_source_charter_id_fkey FOREIGN KEY (source_charter_id) REFERENCES public.charters(charter_id) ON DELETE SET NULL;


--
-- Name: charter_gst_details_2010_2012 charter_gst_details_2010_2012_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_gst_details_2010_2012
    ADD CONSTRAINT charter_gst_details_2010_2012_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id);


--
-- Name: charter_incidents charter_incidents_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_incidents
    ADD CONSTRAINT charter_incidents_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id);


--
-- Name: charter_receipts charter_receipts_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_receipts
    ADD CONSTRAINT charter_receipts_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id);


--
-- Name: charter_receipts charter_receipts_vehicle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_receipts
    ADD CONSTRAINT charter_receipts_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(vehicle_id);


--
-- Name: charter_routes charter_routes_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_routes
    ADD CONSTRAINT charter_routes_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id) ON DELETE CASCADE;


--
-- Name: charter_time_updates charter_time_updates_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_time_updates
    ADD CONSTRAINT charter_time_updates_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id);


--
-- Name: charter_time_updates charter_time_updates_driver_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_time_updates
    ADD CONSTRAINT charter_time_updates_driver_id_fkey FOREIGN KEY (driver_id) REFERENCES public.employees(employee_id);


--
-- Name: charters charters_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charters
    ADD CONSTRAINT charters_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(client_id);


--
-- Name: charters_routing_times charters_routing_times_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charters_routing_times
    ADD CONSTRAINT charters_routing_times_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id);


--
-- Name: chauffeur_float_tracking chauffeur_float_tracking_banking_transaction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chauffeur_float_tracking
    ADD CONSTRAINT chauffeur_float_tracking_banking_transaction_id_fkey FOREIGN KEY (banking_transaction_id) REFERENCES public.banking_transactions(transaction_id);


--
-- Name: chauffeur_pay_entries chauffeur_pay_entries_chauffeur_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chauffeur_pay_entries
    ADD CONSTRAINT chauffeur_pay_entries_chauffeur_id_fkey FOREIGN KEY (chauffeur_id) REFERENCES public.employees(employee_id);


--
-- Name: chauffeur_pay_entries chauffeur_pay_entries_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chauffeur_pay_entries
    ADD CONSTRAINT chauffeur_pay_entries_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.employees(employee_id);


--
-- Name: cheque_register cheque_register_banking_transaction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cheque_register
    ADD CONSTRAINT cheque_register_banking_transaction_id_fkey FOREIGN KEY (banking_transaction_id) REFERENCES public.banking_transactions(transaction_id);


--
-- Name: cibc_auto_categorization_rules cibc_auto_categorization_rules_card_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cibc_auto_categorization_rules
    ADD CONSTRAINT cibc_auto_categorization_rules_card_id_fkey FOREIGN KEY (card_id) REFERENCES public.cibc_business_cards(card_id);


--
-- Name: cibc_business_cards cibc_business_cards_owner_equity_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cibc_business_cards
    ADD CONSTRAINT cibc_business_cards_owner_equity_account_id_fkey FOREIGN KEY (owner_equity_account_id) REFERENCES public.owner_equity_accounts(equity_account_id);


--
-- Name: cibc_card_transactions cibc_card_transactions_banking_transaction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cibc_card_transactions
    ADD CONSTRAINT cibc_card_transactions_banking_transaction_id_fkey FOREIGN KEY (banking_transaction_id) REFERENCES public.banking_transactions(transaction_id);


--
-- Name: cibc_card_transactions cibc_card_transactions_card_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cibc_card_transactions
    ADD CONSTRAINT cibc_card_transactions_card_id_fkey FOREIGN KEY (card_id) REFERENCES public.cibc_business_cards(card_id);


--
-- Name: clients clients_fraud_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clients
    ADD CONSTRAINT clients_fraud_case_id_fkey FOREIGN KEY (fraud_case_id) REFERENCES public.fraud_cases(case_id);


--
-- Name: cra_vehicle_events cra_vehicle_events_vehicle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cra_vehicle_events
    ADD CONSTRAINT cra_vehicle_events_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(vehicle_id);


--
-- Name: customer_comms_log customer_comms_log_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_comms_log
    ADD CONSTRAINT customer_comms_log_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id);


--
-- Name: customer_feedback customer_feedback_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_feedback
    ADD CONSTRAINT customer_feedback_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id);


--
-- Name: customer_name_mapping customer_name_mapping_alms_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customer_name_mapping
    ADD CONSTRAINT customer_name_mapping_alms_client_id_fkey FOREIGN KEY (alms_client_id) REFERENCES public.clients(client_id);


--
-- Name: cvip_compliance_alerts cvip_compliance_alerts_vehicle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cvip_compliance_alerts
    ADD CONSTRAINT cvip_compliance_alerts_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(vehicle_id);


--
-- Name: cvip_defects cvip_defects_inspection_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cvip_defects
    ADD CONSTRAINT cvip_defects_inspection_id_fkey FOREIGN KEY (inspection_id) REFERENCES public.cvip_inspections(inspection_id);


--
-- Name: cvip_inspections cvip_inspections_vehicle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cvip_inspections
    ADD CONSTRAINT cvip_inspections_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(vehicle_id);


--
-- Name: deferred_wage_accounts deferred_wage_accounts_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deferred_wage_accounts
    ADD CONSTRAINT deferred_wage_accounts_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.employees(employee_id);


--
-- Name: deferred_wage_accounts deferred_wage_accounts_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deferred_wage_accounts
    ADD CONSTRAINT deferred_wage_accounts_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- Name: deferred_wage_transactions deferred_wage_transactions_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deferred_wage_transactions
    ADD CONSTRAINT deferred_wage_transactions_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.deferred_wage_accounts(account_id);


--
-- Name: deferred_wage_transactions deferred_wage_transactions_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deferred_wage_transactions
    ADD CONSTRAINT deferred_wage_transactions_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.employees(employee_id);


--
-- Name: deferred_wage_transactions deferred_wage_transactions_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deferred_wage_transactions
    ADD CONSTRAINT deferred_wage_transactions_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id);


--
-- Name: deferred_wage_transactions deferred_wage_transactions_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deferred_wage_transactions
    ADD CONSTRAINT deferred_wage_transactions_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- Name: deferred_wage_transactions deferred_wage_transactions_processed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deferred_wage_transactions
    ADD CONSTRAINT deferred_wage_transactions_processed_by_fkey FOREIGN KEY (processed_by) REFERENCES public.employees(employee_id);


--
-- Name: direct_tips_history direct_tips_history_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.direct_tips_history
    ADD CONSTRAINT direct_tips_history_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id);


--
-- Name: driver_app_actions driver_app_actions_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_app_actions
    ADD CONSTRAINT driver_app_actions_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id);


--
-- Name: driver_app_actions driver_app_actions_driver_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_app_actions
    ADD CONSTRAINT driver_app_actions_driver_id_fkey FOREIGN KEY (driver_id) REFERENCES public.employees(employee_id);


--
-- Name: driver_app_sessions driver_app_sessions_driver_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_app_sessions
    ADD CONSTRAINT driver_app_sessions_driver_id_fkey FOREIGN KEY (driver_id) REFERENCES public.employees(employee_id);


--
-- Name: driver_comms_log driver_comms_log_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_comms_log
    ADD CONSTRAINT driver_comms_log_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- Name: driver_disciplinary_actions driver_disciplinary_actions_driver_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_disciplinary_actions
    ADD CONSTRAINT driver_disciplinary_actions_driver_id_fkey FOREIGN KEY (driver_id) REFERENCES public.employees(employee_id);


--
-- Name: driver_documents driver_documents_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_documents
    ADD CONSTRAINT driver_documents_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- Name: driver_documents driver_documents_uploaded_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_documents
    ADD CONSTRAINT driver_documents_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES public.employees(employee_id);


--
-- Name: driver_employee_mapping driver_employee_mapping_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_employee_mapping
    ADD CONSTRAINT driver_employee_mapping_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- Name: driver_floats driver_floats_cash_box_transaction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_floats
    ADD CONSTRAINT driver_floats_cash_box_transaction_id_fkey FOREIGN KEY (cash_box_transaction_id) REFERENCES public.cash_box_transactions(transaction_id);


--
-- Name: driver_floats driver_floats_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_floats
    ADD CONSTRAINT driver_floats_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- Name: driver_location_history driver_location_history_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_location_history
    ADD CONSTRAINT driver_location_history_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id);


--
-- Name: driver_location_history driver_location_history_driver_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_location_history
    ADD CONSTRAINT driver_location_history_driver_id_fkey FOREIGN KEY (driver_id) REFERENCES public.employees(employee_id);


--
-- Name: driver_pay_entries driver_pay_entries_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_pay_entries
    ADD CONSTRAINT driver_pay_entries_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.employees(employee_id);


--
-- Name: driver_pay_entries driver_pay_entries_driver_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_pay_entries
    ADD CONSTRAINT driver_pay_entries_driver_id_fkey FOREIGN KEY (driver_id) REFERENCES public.employees(employee_id);


--
-- Name: employee_availability employee_availability_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_availability
    ADD CONSTRAINT employee_availability_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- Name: employee_expenses employee_expenses_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_expenses
    ADD CONSTRAINT employee_expenses_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.employees(employee_id);


--
-- Name: employee_expenses employee_expenses_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_expenses
    ADD CONSTRAINT employee_expenses_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- Name: employee_expenses employee_expenses_receipt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_expenses
    ADD CONSTRAINT employee_expenses_receipt_id_fkey FOREIGN KEY (receipt_id) REFERENCES public.receipts(receipt_id);


--
-- Name: employee_expenses employee_expenses_submitted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_expenses
    ADD CONSTRAINT employee_expenses_submitted_by_fkey FOREIGN KEY (submitted_by) REFERENCES public.employees(employee_id);


--
-- Name: employee_expenses employee_expenses_work_assignment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_expenses
    ADD CONSTRAINT employee_expenses_work_assignment_id_fkey FOREIGN KEY (work_assignment_id) REFERENCES public.monthly_work_assignments(assignment_id);


--
-- Name: employee_pay_entries employee_pay_entries_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_pay_entries
    ADD CONSTRAINT employee_pay_entries_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.employees(employee_id);


--
-- Name: employee_pay_entries employee_pay_entries_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_pay_entries
    ADD CONSTRAINT employee_pay_entries_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- Name: employee_pay_master employee_pay_master_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_pay_master
    ADD CONSTRAINT employee_pay_master_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- Name: employee_pay_master employee_pay_master_pay_period_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_pay_master
    ADD CONSTRAINT employee_pay_master_pay_period_id_fkey FOREIGN KEY (pay_period_id) REFERENCES public.pay_periods(pay_period_id);


--
-- Name: employee_roe_records employee_roe_records_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_roe_records
    ADD CONSTRAINT employee_roe_records_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- Name: employee_schedules employee_schedules_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_schedules
    ADD CONSTRAINT employee_schedules_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.employees(employee_id);


--
-- Name: employee_schedules employee_schedules_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_schedules
    ADD CONSTRAINT employee_schedules_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.employees(employee_id);


--
-- Name: employee_schedules employee_schedules_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_schedules
    ADD CONSTRAINT employee_schedules_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- Name: employee_t4_records employee_t4_records_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_t4_records
    ADD CONSTRAINT employee_t4_records_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- Name: employee_t4_summary employee_t4_summary_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_t4_summary
    ADD CONSTRAINT employee_t4_summary_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- Name: employee_time_off_requests employee_time_off_requests_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_time_off_requests
    ADD CONSTRAINT employee_time_off_requests_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- Name: employee_time_off_requests employee_time_off_requests_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_time_off_requests
    ADD CONSTRAINT employee_time_off_requests_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.employees(employee_id);


--
-- Name: employee_work_classifications employee_work_classifications_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employee_work_classifications
    ADD CONSTRAINT employee_work_classifications_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- Name: etransfer_banking_reconciliation etransfer_banking_reconciliation_etransfer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.etransfer_banking_reconciliation
    ADD CONSTRAINT etransfer_banking_reconciliation_etransfer_id_fkey FOREIGN KEY (etransfer_id) REFERENCES public.etransfers_processed(id) ON DELETE CASCADE;


--
-- Name: etransfer_banking_reconciliation etransfer_banking_reconciliation_transaction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.etransfer_banking_reconciliation
    ADD CONSTRAINT etransfer_banking_reconciliation_transaction_id_fkey FOREIGN KEY (transaction_id) REFERENCES public.banking_transactions(transaction_id);


--
-- Name: etransfer_transactions etransfer_transactions_banking_transaction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.etransfer_transactions
    ADD CONSTRAINT etransfer_transactions_banking_transaction_id_fkey FOREIGN KEY (banking_transaction_id) REFERENCES public.banking_transactions(transaction_id);


--
-- Name: etransfer_transactions etransfer_transactions_email_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.etransfer_transactions
    ADD CONSTRAINT etransfer_transactions_email_event_id_fkey FOREIGN KEY (email_event_id) REFERENCES public.email_financial_events(id);


--
-- Name: excluded_charters excluded_charters_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.excluded_charters
    ADD CONSTRAINT excluded_charters_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id);


--
-- Name: financial_adjustments financial_adjustments_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_adjustments
    ADD CONSTRAINT financial_adjustments_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(client_id);


--
-- Name: financial_adjustments financial_adjustments_fraud_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_adjustments
    ADD CONSTRAINT financial_adjustments_fraud_case_id_fkey FOREIGN KEY (fraud_case_id) REFERENCES public.fraud_cases(case_id);


--
-- Name: financial_statement_sections financial_statement_sections_parent_section_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_statement_sections
    ADD CONSTRAINT financial_statement_sections_parent_section_id_fkey FOREIGN KEY (parent_section_id) REFERENCES public.financial_statement_sections(section_id);


--
-- Name: financial_statement_sections financial_statement_sections_statement_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.financial_statement_sections
    ADD CONSTRAINT financial_statement_sections_statement_type_id_fkey FOREIGN KEY (statement_type_id) REFERENCES public.financial_statement_types(statement_type_id);


--
-- Name: banking_transactions fk_account; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.banking_transactions
    ADD CONSTRAINT fk_account FOREIGN KEY (account_number) REFERENCES public.cibc_accounts(account_number);


--
-- Name: vehicle_loan_payments fk_banking_txn; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_loan_payments
    ADD CONSTRAINT fk_banking_txn FOREIGN KEY (banking_transaction_id) REFERENCES public.banking_transactions(transaction_id) ON DELETE SET NULL;


--
-- Name: square_capital_loans fk_banking_txn; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_capital_loans
    ADD CONSTRAINT fk_banking_txn FOREIGN KEY (banking_transaction_id) REFERENCES public.banking_transactions(transaction_id) ON DELETE SET NULL;


--
-- Name: charter_charges fk_charter_charges_reserve_number; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_charges
    ADD CONSTRAINT fk_charter_charges_reserve_number FOREIGN KEY (reserve_number) REFERENCES public.charters(reserve_number) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: charter_payments fk_charter_payments_payment_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charter_payments
    ADD CONSTRAINT fk_charter_payments_payment_id FOREIGN KEY (payment_id) REFERENCES public.payments(payment_id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: charters fk_charters_employee_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charters
    ADD CONSTRAINT fk_charters_employee_id FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE SET NULL;


--
-- Name: charters fk_charters_vehicle_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.charters
    ADD CONSTRAINT fk_charters_vehicle_id FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(vehicle_id) ON DELETE SET NULL;


--
-- Name: driver_payroll fk_driver_payroll_employee_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.driver_payroll
    ADD CONSTRAINT fk_driver_payroll_employee_id FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE SET NULL;


--
-- Name: payments fk_payments_reserve_number; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT fk_payments_reserve_number FOREIGN KEY (reserve_number) REFERENCES public.charters(reserve_number) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: receipts fk_receipts_reserve_number; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT fk_receipts_reserve_number FOREIGN KEY (reserve_number) REFERENCES public.charters(reserve_number) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: receipts fk_receipts_vehicle_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT fk_receipts_vehicle_id FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(vehicle_id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: float_activity_log float_activity_log_float_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.float_activity_log
    ADD CONSTRAINT float_activity_log_float_id_fkey FOREIGN KEY (float_id) REFERENCES public.chauffeur_float_tracking(id);


--
-- Name: fraud_cases fraud_cases_source_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fraud_cases
    ADD CONSTRAINT fraud_cases_source_client_id_fkey FOREIGN KEY (source_client_id) REFERENCES public.clients(client_id);


--
-- Name: fraud_cases fraud_cases_target_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fraud_cases
    ADD CONSTRAINT fraud_cases_target_client_id_fkey FOREIGN KEY (target_client_id) REFERENCES public.clients(client_id);


--
-- Name: fuel_expenses fuel_expenses_expense_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fuel_expenses
    ADD CONSTRAINT fuel_expenses_expense_id_fkey FOREIGN KEY (expense_id) REFERENCES public.personal_expenses(id) ON DELETE CASCADE;


--
-- Name: general_ledger_headers general_ledger_headers_fraud_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.general_ledger_headers
    ADD CONSTRAINT general_ledger_headers_fraud_case_id_fkey FOREIGN KEY (fraud_case_id) REFERENCES public.fraud_cases(case_id);


--
-- Name: general_ledger_lines general_ledger_lines_fraud_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.general_ledger_lines
    ADD CONSTRAINT general_ledger_lines_fraud_case_id_fkey FOREIGN KEY (fraud_case_id) REFERENCES public.fraud_cases(case_id);


--
-- Name: general_ledger_lines general_ledger_lines_header_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.general_ledger_lines
    ADD CONSTRAINT general_ledger_lines_header_id_fkey FOREIGN KEY (header_id) REFERENCES public.general_ledger_headers(header_id) ON DELETE CASCADE;


--
-- Name: hos_14day_summary hos_14day_summary_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hos_14day_summary
    ADD CONSTRAINT hos_14day_summary_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- Name: hos_log hos_log_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hos_log
    ADD CONSTRAINT hos_log_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id);


--
-- Name: hos_log hos_log_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hos_log
    ADD CONSTRAINT hos_log_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- Name: incident_costs incident_costs_incident_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.incident_costs
    ADD CONSTRAINT incident_costs_incident_id_fkey FOREIGN KEY (incident_id) REFERENCES public.incidents(incident_id);


--
-- Name: income_ledger income_ledger_payment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.income_ledger
    ADD CONSTRAINT income_ledger_payment_id_fkey FOREIGN KEY (payment_id) REFERENCES public.payments(payment_id);


--
-- Name: invoice_line_items invoice_line_items_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_line_items
    ADD CONSTRAINT invoice_line_items_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES public.invoices(invoice_id) ON DELETE CASCADE;


--
-- Name: invoice_tracking invoice_tracking_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_tracking
    ADD CONSTRAINT invoice_tracking_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.financial_documents(id);


--
-- Name: maintenance_alerts maintenance_alerts_vehicle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maintenance_alerts
    ADD CONSTRAINT maintenance_alerts_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(vehicle_id);


--
-- Name: maintenance_records maintenance_records_activity_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maintenance_records
    ADD CONSTRAINT maintenance_records_activity_type_id_fkey FOREIGN KEY (activity_type_id) REFERENCES public.maintenance_activity_types(activity_type_id);


--
-- Name: maintenance_records maintenance_records_receipt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maintenance_records
    ADD CONSTRAINT maintenance_records_receipt_id_fkey FOREIGN KEY (receipt_id) REFERENCES public.receipts(receipt_id);


--
-- Name: maintenance_records maintenance_records_vehicle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maintenance_records
    ADD CONSTRAINT maintenance_records_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(vehicle_id);


--
-- Name: maintenance_schedules_auto maintenance_schedules_auto_vehicle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maintenance_schedules_auto
    ADD CONSTRAINT maintenance_schedules_auto_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(vehicle_id);


--
-- Name: major_events major_events_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.major_events
    ADD CONSTRAINT major_events_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.employees(employee_id);


--
-- Name: monthly_work_assignments monthly_work_assignments_assigned_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.monthly_work_assignments
    ADD CONSTRAINT monthly_work_assignments_assigned_by_fkey FOREIGN KEY (assigned_by) REFERENCES public.employees(employee_id);


--
-- Name: monthly_work_assignments monthly_work_assignments_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.monthly_work_assignments
    ADD CONSTRAINT monthly_work_assignments_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- Name: owner_expense_transactions owner_expense_transactions_banking_transaction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.owner_expense_transactions
    ADD CONSTRAINT owner_expense_transactions_banking_transaction_id_fkey FOREIGN KEY (banking_transaction_id) REFERENCES public.banking_transactions(transaction_id);


--
-- Name: owner_expense_transactions owner_expense_transactions_equity_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.owner_expense_transactions
    ADD CONSTRAINT owner_expense_transactions_equity_account_id_fkey FOREIGN KEY (equity_account_id) REFERENCES public.owner_equity_accounts(equity_account_id);


--
-- Name: payday_loan_payments payday_loan_payments_loan_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payday_loan_payments
    ADD CONSTRAINT payday_loan_payments_loan_id_fkey FOREIGN KEY (loan_id) REFERENCES public.payday_loans(id) ON DELETE CASCADE;


--
-- Name: payment_matches payment_matches_deposit_key_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_matches
    ADD CONSTRAINT payment_matches_deposit_key_fkey FOREIGN KEY (deposit_key) REFERENCES public.deposit_records(deposit_key);


--
-- Name: payroll_adjustments payroll_adjustments_driver_payroll_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_adjustments
    ADD CONSTRAINT payroll_adjustments_driver_payroll_id_fkey FOREIGN KEY (driver_payroll_id) REFERENCES public.driver_payroll(id) ON DELETE RESTRICT;


--
-- Name: pre_inspection_issues pre_inspection_issues_inspection_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pre_inspection_issues
    ADD CONSTRAINT pre_inspection_issues_inspection_id_fkey FOREIGN KEY (inspection_id) REFERENCES public.vehicle_pre_inspections(inspection_id);


--
-- Name: receipt_banking_links receipt_banking_links_linked_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_banking_links
    ADD CONSTRAINT receipt_banking_links_linked_by_fkey FOREIGN KEY (linked_by) REFERENCES public.employees(employee_id);


--
-- Name: receipt_banking_links receipt_banking_links_receipt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_banking_links
    ADD CONSTRAINT receipt_banking_links_receipt_id_fkey FOREIGN KEY (receipt_id) REFERENCES public.receipts(receipt_id) ON DELETE CASCADE;


--
-- Name: receipt_banking_links receipt_banking_links_transaction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_banking_links
    ADD CONSTRAINT receipt_banking_links_transaction_id_fkey FOREIGN KEY (transaction_id) REFERENCES public.banking_transactions(transaction_id);


--
-- Name: receipt_cashbox_links receipt_cashbox_links_confirmed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_cashbox_links
    ADD CONSTRAINT receipt_cashbox_links_confirmed_by_fkey FOREIGN KEY (confirmed_by) REFERENCES public.employees(employee_id);


--
-- Name: receipt_cashbox_links receipt_cashbox_links_driver_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_cashbox_links
    ADD CONSTRAINT receipt_cashbox_links_driver_id_fkey FOREIGN KEY (driver_id) REFERENCES public.employees(employee_id);


--
-- Name: receipt_cashbox_links receipt_cashbox_links_receipt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_cashbox_links
    ADD CONSTRAINT receipt_cashbox_links_receipt_id_fkey FOREIGN KEY (receipt_id) REFERENCES public.receipts(receipt_id) ON DELETE CASCADE;


--
-- Name: receipt_deliveries receipt_deliveries_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_deliveries
    ADD CONSTRAINT receipt_deliveries_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id);


--
-- Name: receipt_line_items receipt_line_items_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_line_items
    ADD CONSTRAINT receipt_line_items_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- Name: receipt_line_items receipt_line_items_receipt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_line_items
    ADD CONSTRAINT receipt_line_items_receipt_id_fkey FOREIGN KEY (receipt_id) REFERENCES public.receipts(receipt_id) ON DELETE CASCADE;


--
-- Name: receipt_line_items receipt_line_items_vehicle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_line_items
    ADD CONSTRAINT receipt_line_items_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(vehicle_id);


--
-- Name: receipts receipts_banking_transaction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT receipts_banking_transaction_id_fkey FOREIGN KEY (banking_transaction_id) REFERENCES public.banking_transactions(transaction_id) ON DELETE SET NULL;


--
-- Name: receipts receipts_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT receipts_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id);


--
-- Name: receipts receipts_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT receipts_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- Name: receipts receipts_vendor_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT receipts_vendor_account_id_fkey FOREIGN KEY (vendor_account_id) REFERENCES public.vendor_accounts(account_id) ON DELETE SET NULL;


--
-- Name: rent_debt_ledger rent_debt_ledger_recurring_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rent_debt_ledger
    ADD CONSTRAINT rent_debt_ledger_recurring_invoice_id_fkey FOREIGN KEY (recurring_invoice_id) REFERENCES public.recurring_invoices(id);


--
-- Name: security_audit security_audit_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_audit
    ADD CONSTRAINT security_audit_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id);


--
-- Name: square_api_audit square_api_audit_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_api_audit
    ADD CONSTRAINT square_api_audit_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id) ON DELETE SET NULL;


--
-- Name: square_api_audit square_api_audit_payment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_api_audit
    ADD CONSTRAINT square_api_audit_payment_id_fkey FOREIGN KEY (payment_id) REFERENCES public.payments(payment_id) ON DELETE SET NULL;


--
-- Name: square_etransfer_reconciliation square_etransfer_reconciliation_banking_transaction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_etransfer_reconciliation
    ADD CONSTRAINT square_etransfer_reconciliation_banking_transaction_id_fkey FOREIGN KEY (banking_transaction_id) REFERENCES public.banking_transactions(transaction_id);


--
-- Name: square_etransfer_reconciliation square_etransfer_reconciliation_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_etransfer_reconciliation
    ADD CONSTRAINT square_etransfer_reconciliation_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id);


--
-- Name: square_etransfer_reconciliation square_etransfer_reconciliation_square_payment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_etransfer_reconciliation
    ADD CONSTRAINT square_etransfer_reconciliation_square_payment_id_fkey FOREIGN KEY (square_payment_id) REFERENCES public.payments(payment_id);


--
-- Name: square_raw_records square_raw_records_import_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_raw_records
    ADD CONSTRAINT square_raw_records_import_id_fkey FOREIGN KEY (import_id) REFERENCES public.square_raw_imports(import_id) ON DELETE CASCADE;


--
-- Name: t4_compliance_corrections t4_compliance_corrections_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.t4_compliance_corrections
    ADD CONSTRAINT t4_compliance_corrections_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- Name: t4_compliance_corrections t4_compliance_corrections_prepared_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.t4_compliance_corrections
    ADD CONSTRAINT t4_compliance_corrections_prepared_by_fkey FOREIGN KEY (prepared_by) REFERENCES public.employees(employee_id);


--
-- Name: tax_remittances tax_remittances_tax_return_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_remittances
    ADD CONSTRAINT tax_remittances_tax_return_id_fkey FOREIGN KEY (tax_return_id) REFERENCES public.tax_returns(id) ON DELETE CASCADE;


--
-- Name: tax_returns tax_returns_period_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_returns
    ADD CONSTRAINT tax_returns_period_id_fkey FOREIGN KEY (period_id) REFERENCES public.tax_periods(id) ON DELETE CASCADE;


--
-- Name: tax_variances tax_variances_tax_return_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tax_variances
    ADD CONSTRAINT tax_variances_tax_return_id_fkey FOREIGN KEY (tax_return_id) REFERENCES public.tax_returns(id) ON DELETE CASCADE;


--
-- Name: training_checklist_items training_checklist_items_program_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.training_checklist_items
    ADD CONSTRAINT training_checklist_items_program_id_fkey FOREIGN KEY (program_id) REFERENCES public.training_programs(program_id) ON DELETE CASCADE;


--
-- Name: transaction_log transaction_log_fraud_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transaction_log
    ADD CONSTRAINT transaction_log_fraud_case_id_fkey FOREIGN KEY (fraud_case_id) REFERENCES public.fraud_cases(case_id);


--
-- Name: transaction_log transaction_log_source_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transaction_log
    ADD CONSTRAINT transaction_log_source_client_id_fkey FOREIGN KEY (source_client_id) REFERENCES public.clients(client_id);


--
-- Name: transaction_log transaction_log_target_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transaction_log
    ADD CONSTRAINT transaction_log_target_client_id_fkey FOREIGN KEY (target_client_id) REFERENCES public.clients(client_id);


--
-- Name: transaction_subcategories transaction_subcategories_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transaction_subcategories
    ADD CONSTRAINT transaction_subcategories_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.transaction_categories(id);


--
-- Name: vehicle_documents vehicle_documents_doc_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_documents
    ADD CONSTRAINT vehicle_documents_doc_type_id_fkey FOREIGN KEY (doc_type_id) REFERENCES public.vehicle_document_types(doc_type_id);


--
-- Name: vehicle_documents vehicle_documents_vehicle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_documents
    ADD CONSTRAINT vehicle_documents_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(vehicle_id);


--
-- Name: vehicle_financing vehicle_financing_vehicle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_financing
    ADD CONSTRAINT vehicle_financing_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(vehicle_id);


--
-- Name: vehicle_fuel_log vehicle_fuel_log_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_fuel_log
    ADD CONSTRAINT vehicle_fuel_log_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id);


--
-- Name: vehicle_insurance vehicle_insurance_vehicle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_insurance
    ADD CONSTRAINT vehicle_insurance_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(vehicle_id);


--
-- Name: vehicle_mileage_log vehicle_mileage_log_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_mileage_log
    ADD CONSTRAINT vehicle_mileage_log_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id);


--
-- Name: vehicle_mileage_log vehicle_mileage_log_vehicle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_mileage_log
    ADD CONSTRAINT vehicle_mileage_log_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(vehicle_id);


--
-- Name: vehicle_pre_inspections vehicle_pre_inspections_charter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_pre_inspections
    ADD CONSTRAINT vehicle_pre_inspections_charter_id_fkey FOREIGN KEY (charter_id) REFERENCES public.charters(charter_id);


--
-- Name: vehicle_pre_inspections vehicle_pre_inspections_driver_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_pre_inspections
    ADD CONSTRAINT vehicle_pre_inspections_driver_id_fkey FOREIGN KEY (driver_id) REFERENCES public.employees(employee_id);


--
-- Name: vehicle_pre_inspections vehicle_pre_inspections_previous_inspection_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_pre_inspections
    ADD CONSTRAINT vehicle_pre_inspections_previous_inspection_id_fkey FOREIGN KEY (previous_inspection_id) REFERENCES public.vehicle_pre_inspections(inspection_id);


--
-- Name: vehicle_pre_inspections vehicle_pre_inspections_vehicle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_pre_inspections
    ADD CONSTRAINT vehicle_pre_inspections_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(vehicle_id);


--
-- Name: vehicle_purchases vehicle_purchases_vehicle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_purchases
    ADD CONSTRAINT vehicle_purchases_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(vehicle_id);


--
-- Name: vehicle_repossessions vehicle_repossessions_vehicle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_repossessions
    ADD CONSTRAINT vehicle_repossessions_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(vehicle_id);


--
-- Name: vehicle_sales vehicle_sales_vehicle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_sales
    ADD CONSTRAINT vehicle_sales_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(vehicle_id);


--
-- Name: vehicle_writeoffs vehicle_writeoffs_vehicle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicle_writeoffs
    ADD CONSTRAINT vehicle_writeoffs_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(vehicle_id);


--
-- Name: vendor_account_ledger vendor_account_ledger_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_account_ledger
    ADD CONSTRAINT vendor_account_ledger_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.vendor_accounts(account_id) ON DELETE CASCADE;


--
-- Name: vendor_synonyms vendor_synonyms_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vendor_synonyms
    ADD CONSTRAINT vendor_synonyms_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.vendor_accounts(account_id) ON DELETE CASCADE;


--
-- Name: wage_allocation_pool wage_allocation_pool_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wage_allocation_pool
    ADD CONSTRAINT wage_allocation_pool_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.employees(employee_id);


--
-- Name: wcb_debt_ledger wcb_debt_ledger_wcb_charge_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wcb_debt_ledger
    ADD CONSTRAINT wcb_debt_ledger_wcb_charge_id_fkey FOREIGN KEY (wcb_charge_id) REFERENCES public.wcb_recurring_charges(id);


--
-- PostgreSQL database dump complete
--

\unrestrict HL9bKEBXy0bTFb9nhfMx6knK8nIwQm2qn16chHTdsaYclO3eby5yL5kHzVHLan1

