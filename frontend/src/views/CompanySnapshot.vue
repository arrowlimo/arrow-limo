<template>
  <div class="company-snapshot">
    <div class="snapshot-header">
      <h1>📊 Company Snapshot Report</h1>
      <p class="subtitle">Interactive drill-down financial and operational overview</p>
    </div>

    <!-- Report Controls -->
    <div class="report-controls">
      <div class="control-group">
        <label>Date Range:</label>
        <select v-model="dateRange" @change="loadData">
          <option value="today">Today</option>
          <option value="wtd">Week to Date</option>
          <option value="mtd">Month to Date</option>
          <option value="qtd">Quarter to Date</option>
          <option value="ytd">Year to Date</option>
          <option value="all">All Time</option>
          <option value="custom">Custom Range</option>
        </select>
        <div v-if="dateRange === 'custom'" class="date-inputs">
          <input v-model="customStart" type="date" @change="loadData" />
          <span>to</span>
          <input v-model="customEnd" type="date" @change="loadData" />
        </div>
      </div>

      <div class="control-group">
        <button @click="expandAll" class="btn-control">
          📂 Expand All
        </button>
        <button @click="collapseAll" class="btn-control">
          📁 Collapse All
        </button>
        <button @click="showColumnManager = true" class="btn-control">
          ⚙️ Manage Columns
        </button>
        <button @click="exportReport" class="btn-control btn-export">
          📥 Export to Excel
        </button>
      </div>
    </div>

    <!-- Summary Cards -->
    <div class="summary-cards">
      <div class="summary-card revenue">
        <div class="card-icon">💰</div>
        <div class="card-content">
          <h3>Total Revenue</h3>
          <div class="card-value">{{ formatCurrency(totals.revenue) }}</div>
          <div class="card-change" :class="totals.revenueChange >= 0 ? 'positive' : 'negative'">
            {{ totals.revenueChange >= 0 ? '↑' : '↓' }} {{ Math.abs(totals.revenueChange) }}% vs prior period
          </div>
        </div>
      </div>

      <div class="summary-card expenses">
        <div class="card-icon">💸</div>
        <div class="card-content">
          <h3>Total Expenses</h3>
          <div class="card-value">{{ formatCurrency(totals.expenses) }}</div>
          <div class="card-change" :class="totals.expensesChange <= 0 ? 'positive' : 'negative'">
            {{ totals.expensesChange >= 0 ? '↑' : '↓' }} {{ Math.abs(totals.expensesChange) }}% vs prior period
          </div>
        </div>
      </div>

      <div class="summary-card profit">
        <div class="card-icon">📈</div>
        <div class="card-content">
          <h3>Net Profit</h3>
          <div class="card-value" :class="totals.profit >= 0 ? 'positive' : 'negative'">
            {{ formatCurrency(totals.profit) }}
          </div>
          <div class="card-subtext">Margin: {{ totals.profitMargin }}%</div>
        </div>
      </div>

      <div class="summary-card charters">
        <div class="card-icon">🚐</div>
        <div class="card-content">
          <h3>Total Charters</h3>
          <div class="card-value">{{ totals.charters.toLocaleString() }}</div>
          <div class="card-subtext">{{ totals.activeVehicles }} active vehicles</div>
        </div>
      </div>
    </div>

    <!-- Main Report Table -->
    <div class="report-table-container">
      <div class="table-toolbar">
        <input 
          v-model="searchQuery" 
          type="text" 
          placeholder="🔍 Search report..." 
          class="search-input"
        />
        <div class="view-options">
          <label>
            <input v-model="showZeroBalances" type="checkbox" />
            Show zero balances
          </label>
          <label>
            <input v-model="showInactive" type="checkbox" />
            Show inactive
          </label>
        </div>
      </div>

      <table class="report-table">
        <thead>
          <tr>
            <th 
              v-for="col in visibleColumns" 
              :key="col.key"
              @click="sortBy(col.key)"
              :class="{ sortable: col.sortable !== false, sorted: sortColumn === col.key }"
            >
              {{ col.label }}
              <span v-if="sortColumn === col.key" class="sort-indicator">
                {{ sortDirection === 'asc' ? '▲' : '▼' }}
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          <template v-for="row in filteredData" :key="row.id">
            <tr 
              :class="[
                'data-row', 
                `level-${row.level}`,
                { 
                  expandable: row.children && row.children.length > 0,
                  expanded: expandedRows.has(row.id),
                  'total-row': row.isTotal,
                  'subtotal-row': row.isSubtotal
                }
              ]"
              @click="toggleRow(row)"
            >
              <td 
                v-for="col in visibleColumns" 
                :key="col.key"
                :class="col.class"
                :style="col.key === visibleColumns[0].key ? `padding-left: ${row.level * 30 + 10}px` : ''"
              >
                <span v-if="col.key === visibleColumns[0].key && row.children && row.children.length > 0" class="expand-icon">
                  {{ expandedRows.has(row.id) ? '▼' : '▶' }}
                </span>
                <span v-if="col.key === visibleColumns[0].key && row.icon" class="row-icon">{{ row.icon }}</span>
                <span v-if="col.render">
                  <component :is="'span'" v-html="col.render(row[col.key], row)"></component>
                </span>
                <span v-else-if="col.type === 'currency'">
                  {{ formatCurrency(row[col.key]) }}
                </span>
                <span v-else-if="col.type === 'percent'">
                  {{ formatPercent(row[col.key]) }}
                </span>
                <span v-else-if="col.type === 'number'">
                  {{ formatNumber(row[col.key]) }}
                </span>
                <span v-else>
                  {{ row[col.key] }}
                </span>
              </td>
            </tr>
            
            <!-- Child rows (when expanded) -->
            <template v-if="expandedRows.has(row.id) && row.children">
              <template v-for="child in row.children" :key="child.id">
                <tr 
                  :class="[
                    'data-row', 
                    `level-${child.level}`,
                    { 
                      expandable: child.children && child.children.length > 0,
                      expanded: expandedRows.has(child.id),
                      'subtotal-row': child.isSubtotal
                    }
                  ]"
                  @click="toggleRow(child)"
                >
                  <td 
                    v-for="col in visibleColumns" 
                    :key="col.key"
                    :class="col.class"
                    :style="col.key === visibleColumns[0].key ? `padding-left: ${child.level * 30 + 10}px` : ''"
                  >
                    <span v-if="col.key === visibleColumns[0].key && child.children && child.children.length > 0" class="expand-icon">
                      {{ expandedRows.has(child.id) ? '▼' : '▶' }}
                    </span>
                    <span v-if="col.key === visibleColumns[0].key && child.icon" class="row-icon">{{ child.icon }}</span>
                    <span v-if="col.render">
                      <component :is="'span'" v-html="col.render(child[col.key], child)"></component>
                    </span>
                    <span v-else-if="col.type === 'currency'">
                      {{ formatCurrency(child[col.key]) }}
                    </span>
                    <span v-else-if="col.type === 'percent'">
                      {{ formatPercent(child[col.key]) }}
                    </span>
                    <span v-else-if="col.type === 'number'">
                      {{ formatNumber(child[col.key]) }}
                    </span>
                    <span v-else>
                      {{ child[col.key] }}
                    </span>
                  </td>
                </tr>
                
                <!-- Recursive rendering for deeper levels -->
                <template v-if="expandedRows.has(child.id) && child.children">
                  <CompanySnapshotRow
                    v-for="grandchild in child.children"
                    :key="grandchild.id"
                    :row="grandchild"
                    :columns="visibleColumns"
                    :expanded-rows="expandedRows"
                    @toggle="toggleRow"
                  />
                </template>
              </template>
            </template>
          </template>
        </tbody>
        
        <!-- Grand Totals Footer -->
        <tfoot v-if="grandTotals">
          <tr class="grand-total-row">
            <td 
              v-for="col in visibleColumns" 
              :key="col.key"
              :class="col.class"
            >
              <strong v-if="col.key === visibleColumns[0].key">GRAND TOTAL</strong>
              <strong v-else-if="col.type === 'currency'">{{ formatCurrency(grandTotals[col.key]) }}</strong>
              <strong v-else-if="col.type === 'number'">{{ formatNumber(grandTotals[col.key]) }}</strong>
              <span v-else></span>
            </td>
          </tr>
        </tfoot>
      </table>
    </div>

    <!-- Column Manager Modal -->
    <div v-if="showColumnManager" class="modal-overlay" @click.self="showColumnManager = false">
      <div class="modal-content column-manager">
        <h3>Manage Columns</h3>
        <div class="column-list">
          <draggable 
            v-model="allColumns" 
            item-key="key"
            handle=".drag-handle"
          >
            <template #item="{ element }">
              <div class="column-item">
                <span class="drag-handle">☰</span>
                <label>
                  <input 
                    v-model="element.visible" 
                    type="checkbox"
                  />
                  {{ element.label }}
                </label>
                <span class="column-type">{{ element.type || 'text' }}</span>
              </div>
            </template>
          </draggable>
        </div>
        <div class="modal-actions">
          <button @click="resetColumns" class="btn-secondary">Reset to Default</button>
          <button @click="showColumnManager = false" class="btn-primary">Done</button>
        </div>
      </div>
    </div>

    <!-- Loading Overlay -->
    <div v-if="loading" class="loading-overlay">
      <div class="spinner"></div>
      <p>Loading company snapshot...</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useToast } from 'vue-toastification'

const toast = useToast()

// Data state
const loading = ref(false)
const dateRange = ref('mtd')
const customStart = ref('')
const customEnd = ref('')
const searchQuery = ref('')
const showZeroBalances = ref(false)
const showInactive = ref(false)
const showColumnManager = ref(false)
const expandedRows = ref(new Set())
const sortColumn = ref('name')
const sortDirection = ref('asc')

// Summary totals
const totals = ref({
  revenue: 0,
  expenses: 0,
  profit: 0,
  profitMargin: 0,
  revenueChange: 0,
  expensesChange: 0,
  charters: 0,
  activeVehicles: 0
})

// Column definitions
const defaultColumns = [
  { key: 'name', label: 'Account / Description', type: 'text', visible: true, sortable: true, class: 'text-left', width: '300px' },
  { key: 'amount', label: 'Amount', type: 'currency', visible: true, sortable: true, class: 'text-right', width: '150px' },
  { key: 'count', label: 'Count', type: 'number', visible: true, sortable: true, class: 'text-center', width: '100px' },
  { key: 'percent', label: '% of Total', type: 'percent', visible: true, sortable: true, class: 'text-right', width: '100px' },
  { key: 'avgAmount', label: 'Average', type: 'currency', visible: false, sortable: true, class: 'text-right', width: '150px' },
  { key: 'accountNumber', label: 'Account #', type: 'text', visible: false, sortable: true, class: 'text-center', width: '120px' },
  { key: 'notes', label: 'Notes', type: 'text', visible: false, sortable: false, class: 'text-left', width: '200px' }
]

const allColumns = ref([...defaultColumns])

const visibleColumns = computed(() => {
  return allColumns.value.filter(col => col.visible)
})

// Report data
const reportData = ref([])
const grandTotals = ref(null)

// Filtered and sorted data
const filteredData = computed(() => {
  let data = reportData.value

  // Apply search filter
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    data = filterRecursive(data, row => 
      row.name?.toLowerCase().includes(query) ||
      row.accountNumber?.toLowerCase().includes(query) ||
      row.notes?.toLowerCase().includes(query)
    )
  }

  // Filter zero balances
  if (!showZeroBalances.value) {
    data = filterRecursive(data, row => row.amount !== 0)
  }

  // Filter inactive
  if (!showInactive.value) {
    data = filterRecursive(data, row => row.active !== false)
  }

  // Apply sorting
  data = sortRecursive(data, sortColumn.value, sortDirection.value)

  return data
})

function filterRecursive(data, filterFn) {
  return data.filter(row => {
    if (row.children) {
      row.children = filterRecursive(row.children, filterFn)
      return filterFn(row) || row.children.length > 0
    }
    return filterFn(row)
  })
}

function sortRecursive(data, column, direction) {
  const sorted = [...data].sort((a, b) => {
    let aVal = a[column]
    let bVal = b[column]
    
    if (typeof aVal === 'string') {
      aVal = aVal.toLowerCase()
      bVal = bVal.toLowerCase()
    }
    
    if (aVal < bVal) return direction === 'asc' ? -1 : 1
    if (aVal > bVal) return direction === 'asc' ? 1 : -1
    return 0
  })

  return sorted.map(row => ({
    ...row,
    children: row.children ? sortRecursive(row.children, column, direction) : undefined
  }))
}

// Toggle row expansion
function toggleRow(row) {
  if (!row.children || row.children.length === 0) return
  
  if (expandedRows.value.has(row.id)) {
    expandedRows.value.delete(row.id)
  } else {
    expandedRows.value.add(row.id)
  }
}

// Expand/collapse all
function expandAll() {
  const allIds = new Set()
  const addIds = (rows) => {
    rows.forEach(row => {
      if (row.children && row.children.length > 0) {
        allIds.add(row.id)
        addIds(row.children)
      }
    })
  }
  addIds(reportData.value)
  expandedRows.value = allIds
}

function collapseAll() {
  expandedRows.value.clear()
}

// Sorting
function sortBy(column) {
  if (sortColumn.value === column) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortColumn.value = column
    sortDirection.value = 'asc'
  }
}

// Column management
function resetColumns() {
  allColumns.value = [...defaultColumns]
}

// Formatting helpers
function formatCurrency(value) {
  if (value === null || value === undefined) return '$0.00'
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD'
  }).format(value)
}

function formatPercent(value) {
  if (value === null || value === undefined) return '0%'
  return `${value.toFixed(1)}%`
}

function formatNumber(value) {
  if (value === null || value === undefined) return '0'
  return value.toLocaleString()
}

// Load data from backend
async function loadData() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    params.set('date_range', dateRange.value)
    if (dateRange.value === 'custom') {
      if (customStart.value) params.set('start_date', customStart.value)
      if (customEnd.value) params.set('end_date', customEnd.value)
    }

    const resp = await fetch(`/api/reports/company-snapshot?${params}`)
    if (!resp.ok) throw new Error(`Failed to load data: ${resp.status}`)

    const data = await resp.json()
    reportData.value = data.sections
    grandTotals.value = data.grandTotals
    totals.value = data.totals

    toast.success('Company snapshot loaded successfully')
  } catch (error) {
    console.error('Load error:', error)
    toast.error('Failed to load company snapshot: ' + (error?.message || error))
    
    // Load sample data for demo
    loadSampleData()
  } finally {
    loading.value = false
  }
}

// Sample data structure for demonstration
function loadSampleData() {
  reportData.value = [
    {
      id: 'revenue',
      name: 'REVENUE',
      icon: '💰',
      amount: 1250000,
      count: 1840,
      percent: 100,
      avgAmount: 679.35,
      level: 0,
      isTotal: true,
      children: [
        {
          id: 'charter-revenue',
          name: 'Charter Services',
          icon: '🚐',
          amount: 980000,
          count: 1520,
          percent: 78.4,
          avgAmount: 644.74,
          level: 1,
          isSubtotal: true,
          children: [
            {
              id: 'wedding-charters',
              name: 'Wedding Charters',
              amount: 450000,
              count: 180,
              percent: 36,
              avgAmount: 2500,
              level: 2,
              accountNumber: '4010',
              children: []
            },
            {
              id: 'corporate-charters',
              name: 'Corporate Charters',
              amount: 320000,
              count: 640,
              percent: 25.6,
              avgAmount: 500,
              level: 2,
              accountNumber: '4020',
              children: []
            },
            {
              id: 'airport-transfers',
              name: 'Airport Transfers',
              amount: 210000,
              count: 700,
              percent: 16.8,
              avgAmount: 300,
              level: 2,
              accountNumber: '4030',
              children: []
            }
          ]
        },
        {
          id: 'other-revenue',
          name: 'Other Revenue',
          icon: '📌',
          amount: 270000,
          count: 320,
          percent: 21.6,
          avgAmount: 843.75,
          level: 1,
          isSubtotal: true,
          children: [
            {
              id: 'fuel-surcharge',
              name: 'Fuel Surcharge',
              amount: 180000,
              count: 280,
              percent: 14.4,
              avgAmount: 642.86,
              level: 2,
              accountNumber: '4100',
              children: []
            },
            {
              id: 'gratuities',
              name: 'Gratuities',
              amount: 90000,
              count: 40,
              percent: 7.2,
              avgAmount: 2250,
              level: 2,
              accountNumber: '4110',
              children: []
            }
          ]
        }
      ]
    },
    {
      id: 'expenses',
      name: 'EXPENSES',
      icon: '💸',
      amount: 820000,
      count: 3240,
      percent: 100,
      avgAmount: 253.09,
      level: 0,
      isTotal: true,
      children: [
        {
          id: 'payroll',
          name: 'Payroll & Benefits',
          icon: '👥',
          amount: 420000,
          count: 480,
          percent: 51.2,
          avgAmount: 875,
          level: 1,
          isSubtotal: true,
          children: [
            {
              id: 'driver-wages',
              name: 'Driver Wages',
              amount: 280000,
              count: 240,
              percent: 34.1,
              avgAmount: 1166.67,
              level: 2,
              accountNumber: '5010',
              children: []
            },
            {
              id: 'benefits',
              name: 'Employee Benefits',
              amount: 140000,
              count: 240,
              percent: 17.1,
              avgAmount: 583.33,
              level: 2,
              accountNumber: '5020',
              children: []
            }
          ]
        },
        {
          id: 'vehicle-costs',
          name: 'Vehicle Operating Costs',
          icon: '🚗',
          amount: 250000,
          count: 1840,
          percent: 30.5,
          avgAmount: 135.87,
          level: 1,
          isSubtotal: true,
          children: [
            {
              id: 'fuel',
              name: 'Fuel',
              amount: 120000,
              count: 840,
              percent: 14.6,
              avgAmount: 142.86,
              level: 2,
              accountNumber: '5110',
              children: []
            },
            {
              id: 'maintenance',
              name: 'Maintenance & Repairs',
              amount: 90000,
              count: 600,
              percent: 11,
              avgAmount: 150,
              level: 2,
              accountNumber: '5120',
              children: []
            },
            {
              id: 'insurance',
              name: 'Vehicle Insurance',
              amount: 40000,
              count: 400,
              percent: 4.9,
              avgAmount: 100,
              level: 2,
              accountNumber: '5130',
              children: []
            }
          ]
        },
        {
          id: 'overhead',
          name: 'Operating Overhead',
          icon: '🏢',
          amount: 150000,
          count: 920,
          percent: 18.3,
          avgAmount: 163.04,
          level: 1,
          isSubtotal: true,
          children: [
            {
              id: 'office-rent',
              name: 'Office Rent',
              amount: 60000,
              count: 12,
              percent: 7.3,
              avgAmount: 5000,
              level: 2,
              accountNumber: '5210',
              children: []
            },
            {
              id: 'utilities',
              name: 'Utilities',
              amount: 30000,
              count: 360,
              percent: 3.7,
              avgAmount: 83.33,
              level: 2,
              accountNumber: '5220',
              children: []
            },
            {
              id: 'office-supplies',
              name: 'Office Supplies',
              amount: 20000,
              count: 240,
              percent: 2.4,
              avgAmount: 83.33,
              level: 2,
              accountNumber: '5230',
              children: []
            },
            {
              id: 'advertising',
              name: 'Advertising & Marketing',
              amount: 40000,
              count: 308,
              percent: 4.9,
              avgAmount: 129.87,
              level: 2,
              accountNumber: '5240',
              children: []
            }
          ]
        }
      ]
    }
  ]

  grandTotals.value = {
    name: '',
    amount: 430000, // profit
    count: 5080,
    percent: 100,
    avgAmount: 0
  }

  totals.value = {
    revenue: 1250000,
    expenses: 820000,
    profit: 430000,
    profitMargin: 34.4,
    revenueChange: 12.5,
    expensesChange: 8.2,
    charters: 1840,
    activeVehicles: 27
  }
}

// Export to Excel
async function exportReport() {
  toast.info('Export feature coming soon!')
}

// Initialize
onMounted(() => {
  loadData()
})
</script>

<style scoped>
.company-snapshot {
  padding: 20px;
  max-width: 1800px;
  margin: 0 auto;
}

.snapshot-header {
  margin-bottom: 30px;
}

.snapshot-header h1 {
  margin: 0 0 10px 0;
  color: #2c3e50;
  font-size: 2rem;
}

.subtitle {
  color: #7f8c8d;
  font-size: 1.1rem;
  margin: 0;
}

/* Report Controls */
.report-controls {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  margin-bottom: 25px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 15px;
}

.control-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.control-group label {
  font-weight: 600;
  color: #34495e;
}

.control-group select,
.control-group input[type="date"] {
  padding: 8px 12px;
  border: 2px solid #e0e0e0;
  border-radius: 6px;
  font-size: 0.95rem;
}

.date-inputs {
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-control {
  padding: 10px 18px;
  background: #3498db;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.3s;
}

.btn-control:hover {
  background: #2980b9;
  transform: translateY(-1px);
}

.btn-export {
  background: #27ae60;
}

.btn-export:hover {
  background: #229954;
}

/* Summary Cards */
.summary-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.summary-card {
  background: white;
  border-radius: 12px;
  padding: 25px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  display: flex;
  gap: 20px;
  align-items: center;
  transition: transform 0.3s, box-shadow 0.3s;
}

.summary-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0,0,0,0.12);
}

.card-icon {
  font-size: 3rem;
  opacity: 0.9;
}

.card-content h3 {
  margin: 0 0 10px 0;
  color: #7f8c8d;
  font-size: 0.9rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.card-value {
  font-size: 2rem;
  font-weight: 700;
  color: #2c3e50;
  margin-bottom: 5px;
}

.card-value.positive {
  color: #27ae60;
}

.card-value.negative {
  color: #e74c3c;
}

.card-change {
  font-size: 0.85rem;
  font-weight: 600;
}

.card-change.positive {
  color: #27ae60;
}

.card-change.negative {
  color: #e74c3c;
}

.card-subtext {
  color: #95a5a6;
  font-size: 0.9rem;
}

/* Report Table */
.report-table-container {
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  overflow: hidden;
}

.table-toolbar {
  padding: 20px;
  border-bottom: 2px solid #ecf0f1;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 15px;
}

.search-input {
  flex: 1;
  min-width: 250px;
  padding: 10px 15px;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  font-size: 1rem;
}

.view-options {
  display: flex;
  gap: 20px;
}

.view-options label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.95rem;
  color: #34495e;
  cursor: pointer;
}

.report-table {
  width: 100%;
  border-collapse: collapse;
}

.report-table thead th {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 15px;
  text-align: left;
  font-weight: 600;
  font-size: 0.9rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  position: sticky;
  top: 0;
  z-index: 10;
}

.report-table thead th.sortable {
  cursor: pointer;
  user-select: none;
}

.report-table thead th.sortable:hover {
  background: linear-gradient(135deg, #5568d3 0%, #6a3f8f 100%);
}

.report-table thead th.sorted {
  background: linear-gradient(135deg, #5568d3 0%, #6a3f8f 100%);
}

.sort-indicator {
  margin-left: 5px;
  font-size: 0.8rem;
}

.report-table tbody .data-row {
  border-bottom: 1px solid #ecf0f1;
  transition: background 0.2s;
}

.report-table tbody .data-row:hover {
  background: #f8f9fa;
}

.report-table tbody .data-row.expandable {
  cursor: pointer;
}

.report-table tbody .data-row.expandable:hover {
  background: #e8f4f8;
}

.report-table tbody .data-row td {
  padding: 12px 15px;
  color: #2c3e50;
}

.report-table tbody .data-row.level-0 td {
  font-weight: 700;
  font-size: 1.05rem;
  background: #f8f9fa;
}

.report-table tbody .data-row.level-1 td {
  font-weight: 600;
  background: #fafbfc;
}

.report-table tbody .data-row.total-row td {
  background: #e8f4f8;
  color: #2c3e50;
  font-weight: 700;
  font-size: 1.1rem;
}

.report-table tbody .data-row.subtotal-row td {
  background: #f0f7fa;
  font-weight: 600;
}

.expand-icon {
  display: inline-block;
  width: 20px;
  color: #3498db;
  font-weight: bold;
}

.row-icon {
  margin-right: 8px;
  font-size: 1.1rem;
}

.text-left {
  text-align: left;
}

.text-right {
  text-align: right;
}

.text-center {
  text-align: center;
}

.report-table tfoot .grand-total-row td {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 15px;
  font-weight: 700;
  font-size: 1.1rem;
  border-top: 3px solid #5568d3;
}

/* Column Manager Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 12px;
  padding: 30px;
  max-width: 600px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 10px 40px rgba(0,0,0,0.2);
}

.modal-content h3 {
  margin: 0 0 20px 0;
  color: #2c3e50;
}

.column-list {
  margin-bottom: 20px;
}

.column-item {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
  margin-bottom: 10px;
  cursor: move;
}

.drag-handle {
  cursor: grab;
  color: #95a5a6;
  font-size: 1.2rem;
}

.drag-handle:active {
  cursor: grabbing;
}

.column-item label {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}

.column-type {
  background: #3498db;
  color: white;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 0.8rem;
  font-weight: 600;
}

.modal-actions {
  display: flex;
  justify-content: space-between;
  gap: 15px;
}

.btn-primary,
.btn-secondary {
  flex: 1;
  padding: 12px;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-primary {
  background: #3498db;
  color: white;
}

.btn-primary:hover {
  background: #2980b9;
}

.btn-secondary {
  background: #ecf0f1;
  color: #2c3e50;
}

.btn-secondary:hover {
  background: #d5dbdb;
}

/* Loading Overlay */
.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

.spinner {
  border: 4px solid #f3f3f3;
  border-top: 4px solid #3498db;
  border-radius: 50%;
  width: 50px;
  height: 50px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.loading-overlay p {
  margin-top: 20px;
  font-size: 1.1rem;
  color: #7f8c8d;
}
</style>
