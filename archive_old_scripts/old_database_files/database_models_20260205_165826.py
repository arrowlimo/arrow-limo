# AUTO-GENERATED Pydantic models from database schema
# Generated: 2026-02-05T16:58:26.101031
# DO NOT EDIT MANUALLY - regenerate using generate_field_mapping.py

from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import date, time, datetime

class BankingReceiptMatchingLedger(BaseModel):
    id: int  # integer
    banking_transaction_id: int  # bigint
    receipt_id: Optional[int] = None  # bigint
    match_date: Optional[datetime] = None  # timestamp without time zone
    match_type: Optional[str] = None  # character varying(50)
    match_status: Optional[str] = None  # character varying(20)
    match_confidence: Optional[str] = None  # character varying(20)
    notes: Optional[str] = None  # text
    created_by: Optional[str] = None  # character varying(50)
    amount_allocated: Optional[Decimal] = None  # numeric
    allocation_date: Optional[datetime] = None  # timestamp without time zone
    allocation_type: Optional[str] = None  # character varying(50)

class BeverageOrders(BaseModel):
    order_id: int  # integer
    reserve_number: str  # character varying(32)
    order_date: datetime  # timestamp without time zone
    subtotal: Decimal  # numeric
    gst: Decimal  # numeric
    total: Decimal  # numeric
    status: Optional[str] = None  # text

class ChartOfAccounts(BaseModel):
    account_code: str  # character varying(10)
    parent_account: Optional[str] = None  # character varying(10)
    account_name: str  # character varying(200)
    account_type: str  # character varying(50)
    description: Optional[str] = None  # text
    is_active: Optional[bool] = None  # boolean
    created_at: Optional[datetime] = None  # timestamp without time zone
    qb_account_type: Optional[str] = None  # character varying(50)
    account_level: Optional[int] = None  # integer
    is_header_account: Optional[bool] = None  # boolean
    normal_balance: Optional[str] = None  # character varying(10)
    current_balance: Optional[Decimal] = None  # numeric
    bank_account_number: Optional[str] = None  # text
    updated_at: Optional[datetime] = None  # timestamp without time zone

class Charters(BaseModel):
    charter_id: int  # integer
    reserve_number: str  # character varying(50)
    client_id: Optional[int] = None  # integer
    charter_date: Optional[date] = None  # date
    pickup_time: Optional[time] = None  # time without time zone
    pickup_address: Optional[str] = None  # text
    dropoff_address: Optional[str] = None  # text
    passenger_count: Optional[int] = None  # integer
    rate: Optional[Decimal] = None  # numeric
    balance: Optional[Decimal] = None  # numeric
    payment_totals: Optional[Decimal] = None  # numeric
    status: Optional[str] = None  # character varying(50)
    created_at: Optional[datetime] = None  # timestamp without time zone
    updated_at: Optional[datetime] = None  # timestamp without time zone
    driver_notes: Optional[str] = None  # text
    client_notes: Optional[str] = None  # text
    booking_notes: Optional[str] = None  # text
    total_amount_due: Optional[Decimal] = None  # numeric
    dispatcher_approved: Optional[bool] = None  # boolean
    driver_base_pay: Optional[Decimal] = None  # numeric
    driver_gratuity: Optional[Decimal] = None  # numeric
    driver_total_expense: Optional[Decimal] = None  # numeric
    expense_calculated_at: Optional[datetime] = None  # timestamp without time zone
    odometer_start: Optional[Decimal] = None  # numeric
    odometer_end: Optional[Decimal] = None  # numeric
    total_kms: Optional[Decimal] = None  # numeric
    vehicle_notes: Optional[str] = None  # text
    is_placeholder: bool  # boolean
    default_hourly_price: Optional[Decimal] = None  # numeric
    package_rate: Optional[Decimal] = None  # numeric
    extra_time_rate: Optional[Decimal] = None  # numeric
    daily_rate: Optional[Decimal] = None  # numeric
    airport_pickup_price: Optional[Decimal] = None  # numeric
    employee_id: Optional[int] = None  # integer
    vehicle_id: Optional[int] = None  # integer
    client_display_name: Optional[str] = None  # text
    nrd_received: Optional[bool] = None  # boolean
    nrd_amount: Optional[Decimal] = None  # numeric
    nrd_method: Optional[str] = None  # character varying
    is_out_of_town: Optional[bool] = None  # boolean
    fuel_litres: Optional[Decimal] = None  # numeric
    float_received: Optional[Decimal] = None  # numeric
    float_reimbursement_needed: Optional[Decimal] = None  # numeric
    calendar_color: Optional[str] = None  # character varying(20)
    separate_customer_printout: Optional[bool] = None  # boolean
    charter_type: Optional[str] = None  # character varying
    quoted_hours: Optional[Decimal] = None  # numeric
    standby_rate: Optional[Decimal] = None  # numeric
    split_run_start_time: Optional[Decimal] = None  # numeric
    split_run_time: Optional[Decimal] = None  # numeric
    calendar_sync_status: Optional[str] = None  # character varying
    outlook_entry_id: Optional[str] = None  # character varying
    calendar_notes: Optional[str] = None  # text
    record_type: Optional[str] = None  # USER-DEFINED
    version: Optional[int] = None  # integer
    do_time: Optional[time] = None  # time without time zone
    cart_order_list: Optional[str] = None  # text
    fuel_price: Optional[Decimal] = None  # numeric
    fuel_gst: Optional[Decimal] = None  # numeric
    locked: bool  # boolean

class Clients(BaseModel):
    client_id: int  # integer
    account_number: str  # character varying(50)
    company_name: Optional[str] = None  # character varying(255)
    primary_phone: Optional[str] = None  # character varying(50)
    email: Optional[str] = None  # character varying(255)
    address_line1: Optional[str] = None  # character varying(255)
    city: Optional[str] = None  # character varying(100)
    state: Optional[str] = None  # character varying(50)
    zip_code: Optional[str] = None  # character varying(20)
    balance: Optional[Decimal] = None  # numeric
    credit_limit: Optional[Decimal] = None  # numeric
    discount_percentage: Optional[Decimal] = None  # numeric
    discount_flat: Optional[Decimal] = None  # numeric
    gratuity_percentage: Optional[Decimal] = None  # numeric
    interest_rate: Optional[Decimal] = None  # numeric
    grace_days: Optional[int] = None  # integer
    is_inactive: Optional[bool] = None  # boolean
    status: Optional[str] = None  # character varying(20)
    created_at: Optional[datetime] = None  # timestamp without time zone
    updated_at: Optional[datetime] = None  # timestamp without time zone
    billing_no: Optional[str] = None  # character varying
    is_gst_exempt: Optional[bool] = None  # boolean
    exemption_certificate_number: Optional[str] = None  # character varying(50)
    exemption_certificate_expiry: Optional[date] = None  # date
    exemption_type: Optional[str] = None  # character varying(50)
    exemption_notes: Optional[str] = None  # text
    bad_debt_status: Optional[str] = None  # character varying(20)
    collection_attempts_count: Optional[int] = None  # integer
    last_collection_date: Optional[date] = None  # date
    first_overdue_date: Optional[date] = None  # date
    writeoff_date: Optional[date] = None  # date
    writeoff_amount: Optional[Decimal] = None  # numeric
    bankruptcy_status: Optional[str] = None  # character varying(20)
    collection_notes: Optional[str] = None  # text
    bad_debt_reason: Optional[str] = None  # character varying(100)
    recovery_probability: Optional[str] = None  # character varying(10)
    fraud_case_id: Optional[int] = None  # integer
    client_name: Optional[str] = None  # text
    lms_customer_number: Optional[str] = None  # text
    qb_customer_id: Optional[str] = None  # character varying(50)
    qb_customer_type: Optional[str] = None  # character varying(50)
    payment_terms: Optional[str] = None  # character varying(50)
    tax_code: Optional[str] = None  # character varying(20)
    billing_rate_level: Optional[str] = None  # character varying(50)
    sales_tax_code: Optional[str] = None  # character varying(20)
    province: Optional[str] = None  # character varying(50)
    country: Optional[str] = None  # character varying(50)
    warning_flag: Optional[bool] = None  # boolean
    billing_address: Optional[str] = None  # character varying(500)
    contact_info: Optional[str] = None  # character varying(200)
    notes: Optional[str] = None  # text
    name: Optional[str] = None  # character varying
    phone: Optional[str] = None  # character varying
    address: Optional[str] = None  # text
    first_name: Optional[str] = None  # character varying(100)
    last_name: Optional[str] = None  # character varying(100)
    cell_phone: Optional[str] = None  # character varying(20)
    home_phone: Optional[str] = None  # character varying(20)
    work_phone: Optional[str] = None  # character varying(20)
    fax_phone: Optional[str] = None  # character varying(20)
    full_name_search: Optional[str] = None  # text
    corporate_parent_id: Optional[int] = None  # integer
    corporate_role: Optional[str] = None  # character varying
    gst_exempt: Optional[bool] = None  # boolean

class Employees(BaseModel):
    employee_id: int  # integer
    employee_number: str  # character varying(50)
    full_name: str  # character varying(255)
    last_name: Optional[str] = None  # character varying(100)
    first_name: Optional[str] = None  # character varying(100)
    phone: Optional[str] = None  # character varying(50)
    cell_phone: Optional[str] = None  # character varying(50)
    employee_category: Optional[str] = None  # character varying(100)
    position: Optional[str] = None  # character varying(100)
    is_chauffeur: Optional[bool] = None  # boolean
    salary: Optional[Decimal] = None  # numeric
    tax_exemptions: Optional[int] = None  # integer
    deduction_per_voucher: Optional[Decimal] = None  # numeric
    deduction_radio_dues: Optional[Decimal] = None  # numeric
    deduction_misc_fees: Optional[Decimal] = None  # numeric
    status: Optional[str] = None  # character varying(20)
    created_at: Optional[datetime] = None  # timestamp without time zone
    updated_at: Optional[datetime] = None  # timestamp without time zone
    hire_date: Optional[date] = None  # date
    emergency_contact_name: Optional[str] = None  # character varying(100)
    emergency_contact_phone: Optional[str] = None  # character varying(20)
    employment_status: Optional[str] = None  # character varying(20)
    compliance_status: Optional[str] = None  # character varying(20)
    total_trips: Optional[int] = None  # integer
    total_hours: Optional[Decimal] = None  # numeric
    total_revenue: Optional[Decimal] = None  # numeric
    profile_updated: Optional[datetime] = None  # timestamp without time zone
    hourly_rate: Optional[Decimal] = None  # numeric
    rate_effective_date: Optional[date] = None  # date
    quickbooks_id: Optional[str] = None  # character varying(50)
    name: Optional[str] = None  # character varying(255)
    email: Optional[str] = None  # character varying(255)
    quickbooks_source: Optional[str] = None  # character varying(255)
    t4_sin: Optional[str] = None  # character varying(15)
    legacy_name: Optional[str] = None  # character varying(255)
    legacy_employee: Optional[bool] = None  # boolean
    street_address: Optional[str] = None  # character varying(200)
    city: Optional[str] = None  # character varying(100)
    province: Optional[str] = None  # character varying(50)
    postal_code: Optional[str] = None  # character varying(10)
    country: Optional[str] = None  # character varying(50)
    driver_license_number: Optional[str] = None  # character varying(50)
    driver_license_expiry: Optional[date] = None  # date
    chauffeur_permit_number: Optional[str] = None  # character varying(50)
    chauffeur_permit_expiry: Optional[date] = None  # date
    salary_deferred: Optional[Decimal] = None  # numeric
    hourly_pay_rate: Optional[Decimal] = None  # numeric
    gratuity_eligible: Optional[bool] = None  # boolean
    gratuity_percentage: Optional[int] = None  # integer
    red_deer_compliant: Optional[bool] = None  # boolean
    red_deer_required: Optional[bool] = None  # boolean
    license_class: Optional[str] = None  # character varying(10)
    medical_fitness_expiry: Optional[date] = None  # date
    vulnerable_sector_check_date: Optional[date] = None  # date
    drivers_abstract_date: Optional[date] = None  # date
    proserve_number: Optional[str] = None  # character varying
    proserve_expiry: Optional[date] = None  # date
    bylaw_permit_renewal_fee: Optional[Decimal] = None  # numeric
    driver_license_class: Optional[str] = None  # character varying
    driver_license_restrictions: Optional[str] = None  # text
    qualification_1_date: Optional[date] = None  # date
    qualification_2_date: Optional[date] = None  # date
    qualification_3_date: Optional[date] = None  # date
    qualification_4_date: Optional[date] = None  # date
    qualification_5_date: Optional[date] = None  # date

class Payments(BaseModel):
    payment_id: int  # integer
    account_number: Optional[str] = None  # character varying(50)
    reserve_number: Optional[str] = None  # character varying(50)
    amount: Optional[Decimal] = None  # numeric
    payment_key: Optional[str] = None  # character varying(100)
    last_updated: Optional[datetime] = None  # timestamp without time zone
    created_at: Optional[datetime] = None  # timestamp without time zone
    payment_method: Optional[str] = None  # character varying(50)
    payment_date: Optional[date] = None  # date
    status: Optional[str] = None  # character varying(20)
    notes: Optional[str] = None  # text
    payment_code_4char: Optional[str] = None  # character varying(4)
    updated_at: Optional[datetime] = None  # timestamp without time zone
    reference_number: Optional[str] = None  # character varying(50)
    is_deposited: Optional[bool] = None  # boolean
    payment_label: Optional[str] = None  # character varying(50)
    verified: Optional[bool] = None  # boolean
    verified_date: Optional[datetime] = None  # timestamp without time zone
    verified_by: Optional[str] = None  # character varying(100)
    square_fee_gl_code: Optional[str] = None  # character varying(20)
    square_fee_gl_description: Optional[str] = None  # text

class Receipts(BaseModel):
    receipt_id: int  # bigint
    source_system: Optional[str] = None  # text
    source_reference: Optional[str] = None  # text
    receipt_date: date  # date
    vendor_name: Optional[str] = None  # text
    description: Optional[str] = None  # text
    currency: str  # character(3)
    gross_amount: Optional[Decimal] = None  # numeric
    gst_amount: Decimal  # numeric
    expense_account: Optional[str] = None  # text
    payment_method: Optional[str] = None  # text
    source_hash: Optional[str] = None  # text
    created_at: datetime  # timestamp with time zone
    document_type: Optional[str] = None  # character varying(50)
    type: Optional[str] = None  # character varying(50)
    tax_category: Optional[str] = None  # character varying(50)
    card_type: Optional[str] = None  # character varying(50)
    card_number: Optional[str] = None  # character varying(50)
    comment: Optional[str] = None  # text
    pay_method: Optional[str] = None  # text
    mapped_bank_account_id: Optional[int] = None  # integer
    canonical_pay_method: Optional[str] = None  # text
    category: Optional[str] = None  # character varying(100)
    expense: Optional[Decimal] = None  # numeric
    vehicle_id: Optional[int] = None  # integer
    vehicle_number: Optional[str] = None  # character varying(50)
    fuel: Optional[Decimal] = None  # numeric
    created_from_banking: Optional[bool] = None  # boolean
    revenue: Decimal  # numeric
    gst_code: Optional[str] = None  # text
    split_key: Optional[str] = None  # text
    split_group_total: Optional[Decimal] = None  # numeric
    fuel_amount: Optional[Decimal] = None  # numeric
    deductible_status: Optional[str] = None  # text
    business_personal: Optional[str] = None  # text
    source_file: Optional[str] = None  # text
    gl_account_code: Optional[str] = None  # character varying(10)
    gl_account_name: Optional[str] = None  # character varying(200)
    gl_subcategory: Optional[str] = None  # character varying(200)
    auto_categorized: Optional[bool] = None  # boolean
    net_amount: Decimal  # numeric
    is_split_receipt: Optional[bool] = None  # boolean
    is_personal_purchase: Optional[bool] = None  # boolean
    owner_personal_amount: Optional[Decimal] = None  # numeric
    is_driver_reimbursement: Optional[bool] = None  # boolean
    banking_transaction_id: Optional[int] = None  # integer
    receipt_source: Optional[str] = None  # character varying(50)
    display_color: Optional[str] = None  # character varying(20)
    canonical_vendor: Optional[str] = None  # character varying(255)
    is_transfer: Optional[bool] = None  # boolean
    verified_source: Optional[str] = None  # text
    is_verified_banking: Optional[bool] = None  # boolean
    potential_duplicate: Optional[bool] = None  # boolean
    duplicate_check_key: Optional[str] = None  # text
    is_nsf: Optional[bool] = None  # boolean
    is_voided: Optional[bool] = None  # boolean
    exclude_from_reports: Optional[bool] = None  # boolean
    vendor_account_id: Optional[int] = None  # bigint
    fiscal_year: Optional[int] = None  # integer
    invoice_date: Optional[date] = None  # date
    is_paper_verified: Optional[bool] = None  # boolean
    paper_verification_date: Optional[datetime] = None  # timestamp without time zone
    verified_by_user: Optional[str] = None  # character varying(255)
    employee_id: Optional[int] = None  # integer
    charter_id: Optional[int] = None  # integer
    reserve_number: Optional[str] = None  # character varying(20)
    gst_exempt: Optional[bool] = None  # boolean
    split_status: Optional[str] = None  # character varying(50)
    split_group_id: Optional[int] = None  # integer
    verified_by_edit: Optional[bool] = None  # boolean
    verified_at: Optional[datetime] = None  # timestamp without time zone
    verified: Optional[bool] = None  # boolean
    verified_date: Optional[datetime] = None  # timestamp without time zone
    verified_by: Optional[str] = None  # character varying(100)
    gl_code: Optional[str] = None  # character varying(20)
    gl_description: Optional[str] = None  # text
    receipt_review_status: Optional[str] = None  # character varying(20)
    receipt_review_notes: Optional[str] = None  # text
    receipt_reviewed_at: Optional[datetime] = None  # timestamp without time zone
    receipt_reviewed_by: Optional[str] = None  # character varying(100)

class SplitRunSegments(BaseModel):
    pass

class Vehicles(BaseModel):
    vehicle_id: int  # integer
    vehicle_number: Optional[str] = None  # character varying(50)
    make: Optional[str] = None  # character varying(100)
    model: Optional[str] = None  # character varying(100)
    year: Optional[int] = None  # integer
    license_plate: Optional[str] = None  # character varying(50)
    passenger_capacity: Optional[int] = None  # integer
    updated_at: Optional[datetime] = None  # timestamp without time zone
    operational_status: Optional[str] = None  # character varying(20)
    last_service_date: Optional[date] = None  # date
    next_service_due: Optional[date] = None  # date
    vin_number: Optional[str] = None  # character varying(17)
    description: Optional[str] = None  # text
    ext_color: Optional[str] = None  # character varying(50)
    int_color: Optional[str] = None  # character varying(50)
    length: Optional[Decimal] = None  # numeric
    width: Optional[Decimal] = None  # numeric
    height: Optional[Decimal] = None  # numeric
    odometer: Optional[int] = None  # integer
    odometer_type: str  # character varying(2)
    type: Optional[str] = None  # character varying(50)
    engine_oil_type: Optional[str] = None  # character varying
    fuel_filter_number: Optional[str] = None  # character varying
    fuel_type: Optional[str] = None  # character varying
    transmission_fluid_type: Optional[str] = None  # character varying
    transmission_fluid_quantity: Optional[str] = None  # character varying
    fuel_filter_interval_km: Optional[int] = None  # integer
    transmission_service_interval_km: Optional[int] = None  # integer
    curb_weight: Optional[int] = None  # integer
    gross_vehicle_weight: Optional[int] = None  # integer
    fuel_efficiency_data: Optional[dict] = None  # jsonb
    oil_quantity: Optional[str] = None  # character varying
    oil_filter_number: Optional[str] = None  # character varying
    coolant_type: Optional[str] = None  # character varying
    coolant_quantity: Optional[str] = None  # character varying
    belt_size: Optional[str] = None  # character varying
    tire_size: Optional[str] = None  # character varying
    tire_pressure: Optional[str] = None  # character varying
    brake_fluid_type: Optional[str] = None  # character varying
    power_steering_fluid_type: Optional[str] = None  # character varying
    oil_change_interval_km: Optional[int] = None  # integer
    oil_change_interval_months: Optional[int] = None  # integer
    air_filter_interval_km: Optional[int] = None  # integer
    coolant_change_interval_km: Optional[int] = None  # integer
    brake_fluid_change_interval_months: Optional[int] = None  # integer
    air_filter_part_number: Optional[str] = None  # character varying
    cabin_filter_part_number: Optional[str] = None  # character varying
    serpentine_belt_part_number: Optional[str] = None  # character varying
    return_to_service_date: Optional[date] = None  # date
    maintenance_schedule: Optional[dict] = None  # jsonb
    service_history: Optional[dict] = None  # jsonb
    parts_replacement_history: Optional[dict] = None  # jsonb
    vehicle_type: Optional[str] = None  # character varying(100)
    fleet_number: Optional[str] = None  # character varying(10)
    vehicle_category: Optional[str] = None  # character varying(50)
    vehicle_class: Optional[str] = None  # character varying(50)
    fleet_position: Optional[int] = None  # integer
    vehicle_history_id: Optional[str] = None  # character varying(50)
    commission_date: Optional[date] = None  # date
    decommission_date: Optional[date] = None  # date
    is_active: Optional[bool] = None  # boolean
    unit_number: Optional[str] = None  # character varying(50)
    status: Optional[str] = None  # character varying(50)
    cvip_expiry_date: Optional[date] = None  # date
    cvip_inspection_number: Optional[str] = None  # character varying(50)
    last_cvip_date: Optional[date] = None  # date
    next_cvip_due: Optional[date] = None  # date
    cvip_compliance_status: Optional[str] = None  # character varying(50)
    purchase_date: Optional[date] = None  # date
    purchase_price: Optional[Decimal] = None  # numeric
    purchase_vendor: Optional[str] = None  # character varying(200)
    finance_partner: Optional[str] = None  # character varying(200)
    financing_amount: Optional[Decimal] = None  # numeric
    monthly_payment: Optional[Decimal] = None  # numeric
    sale_date: Optional[date] = None  # date
    sale_price: Optional[Decimal] = None  # numeric
    writeoff_date: Optional[date] = None  # date
    writeoff_reason: Optional[str] = None  # character varying(200)
    repossession_date: Optional[date] = None  # date
    lifecycle_status: Optional[str] = None  # character varying(50)
    tier_id: Optional[int] = None  # integer
    maintenance_start_date: Optional[date] = None  # date
    maintenance_end_date: Optional[date] = None  # date
    is_in_maintenance: Optional[bool] = None  # boolean
    red_deer_compliant: Optional[bool] = None  # boolean
