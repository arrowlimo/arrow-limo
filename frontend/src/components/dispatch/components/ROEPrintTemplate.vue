<!--
  Record of Employment (ROE) Print Template
  Purpose: Official Canadian government ROE form for employment terminations
  Format: Follows Service Canada ROE requirements and layout
  Created: October 21, 2025
-->
<template>
  <div class="roe-print-template" v-if="roeData">
    <!-- ROE Header -->
    <div class="roe-header">
      <div class="roe-title">
        <h1>RECORD OF EMPLOYMENT</h1>
        <h2>RELEVÉ D'EMPLOI</h2>
      </div>
      
      <div class="roe-number">
        <div class="roe-number-label">ROE Number / No du relevé d'emploi</div>
        <div class="roe-number-value">{{ roeData.roe_number }}</div>
      </div>
      
      <div class="service-canada-logo">
        <div class="logo-placeholder">Service Canada</div>
      </div>
    </div>

    <!-- Employer Information Section -->
    <div class="roe-section employer-section">
      <div class="section-title">EMPLOYER INFORMATION / RENSEIGNEMENTS SUR L'EMPLOYEUR</div>
      
      <div class="employer-grid">
        <div class="field-group">
          <label class="field-label">1. Business Number / Numéro d'entreprise</label>
          <div class="field-value">{{ employerInfo.business_number || '123456789RC0001' }}</div>
        </div>
        
        <div class="field-group">
          <label class="field-label">2. Employer Name / Nom de l'employeur</label>
          <div class="field-value">{{ employerInfo.company_name || 'Arrow Limousine Service' }}</div>
        </div>
        
        <div class="field-group full-width">
          <label class="field-label">3. Address / Adresse</label>
          <div class="field-value">
            {{ employerInfo.address_line1 || '1234 Business Street' }}<br>
            {{ employerInfo.city || 'Red Deer' }}, {{ employerInfo.province || 'AB' }} {{ employerInfo.postal_code || 'T4N 1A1' }}
          </div>
        </div>
        
        <div class="field-group">
          <label class="field-label">4. Telephone / Téléphone</label>
          <div class="field-value">{{ employerInfo.phone || '(403) 555-0123' }}</div>
        </div>
        
        <div class="field-group">
          <label class="field-label">5. Email / Courriel</label>
          <div class="field-value">{{ employerInfo.email || 'info@arrowlimo.ca' }}</div>
        </div>
      </div>
    </div>

    <!-- Employee Information Section -->
    <div class="roe-section employee-section">
      <div class="section-title">EMPLOYEE INFORMATION / RENSEIGNEMENTS SUR L'EMPLOYÉ(E)</div>
      
      <div class="employee-grid">
        <div class="field-group">
          <label class="field-label">6. Social Insurance Number / Numéro d'assurance sociale</label>
          <div class="field-value sin-field">{{ formatSIN(roeData.employee_sin) }}</div>
        </div>
        
        <div class="field-group">
          <label class="field-label">7. Employee Number / Numéro d'employé(e)</label>
          <div class="field-value">{{ roeData.employee_number || roeData.employee_id }}</div>
        </div>
        
        <div class="field-group full-width">
          <label class="field-label">8. Employee Name / Nom de l'employé(e)</label>
          <div class="field-value">{{ roeData.employee_name }}</div>
        </div>
        
        <div class="field-group full-width">
          <label class="field-label">9. Employee Address / Adresse de l'employé(e)</label>
          <div class="field-value">
            {{ roeData.employee_address || 'Employee Address' }}<br>
            {{ roeData.employee_city || 'City' }}, {{ roeData.employee_province || 'AB' }} {{ roeData.employee_postal_code || 'T0M 0A0' }}
          </div>
        </div>
      </div>
    </div>

    <!-- Employment Period Section -->
    <div class="roe-section employment-section">
      <div class="section-title">EMPLOYMENT INFORMATION / RENSEIGNEMENTS SUR L'EMPLOI</div>
      
      <div class="employment-grid">
        <div class="field-group">
          <label class="field-label">10. First Day Worked / Premier jour travaillé</label>
          <div class="field-value date-field">{{ formatDate(roeData.first_day_worked) }}</div>
        </div>
        
        <div class="field-group">
          <label class="field-label">11. Last Day for Which Paid / Dernier jour payé</label>
          <div class="field-value date-field">{{ formatDate(roeData.last_day_paid) }}</div>
        </div>
        
        <div class="field-group">
          <label class="field-label">12. Final Pay Period Ending Date / Date de fin de la dernière période de paie</label>
          <div class="field-value date-field">{{ formatDate(roeData.final_pay_period_end) }}</div>
        </div>
        
        <div class="field-group">
          <label class="field-label">13. Pay Period Type / Type de période de paie</label>
          <div class="field-value">{{ formatPayPeriodType(roeData.pay_period_type) }}</div>
        </div>
      </div>
    </div>

    <!-- Reason for Issuing ROE Section -->
    <div class="roe-section reason-section">
      <div class="section-title">REASON FOR ISSUING THIS ROE / RAISON DE LA PRODUCTION DE CE RELEVÉ</div>
      
      <div class="reason-grid">
        <div class="field-group">
          <label class="field-label">14. Reason Code / Code de raison</label>
          <div class="field-value reason-code">{{ roeData.reason_code }}</div>
        </div>
        
        <div class="field-group full-width">
          <label class="field-label">15. Comments / Commentaires</label>
          <div class="field-value">{{ roeData.reason_description }}</div>
        </div>
      </div>
    </div>

    <!-- Earnings and Hours Section -->
    <div class="roe-section earnings-section">
      <div class="section-title">EARNINGS AND HOURS / GAINS ET HEURES</div>
      
      <div class="earnings-grid">
        <div class="field-group">
          <label class="field-label">16. Total Insurable Hours / Total des heures assurables</label>
          <div class="field-value hours-field">{{ roeData.total_insurable_hours || 0 }}</div>
        </div>
        
        <div class="field-group">
          <label class="field-label">17. Total Insurable Earnings / Total des gains assurables</label>
          <div class="field-value currency-field">${{ formatCurrency(roeData.total_insurable_earnings) }}</div>
        </div>
      </div>

      <!-- Pay Period Details Table -->
      <div class="pay-periods-table">
        <div class="table-title">PAY PERIOD DETAILS / DÉTAILS DES PÉRIODES DE PAIE</div>
        <table class="pay-periods">
          <thead>
            <tr>
              <th>Period / Période</th>
              <th>From / Du</th>
              <th>To / Au</th>
              <th>Insurable Hours / Heures assurables</th>
              <th>Insurable Earnings / Gains assurables</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(period, index) in roeData.pay_periods" :key="index">
              <td>{{ index + 1 }}</td>
              <td>{{ formatDate(period.period_start) }}</td>
              <td>{{ formatDate(period.period_end) }}</td>
              <td class="text-right">{{ period.insurable_hours || 0 }}</td>
              <td class="text-right">${{ formatCurrency(period.insurable_earnings) }}</td>
            </tr>
            <!-- Show empty rows if less than 6 periods -->
            <tr v-for="n in Math.max(0, 6 - (roeData.pay_periods?.length || 0))" :key="`empty-${n}`" class="empty-row">
              <td>{{ (roeData.pay_periods?.length || 0) + n }}</td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Additional Information Section -->
    <div class="roe-section additional-section">
      <div class="section-title">ADDITIONAL INFORMATION / RENSEIGNEMENTS SUPPLÉMENTAIRES</div>
      
      <div class="additional-grid">
        <div class="field-group">
          <label class="field-label">18. Vacation Pay / Paie de vacances</label>
          <div class="field-value currency-field">${{ formatCurrency(roeData.vacation_pay) }}</div>
        </div>
        
        <div class="field-group">
          <label class="field-label">19. Statutory Holiday Pay / Paie de congé férié</label>
          <div class="field-value currency-field">${{ formatCurrency(roeData.statutory_holiday_pay) }}</div>
        </div>
        
        <div class="field-group">
          <label class="field-label">20. Other Monies / Autres sommes</label>
          <div class="field-value currency-field">${{ formatCurrency(roeData.other_monies) }}</div>
        </div>
        
        <div class="field-group full-width">
          <label class="field-label">21. Expected Date of Recall / Date prévue de rappel</label>
          <div class="field-value date-field">{{ formatDate(roeData.expected_recall_date) }}</div>
        </div>
      </div>
    </div>

    <!-- Signature Section -->
    <div class="roe-section signature-section">
      <div class="section-title">CERTIFICATION / ATTESTATION</div>
      
      <div class="signature-grid">
        <div class="field-group">
          <label class="field-label">22. Name of Person Completing ROE / Nom de la personne qui remplit le relevé</label>
          <div class="field-value">{{ roeData.completed_by_name || 'Human Resources' }}</div>
        </div>
        
        <div class="field-group">
          <label class="field-label">23. Title / Titre</label>
          <div class="field-value">{{ roeData.completed_by_title || 'HR Manager' }}</div>
        </div>
        
        <div class="field-group">
          <label class="field-label">24. Telephone / Téléphone</label>
          <div class="field-value">{{ roeData.completed_by_phone || employerInfo.phone }}</div>
        </div>
        
        <div class="field-group">
          <label class="field-label">25. Date Completed / Date de production</label>
          <div class="field-value date-field">{{ formatDate(roeData.completed_date || new Date()) }}</div>
        </div>
        
        <div class="field-group signature-field">
          <label class="field-label">26. Signature</label>
          <div class="field-value signature-line"></div>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <div class="roe-footer">
      <div class="footer-text">
        <p><strong>IMPORTANT:</strong> This Record of Employment must be given to the employee immediately upon interruption of earnings.</p>
        <p><strong>IMPORTANT :</strong> Ce relevé d'emploi doit être remis à l'employé(e) immédiatement dès l'interruption de rémunération.</p>
      </div>
      
      <div class="footer-info">
        <div class="submission-info">
          <div v-if="roeData.roe_status === 'submitted'">
            <strong>Submitted to Service Canada:</strong> {{ formatDateTime(roeData.submitted_at) }}
          </div>
          <div v-else>
            <strong>Status:</strong> {{ formatROEStatus(roeData.roe_status) }}
          </div>
        </div>
        
        <div class="form-version">
          ROE Form Version: {{ new Date().getFullYear() }}.1
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ROEPrintTemplate',
  props: {
    roeData: {
      type: Object,
      required: true
    }
  },
  data() {
    return {
      employerInfo: {
        business_number: '123456789RC0001',
        company_name: 'Arrow Limousine Service',
        address_line1: '1234 Business Street',
        city: 'Red Deer',
        province: 'AB',
        postal_code: 'T4N 1A1',
        phone: '(403) 555-0123',
        email: 'info@arrowlimo.ca'
      }
    }
  },
  methods: {
    formatDate(dateString) {
      if (!dateString) return ''
      const date = new Date(dateString)
      return date.toLocaleDateString('en-CA', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
      })
    },
    
    formatDateTime(dateTimeString) {
      if (!dateTimeString) return ''
      const date = new Date(dateTimeString)
      return date.toLocaleDateString('en-CA', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    },
    
    formatCurrency(amount) {
      if (!amount) return '0.00'
      return parseFloat(amount).toLocaleString('en-CA', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      })
    },
    
    formatSIN(sin) {
      if (!sin) return '___-___-___'
      // Format SIN as XXX-XXX-XXX
      const digits = sin.replace(/\D/g, '')
      if (digits.length !== 9) return '___-___-___'
      return `${digits.slice(0,3)}-${digits.slice(3,6)}-${digits.slice(6,9)}`
    },
    
    formatPayPeriodType(type) {
      const types = {
        'weekly': 'Weekly / Hebdomadaire',
        'bi_weekly': 'Bi-weekly / Aux deux semaines',
        'semi_monthly': 'Semi-monthly / Bimensuel',
        'monthly': 'Monthly / Mensuel'
      }
      return types[type] || type
    },
    
    formatROEStatus(status) {
      const statuses = {
        'draft': 'Draft',
        'completed': 'Completed',
        'submitted': 'Submitted to Service Canada',
        'amended': 'Amended'
      }
      return statuses[status] || status
    },
    
    printROE() {
      window.print()
    }
  }
}
</script>

<style scoped>
/* Print-specific styles */
@media print {
  .roe-print-template {
    width: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
    box-shadow: none !important;
    background: white !important;
    color: black !important;
    font-size: 12px !important;
    line-height: 1.3 !important;
  }
  
  .roe-header,
  .roe-section {
    page-break-inside: avoid;
  }
  
  .pay-periods-table {
    page-break-inside: avoid;
  }
}

/* Main container */
.roe-print-template {
  max-width: 8.5in;
  margin: 0 auto;
  background: white;
  padding: 0.5in;
  font-family: 'Arial', sans-serif;
  font-size: 11px;
  line-height: 1.4;
  color: #000;
  box-shadow: 0 0 10px rgba(0,0,0,0.1);
}

/* Header styles */
.roe-header {
  display: grid;
  grid-template-columns: 2fr 1fr auto;
  gap: 20px;
  align-items: start;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 2px solid #000;
}

.roe-title h1 {
  font-size: 18px;
  font-weight: bold;
  margin: 0;
  color: #000;
}

.roe-title h2 {
  font-size: 14px;
  font-weight: normal;
  margin: 2px 0 0 0;
  color: #666;
  font-style: italic;
}

.roe-number {
  text-align: center;
  border: 2px solid #000;
  padding: 10px;
}

.roe-number-label {
  font-size: 9px;
  margin-bottom: 5px;
  color: #666;
}

.roe-number-value {
  font-size: 16px;
  font-weight: bold;
  color: #000;
}

.service-canada-logo {
  text-align: center;
  border: 1px solid #ccc;
  padding: 10px;
  background: #f5f5f5;
}

.logo-placeholder {
  font-weight: bold;
  color: #333;
}

/* Section styles */
.roe-section {
  margin-bottom: 25px;
  border: 1px solid #000;
}

.section-title {
  background: #000;
  color: white;
  padding: 8px 12px;
  font-weight: bold;
  font-size: 12px;
  margin: 0;
}

/* Grid layouts */
.employer-grid,
.employee-grid,
.employment-grid,
.reason-grid,
.earnings-grid,
.additional-grid,
.signature-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
  padding: 15px;
}

.field-group {
  display: flex;
  flex-direction: column;
}

.field-group.full-width {
  grid-column: 1 / -1;
}

.field-label {
  font-size: 9px;
  font-weight: bold;
  margin-bottom: 3px;
  color: #333;
  text-transform: uppercase;
}

.field-value {
  border: 1px solid #666;
  padding: 6px 8px;
  min-height: 20px;
  background: white;
  font-size: 11px;
  color: #000;
}

/* Special field styles */
.sin-field {
  font-family: 'Courier New', monospace;
  font-weight: bold;
  text-align: center;
  letter-spacing: 2px;
}

.date-field {
  font-family: 'Courier New', monospace;
  text-align: center;
}

.currency-field {
  text-align: right;
  font-weight: bold;
}

.hours-field {
  text-align: right;
}

.reason-code {
  font-size: 14px;
  font-weight: bold;
  text-align: center;
  background: #f0f0f0;
}

.signature-field .field-value {
  border-bottom: 1px solid #000;
  border-left: none;
  border-right: none;
  border-top: none;
  background: none;
  min-height: 30px;
}

/* Pay periods table */
.pay-periods-table {
  margin-top: 20px;
}

.table-title {
  background: #333;
  color: white;
  padding: 6px 12px;
  font-weight: bold;
  font-size: 10px;
  text-align: center;
}

.pay-periods {
  width: 100%;
  border-collapse: collapse;
  margin-top: 0;
}

.pay-periods th,
.pay-periods td {
  border: 1px solid #666;
  padding: 6px 8px;
  text-align: left;
  font-size: 10px;
}

.pay-periods th {
  background: #f0f0f0;
  font-weight: bold;
  text-align: center;
}

.pay-periods .text-right {
  text-align: right;
}

.pay-periods .empty-row {
  height: 25px;
}

.pay-periods .empty-row td {
  background: #fafafa;
}

/* Footer styles */
.roe-footer {
  margin-top: 30px;
  padding-top: 15px;
  border-top: 1px solid #ccc;
}

.footer-text {
  background: #fff3cd;
  border: 1px solid #ffc107;
  padding: 10px;
  margin-bottom: 15px;
}

.footer-text p {
  margin: 0 0 5px 0;
  font-size: 10px;
}

.footer-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 10px;
  color: #666;
}

.submission-info {
  font-weight: bold;
}

.form-version {
  font-style: italic;
}

/* Responsive adjustments */
@media (max-width: 8.5in) {
  .roe-print-template {
    padding: 0.25in;
  }
  
  .roe-header {
    grid-template-columns: 1fr;
    text-align: center;
  }
  
  .employer-grid,
  .employee-grid,
  .employment-grid,
  .signature-grid {
    grid-template-columns: 1fr;
  }
}
</style>