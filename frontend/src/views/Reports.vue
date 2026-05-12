<template>
  <div>
    <h1>📊 Reports Dashboard</h1>
    
    <!-- Report Categories -->
    <div class="report-categories">
      <button 
        v-for="category in categories" 
        :key="category.id"
        @click="activeCategory = category.id"
        :class="['category-button', { active: activeCategory === category.id }]"
      >
        {{ category.icon }} {{ category.name }}
      </button>
    </div>

    <!-- Financial Reports -->
    <div v-if="activeCategory === 'financial'" class="report-section">
      <h2>💰 Financial Reports</h2>
      
      <div class="reports-grid">
        <div class="report-card">
          <div class="report-header">
            <h3>📈 Revenue Analysis</h3>
            <span class="report-type">Financial</span>
          </div>
          <p>Comprehensive revenue breakdown by period, client, and service type</p>
          <div class="report-params">
            <span class="field-label">Period:</span>
            <select v-model="revenueParams.period">
              <option value="monthly">Monthly</option>
              <option value="quarterly">Quarterly</option>
              <option value="yearly">Yearly</option>
              <option value="custom">Custom Range</option>
            </select>
            <div v-if="revenueParams.period === 'custom'" class="date-range">
              <input v-model="revenueParams.startDate" type="date" />
              <input v-model="revenueParams.endDate" type="date" />
            </div>
          </div>
          <div class="report-actions">
            <button @click="generateReport('revenue-analysis')" class="btn-generate" :disabled="isGenerating['revenue-analysis']">
              {{ isGenerating['revenue-analysis'] ? 'Generating…' : 'Generate Report' }}
            </button>
            <button @click="exportReport('revenue-analysis')" class="btn-export" :disabled="isExporting['revenue-analysis']">
              {{ isExporting['revenue-analysis'] ? 'Exporting…' : 'Export CSV' }}
            </button>
          </div>
        </div>

        <div class="report-card">
          <div class="report-header">
            <h3>🧾 GST Reconciliation</h3>
            <span class="report-type">Tax</span>
          </div>
          <p>GST collected, paid, and year-end reconciliation reports</p>
          <div class="report-params">
            <span class="field-label">Report Type:</span>
            <select v-model="gstParams.type">
              <option value="collected">GST Collected</option>
              <option value="paid">GST Paid (Input Tax)</option>
              <option value="year-end">Year-End Reconciliation</option>
              <option value="extraction">GST Extraction Report</option>
            </select>
            <span class="field-label">Year:</span>
            <select v-model="gstParams.year">
              <option value="2025">2025</option>
              <option value="2024">2024</option>
              <option value="2023">2023</option>
            </select>
          </div>
          <div class="report-actions">
            <button @click="generateReport('gst-reconciliation')" class="btn-generate" :disabled="isGenerating['gst-reconciliation']">
              {{ isGenerating['gst-reconciliation'] ? 'Generating…' : 'Generate Report' }}
            </button>
            <button @click="exportReport('gst-reconciliation')" class="btn-export" :disabled="isExporting['gst-reconciliation']">
              {{ isExporting['gst-reconciliation'] ? 'Exporting…' : 'Export PDF' }}
            </button>
          </div>
        </div>

        <div class="report-card">
          <div class="report-header">
            <h3>💳 Payment Analysis</h3>
            <span class="report-type">Financial</span>
          </div>
          <p>Payment trends, outstanding amounts, and collection reports</p>
          <div class="report-params">
            <span class="field-label">Analysis Type:</span>
            <select v-model="paymentParams.type">
              <option value="trends">Payment Trends</option>
              <option value="outstanding">Outstanding Balances</option>
              <option value="collections">Collection Efficiency</option>
              <option value="unmatched">Unmatched Payments</option>
            </select>
          </div>
          <div class="report-actions">
            <button @click="generateReport('payment-analysis')" class="btn-generate" :disabled="isGenerating['payment-analysis']">
              {{ isGenerating['payment-analysis'] ? 'Generating…' : 'Generate Report' }}
            </button>
            <button @click="exportReport('payment-analysis')" class="btn-export" :disabled="isExporting['payment-analysis']">
              {{ isExporting['payment-analysis'] ? 'Exporting…' : 'Export CSV' }}
            </button>
          </div>
        </div>

        <div class="report-card">
          <div class="report-header">
            <h3>📋 Receipts & Expenses</h3>
            <span class="report-type">Financial</span>
          </div>
          <p>Detailed expense categorization and receipt reconciliation</p>
          <div class="report-params">
            <span class="field-label">Report Year:</span>
            <select v-model="expenseParams.year">
              <option value="2025">2025</option>
              <option value="2024">2024</option>
              <option value="2019">2019</option>
            </select>
            <span class="field-label">Detail Level:</span>
            <select v-model="expenseParams.detail">
              <option value="summary">Summary</option>
              <option value="detailed">Detailed</option>
              <option value="full">Full Report</option>
            </select>
          </div>
          <div class="report-actions">
            <button @click="generateReport('receipts-expenses')" class="btn-generate" :disabled="isGenerating['receipts-expenses']">
              {{ isGenerating['receipts-expenses'] ? 'Generating…' : 'Generate Report' }}
            </button>
            <button @click="exportReport('receipts-expenses')" class="btn-export" :disabled="isExporting['receipts-expenses']">
              {{ isExporting['receipts-expenses'] ? 'Exporting…' : 'Export PDF' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Operational Reports -->
    <div v-if="activeCategory === 'operational'" class="report-section">
      <h2>🚐 Operational Reports</h2>
      
      <div class="reports-grid">
        <div class="report-card">
          <div class="report-header">
            <h3>📊 Charter Analysis</h3>
            <span class="report-type">Operations</span>
          </div>
          <p>Comprehensive charter performance and booking analysis</p>
          <div class="report-params">
            <span class="field-label">Analysis Type:</span>
            <select v-model="charterParams.type">
              <option value="detailed">Detailed Charter Report</option>
              <option value="mega">Mega Charter Report</option>
              <option value="client-specific">Client-Specific Analysis</option>
              <option value="wtf-analysis">Problem Charter Analysis</option>
            </select>
            <span class="field-label">Date Range:</span>
            <input v-model="charterParams.startDate" type="date" />
            <input v-model="charterParams.endDate" type="date" />
          </div>
          <div class="report-actions">
            <button @click="generateReport('charter-analysis')" class="btn-generate" :disabled="isGenerating['charter-analysis']">
              {{ isGenerating['charter-analysis'] ? 'Generating…' : 'Generate Report' }}
            </button>
            <button @click="exportReport('charter-analysis')" class="btn-export" :disabled="isExporting['charter-analysis']">
              {{ isExporting['charter-analysis'] ? 'Exporting…' : 'Export PDF' }}
            </button>
          </div>
        </div>

        <div class="report-card">
          <div class="report-header">
            <h3>👥 Driver Performance</h3>
            <span class="report-type">HR</span>
          </div>
          <p>Driver hours, payroll, and performance metrics</p>
          <div class="report-params">
            <span class="field-label">Report Type:</span>
            <select v-model="driverParams.type">
              <option value="basic">Basic Driver Report</option>
              <option value="with-charters">Driver with Charters</option>
              <option value="with-wcb">Driver with WCB</option>
              <option value="performance">Performance Metrics</option>
            </select>
            <span class="field-label">Period:</span>
            <select v-model="driverParams.period">
              <option value="monthly">Monthly</option>
              <option value="quarterly">Quarterly</option>
              <option value="yearly">Yearly</option>
            </select>
          </div>
          <div class="report-actions">
            <button @click="generateReport('driver-performance')" class="btn-generate" :disabled="isGenerating['driver-performance']">
              {{ isGenerating['driver-performance'] ? 'Generating…' : 'Generate Report' }}
            </button>
            <button @click="exportReport('driver-performance')" class="btn-export" :disabled="isExporting['driver-performance']">
              {{ isExporting['driver-performance'] ? 'Exporting…' : 'Export PDF' }}
            </button>
          </div>
        </div>

        <div class="report-card">
          <div class="report-header">
            <h3>🚗 Fleet Utilization</h3>
            <span class="report-type">Fleet</span>
          </div>
          <p>Vehicle usage, maintenance, and efficiency reports</p>
          <div class="report-params">
            <span class="field-label">Vehicle Filter:</span>
            <select v-model="fleetParams.vehicle">
              <option value="all">All Vehicles</option>
              <option value="sedans">Sedans</option>
              <option value="suvs">SUVs</option>
              <option value="vans">Vans</option>
            </select>
            <span class="field-label">Metric:</span>
            <select v-model="fleetParams.metric">
              <option value="utilization">Utilization Rate</option>
              <option value="mileage">Mileage Analysis</option>
              <option value="maintenance">Maintenance Costs</option>
              <option value="efficiency">Fuel Efficiency</option>
            </select>
          </div>
          <div class="report-actions">
            <button @click="generateReport('fleet-utilization')" class="btn-generate" :disabled="isGenerating['fleet-utilization']">
              {{ isGenerating['fleet-utilization'] ? 'Generating…' : 'Generate Report' }}
            </button>
            <button @click="exportReport('fleet-utilization')" class="btn-export" :disabled="isExporting['fleet-utilization']">
              {{ isExporting['fleet-utilization'] ? 'Exporting…' : 'Export CSV' }}
            </button>
          </div>
        </div>

        <div class="report-card">
          <div class="report-header">
            <h3>📈 Booking Trends</h3>
            <span class="report-type">Analytics</span>
          </div>
          <p>Booking patterns, seasonal trends, and demand forecasting</p>
          <div class="report-params">
            <span class="field-label">Trend Type:</span>
            <select v-model="bookingParams.type">
              <option value="seasonal">Seasonal Patterns</option>
              <option value="client-trends">Client Booking Trends</option>
              <option value="demand-forecast">Demand Forecasting</option>
              <option value="route-analysis">Route Analysis</option>
            </select>
            <span class="field-label">Time Frame:</span>
            <select v-model="bookingParams.timeFrame">
              <option value="12months">Last 12 Months</option>
              <option value="24months">Last 24 Months</option>
              <option value="custom">Custom Period</option>
            </select>
          </div>
          <div class="report-actions">
            <button @click="generateReport('booking-trends')" class="btn-generate" :disabled="isGenerating['booking-trends']">
              {{ isGenerating['booking-trends'] ? 'Generating…' : 'Generate Report' }}
            </button>
            <button @click="exportReport('booking-trends')" class="btn-export" :disabled="isExporting['booking-trends']">
              {{ isExporting['booking-trends'] ? 'Exporting…' : 'Export PDF' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Compliance Reports -->
    <div v-if="activeCategory === 'compliance'" class="report-section">
      <h2>📋 Compliance Reports</h2>
      
      <div class="reports-grid">
        <div class="report-card">
          <div class="report-header">
            <h3>🏥 WCB Compliance</h3>
            <span class="report-type">Legal</span>
          </div>
          <p>Workers' Compensation Board reporting and compliance tracking</p>
          <div class="report-params">
            <span class="field-label">Report Type:</span>
            <select v-model="wcbParams.type">
              <option value="payment-search">Payment Search</option>
              <option value="coverage-report">Coverage Report</option>
              <option value="claims-history">Claims History</option>
              <option value="premium-analysis">Premium Analysis</option>
            </select>
          </div>
          <div class="report-actions">
            <button @click="generateReport('wcb-compliance')" class="btn-generate" :disabled="isGenerating['wcb-compliance']">
              {{ isGenerating['wcb-compliance'] ? 'Generating…' : 'Generate Report' }}
            </button>
            <button @click="exportReport('wcb-compliance')" class="btn-export" :disabled="isExporting['wcb-compliance']">
              {{ isExporting['wcb-compliance'] ? 'Exporting…' : 'Export PDF' }}
            </button>
          </div>
        </div>

        <div class="report-card">
          <div class="report-header">
            <h3>🔧 Vehicle Inspections</h3>
            <span class="report-type">Safety</span>
          </div>
          <p>Vehicle safety inspections and maintenance compliance</p>
          <div class="report-params">
            <span class="field-label">Inspection Type:</span>
            <select v-model="inspectionParams.type">
              <option value="safety">Safety Inspections</option>
              <option value="maintenance">Maintenance Records</option>
              <option value="compliance">Compliance Status</option>
              <option value="upcoming">Upcoming Due Dates</option>
            </select>
          </div>
          <div class="report-actions">
            <button @click="generateReport('vehicle-inspections')" class="btn-generate" :disabled="isGenerating['vehicle-inspections']">
              {{ isGenerating['vehicle-inspections'] ? 'Generating…' : 'Generate Report' }}
            </button>
            <button @click="exportReport('vehicle-inspections')" class="btn-export" :disabled="isExporting['vehicle-inspections']">
              {{ isExporting['vehicle-inspections'] ? 'Exporting…' : 'Export CSV' }}
            </button>
            <button @click="printPreTripBlank()" class="btn-export" style="background:#4a7c59;">
              🖨 Print Pre-Trip Form
            </button>
          </div>
        </div>

        <div class="report-card">
          <div class="report-header">
            <h3>🪪 License Tracking</h3>
            <span class="report-type">Legal</span>
          </div>
          <p>Driver license expiration and renewal tracking</p>
          <div class="report-params">
            <span class="field-label">License Type:</span>
            <select v-model="licenseParams.type">
              <option value="all">All Licenses</option>
              <option value="class-4">Class 4 Licenses</option>
              <option value="expiring">Expiring Soon</option>
              <option value="expired">Expired</option>
            </select>
          </div>
          <div class="report-actions">
            <button @click="generateReport('license-tracking')" class="btn-generate" :disabled="isGenerating['license-tracking']">
              {{ isGenerating['license-tracking'] ? 'Generating…' : 'Generate Report' }}
            </button>
            <button @click="exportReport('license-tracking')" class="btn-export" :disabled="isExporting['license-tracking']">
              {{ isExporting['license-tracking'] ? 'Exporting…' : 'Export PDF' }}
            </button>
          </div>
        </div>

        <div class="report-card">
          <div class="report-header">
            <h3>🛡️ Insurance Coverage</h3>
            <span class="report-type">Legal</span>
          </div>
          <p>Insurance policy tracking and coverage analysis</p>
          <div class="report-params">
            <span class="field-label">Coverage Type:</span>
            <select v-model="insuranceParams.type">
              <option value="vehicle">Vehicle Insurance</option>
              <option value="liability">Liability Coverage</option>
              <option value="comprehensive">Comprehensive Analysis</option>
              <option value="renewals">Upcoming Renewals</option>
            </select>
          </div>
          <div class="report-actions">
            <button @click="generateReport('insurance-coverage')" class="btn-generate" :disabled="isGenerating['insurance-coverage']">
              {{ isGenerating['insurance-coverage'] ? 'Generating…' : 'Generate Report' }}
            </button>
            <button @click="exportReport('insurance-coverage')" class="btn-export" :disabled="isExporting['insurance-coverage']">
              {{ isExporting['insurance-coverage'] ? 'Exporting…' : 'Export PDF' }}
            </button>
          </div>
        </div>

        <div class="report-card highlight-card">
          <div class="report-header">
            <h3>🏛️ CRA Audit Export</h3>
            <span class="report-type">Government</span>
          </div>
          <p>Generate official CRA audit format export (XML) for tax compliance and government audits</p>
          <div class="report-params">
            <span class="field-label">Date Range:</span>
            <div class="date-range">
              <input v-model="craParams.startDate" type="date" placeholder="Start Date" />
              <span style="padding: 0 8px;">to</span>
              <input v-model="craParams.endDate" type="date" placeholder="End Date" />
            </div>
            <span class="field-label field-label-spaced">Export Type:</span>
            <select v-model="craParams.exportType">
              <option value="full">Full Export (All Files)</option>
              <option value="transactions">Transactions Only</option>
              <option value="summary">Summary (No Transactions)</option>
            </select>
            <div class="info-box" style="margin-top: 12px;">
              <strong>Includes:</strong> Accounts, Vendors, Employees, Transactions, Trial Balance<br>
              <strong>Format:</strong> XML (audit-compatible)<br>
              <strong>Records:</strong> 128,786 transactions • 757 vendors • 55 employees
            </div>
          </div>
          <div class="report-actions">
            <button @click="generateCRAExport()" class="btn-generate highlight-btn" :disabled="isGenerating['cra-audit']">
              {{ isGenerating['cra-audit'] ? 'Generating…' : '📥 Generate CRA Export' }}
            </button>
            <button @click="downloadCRAExport()" class="btn-export" :disabled="!craExportReady || isExporting['cra-audit']">
              {{ isExporting['cra-audit'] ? 'Downloading…' : '⬇️ Download ZIP' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Accounting Export Dashboard -->
    <div v-if="activeCategory === 'accounting-exports'" class="report-section">
      <h2>📗 Accounting Export Dashboard</h2>
      
      <div class="accounting-intro-card">
        <h3>💼 Accounting System Integration</h3>
        <p>Export your ALMS data in accounting-compatible format for seamless import into your reporting system.</p>
        <p><strong>Column names are export-ready</strong> to minimize manual mapping.</p>
      </div>

      <div class="accounting-status-bar" v-if="accountingExportStatus">
        <div v-if="accountingExportStatus.status === 'ready'" class="status-ready">
          ✅ Accounting export views ready: {{ accountingExportStatus.total_views }} views available
        </div>
        <div v-else-if="accountingExportStatus.status === 'not_initialized'" class="status-error">
          ⚠️ Accounting export views not initialized. Run migration script first.
        </div>
        <div v-else class="status-loading">
          ⏳ Loading export status...
        </div>
      </div>

      <!-- Export All Section -->
      <div class="accounting-export-all-section">
        <div class="report-card highlight-card">
          <div class="report-header">
            <h3>📦 Export All Accounting Data</h3>
            <span class="report-type">Complete Package</span>
          </div>
          <p>Export all data tables in a single ZIP file for complete accounting import</p>
          
          <div class="report-params">
            <span class="field-label">Date Range (Optional - applies to dated tables):</span>
            <div class="date-range">
              <input v-model="accountingParams.startDate" type="date" placeholder="Start Date" />
              <span style="padding: 0 8px;">to</span>
              <input v-model="accountingParams.endDate" type="date" placeholder="End Date" />
            </div>
            <div class="info-box" style="margin-top: 12px;">
              <strong>Includes:</strong> Chart of Accounts, Customers, Vendors, Employees, Journal Entries, A/R Aging, P&L, Balance Sheet, Vehicles, Invoices<br>
              <strong>Format:</strong> CSV files in ZIP archive<br>
              <strong>Ready for:</strong> Direct import into accounting tools
            </div>
          </div>
          
          <div class="report-actions">
            <button @click="exportAllAccountingData()" class="btn-generate highlight-btn" :disabled="isGenerating['accounting-export-all']">
              {{ isGenerating['accounting-export-all'] ? 'Generating…' : '📦 Export All Data (ZIP)' }}
            </button>
            <button @click="refreshAccountingExportStatus()" class="btn-export">
              🔄 Refresh Status
            </button>
          </div>
        </div>
      </div>

      <!-- Individual Export Cards -->
      <h3 style="margin-top: 2rem; margin-bottom: 1rem;">📋 Individual Exports</h3>
      <div class="reports-grid">
        <!-- Chart of Accounts -->
        <div class="report-card">
          <div class="report-header">
            <h3>📊 Chart of Accounts</h3>
            <span class="report-type">Setup</span>
          </div>
          <p>Account structure with types, numbers, and descriptions</p>
          <div class="accounting-record-count" v-if="getAccountingViewInfo('qb_export_chart_of_accounts')">
            {{ getAccountingViewInfo('qb_export_chart_of_accounts').record_count.toLocaleString() }} accounts
          </div>
          <div class="report-actions">
            <button @click="exportAccountingView('qb_export_chart_of_accounts')" class="btn-export" :disabled="isExporting['qb_export_chart_of_accounts']">
              {{ isExporting['qb_export_chart_of_accounts'] ? 'Exporting…' : '📥 Export CSV' }}
            </button>
          </div>
        </div>

        <!-- General Journal -->
        <div class="report-card">
          <div class="report-header">
            <h3>📖 General Journal</h3>
            <span class="report-type">Transactions</span>
          </div>
          <p>Complete transaction history with debits and credits</p>
          <div class="accounting-record-count" v-if="getAccountingViewInfo('qb_export_general_journal')">
            {{ getAccountingViewInfo('qb_export_general_journal').record_count.toLocaleString() }} transactions
          </div>
          <div class="report-params">
            <div class="date-range-compact">
              <input v-model="accountingIndividualDates.journal.startDate" type="date" placeholder="From" />
              <input v-model="accountingIndividualDates.journal.endDate" type="date" placeholder="To" />
            </div>
          </div>
          <div class="report-actions">
            <button @click="exportAccountingView('qb_export_general_journal', accountingIndividualDates.journal)" class="btn-export" :disabled="isExporting['qb_export_general_journal']">
              {{ isExporting['qb_export_general_journal'] ? 'Exporting…' : '📥 Export CSV' }}
            </button>
          </div>
        </div>

        <!-- Customers -->
        <div class="report-card">
          <div class="report-header">
            <h3>👥 Customer List</h3>
            <span class="report-type">Master Data</span>
          </div>
          <p>Complete customer contact information and account numbers</p>
          <div class="accounting-record-count" v-if="getAccountingViewInfo('qb_export_customers')">
            {{ getAccountingViewInfo('qb_export_customers').record_count.toLocaleString() }} customers
          </div>
          <div class="report-actions">
            <button @click="exportAccountingView('qb_export_customers')" class="btn-export" :disabled="isExporting['qb_export_customers']">
              {{ isExporting['qb_export_customers'] ? 'Exporting…' : '📥 Export CSV' }}
            </button>
          </div>
        </div>

        <!-- Vendors -->
        <div class="report-card">
          <div class="report-header">
            <h3>🏢 Vendor List</h3>
            <span class="report-type">Master Data</span>
          </div>
          <p>Supplier and vendor contact information</p>
          <div class="accounting-record-count" v-if="getAccountingViewInfo('qb_export_vendors')">
            {{ getAccountingViewInfo('qb_export_vendors').record_count.toLocaleString() }} vendors
          </div>
          <div class="report-actions">
            <button @click="exportAccountingView('qb_export_vendors')" class="btn-export" :disabled="isExporting['qb_export_vendors']">
              {{ isExporting['qb_export_vendors'] ? 'Exporting…' : '📥 Export CSV' }}
            </button>
          </div>
        </div>

        <!-- Employees -->
        <div class="report-card">
          <div class="report-header">
            <h3>👨‍💼 Employee List</h3>
            <span class="report-type">Payroll</span>
          </div>
          <p>Employee records for payroll setup</p>
          <div class="accounting-record-count" v-if="getAccountingViewInfo('qb_export_employees')">
            {{ getAccountingViewInfo('qb_export_employees').record_count.toLocaleString() }} employees
          </div>
          <div class="report-actions">
            <button @click="exportAccountingView('qb_export_employees')" class="btn-export" :disabled="isExporting['qb_export_employees']">
              {{ isExporting['qb_export_employees'] ? 'Exporting…' : '📥 Export CSV' }}
            </button>
          </div>
        </div>

        <!-- A/R Aging -->
        <div class="report-card">
          <div class="report-header">
            <h3>📅 A/R Aging Report</h3>
            <span class="report-type">Receivables</span>
          </div>
          <p>Customer balances by aging period (Current, 1-30, 31-60, 61-90)</p>
          <div class="accounting-record-count" v-if="getAccountingViewInfo('qb_export_ar_aging')">
            {{ getAccountingViewInfo('qb_export_ar_aging').record_count.toLocaleString() }} customer balances
          </div>
          <div class="report-actions">
            <button @click="exportAccountingView('qb_export_ar_aging')" class="btn-export" :disabled="isExporting['qb_export_ar_aging']">
              {{ isExporting['qb_export_ar_aging'] ? 'Exporting…' : '📥 Export CSV' }}
            </button>
          </div>
        </div>

        <!-- Profit & Loss -->
        <div class="report-card">
          <div class="report-header">
            <h3>💰 Profit & Loss</h3>
            <span class="report-type">Financial</span>
          </div>
          <p>Income and expense summary by account</p>
          <div class="accounting-record-count" v-if="getAccountingViewInfo('qb_export_profit_loss')">
            {{ getAccountingViewInfo('qb_export_profit_loss').record_count.toLocaleString() }} line items
          </div>
          <div class="report-actions">
            <button @click="exportAccountingView('qb_export_profit_loss')" class="btn-export" :disabled="isExporting['qb_export_profit_loss']">
              {{ isExporting['qb_export_profit_loss'] ? 'Exporting…' : '📥 Export CSV' }}
            </button>
          </div>
        </div>

        <!-- Balance Sheet -->
        <div class="report-card">
          <div class="report-header">
            <h3>⚖️ Balance Sheet</h3>
            <span class="report-type">Financial</span>
          </div>
          <p>Assets, liabilities, and equity by account</p>
          <div class="accounting-record-count" v-if="getAccountingViewInfo('qb_export_balance_sheet')">
            {{ getAccountingViewInfo('qb_export_balance_sheet').record_count.toLocaleString() }} line items
          </div>
          <div class="report-actions">
            <button @click="exportAccountingView('qb_export_balance_sheet')" class="btn-export" :disabled="isExporting['qb_export_balance_sheet']">
              {{ isExporting['qb_export_balance_sheet'] ? 'Exporting…' : '📥 Export CSV' }}
            </button>
          </div>
        </div>

        <!-- Vehicles -->
        <div class="report-card">
          <div class="report-header">
            <h3>🚐 Vehicle List</h3>
            <span class="report-type">Fixed Assets</span>
          </div>
          <p>Fleet vehicles for fixed asset tracking</p>
          <div class="accounting-record-count" v-if="getAccountingViewInfo('qb_export_vehicles')">
            {{ getAccountingViewInfo('qb_export_vehicles').record_count.toLocaleString() }} vehicles
          </div>
          <div class="report-actions">
            <button @click="exportAccountingView('qb_export_vehicles')" class="btn-export" :disabled="isExporting['qb_export_vehicles']">
              {{ isExporting['qb_export_vehicles'] ? 'Exporting…' : '📥 Export CSV' }}
            </button>
          </div>
        </div>

        <!-- Invoices -->
        <div class="report-card">
          <div class="report-header">
            <h3>🧾 Invoice List</h3>
            <span class="report-type">Billing</span>
          </div>
          <p>Customer invoices with payment status</p>
          <div class="accounting-record-count" v-if="getAccountingViewInfo('qb_export_invoices')">
            {{ getAccountingViewInfo('qb_export_invoices').record_count.toLocaleString() }} invoices
          </div>
          <div class="report-params">
            <div class="date-range-compact">
              <input v-model="accountingIndividualDates.invoices.startDate" type="date" placeholder="From" />
              <input v-model="accountingIndividualDates.invoices.endDate" type="date" placeholder="To" />
            </div>
          </div>
          <div class="report-actions">
            <button @click="exportAccountingView('qb_export_invoices', accountingIndividualDates.invoices)" class="btn-export" :disabled="isExporting['qb_export_invoices']">
              {{ isExporting['qb_export_invoices'] ? 'Exporting…' : '📥 Export CSV' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Import Instructions -->
      <div class="accounting-import-instructions">
        <h3>📖 Import Instructions</h3>
        <ol>
          <li>Export the data you need using the buttons above</li>
          <li>Open your accounting application</li>
          <li>Go to <strong>File → Utilities → Import → Excel Files</strong></li>
          <li>Select the CSV file you downloaded</li>
          <li>Follow the import wizard (column names already match!)</li>
          <li>Review and confirm the import</li>
        </ol>
        <div class="info-box">
          <strong>💡 Tips:</strong>
          <ul>
            <li>Start with Chart of Accounts before importing transactions</li>
            <li>Import Customers and Vendors before invoices</li>
            <li>Use date filters to export specific periods</li>
            <li>Use "Export All" for complete data migration</li>
          </ul>
        </div>
      </div>

      <div class="accounting-admin-grid">
        <div class="accounting-admin-card">
          <h3>🧩 GL Classification Rules</h3>
          <p>Create and maintain rules to organize ledger rows by pattern and assign GL codes.</p>

          <div class="rule-form-grid">
            <input v-model="ruleForm.rule_name" type="text" placeholder="Rule name" />
            <select v-model="ruleForm.match_field">
              <option value="name">Name</option>
              <option value="memo_description">Memo</option>
              <option value="account_name">Account Name</option>
              <option value="supplier">Supplier</option>
              <option value="customer">Customer</option>
              <option value="employee">Employee</option>
              <option value="transaction_type">Transaction Type</option>
            </select>
            <input v-model="ruleForm.match_pattern" type="text" placeholder="Pattern (contains match)" />
            <input v-model="ruleForm.gl_code" type="text" placeholder="GL code" />
            <input v-model="ruleForm.account_type" type="text" placeholder="Account type (optional)" />
            <input v-model.number="ruleForm.sort_order" type="number" min="0" max="10000" placeholder="Sort order" />
            <label class="inline-toggle">
              <input v-model="ruleForm.is_active" type="checkbox" /> Active
            </label>
          </div>

          <div class="report-actions" style="margin-top: 12px;">
            <button @click="saveAccountingRule" class="btn-generate" :disabled="isSavingRule">
              {{ isSavingRule ? 'Saving…' : (editingRuleId ? 'Update Rule' : 'Create Rule') }}
            </button>
            <button @click="resetRuleForm" class="btn-export">
              Clear
            </button>
          </div>

          <div class="rules-list">
            <div v-if="!accountingRules.length" class="rules-empty">No rules yet.</div>
            <div v-for="rule in accountingRules" :key="rule.rule_id" class="rule-item">
              <div class="rule-main">
                <strong>{{ rule.rule_name }}</strong>
                <span class="rule-pill">{{ rule.match_field }}</span>
                <span class="rule-pill">{{ rule.match_pattern }}</span>
                <span class="rule-pill">GL {{ rule.gl_code }}</span>
              </div>
              <div class="rule-actions">
                <button @click="startEditRule(rule)" class="btn-load">Edit</button>
                <button @click="deleteAccountingRule(rule.rule_id)" class="btn-delete">Delete</button>
              </div>
            </div>
          </div>
        </div>

        <div class="accounting-admin-card">
          <h3>🛠 Bulk Reclassify</h3>
          <p>Move data and correct GL/account assignments in bulk.</p>

          <div class="form-group">
            <span class="field-label">Receipt IDs (comma-separated)</span>
            <input v-model="reclassifyForm.receipt_ids" type="text" placeholder="e.g. 101,102,103" />
          </div>
          <div class="form-group">
            <span class="field-label">GL Code</span>
            <input v-model="reclassifyForm.gl_code" type="text" placeholder="e.g. 4100" />
          </div>
          <button @click="applyReceiptReclassify" class="btn-generate" :disabled="isApplyingReclassify">
            {{ isApplyingReclassify ? 'Applying…' : 'Apply to Receipts' }}
          </button>

          <hr style="margin: 18px 0; border: none; border-top: 1px solid #e9ecef;" />

          <div class="form-group">
            <span class="field-label">Ledger Row IDs (comma-separated)</span>
            <input v-model="reclassifyForm.ledger_ids" type="text" placeholder="e.g. 501,502,503" />
          </div>
          <div class="form-group">
            <span class="field-label">Account Name (optional)</span>
            <input v-model="reclassifyForm.account_name" type="text" placeholder="e.g. Fuel Expense" />
          </div>
          <div class="form-group">
            <span class="field-label">Account Type (optional)</span>
            <input v-model="reclassifyForm.account_type" type="text" placeholder="e.g. Expense" />
          </div>
          <button @click="applyLedgerReclassify" class="btn-generate" :disabled="isApplyingReclassify">
            {{ isApplyingReclassify ? 'Applying…' : 'Apply to Ledger Rows' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Custom Reports -->
    <div v-if="activeCategory === 'custom'" class="report-section">
      <h2>⚙️ Custom Reports</h2>
      
      <div class="custom-report-builder">
        <h3>Build Custom Report</h3>
        <div class="builder-form">
          <div class="form-group">
            <span class="field-label">Report Name:</span>
            <input v-model="customReport.name" type="text" placeholder="Enter report name" />
          </div>
          
          <div class="form-group">
            <span class="field-label">Data Source:</span>
            <select v-model="customReport.dataSource">
              <option value="">Select Data Source</option>
              <option value="charters">Charters</option>
              <option value="clients">Clients</option>
              <option value="vehicles">Vehicles</option>
              <option value="employees">Employees</option>
              <option value="payments">Payments</option>
              <option value="receipts">Receipts</option>
            </select>
          </div>
          
          <div class="form-group">
            <span class="field-label">Fields to Include:</span>
            <div class="field-checkboxes">
              <label v-for="field in getAvailableFields()" :key="field.id">
                <input v-model="customReport.fields" :value="field.id" type="checkbox" />
                {{ field.name }}
              </label>
            </div>
          </div>
          
          <div class="form-group">
            <span class="field-label">Filters:</span>
            <div class="filter-builder">
              <div v-for="(filter, index) in customReport.filters" :key="index" class="filter-row">
                <select v-model="filter.field">
                  <option value="">Select Field</option>
                  <option v-for="field in getFilterFields()" :key="field.id" :value="field.id">
                    {{ field.name }}
                  </option>
                </select>
                <select v-model="filter.operator">
                  <option value="equals">Equals</option>
                  <option value="contains">Contains</option>
                  <option value="greater">Greater Than</option>
                  <option value="less">Less Than</option>
                  <option value="between">Between</option>
                </select>
                <input v-model="filter.value" type="text" placeholder="Filter value" />
                <button @click="removeFilter(index)" class="btn-remove">Remove</button>
              </div>
              <button @click="addFilter" class="btn-add">Add Filter</button>
            </div>
          </div>
          
          <div class="form-group">
            <span class="field-label">Sort By:</span>
            <select v-model="customReport.sortBy">
              <option value="">No Sorting</option>
              <option v-for="field in getAvailableFields()" :key="field.id" :value="field.id">
                {{ field.name }}
              </option>
            </select>
            <select v-model="customReport.sortOrder">
              <option value="asc">Ascending</option>
              <option value="desc">Descending</option>
            </select>
          </div>
          
          <div class="custom-report-actions">
            <button @click="generateCustomReport" class="btn-generate" :disabled="isGenerating['custom']">
              {{ isGenerating['custom'] ? 'Generating…' : 'Generate Custom Report' }}
            </button>
            <button @click="saveCustomReport" class="btn-save" :disabled="isSavingTemplate">
              {{ isSavingTemplate ? 'Saving…' : 'Save Report Template' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Saved Custom Reports -->
      <div class="saved-reports">
        <h3>Saved Report Templates</h3>
        <div class="saved-reports-list">
          <div v-for="report in savedReports" :key="report.id" class="saved-report-item">
            <div class="report-info">
              <h4>{{ report.name }}</h4>
              <p>{{ report.description }}</p>
              <small>Created: {{ formatDate(report.created_at) }}</small>
            </div>
            <div class="report-actions">
              <button @click="loadCustomReport(report)" class="btn-load">Load</button>
              <button @click="runSavedReport(report)" class="btn-run">Run</button>
              <button @click="deleteSavedReport(report)" class="btn-delete">Delete</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Report Output -->
    <div v-if="reportOutput" class="report-output">
      <div class="output-header">
        <h3>📋 Report Results: {{ reportOutput.title }}</h3>
        <div class="output-actions">
          <button @click="downloadReport" class="btn-download">Download</button>
          <button @click="emailReport" class="btn-email">Email</button>
          <button @click="printReport" class="btn-print">Print</button>
          <button @click="closeReport" class="btn-close">Close</button>
        </div>
      </div>
      
      <div class="output-content">
        <div v-if="reportOutput.type === 'table'" class="table-output">
          <table>
            <thead>
              <tr>
                <th v-for="column in reportOutput.columns" :key="column">{{ column }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in reportOutput.data" :key="row.id">
                <td v-for="column in reportOutput.columns" :key="column">{{ row[column] }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        
        <div v-else-if="reportOutput.type === 'chart'" class="chart-output">
          <div v-if="chartPoints.length" class="mini-chart">
            <div class="mini-chart-bars">
              <div
                v-for="point in chartPoints"
                :key="point.label"
                class="mini-chart-bar-wrap"
              >
                <div class="mini-chart-value">{{ point.value.toLocaleString() }}</div>
                <div class="mini-chart-bar" :style="{ height: `${point.heightPct}%` }" :title="`${point.label}: ${point.value}`"></div>
                <div class="mini-chart-label">{{ point.shortLabel }}</div>
              </div>
            </div>
            <div class="mini-chart-meta">
              {{ reportOutput.chartType }} • {{ chartPoints.length }} points
            </div>
          </div>
          <div v-else class="chart-placeholder">
            No chartable numeric data found for this report.
          </div>
        </div>
        
        <div v-else class="text-output">
          <pre>{{ reportOutput.content }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { authFetch } from '@/utils/authFetch'
import { toast } from '@/toast/toastStore'

const activeCategory = ref('financial')
const reportOutput = ref(null)

const categories = [
  { id: 'financial', name: 'Financial', icon: '💰' },
  { id: 'operational', name: 'Operational', icon: '🚐' },
  { id: 'compliance', name: 'Compliance', icon: '📋' },
  { id: 'accounting-exports', name: 'Accounting Exports', icon: '📗' },
  { id: 'custom', name: 'Custom', icon: '⚙️' }
]

// Report parameters
const revenueParams = ref({ period: 'monthly', startDate: '', endDate: '' })
const gstParams = ref({ type: 'collected', year: '2025' })
const paymentParams = ref({ type: 'trends' })
const expenseParams = ref({ year: '2025', detail: 'summary' })
const charterParams = ref({ type: 'detailed', startDate: '', endDate: '' })
const driverParams = ref({ type: 'basic', period: 'monthly' })
const fleetParams = ref({ vehicle: 'all', metric: 'utilization' })
const bookingParams = ref({ type: 'seasonal', timeFrame: '12months' })
const wcbParams = ref({ type: 'payment-search' })
const inspectionParams = ref({ type: 'safety' })
const licenseParams = ref({ type: 'all' })
const insuranceParams = ref({ type: 'vehicle' })
const craParams = ref({ startDate: '', endDate: '', exportType: 'full' })
const craExportReady = ref(false)

// Accounting export parameters
const accountingParams = ref({ startDate: '', endDate: '' })
const accountingExportStatus = ref(null)
const accountingIndividualDates = ref({
  journal: { startDate: '', endDate: '' },
  invoices: { startDate: '', endDate: '' }
})

// Custom report builder
const customReport = ref({
  name: '',
  dataSource: '',
  fields: [],
  filters: [],
  sortBy: '',
  sortOrder: 'asc'
})

const savedReports = ref([])
const isGenerating = ref({})
const isExporting = ref({})
const isSavingTemplate = ref(false)
const accountingRules = ref([])
const editingRuleId = ref(null)
const isSavingRule = ref(false)
const isApplyingReclassify = ref(false)
const ruleForm = ref({
  rule_name: '',
  match_field: 'name',
  match_pattern: '',
  gl_code: '',
  account_type: '',
  sort_order: 100,
  is_active: true,
})
const reclassifyForm = ref({
  receipt_ids: '',
  ledger_ids: '',
  gl_code: '',
  account_name: '',
  account_type: '',
})

const chartPoints = computed(() => {
  const output = reportOutput.value
  if (!output || output.type !== 'chart' || !Array.isArray(output.data) || output.data.length === 0) {
    return []
  }

  const sample = output.data[0] || {}
  const keys = Object.keys(sample)
  if (!keys.length) return []

  const numericKey = keys.find((k) => typeof sample[k] === 'number') || keys[1]
  const labelKey = keys.find((k) => k !== numericKey) || keys[0]

  const raw = output.data
    .map((row) => {
      const value = Number(row[numericKey])
      if (!Number.isFinite(value)) return null
      const label = String(row[labelKey] ?? '')
      return { label, value }
    })
    .filter(Boolean)
    .slice(0, 24)

  if (!raw.length) return []
  const maxValue = Math.max(...raw.map((p) => Math.abs(p.value)), 1)
  return raw.map((p) => ({
    ...p,
    shortLabel: p.label.length > 12 ? `${p.label.slice(0, 11)}…` : p.label,
    heightPct: Math.max(6, Math.round((Math.abs(p.value) / maxValue) * 100)),
  }))
})

const isAccountingReady = computed(() => {
  return accountingExportStatus.value?.status === 'ready'
})

function getAvailableFields() {
  const fieldMap = {
    charters: [
      { id: 'charter_id', name: 'Charter ID' },
      { id: 'reserve_number', name: 'Reserve Number' },
      { id: 'charter_date', name: 'Charter Date' },
      { id: 'client_name', name: 'Client Name' },
      { id: 'total_amount_due', name: 'Total Amount' },
      { id: 'payment_status', name: 'Payment Status' }
    ],
    clients: [
      { id: 'client_id', name: 'Client ID' },
      { id: 'company_name', name: 'Company Name' },
      { id: 'contact_person', name: 'Contact Person' },
      { id: 'phone', name: 'Phone' },
      { id: 'email', name: 'Email' }
    ],
    vehicles: [
      { id: 'vehicle_id', name: 'Vehicle ID' },
      { id: 'make', name: 'Make' },
      { id: 'model', name: 'Model' },
      { id: 'year', name: 'Year' },
      { id: 'license_plate', name: 'License Plate' }
    ]
  }
  return fieldMap[customReport.value.dataSource] || []
}

function getFilterFields() {
  return getAvailableFields()
}

function addFilter() {
  customReport.value.filters.push({ field: '', operator: 'equals', value: '' })
}

function removeFilter(index) {
  customReport.value.filters.splice(index, 1)
}

async function generateReport(reportType) {
  if (isGenerating.value[reportType]) return
  isGenerating.value = { ...isGenerating.value, [reportType]: true }
  try {
    const today = new Date()
    const toISO = (d) => new Date(d).toISOString().slice(0, 10)
    const yearStart = (y) => `${y}-01-01`
    const yearEnd = (y) => `${y}-12-31`

    // Map frontend report card IDs → real backend endpoint + params
    const ENDPOINT_MAP = {
      // Financial
      'revenue-analysis':   () => {
        const p = new URLSearchParams({ limit: 500 })
        if (revenueParams.value.period === 'custom' && revenueParams.value.startDate) {
          p.set('start_date', revenueParams.value.startDate)
          p.set('end_date', revenueParams.value.endDate)
        }
        return ['/api/reports/income-summary', p]
      },
      'payment-analysis':   () => ['/api/reports/payment-list',       new URLSearchParams({ limit: 500 })],
      'receipts-expenses':  () => {
        const year = expenseParams.value.year || today.getFullYear()
        return ['/api/reports/invoiced-charges', new URLSearchParams({ start_date: yearStart(year), end_date: yearEnd(year), limit: 500 })]
      },
      // Operational
      'charter-analysis':   () => {
        const p = new URLSearchParams({ report_family: 'manifest', limit: 500 })
        if (charterParams.value.startDate) p.set('start_date', charterParams.value.startDate)
        if (charterParams.value.endDate)   p.set('end_date',   charterParams.value.endDate)
        return ['/api/reports/legacy-ops', p]
      },
      'driver-performance': () => {
        const p = new URLSearchParams({ limit: 500 })
        if (driverParams.value.period === 'monthly') {
          const start = new Date(today); start.setDate(1)
          p.set('start_date', toISO(start))
          p.set('end_date', toISO(today))
        }
        return ['/api/reports/driver-pay', p]
      },
      'fleet-utilization':  () => ['/api/reports/fleet',              new URLSearchParams({ limit: 500 })],
      'booking-trends':     () => {
        const end = today
        const start = new Date(end); start.setMonth(start.getMonth() - 12)
        return ['/api/reports/legacy-ops', new URLSearchParams({ report_family: 'sales_summary', start_date: toISO(start), end_date: toISO(end), limit: 500 })]
      },
      // Compliance
      'wcb-compliance':     () => ['/api/reports/driver-pay',         new URLSearchParams({ limit: 200 })],
      'vehicle-inspections':() => ['/api/reports/fleet',              new URLSearchParams({ limit: 200 })],
      'license-tracking':   () => ['/api/reports/fleet',              new URLSearchParams({ limit: 200 })],
      'insurance-coverage': () => ['/api/reports/vehicle-insurance-yearly', new URLSearchParams()],
      // Accounting / crystal
      'aged-receivables':   () => ['/api/reports/aged-receivables',   new URLSearchParams({ limit: 500 })],
      'income-summary':     () => ['/api/reports/income-summary',     new URLSearchParams({ limit: 500 })],
      'long-trip':          () => ['/api/reports/long-trip',          new URLSearchParams({ limit: 500 })],
      'short-trip':         () => ['/api/reports/short-trip',         new URLSearchParams({ limit: 500 })],
      'driver-pay':         () => ['/api/reports/driver-pay',         new URLSearchParams({ limit: 500 })],
      'invoiced-charges':   () => ['/api/reports/invoiced-charges',   new URLSearchParams({ limit: 500 })],
      'client-activity':    () => ['/api/reports/client-activity',    new URLSearchParams({ limit: 500 })],
      'pl-summary':         () => ['/api/reports/pl-summary',         new URLSearchParams()],
      'trial-balance':      () => ['/api/reports/trial-balance',      new URLSearchParams()],
      'bank-reconciliation':() => ['/api/reports/bank-reconciliation',new URLSearchParams({ limit: 500 })],
    }

    const builder = ENDPOINT_MAP[reportType]
    if (!builder) {
      toast.info(`"${reportType}" report coming soon`)
      return
    }

    const [url, params] = builder()
    const qs = params.toString() ? `?${params.toString()}` : ''
    const resp = await authFetch(`${url}${qs}`)
    if (!resp) return
    if (!resp.ok) {
      const detail = await resp.text().catch(() => resp.statusText)
      throw new Error(`Server error ${resp.status}: ${detail}`)
    }
    const json = await resp.json()

    // Normalise response into { columns, data }
    let rows = []
    if (Array.isArray(json)) {
      rows = json
    } else if (Array.isArray(json.items)) {
      rows = json.items
    } else if (Array.isArray(json.data)) {
      rows = json.data
    } else if (Array.isArray(json.rows)) {
      rows = json.rows
    } else if (Array.isArray(json.results)) {
      rows = json.results
    }

    const columns = rows.length > 0 ? Object.keys(rows[0]) : []
    const title = reportType
      .split('-')
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(' ')

    const chartableTypes = new Set(['booking-trends', 'revenue-analysis', 'payment-analysis'])
    const outputType = chartableTypes.has(reportType) ? 'chart' : 'table'

    reportOutput.value = {
      title: `${title} (${rows.length} rows)`,
      type: outputType,
      columns,
      data: rows,
      meta: json.totals || json.summary || null,
      reportType,
    }
    toast.success(`${title}: ${rows.length} rows loaded`)
  } catch (error) {
    console.error('Error generating report:', error)
    toast.error('Error generating report: ' + (error?.message || error))
  } finally {
    isGenerating.value = { ...isGenerating.value, [reportType]: false }
  }
}

const SUPPORTED_EXPORT_REPORTS = new Set([
  'revenue-analysis',
  'payment-analysis',
  'receipts-expenses',
  'charter-analysis',
  'fleet-utilization',
  'booking-trends',
])

function applyExportDateParams(reportType, params) {
  const today = new Date()
  const toISO = (d) => new Date(d).toISOString().slice(0, 10)

  const handlers = {
    'revenue-analysis': () => {
      if (
        revenueParams.value.period === 'custom' &&
        revenueParams.value.startDate &&
        revenueParams.value.endDate
      ) {
        params.set('start_date', revenueParams.value.startDate)
        params.set('end_date', revenueParams.value.endDate)
      }
    },
    'receipts-expenses': () => {
      const year = Number.parseInt(
        String(expenseParams.value.year || today.getFullYear()),
        10
      )
      params.set('start_date', `${year}-01-01`)
      params.set('end_date', `${year}-12-31`)
    },
    'charter-analysis': () => {
      if (charterParams.value.startDate) {
        params.set('start_date', charterParams.value.startDate)
      }
      if (charterParams.value.endDate) {
        params.set('end_date', charterParams.value.endDate)
      }
    },
    'booking-trends': () => {
      const end = today
      const start = new Date(end)
      start.setMonth(
        start.getMonth() - (bookingParams.value.timeFrame === '24months' ? 24 : 12)
      )
      params.set('start_date', toISO(start))
      params.set('end_date', toISO(end))
    },
    'fleet-utilization': () => {
      if (charterParams.value?.startDate) {
        params.set('start_date', charterParams.value.startDate)
      }
      if (charterParams.value?.endDate) {
        params.set('end_date', charterParams.value.endDate)
      }
    },
  }

  const handler = handlers[reportType]
  if (handler) {
    handler()
  }
}

function filenameFromResponse(resp, fallback = 'report.csv') {
  const cd = resp.headers.get('Content-Disposition') || ''
  const match = /filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i.exec(cd)
  if (!match) return fallback
  return decodeURIComponent(match[1] || match[2])
}

async function exportReport(reportType) {
  if (isExporting.value[reportType]) return
  isExporting.value = { ...isExporting.value, [reportType]: true }
  try {
    if (!SUPPORTED_EXPORT_REPORTS.has(reportType)) {
      toast.info(`${reportType} export coming soon`)
      return
    }

    const params = new URLSearchParams({ type: reportType, format: 'csv' })
    applyExportDateParams(reportType, params)

    const resp = await authFetch(`/api/reports/export?${params.toString()}`)
    if (!resp) return
    if (!resp.ok) {
      let msg = `${reportType} export failed (${resp.status})`
      try {
        const j = await resp.json()
        if (j?.error || j?.message) msg = `${msg}: ${j.error || j.message}`
      } catch {}
      throw new Error(msg)
    }

    const filename = filenameFromResponse(resp)
    const blob = await resp.blob()
    const blobUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = blobUrl
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(blobUrl)
    toast.success(`Exported ${filename}`)
  } catch (error) {
    console.error(error)
    toast.error('Export failed: ' + (error?.message || error))
  } finally {
    isExporting.value = { ...isExporting.value, [reportType]: false }
  }
}

function printPreTripBlank() {
  globalThis.open('/api/inspection-forms/pre-trip-blank', '_blank')
}

// CRA Audit Export functions
async function generateCRAExport() {
  if (isGenerating.value['cra-audit']) return
  isGenerating.value = { ...isGenerating.value, 'cra-audit': true }
  craExportReady.value = false
  
  try {
    const params = new URLSearchParams()
    params.set('export_type', craParams.value.exportType)
    if (craParams.value.startDate) params.set('start_date', craParams.value.startDate)
    if (craParams.value.endDate) params.set('end_date', craParams.value.endDate)
    
    const url = `/api/reports/cra-audit-export?${params.toString()}`
    const resp = await authFetch(url)
    if (!resp) return
    
    if (!resp.ok) {
      let msg = `CRA export failed (${resp.status})`
      try {
        const text = await resp.text()
        if (text) msg = `${msg}: ${text}`
      } catch {}
      throw new Error(msg)
    }
    
    // Extract filename from headers
    const cd = resp.headers.get('Content-Disposition') || ''
    let filename = 'CRA_Audit_Export.zip'
    const m = /filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i.exec(cd)
    if (m) filename = decodeURIComponent(m[1] || m[2])
    
    // Save blob for download
    const blob = await resp.blob()
    const blobUrl = URL.createObjectURL(blob)
    
    // Store for download button
    globalThis.craExportBlob = blobUrl
    globalThis.craExportFilename = filename
    craExportReady.value = true
    
    toast.success(`CRA Export generated successfully! (${(blob.size / 1024 / 1024).toFixed(1)} MB)`)
  } catch (error) {
    console.error('CRA export error:', error)
    toast.error('CRA export failed: ' + (error?.message || error))
  } finally {
    isGenerating.value = { ...isGenerating.value, 'cra-audit': false }
  }
}

async function downloadCRAExport() {
  if (!craExportReady.value || !globalThis.craExportBlob) {
    toast.error('Please generate the export first')
    return
  }
  
  isExporting.value = { ...isExporting.value, 'cra-audit': true }
  
  try {
    const a = document.createElement('a')
    a.href = globalThis.craExportBlob
    a.download = globalThis.craExportFilename || 'CRA_Audit_Export.zip'
    document.body.appendChild(a)
    a.click()
    a.remove()
    
    toast.success(`Downloaded ${a.download}`)
  } catch (error) {
    console.error('Download error:', error)
    toast.error('Download failed: ' + (error?.message || error))
  } finally {
    isExporting.value = { ...isExporting.value, 'cra-audit': false }
  }
}

// Accounting export functions
async function refreshAccountingExportStatus() {
  try {
    const resp = await authFetch('/api/reports/accounting/views')
    if (!resp) return
    if (!resp.ok) throw new Error(`Failed to fetch export status: ${resp.status}`)
    
    accountingExportStatus.value = await resp.json()
    
    if (accountingExportStatus.value.status === 'ready') {
      toast.success(`Accounting exports ready: ${accountingExportStatus.value.total_views} views available`)
    } else if (accountingExportStatus.value.status === 'not_initialized') {
      toast.warning('Accounting export views not initialized. Run migration script.')
    }
  } catch (error) {
    console.error('Accounting status error:', error)
    toast.error('Failed to load export status: ' + (error?.message || error))
  }
}

function getAccountingViewInfo(viewName) {
  if (!accountingExportStatus.value || !accountingExportStatus.value.views) return null
  return accountingExportStatus.value.views.find(v => v.view_name === viewName)
}

async function exportAccountingView(viewName, dateParams = null) {
  if (isExporting.value[viewName]) return
  if (!isAccountingReady.value) {
    toast.warning('Accounting export views are not initialized yet')
    return
  }
  isExporting.value = { ...isExporting.value, [viewName]: true }
  
  try {
    const params = new URLSearchParams()
    params.set('format', 'csv')
    
    if (dateParams) {
      if (dateParams.startDate) params.set('start_date', dateParams.startDate)
      if (dateParams.endDate) params.set('end_date', dateParams.endDate)
    }
    
    const url = `/api/reports/accounting/export/${viewName}?${params.toString()}`
    const resp = await authFetch(url)
    if (!resp) return
    
    if (!resp.ok) {
      let msg = `Export failed (${resp.status})`
      try {
        const text = await resp.text()
        if (text) msg = `${msg}: ${text}`
      } catch {}
      throw new Error(msg)
    }
    
    // Extract filename from headers
    const cd = resp.headers.get('Content-Disposition') || ''
    let filename = `${viewName}.csv`
    const m = /filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i.exec(cd)
    if (m) filename = decodeURIComponent(m[1] || m[2])
    
    // Download file
    const blob = await resp.blob()
    const blobUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = blobUrl
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(blobUrl)
    
    toast.success(`Downloaded ${filename} (${(blob.size / 1024).toFixed(1)} KB)`)
  } catch (error) {
    console.error('Accounting export error:', error)
    toast.error('Export failed: ' + (error?.message || error))
  } finally {
    isExporting.value = { ...isExporting.value, [viewName]: false }
  }
}

async function exportAllAccountingData() {
  if (isGenerating.value['accounting-export-all']) return
  if (!isAccountingReady.value) {
    toast.warning('Accounting export views are not initialized yet')
    return
  }
  isGenerating.value = { ...isGenerating.value, 'accounting-export-all': true }
  
  try {
    const params = new URLSearchParams()
    if (accountingParams.value.startDate) params.set('start_date', accountingParams.value.startDate)
    if (accountingParams.value.endDate) params.set('end_date', accountingParams.value.endDate)
    
    const url = `/api/reports/accounting/export-all?${params.toString()}`
    const resp = await authFetch(url)
    if (!resp) return
    
    if (!resp.ok) {
      let msg = `Export failed (${resp.status})`
      try {
        const text = await resp.text()
        if (text) msg = `${msg}: ${text}`
      } catch {}
      throw new Error(msg)
    }
    
    // Extract filename from headers
    const cd = resp.headers.get('Content-Disposition') || ''
    let filename = 'Accounting_Export.zip'
    const m = /filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i.exec(cd)
    if (m) filename = decodeURIComponent(m[1] || m[2])
    
    // Download file
    const blob = await resp.blob()
    const blobUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = blobUrl
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(blobUrl)
    
    toast.success(`Downloaded ${filename} (${(blob.size / 1024 / 1024).toFixed(1)} MB)`)
  } catch (error) {
    console.error('Accounting export-all error:', error)
    toast.error('Export failed: ' + (error?.message || error))
  } finally {
    isGenerating.value = { ...isGenerating.value, 'accounting-export-all': false }
  }
}

function generateCustomReport() {
  console.log('Generating custom report:', customReport.value)
  if (!customReport.value.name || !customReport.value.dataSource) {
    toast.error('Please enter a report name and select a data source')
    return
  }
  
  generateReport(
    'custom-' + customReport.value.name.toLowerCase().split(/\s+/).join('-')
  )
}

function saveCustomReport() {
  if (isSavingTemplate.value) return
  isSavingTemplate.value = true
  if (!customReport.value.name) {
    toast.error('Please enter a report name')
    isSavingTemplate.value = false
    return
  }
  
  const report = {
    id: Date.now(),
    name: customReport.value.name,
    description: `Custom report for ${customReport.value.dataSource}`,
    created_at: new Date().toISOString(),
    config: { ...customReport.value }
  }
  
  savedReports.value.push(report)
  toast.success('Report template saved successfully!')
  
  // Reset form
  customReport.value = {
    name: '',
    dataSource: '',
    fields: [],
    filters: [],
    sortBy: '',
    sortOrder: 'asc'
  }
  isSavingTemplate.value = false
}

function loadCustomReport(report) {
  customReport.value = { ...report.config }
}

function runSavedReport(report) {
  loadCustomReport(report)
  generateCustomReport()
}

function deleteSavedReport(report) {
  if (confirm(`Are you sure you want to delete the report "${report.name}"?`)) {
    savedReports.value = savedReports.value.filter(r => r.id !== report.id)
    toast.success('Report template deleted')
  }
}

function toCsv(columns, rows) {
  const esc = (v) => {
    const s = v == null ? '' : String(v)
    if (/[,"\n]/.test(s)) return `"${s.replaceAll('"', '""')}"`
    return s
  }
  const header = columns.map(esc).join(',')
  const body = rows.map((row) => columns.map((c) => esc(row[c])).join(',')).join('\n')
  return `${header}\n${body}`
}

function downloadBlob(content, filename, type = 'text/plain;charset=utf-8') {
  const blob = content instanceof Blob ? content : new Blob([content], { type })
  const href = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = href
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(href)
}

function downloadReport() {
  if (!reportOutput.value) {
    toast.error('No report to download')
    return
  }
  const slug = (reportOutput.value.title || 'report')
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter(Boolean)
    .join('-')

  if (reportOutput.value.type === 'table' || reportOutput.value.type === 'chart') {
    const csv = toCsv(reportOutput.value.columns || [], reportOutput.value.data || [])
    downloadBlob(csv, `${slug || 'report'}.csv`, 'text/csv;charset=utf-8')
    toast.success('Report downloaded')
    return
  }

  if (reportOutput.value.content) {
    downloadBlob(String(reportOutput.value.content), `${slug || 'report'}.txt`)
    toast.success('Report downloaded')
    return
  }

  toast.error('Nothing to download for this report')
}

function emailReport() {
  if (!reportOutput.value) {
    toast.error('No report selected')
    return
  }

  const subject = `ALMS Report: ${reportOutput.value.title || 'Report'}`
  const rowCount = Array.isArray(reportOutput.value.data) ? reportOutput.value.data.length : 0
  const bodyLines = [
    `Report: ${reportOutput.value.title || 'Report'}`,
    `Type: ${reportOutput.value.type || 'table'}`,
    `Rows: ${rowCount}`,
    '',
    'Downloaded from ALMS Reports Dashboard.',
    'Attach the exported CSV from the Download button if needed.',
  ]
  const mailto = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(bodyLines.join('\n'))}`
  globalThis.location.href = mailto
}

function printReport() {
  globalThis.print()
}

function closeReport() {
  reportOutput.value = null
}

function formatDate(dateString) {
  return new Date(dateString).toLocaleDateString()
}

async function loadAccountingRules() {
  try {
    const resp = await authFetch('/api/reports/accounting/rules')
    if (!resp) return
    if (!resp.ok) throw new Error(`Failed to load rules (${resp.status})`)
    const json = await resp.json()
    accountingRules.value = Array.isArray(json.items) ? json.items : []
  } catch (error) {
    console.error('Load accounting rules error:', error)
    toast.error('Failed to load accounting rules')
  }
}

function startEditRule(rule) {
  editingRuleId.value = rule.rule_id
  ruleForm.value = {
    rule_name: rule.rule_name || '',
    match_field: rule.match_field || 'name',
    match_pattern: rule.match_pattern || '',
    gl_code: rule.gl_code || '',
    account_type: rule.account_type || '',
    sort_order: Number(rule.sort_order || 100),
    is_active: Boolean(rule.is_active),
  }
}

function resetRuleForm() {
  editingRuleId.value = null
  ruleForm.value = {
    rule_name: '',
    match_field: 'name',
    match_pattern: '',
    gl_code: '',
    account_type: '',
    sort_order: 100,
    is_active: true,
  }
}

async function saveAccountingRule() {
  if (isSavingRule.value) return
  if (!ruleForm.value.rule_name || !ruleForm.value.match_pattern || !ruleForm.value.gl_code) {
    toast.error('Rule name, match pattern, and GL code are required')
    return
  }

  isSavingRule.value = true
  try {
    const method = editingRuleId.value ? 'PUT' : 'POST'
    const url = editingRuleId.value
      ? `/api/reports/accounting/rules/${editingRuleId.value}`
      : '/api/reports/accounting/rules'

    const resp = await authFetch(url, {
      method,
      body: JSON.stringify(ruleForm.value),
    })
    if (!resp) return
    if (!resp.ok) {
      const detail = await resp.text().catch(() => '')
      throw new Error(detail || `Failed to save rule (${resp.status})`)
    }

    await loadAccountingRules()
    resetRuleForm()
    toast.success('Accounting rule saved')
  } catch (error) {
    console.error('Save accounting rule error:', error)
    toast.error('Failed to save rule: ' + (error?.message || error))
  } finally {
    isSavingRule.value = false
  }
}

async function deleteAccountingRule(ruleId) {
  if (!confirm('Delete this accounting rule?')) return
  try {
    const resp = await authFetch(`/api/reports/accounting/rules/${ruleId}`, { method: 'DELETE' })
    if (!resp) return
    if (!resp.ok) {
      const detail = await resp.text().catch(() => '')
      throw new Error(detail || `Failed to delete rule (${resp.status})`)
    }
    await loadAccountingRules()
    if (editingRuleId.value === ruleId) resetRuleForm()
    toast.success('Accounting rule deleted')
  } catch (error) {
    console.error('Delete accounting rule error:', error)
    toast.error('Failed to delete rule: ' + (error?.message || error))
  }
}

function parseIds(input) {
  return String(input || '')
    .split(',')
    .map((v) => Number(v.trim()))
    .filter((n) => Number.isInteger(n) && n > 0)
}

async function applyReceiptReclassify() {
  const receiptIds = parseIds(reclassifyForm.value.receipt_ids)
  if (!receiptIds.length || !reclassifyForm.value.gl_code) {
    toast.error('Enter receipt IDs and a GL code')
    return
  }
  isApplyingReclassify.value = true
  try {
    const resp = await authFetch('/api/reports/accounting/reclassify/receipts', {
      method: 'POST',
      body: JSON.stringify({
        receipt_ids: receiptIds,
        gl_code: reclassifyForm.value.gl_code,
      }),
    })
    if (!resp) return
    if (!resp.ok) {
      const detail = await resp.text().catch(() => '')
      throw new Error(detail || `Failed to reclassify receipts (${resp.status})`)
    }
    const json = await resp.json()
    toast.success(`Updated ${json.updated_count || 0} receipt rows`)
  } catch (error) {
    console.error('Receipt reclassify error:', error)
    toast.error('Receipt reclassify failed: ' + (error?.message || error))
  } finally {
    isApplyingReclassify.value = false
  }
}

async function applyLedgerReclassify() {
  const ledgerIds = parseIds(reclassifyForm.value.ledger_ids)
  if (!ledgerIds.length) {
    toast.error('Enter ledger row IDs')
    return
  }
  if (!reclassifyForm.value.gl_code && !reclassifyForm.value.account_name && !reclassifyForm.value.account_type) {
    toast.error('Provide at least one field: GL code, account name, or account type')
    return
  }

  isApplyingReclassify.value = true
  try {
    const resp = await authFetch('/api/reports/accounting/reclassify/ledger', {
      method: 'POST',
      body: JSON.stringify({
        ledger_ids: ledgerIds,
        gl_code: reclassifyForm.value.gl_code || null,
        account_name: reclassifyForm.value.account_name || null,
        account_type: reclassifyForm.value.account_type || null,
      }),
    })
    if (!resp) return
    if (!resp.ok) {
      const detail = await resp.text().catch(() => '')
      throw new Error(detail || `Failed to reclassify ledger rows (${resp.status})`)
    }
    const json = await resp.json()
    toast.success(`Updated ${json.updated_count || 0} ledger rows`)
  } catch (error) {
    console.error('Ledger reclassify error:', error)
    toast.error('Ledger reclassify failed: ' + (error?.message || error))
  } finally {
    isApplyingReclassify.value = false
  }
}

onMounted(() => {
  // Load saved reports from localStorage or API
  const saved = localStorage.getItem('savedReports')
  if (saved) {
    savedReports.value = JSON.parse(saved)
  }
  
  // Load accounting export status
  refreshAccountingExportStatus()
  loadAccountingRules()
})

// Persist saved reports
watch(savedReports, (val) => {
  try { localStorage.setItem('savedReports', JSON.stringify(val)) } catch {}
}, { deep: true })
</script>

<style scoped>
.report-categories {
  display: flex;
  gap: 10px;
  margin-bottom: 30px;
  border-bottom: 2px solid #e9ecef;
}

.category-button {
  padding: 12px 24px;
  background: none;
  border: none;
  border-bottom: 3px solid transparent;
  cursor: pointer;
  font-weight: 500;
  color: #666;
  transition: all 0.3s;
}

.category-button:hover {
  color: #1e3a8a;
  background: #eef2ff;
}

.category-button.active {
  color: #1e3a8a;
  border-bottom-color: #1e3a8a;
  background: #e0e7ff;
}

.report-section {
  margin-bottom: 40px;
}

.reports-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 25px;
  margin-top: 20px;
}

.report-card {
  background: white;
  border-radius: 12px;
  padding: 25px;
  box-shadow: 0 4px 6px rgba(0,0,0,0.1);
  border-left: 5px solid #007bff;
}

.report-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 15px;
}

.report-header h3 {
  margin: 0;
  color: #333;
  font-size: 1.1rem;
}

.report-type {
  background: #dbeafe;
  color: #1e3a8a;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.8rem;
  font-weight: 500;
}

.report-card p {
  color: #666;
  margin-bottom: 20px;
  line-height: 1.5;
}

.report-params {
  margin-bottom: 20px;
}

.report-params label, .report-params .field-label {
  display: block;
  margin-bottom: 5px;
  font-weight: 500;
  color: #333;
}

.report-params select,
.report-params input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  margin-bottom: 10px;
}

.date-range {
  display: flex;
  gap: 10px;
}

.date-range input {
  flex: 1;
}

.report-actions {
  display: flex;
  gap: 10px;
}

.btn-generate, .btn-export, .btn-save, .btn-load, .btn-run, .btn-download, .btn-email, .btn-print, .btn-close {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.3s;
}

.btn-generate:disabled, .btn-export:disabled, .btn-save:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-generate { background: #22c55e; color: #0f172a; }
.btn-export { background: #38bdf8; color: #0f172a; }
.btn-save { background: #ffc107; color: black; }
.btn-load { background: #94a3b8; color: #0f172a; }
.btn-run { background: #60a5fa; color: #0f172a; }
.btn-download { background: #22c55e; color: #0f172a; }
.btn-email { background: #fb923c; color: #0f172a; }
.btn-print { background: #94a3b8; color: #0f172a; }
.btn-close { background: #f87171; color: #0f172a; }

.custom-report-builder {
  background: white;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 4px 6px rgba(0,0,0,0.1);
  margin-bottom: 30px;
}

.builder-form {
  max-width: 800px;
}

.form-group {
  margin-bottom: 25px;
}

.form-group label, .form-group .field-label {
  display: block;
  margin-bottom: 8px;
  font-weight: 600;
  color: #333;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 10px 15px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
}

.field-checkboxes {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 10px;
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid #eee;
  padding: 15px;
  border-radius: 6px;
}

.field-checkboxes label {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-weight: normal;
}

.filter-builder {
  border: 1px solid #eee;
  padding: 15px;
  border-radius: 6px;
}

.filter-row {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
  align-items: center;
}

.filter-row select,
.filter-row input {
  margin: 0;
}

.btn-add, .btn-remove {
  padding: 8px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
}

.btn-add { background: #22c55e; color: #0f172a; }
.btn-remove { background: #dc3545; color: white; }

.custom-report-actions {
  display: flex;
  gap: 15px;
  margin-top: 30px;
}

.saved-reports {
  background: white;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}

.saved-reports-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
  margin-top: 20px;
}

.saved-report-item {
  border: 1px solid #eee;
  border-radius: 8px;
  padding: 20px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.report-info h4 {
  margin: 0 0 8px 0;
  color: #333;
}

.report-info p {
  margin: 0 0 8px 0;
  color: #666;
  font-size: 0.9rem;
}

.report-info small {
  color: #999;
  font-size: 0.8rem;
}

.saved-reports .report-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.report-output {
  background: white;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 4px 6px rgba(0,0,0,0.1);
  margin-top: 30px;
}

.output-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 2px solid #eee;
}

.output-actions {
  display: flex;
  gap: 10px;
}

.output-content {
  max-height: 600px;
  overflow: auto;
}

.table-output table {
  width: 100%;
  border-collapse: collapse;
}

.table-output th,
.table-output td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #eee;
}

.table-output th {
  background: #f8f9fa;
  font-weight: 600;
  color: #333;
}

.table-output tr:hover {
  background: #f5f5f5;
}

.chart-placeholder {
  height: 400px;
  background: #f8f9fa;
  border: 2px dashed #ddd;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #666;
  font-size: 1.1rem;
  text-align: center;
}

.mini-chart {
  background: #f8f9fa;
  border: 1px solid #e9ecef;
  border-radius: 10px;
  padding: 16px;
}

.mini-chart-bars {
  height: 360px;
  display: flex;
  align-items: flex-end;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 6px;
}

.mini-chart-bar-wrap {
  min-width: 44px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.mini-chart-bar {
  width: 100%;
  background: linear-gradient(180deg, #37b24d 0%, #2f9e44 100%);
  border-radius: 6px 6px 0 0;
}

.mini-chart-value {
  font-size: 0.75rem;
  color: #495057;
  white-space: nowrap;
}

.mini-chart-label {
  font-size: 0.75rem;
  color: #343a40;
  text-align: center;
}

.mini-chart-meta {
  margin-top: 8px;
  font-size: 0.85rem;
  color: #6c757d;
}

.text-output pre {
  background: #f8f9fa;
  padding: 20px;
  border-radius: 6px;
  white-space: pre-wrap;
  word-wrap: break-word;
  max-height: 500px;
  overflow: auto;
}

h1, h2, h3 {
  color: #333;
  margin-bottom: 1rem;
}

/* CRA Audit Export Highlight Styles */
.highlight-card {
  border: 2px solid #28a745;
  box-shadow: 0 6px 16px rgba(40, 167, 69, 0.15);
  background: linear-gradient(135deg, #ffffff 0%, #f0fff4 100%);
}

.highlight-card .report-header {
  border-bottom: 2px solid #28a745;
  padding-bottom: 15px;
}

.highlight-card .report-header h3 {
  color: #155724;
  font-size: 1.3rem;
}

.highlight-btn {
  background: #28a745 !important;
  font-size: 1.05rem;
  padding: 10px 20px !important;
  box-shadow: 0 2px 8px rgba(40, 167, 69, 0.3);
}

.highlight-btn:hover:not(:disabled) {
  background: #218838 !important;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(40, 167, 69, 0.4);
}

.info-box {
  background: #e7f7ef;
  border: 1px solid #c3e6cb;
  border-radius: 6px;
  padding: 12px 15px;
  font-size: 0.9rem;
  line-height: 1.6;
  color: #155724;
}

/* Accounting Export Dashboard Styles */
.accounting-intro-card {
  background: linear-gradient(135deg, #2c7a2f 0%, #3ea643 100%);
  color: white;
  padding: 30px;
  border-radius: 12px;
  margin-bottom: 25px;
  box-shadow: 0 4px 12px rgba(44, 122, 47, 0.3);
}

.accounting-intro-card h3 {
  color: white;
  margin-top: 0;
  margin-bottom: 15px;
  font-size: 1.5rem;
}

.accounting-intro-card p {
  color: rgba(255, 255, 255, 0.95);
  margin-bottom: 10px;
  font-size: 1rem;
}

.accounting-status-bar {
  background: white;
  border-radius: 8px;
  padding: 15px 20px;
  margin-bottom: 25px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.status-ready {
  color: #28a745;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 10px;
}

.status-error {
  color: #dc3545;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 10px;
}

.status-loading {
  color: #6c757d;
  display: flex;
  align-items: center;
  gap: 10px;
}

.accounting-export-all-section {
  margin-bottom: 30px;
}

.accounting-record-count {
  background: #e9f7ef;
  color: #2c7a2f;
  padding: 8px 12px;
  border-radius: 6px;
  font-weight: 600;
  font-size: 0.9rem;
  margin-bottom: 15px;
  display: inline-block;
}

.date-range-compact {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.date-range-compact input {
  flex: 1;
  padding: 8px;
  border: 1px solid #ced4da;
  border-radius: 4px;
  font-size: 0.9rem;
}

.accounting-import-instructions {
  background: white;
  padding: 30px;
  border-radius: 12px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  margin-top: 40px;
}

.accounting-import-instructions h3 {
  color: #2c7a2f;
  margin-top: 0;
  margin-bottom: 20px;
}

.accounting-import-instructions ol {
  margin-bottom: 20px;
  line-height: 2;
  font-size: 1rem;
}

.accounting-import-instructions ol li {
  margin-bottom: 10px;
  color: #333;
}

.accounting-import-instructions .info-box {
  background: #fff8e1;
  border: 1px solid #ffc107;
  color: #856404;
}

.accounting-import-instructions .info-box ul {
  margin: 10px 0 0 0;
  padding-left: 20px;
}

.accounting-import-instructions .info-box ul li {
  margin-bottom: 8px;
}

.accounting-admin-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 18px;
  margin-top: 24px;
}

.accounting-admin-card {
  background: #fff;
  border: 1px solid #e9ecef;
  border-radius: 12px;
  padding: 18px;
}

.rule-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.rule-form-grid input,
.rule-form-grid select {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #ced4da;
  border-radius: 6px;
}

.inline-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}

.rules-list {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 320px;
  overflow: auto;
}

.rules-empty {
  color: #6c757d;
  font-size: 0.9rem;
}

.rule-item {
  border: 1px solid #e9ecef;
  border-radius: 8px;
  padding: 10px;
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.rule-main {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.rule-pill {
  background: #edf2ff;
  color: #364fc7;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 0.78rem;
}

.rule-actions {
  display: flex;
  gap: 6px;
}

.btn-delete {
  background: #dc3545;
  color: #fff;
}
</style>
