<template>
  <div class="print-wrapper" v-if="booking">
    <div class="print-container">
      <!-- HEADER WITH LOGO AND TITLE -->
      <div class="print-header">
        <div class="header-left">
          <div class="company-name">ALMS Charter Services</div>
          <div class="subtitle">Charter Invoice & Receipt</div>
        </div>
        <div class="header-right">
          <div class="invoice-number">Invoice #: {{ booking.reserve_number }}</div>
          <div class="invoice-date">Date: {{ formatDate(booking.charter_date) }}</div>
        </div>
      </div>

      <!-- CUSTOMER & BILLING INFO -->
      <div class="print-section section-1">
        <div class="column">
          <div class="section-label">BILL TO:</div>
          <div class="section-content">
            <p class="name">{{ booking.client_name }}</p>
            <p v-if="booking.company_name">{{ booking.company_name }}</p>
            <p v-if="booking.email">{{ booking.email }}</p>
            <p v-if="booking.phone">{{ booking.phone }}</p>
          </div>
        </div>
        <div class="column">
          <div class="section-label">CHARTER TYPE:</div>
          <div class="section-content charter-badge">
            {{ formatCharterType(booking.charter_type) }}
          </div>
          <div style="margin-top: 1rem;">
            <div class="label-small">Status:</div>
            <div>{{ booking.status || 'Active' }}</div>
          </div>
          <div style="margin-top: 0.5rem;">
            <div class="label-small">Reconciliation:</div>
            <div>{{ booking.reconciliation_status || 'Not Reconciled' }}</div>
          </div>
        </div>
      </div>

      <!-- RESERVATION SUMMARY -->
      <div class="print-section section-2">
        <div class="section-title">RESERVATION SUMMARY</div>
        <div class="three-column">
          <div class="info-block">
            <div class="label-small">RESERVE #</div>
            <div class="value">{{ booking.reserve_number }}</div>
          </div>
          <div class="info-block">
            <div class="label-small">CHARTER DATE</div>
            <div class="value">{{ formatDate(booking.charter_date) }}</div>
          </div>
          <div class="info-block">
            <div class="label-small">PASSENGERS</div>
            <div class="value">{{ booking.passenger_load || 'TBD' }}</div>
          </div>
        </div>
      </div>

      <!-- TRIP & SERVICE DETAILS -->
      <div class="print-section section-3">
        <div class="section-title">TRIP DETAILS</div>
        <div class="trip-info">
          <div class="trip-row">
            <div class="trip-label">PICKUP:</div>
            <div class="trip-value">{{ booking.pickup_address || 'Not specified' }}</div>
          </div>
          <div class="trip-row">
            <div class="trip-label">DROPOFF:</div>
            <div class="trip-value">{{ booking.dropoff_address || 'Not specified' }}</div>
          </div>
        </div>
      </div>

      <!-- VEHICLE & DRIVER INFO -->
      <div class="print-section section-4">
        <div class="section-title">VEHICLE & DRIVER INFORMATION</div>
        <div class="three-column">
          <div class="info-block">
            <div class="label-small">VEHICLE</div>
            <div class="value">{{ booking.vehicle || 'Not assigned' }}</div>
          </div>
          <div class="info-block">
            <div class="label-small">VEHICLE TYPE</div>
            <div class="value">{{ booking.vehicle_type_requested || booking.vehicle_description || 'N/A' }}</div>
          </div>
          <div class="info-block">
            <div class="label-small">CAPACITY</div>
            <div class="value">{{ booking.vehicle_capacity ? booking.vehicle_capacity + ' pax' : 'N/A' }}</div>
          </div>
        </div>
        <div class="three-column" style="margin-top: 0.5rem;">
          <div class="info-block">
            <div class="label-small">DRIVER</div>
            <div class="value">{{ booking.driver_name || booking.driver || 'Not assigned' }}</div>
          </div>
        </div>
      </div>

      <!-- CHARGES -->
      <div class="print-section section-5">
        <div class="section-title">CHARGES & FEES</div>
        <table class="charges-table">
          <thead>
            <tr>
              <th style="width: 40%;">Description</th>
              <th style="width: 20%; text-align: right;">Quantity</th>
              <th style="width: 20%; text-align: right;">Rate</th>
              <th style="width: 20%; text-align: right;">Amount</th>
            </tr>
          </thead>
          <tbody>
            <tr class="charge-row">
              <td>Charter Service</td>
              <td style="text-align: right;">1</td>
              <td style="text-align: right;">${{ parseFloat(booking.total_amount_due || 0).toFixed(2) }}</td>
              <td style="text-align: right;">${{ parseFloat(booking.total_amount_due || 0).toFixed(2) }}</td>
            </tr>
            <tr v-if="parseFloat(booking.nrr_amount || 0) > 0" class="charge-row">
              <td>NRR/Retainer (Non-Refundable)</td>
              <td style="text-align: right;">1</td>
              <td style="text-align: right;">${{ parseFloat(booking.nrr_amount || 0).toFixed(2) }}</td>
              <td style="text-align: right;">${{ parseFloat(booking.nrr_amount || 0).toFixed(2) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- PAYMENT SUMMARY -->
      <div class="print-section section-6">
        <div class="section-title">PAYMENT SUMMARY</div>
        <div class="payment-summary">
          <div class="payment-row">
            <span>Total Charges:</span>
            <span class="amount">${{ parseFloat(booking.total_amount_due || 0).toFixed(2) }}</span>
          </div>
          <div class="payment-row">
            <span>Total Payments:</span>
            <span class="amount">${{ parseFloat(booking.total_paid || 0).toFixed(2) }}</span>
          </div>
          <div class="payment-row" v-if="parseFloat(booking.nrr_amount || 0) > 0">
            <span>NRR/Retainer:</span>
            <span class="amount">${{ parseFloat(booking.nrr_amount || 0).toFixed(2) }}</span>
          </div>
          <div class="payment-row total">
            <span>Balance Due:</span>
            <span class="amount">${{ (parseFloat(booking.total_amount_due || 0) - parseFloat(booking.total_paid || 0)).toFixed(2) }}</span>
          </div>
        </div>
      </div>

      <!-- EXCHANGE OF SERVICES (conditional) -->
      <div v-if="booking.charter_type === 'exchange_of_services'" class="print-section section-7">
        <div class="section-title">EXCHANGE OF SERVICES DETAILS</div>
        <div class="exchange-info">
          <div class="exchange-row">
            <span class="label-small">Service Provided:</span>
            <span>{{ booking.exchange_of_services_details?.service_provided || 'Not specified' }}</span>
          </div>
          <div class="exchange-row">
            <span class="label-small">Service Provider:</span>
            <span>{{ booking.exchange_of_services_details?.service_provider || 'Not specified' }}</span>
          </div>
          <div class="exchange-row">
            <span class="label-small">Exchange Value:</span>
            <span>${{ parseFloat(booking.exchange_of_services_details?.exchange_value || 0).toFixed(2) }}</span>
          </div>
          <div class="exchange-row">
            <span class="label-small">GL Revenue Code:</span>
            <span>{{ booking.gl_revenue_code || '4000' }}</span>
          </div>
          <div class="exchange-row">
            <span class="label-small">GL Expense Code:</span>
            <span>{{ booking.gl_expense_code || '6100' }}</span>
          </div>
          <div class="exchange-row full-width">
            <span class="label-small">Description:</span>
            <p>{{ booking.exchange_of_services_details?.description || 'No description provided' }}</p>
          </div>
        </div>
      </div>

      <!-- BILLING & GL CODES -->
      <div class="print-section section-8">
        <div class="section-title">BILLING & ACCOUNTING CODES</div>
        <div class="accounting-info">
          <div class="accounting-row">
            <span class="label-small">GL Revenue Code:</span>
            <span class="code">{{ booking.gl_revenue_code || '4000' }}</span>
          </div>
          <div class="accounting-row">
            <span class="label-small">GL Expense Code:</span>
            <span class="code">{{ booking.gl_expense_code || '6100' }}</span>
          </div>
        </div>
      </div>

      <!-- FOOTER -->
      <div class="print-footer">
        <div class="footer-text">
          <p>Thank you for your business!</p>
          <p style="font-size: 0.85rem; color: #666;">This is an automated invoice. For questions, please contact our office.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed } from 'vue'
import { formatDate } from '@/utils/dateFormatter'

export default {
  name: 'PrintTemplate',
  props: {
    booking: {
      type: Object,
      required: true
    }
  },
  setup(props) {
    const formatCharterType = (type) => {
      const typeMap = {
        'standard': 'Standard Charter',
        'exchange_of_services': 'Exchange of Services',
        'promotional': 'Promotional',
        'internal': 'Internal'
      }
      return typeMap[type] || type
    }

    return {
      formatDate,
      formatCharterType
    }
  }
}
</script>

<style scoped>
/* PRINT STYLES */
@media print {
  * {
    margin: 0;
    padding: 0;
  }
  
  body {
    margin: 0;
    padding: 0;
  }

  .print-wrapper {
    width: 100%;
    background: white;
  }
}

.print-wrapper {
  background: white;
  color: #333;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  line-height: 1.4;
  width: 100%;
}

.print-container {
  max-width: 8.5in;
  margin: 0 auto;
  padding: 0.5in;
  page-break-after: always;
}

/* HEADER */
.print-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  border-bottom: 3px solid #007bff;
  padding-bottom: 0.5rem;
  margin-bottom: 1rem;
}

.header-left {
  flex: 1;
}

.company-name {
  font-size: 1.5rem;
  font-weight: bold;
  color: #007bff;
}

.subtitle {
  font-size: 0.9rem;
  color: #666;
}

.header-right {
  text-align: right;
  font-size: 0.9rem;
}

.invoice-number {
  font-weight: bold;
}

/* SECTIONS */
.print-section {
  margin-bottom: 1.5rem;
  page-break-inside: avoid;
}

.section-title {
  font-size: 0.95rem;
  font-weight: bold;
  background: #f0f7ff;
  padding: 0.4rem 0.6rem;
  border-left: 4px solid #007bff;
  margin-bottom: 0.6rem;
}

.section-label {
  font-weight: bold;
  color: #007bff;
  font-size: 0.9rem;
  margin-bottom: 0.3rem;
}

.section-content {
  padding: 0.4rem 0;
  font-size: 0.9rem;
}

.section-content p {
  margin: 0.2rem 0;
}

.section-content.charter-badge {
  background: #f3f8fb;
  padding: 0.5rem;
  border-radius: 4px;
  font-weight: bold;
  color: #0056b3;
}

/* COLUMNS */
.column {
  display: inline-block;
  width: 48%;
  vertical-align: top;
  margin-right: 2%;
}

.column:last-child {
  margin-right: 0;
}

.three-column {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 1rem;
}

.info-block {
  padding: 0.4rem;
  background: #f9f9f9;
  border-radius: 4px;
}

.label-small {
  font-size: 0.75rem;
  font-weight: bold;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.value {
  font-size: 0.95rem;
  margin-top: 0.2rem;
}

/* TRIP INFO */
.trip-info {
  padding: 0.5rem 0;
}

.trip-row {
  display: flex;
  margin-bottom: 0.5rem;
}

.trip-label {
  font-weight: bold;
  width: 100px;
  font-size: 0.9rem;
}

.trip-value {
  flex: 1;
  font-size: 0.9rem;
}

/* CHARGES TABLE */
.charges-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
  margin-bottom: 0.5rem;
}

.charges-table th {
  background: #e8f0f8;
  padding: 0.5rem;
  text-align: left;
  border-bottom: 2px solid #007bff;
  font-weight: bold;
}

.charges-table td {
  padding: 0.5rem;
  border-bottom: 1px solid #ddd;
}

.charge-row:hover {
  background: #f9f9f9;
}

/* PAYMENT SUMMARY */
.payment-summary {
  background: #f9f9f9;
  padding: 0.8rem;
  border-radius: 4px;
}

.payment-row {
  display: flex;
  justify-content: space-between;
  padding: 0.4rem 0;
  font-size: 0.95rem;
  border-bottom: 1px solid #e0e0e0;
}

.payment-row.total {
  font-weight: bold;
  border-bottom: none;
  border-top: 2px solid #007bff;
  padding-top: 0.5rem;
  margin-top: 0.5rem;
}

.amount {
  text-align: right;
  font-weight: bold;
  color: #0056b3;
  min-width: 100px;
}

/* EXCHANGE OF SERVICES */
.exchange-info {
  background: #f9f9f9;
  padding: 0.8rem;
  border-radius: 4px;
  border-left: 3px solid #9c27b0;
}

.exchange-row {
  display: flex;
  margin-bottom: 0.5rem;
  font-size: 0.9rem;
}

.exchange-row.full-width {
  flex-direction: column;
}

.exchange-row .label-small {
  min-width: 150px;
  margin-right: 1rem;
}

.exchange-row p {
  margin: 0;
  font-size: 0.9rem;
}

/* ACCOUNTING CODES */
.accounting-info {
  background: #f0f7ff;
  padding: 0.8rem;
  border-radius: 4px;
  border-left: 3px solid #007bff;
}

.accounting-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.5rem;
  font-size: 0.9rem;
}

.code {
  font-family: 'Courier New', monospace;
  font-weight: bold;
  background: white;
  padding: 0.2rem 0.4rem;
  border-radius: 2px;
}

/* FOOTER */
.print-footer {
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 1px solid #ddd;
  text-align: center;
  font-size: 0.85rem;
  color: #666;
}

.footer-text p {
  margin: 0.3rem 0;
}

/* PRINT SPECIFIC */
@media print {
  .print-container {
    page-break-after: always;
  }

  .print-section {
    page-break-inside: avoid;
  }

  body {
    background: white !important;
  }

  .print-wrapper {
    box-shadow: none !important;
  }
}

/* SCREEN DISPLAY */
@media screen {
  .print-wrapper {
    margin: 1rem;
    background: white;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  }
  
  .print-container {
    box-shadow: inset 0 0 0 1px #ddd;
  }
}
</style>
