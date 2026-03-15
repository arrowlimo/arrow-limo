// AUTO-GENERATED TypeScript interfaces from database schema
// Generated: 2026-02-05T16:59:31.283803
// DO NOT EDIT MANUALLY - regenerate using generate_field_mapping.py

export interface BankingReceiptMatchingLedger {
  id: number;  // integer
  banking_transaction_id: number;  // bigint
  receipt_id?: number;  // bigint
  match_date?: string;  // timestamp without time zone
  match_type?: string;  // character varying(50)
  match_status?: string;  // character varying(20)
  match_confidence?: string;  // character varying(20)
  notes?: string;  // text
  created_by?: string;  // character varying(50)
  amount_allocated?: number;  // numeric
  allocation_date?: string;  // timestamp without time zone
  allocation_type?: string;  // character varying(50)
}

export interface BeverageOrders {
  order_id: number;  // integer
  reserve_number: string;  // character varying(32)
  order_date: string;  // timestamp without time zone
  subtotal: number;  // numeric
  gst: number;  // numeric
  total: number;  // numeric
  status?: string;  // text
}

export interface ChartOfAccounts {
  account_code: string;  // character varying(10)
  parent_account?: string;  // character varying(10)
  account_name: string;  // character varying(200)
  account_type: string;  // character varying(50)
  description?: string;  // text
  is_active?: boolean;  // boolean
  created_at?: string;  // timestamp without time zone
  qb_account_type?: string;  // character varying(50)
  account_level?: number;  // integer
  is_header_account?: boolean;  // boolean
  normal_balance?: string;  // character varying(10)
  current_balance?: number;  // numeric
  bank_account_number?: string;  // text
  updated_at?: string;  // timestamp without time zone
}

export interface Charters {
  charter_id: number;  // integer
  reserve_number: string;  // character varying(50)
  client_id?: number;  // integer
  charter_date?: string;  // date
  pickup_time?: string;  // time without time zone
  pickup_address?: string;  // text
  dropoff_address?: string;  // text
  passenger_count?: number;  // integer
  rate?: number;  // numeric
  balance?: number;  // numeric
  payment_totals?: number;  // numeric
  status?: string;  // character varying(50)
  created_at?: string;  // timestamp without time zone
  updated_at?: string;  // timestamp without time zone
  driver_notes?: string;  // text
  client_notes?: string;  // text
  booking_notes?: string;  // text
  total_amount_due?: number;  // numeric
  dispatcher_approved?: boolean;  // boolean
  driver_base_pay?: number;  // numeric
  driver_gratuity?: number;  // numeric
  driver_total_expense?: number;  // numeric
  expense_calculated_at?: string;  // timestamp without time zone
  odometer_start?: number;  // numeric
  odometer_end?: number;  // numeric
  total_kms?: number;  // numeric
  vehicle_notes?: string;  // text
  is_placeholder: boolean;  // boolean
  default_hourly_price?: number;  // numeric
  package_rate?: number;  // numeric
  extra_time_rate?: number;  // numeric
  daily_rate?: number;  // numeric
  airport_pickup_price?: number;  // numeric
  employee_id?: number;  // integer
  vehicle_id?: number;  // integer
  client_display_name?: string;  // text
  nrd_received?: boolean;  // boolean
  nrd_amount?: number;  // numeric
  nrd_method?: string;  // character varying
  is_out_of_town?: boolean;  // boolean
  fuel_litres?: number;  // numeric
  float_received?: number;  // numeric
  float_reimbursement_needed?: number;  // numeric
  calendar_color?: string;  // character varying(20)
  separate_customer_printout?: boolean;  // boolean
  charter_type?: string;  // character varying
  quoted_hours?: number;  // numeric
  standby_rate?: number;  // numeric
  split_run_start_time?: number;  // numeric
  split_run_time?: number;  // numeric
  calendar_sync_status?: string;  // character varying
  outlook_entry_id?: string;  // character varying
  calendar_notes?: string;  // text
  record_type?: any;  // USER-DEFINED
  version?: number;  // integer
  do_time?: string;  // time without time zone
  cart_order_list?: string;  // text
  fuel_price?: number;  // numeric
  fuel_gst?: number;  // numeric
  locked: boolean;  // boolean
}

export interface Clients {
  client_id: number;  // integer
  account_number: string;  // character varying(50)
  company_name?: string;  // character varying(255)
  primary_phone?: string;  // character varying(50)
  email?: string;  // character varying(255)
  address_line1?: string;  // character varying(255)
  city?: string;  // character varying(100)
  state?: string;  // character varying(50)
  zip_code?: string;  // character varying(20)
  balance?: number;  // numeric
  credit_limit?: number;  // numeric
  discount_percentage?: number;  // numeric
  discount_flat?: number;  // numeric
  gratuity_percentage?: number;  // numeric
  interest_rate?: number;  // numeric
  grace_days?: number;  // integer
  is_inactive?: boolean;  // boolean
  status?: string;  // character varying(20)
  created_at?: string;  // timestamp without time zone
  updated_at?: string;  // timestamp without time zone
  billing_no?: string;  // character varying
  is_gst_exempt?: boolean;  // boolean
  exemption_certificate_number?: string;  // character varying(50)
  exemption_certificate_expiry?: string;  // date
  exemption_type?: string;  // character varying(50)
  exemption_notes?: string;  // text
  bad_debt_status?: string;  // character varying(20)
  collection_attempts_count?: number;  // integer
  last_collection_date?: string;  // date
  first_overdue_date?: string;  // date
  writeoff_date?: string;  // date
  writeoff_amount?: number;  // numeric
  bankruptcy_status?: string;  // character varying(20)
  collection_notes?: string;  // text
  bad_debt_reason?: string;  // character varying(100)
  recovery_probability?: string;  // character varying(10)
  fraud_case_id?: number;  // integer
  client_name?: string;  // text
  lms_customer_number?: string;  // text
  qb_customer_id?: string;  // character varying(50)
  qb_customer_type?: string;  // character varying(50)
  payment_terms?: string;  // character varying(50)
  tax_code?: string;  // character varying(20)
  billing_rate_level?: string;  // character varying(50)
  sales_tax_code?: string;  // character varying(20)
  province?: string;  // character varying(50)
  country?: string;  // character varying(50)
  warning_flag?: boolean;  // boolean
  billing_address?: string;  // character varying(500)
  contact_info?: string;  // character varying(200)
  notes?: string;  // text
  name?: string;  // character varying
  phone?: string;  // character varying
  address?: string;  // text
  first_name?: string;  // character varying(100)
  last_name?: string;  // character varying(100)
  cell_phone?: string;  // character varying(20)
  home_phone?: string;  // character varying(20)
  work_phone?: string;  // character varying(20)
  fax_phone?: string;  // character varying(20)
  full_name_search?: string;  // text
  corporate_parent_id?: number;  // integer
  corporate_role?: string;  // character varying
  gst_exempt?: boolean;  // boolean
}

export interface Employees {
  employee_id: number;  // integer
  employee_number: string;  // character varying(50)
  full_name: string;  // character varying(255)
  last_name?: string;  // character varying(100)
  first_name?: string;  // character varying(100)
  phone?: string;  // character varying(50)
  cell_phone?: string;  // character varying(50)
  employee_category?: string;  // character varying(100)
  position?: string;  // character varying(100)
  is_chauffeur?: boolean;  // boolean
  salary?: number;  // numeric
  tax_exemptions?: number;  // integer
  deduction_per_voucher?: number;  // numeric
  deduction_radio_dues?: number;  // numeric
  deduction_misc_fees?: number;  // numeric
  status?: string;  // character varying(20)
  created_at?: string;  // timestamp without time zone
  updated_at?: string;  // timestamp without time zone
  hire_date?: string;  // date
  emergency_contact_name?: string;  // character varying(100)
  emergency_contact_phone?: string;  // character varying(20)
  employment_status?: string;  // character varying(20)
  compliance_status?: string;  // character varying(20)
  total_trips?: number;  // integer
  total_hours?: number;  // numeric
  total_revenue?: number;  // numeric
  profile_updated?: string;  // timestamp without time zone
  hourly_rate?: number;  // numeric
  rate_effective_date?: string;  // date
  quickbooks_id?: string;  // character varying(50)
  name?: string;  // character varying(255)
  email?: string;  // character varying(255)
  quickbooks_source?: string;  // character varying(255)
  t4_sin?: string;  // character varying(15)
  legacy_name?: string;  // character varying(255)
  legacy_employee?: boolean;  // boolean
  street_address?: string;  // character varying(200)
  city?: string;  // character varying(100)
  province?: string;  // character varying(50)
  postal_code?: string;  // character varying(10)
  country?: string;  // character varying(50)
  driver_license_number?: string;  // character varying(50)
  driver_license_expiry?: string;  // date
  chauffeur_permit_number?: string;  // character varying(50)
  chauffeur_permit_expiry?: string;  // date
  salary_deferred?: number;  // numeric
  hourly_pay_rate?: number;  // numeric
  gratuity_eligible?: boolean;  // boolean
  gratuity_percentage?: number;  // integer
  red_deer_compliant?: boolean;  // boolean
  red_deer_required?: boolean;  // boolean
  license_class?: string;  // character varying(10)
  medical_fitness_expiry?: string;  // date
  vulnerable_sector_check_date?: string;  // date
  drivers_abstract_date?: string;  // date
  proserve_number?: string;  // character varying
  proserve_expiry?: string;  // date
  bylaw_permit_renewal_fee?: number;  // numeric
  driver_license_class?: string;  // character varying
  driver_license_restrictions?: string;  // text
  qualification_1_date?: string;  // date
  qualification_2_date?: string;  // date
  qualification_3_date?: string;  // date
  qualification_4_date?: string;  // date
  qualification_5_date?: string;  // date
}

export interface Payments {
  payment_id: number;  // integer
  account_number?: string;  // character varying(50)
  reserve_number?: string;  // character varying(50)
  amount?: number;  // numeric
  payment_key?: string;  // character varying(100)
  last_updated?: string;  // timestamp without time zone
  created_at?: string;  // timestamp without time zone
  payment_method?: string;  // character varying(50)
  payment_date?: string;  // date
  status?: string;  // character varying(20)
  notes?: string;  // text
  payment_code_4char?: string;  // character varying(4)
  updated_at?: string;  // timestamp without time zone
  reference_number?: string;  // character varying(50)
  is_deposited?: boolean;  // boolean
  payment_label?: string;  // character varying(50)
  verified?: boolean;  // boolean
  verified_date?: string;  // timestamp without time zone
  verified_by?: string;  // character varying(100)
  square_fee_gl_code?: string;  // character varying(20)
  square_fee_gl_description?: string;  // text
}

export interface Receipts {
  receipt_id: number;  // bigint
  source_system?: string;  // text
  source_reference?: string;  // text
  receipt_date: string;  // date
  vendor_name?: string;  // text
  description?: string;  // text
  currency: string;  // character(3)
  gross_amount?: number;  // numeric
  gst_amount: number;  // numeric
  expense_account?: string;  // text
  payment_method?: string;  // text
  source_hash?: string;  // text
  created_at: string;  // timestamp with time zone
  document_type?: string;  // character varying(50)
  type?: string;  // character varying(50)
  tax_category?: string;  // character varying(50)
  card_type?: string;  // character varying(50)
  card_number?: string;  // character varying(50)
  comment?: string;  // text
  pay_method?: string;  // text
  mapped_bank_account_id?: number;  // integer
  canonical_pay_method?: string;  // text
  category?: string;  // character varying(100)
  expense?: number;  // numeric
  vehicle_id?: number;  // integer
  vehicle_number?: string;  // character varying(50)
  fuel?: number;  // numeric
  created_from_banking?: boolean;  // boolean
  revenue: number;  // numeric
  gst_code?: string;  // text
  split_key?: string;  // text
  split_group_total?: number;  // numeric
  fuel_amount?: number;  // numeric
  deductible_status?: string;  // text
  business_personal?: string;  // text
  source_file?: string;  // text
  gl_account_code?: string;  // character varying(10)
  gl_account_name?: string;  // character varying(200)
  gl_subcategory?: string;  // character varying(200)
  auto_categorized?: boolean;  // boolean
  net_amount: number;  // numeric
  is_split_receipt?: boolean;  // boolean
  is_personal_purchase?: boolean;  // boolean
  owner_personal_amount?: number;  // numeric
  is_driver_reimbursement?: boolean;  // boolean
  banking_transaction_id?: number;  // integer
  receipt_source?: string;  // character varying(50)
  display_color?: string;  // character varying(20)
  canonical_vendor?: string;  // character varying(255)
  is_transfer?: boolean;  // boolean
  verified_source?: string;  // text
  is_verified_banking?: boolean;  // boolean
  potential_duplicate?: boolean;  // boolean
  duplicate_check_key?: string;  // text
  is_nsf?: boolean;  // boolean
  is_voided?: boolean;  // boolean
  exclude_from_reports?: boolean;  // boolean
  vendor_account_id?: number;  // bigint
  fiscal_year?: number;  // integer
  invoice_date?: string;  // date
  is_paper_verified?: boolean;  // boolean
  paper_verification_date?: string;  // timestamp without time zone
  verified_by_user?: string;  // character varying(255)
  employee_id?: number;  // integer
  charter_id?: number;  // integer
  reserve_number?: string;  // character varying(20)
  gst_exempt?: boolean;  // boolean
  split_status?: string;  // character varying(50)
  split_group_id?: number;  // integer
  verified_by_edit?: boolean;  // boolean
  verified_at?: string;  // timestamp without time zone
  verified?: boolean;  // boolean
  verified_date?: string;  // timestamp without time zone
  verified_by?: string;  // character varying(100)
  gl_code?: string;  // character varying(20)
  gl_description?: string;  // text
  receipt_review_status?: string;  // character varying(20)
  receipt_review_notes?: string;  // text
  receipt_reviewed_at?: string;  // timestamp without time zone
  receipt_reviewed_by?: string;  // character varying(100)
}

export interface SplitRunSegments {
}

export interface Vehicles {
  vehicle_id: number;  // integer
  vehicle_number?: string;  // character varying(50)
  make?: string;  // character varying(100)
  model?: string;  // character varying(100)
  year?: number;  // integer
  license_plate?: string;  // character varying(50)
  passenger_capacity?: number;  // integer
  updated_at?: string;  // timestamp without time zone
  operational_status?: string;  // character varying(20)
  last_service_date?: string;  // date
  next_service_due?: string;  // date
  vin_number?: string;  // character varying(17)
  description?: string;  // text
  ext_color?: string;  // character varying(50)
  int_color?: string;  // character varying(50)
  length?: number;  // numeric
  width?: number;  // numeric
  height?: number;  // numeric
  odometer?: number;  // integer
  odometer_type: string;  // character varying(2)
  type?: string;  // character varying(50)
  engine_oil_type?: string;  // character varying
  fuel_filter_number?: string;  // character varying
  fuel_type?: string;  // character varying
  transmission_fluid_type?: string;  // character varying
  transmission_fluid_quantity?: string;  // character varying
  fuel_filter_interval_km?: number;  // integer
  transmission_service_interval_km?: number;  // integer
  curb_weight?: number;  // integer
  gross_vehicle_weight?: number;  // integer
  fuel_efficiency_data?: any;  // jsonb
  oil_quantity?: string;  // character varying
  oil_filter_number?: string;  // character varying
  coolant_type?: string;  // character varying
  coolant_quantity?: string;  // character varying
  belt_size?: string;  // character varying
  tire_size?: string;  // character varying
  tire_pressure?: string;  // character varying
  brake_fluid_type?: string;  // character varying
  power_steering_fluid_type?: string;  // character varying
  oil_change_interval_km?: number;  // integer
  oil_change_interval_months?: number;  // integer
  air_filter_interval_km?: number;  // integer
  coolant_change_interval_km?: number;  // integer
  brake_fluid_change_interval_months?: number;  // integer
  air_filter_part_number?: string;  // character varying
  cabin_filter_part_number?: string;  // character varying
  serpentine_belt_part_number?: string;  // character varying
  return_to_service_date?: string;  // date
  maintenance_schedule?: any;  // jsonb
  service_history?: any;  // jsonb
  parts_replacement_history?: any;  // jsonb
  vehicle_type?: string;  // character varying(100)
  fleet_number?: string;  // character varying(10)
  vehicle_category?: string;  // character varying(50)
  vehicle_class?: string;  // character varying(50)
  fleet_position?: number;  // integer
  vehicle_history_id?: string;  // character varying(50)
  commission_date?: string;  // date
  decommission_date?: string;  // date
  is_active?: boolean;  // boolean
  unit_number?: string;  // character varying(50)
  status?: string;  // character varying(50)
  cvip_expiry_date?: string;  // date
  cvip_inspection_number?: string;  // character varying(50)
  last_cvip_date?: string;  // date
  next_cvip_due?: string;  // date
  cvip_compliance_status?: string;  // character varying(50)
  purchase_date?: string;  // date
  purchase_price?: number;  // numeric
  purchase_vendor?: string;  // character varying(200)
  finance_partner?: string;  // character varying(200)
  financing_amount?: number;  // numeric
  monthly_payment?: number;  // numeric
  sale_date?: string;  // date
  sale_price?: number;  // numeric
  writeoff_date?: string;  // date
  writeoff_reason?: string;  // character varying(200)
  repossession_date?: string;  // date
  lifecycle_status?: string;  // character varying(50)
  tier_id?: number;  // integer
  maintenance_start_date?: string;  // date
  maintenance_end_date?: string;  // date
  is_in_maintenance?: boolean;  // boolean
  red_deer_compliant?: boolean;  // boolean
}
