<script setup>
import { ref, computed } from 'vue'
import { toast } from 'vue-sonner'

const start_date = ref(new Date(new Date().setDate(new Date().getDate() - 30)).toISOString().split('T')[0])
const end_date = ref(new Date().toISOString().split('T')[0])
const selected_account = ref(null)
const accounts_list = ref([])
const loading = ref(false)
const report_data = ref(null)
const print_mode = ref(false)

const loadAccounts = async () => {
  try {
    const response = await fetch('/api/bank-audit/accounts')
    const result = await response.json()
    accounts_list.value = result.accounts || []
  } catch (error) {
    toast.error('Failed to load accounts: ' + error.message)
  }
}

const generateReport = async () => {
  if (!start_date.value || !end_date.value) {
    toast.warning('Select date range')
    return
  }

  loading.value = true
  try {
    let url = `/api/bank-audit/account-reconciliation?start_date=${start_date.value}&end_date=${end_date.value}`
    if (selected_account.value) {
      url += `&account_number=${selected_account.value}`
    }

    const response = await fetch(url)
    report_data.value = await response.json()
    toast.success(`✓ Loaded ${report_data.value.account_count} bank accounts`)
  } catch (error) {
    toast.error('Failed to generate report: ' + error.message)
  } finally {
    loading.value = false
  }
}

const formatCurrency = (val) => {
  return new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(val || 0)
}

const formatDate = (dateStr) => {
  return new Date(dateStr).toLocaleDateString('en-CA', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

const getVarianceClass = (variance) => {
  if (!variance || variance === 0) return 'text-green-600 font-bold'
  return 'text-red-600 font-bold'
}

const getVarianceIcon = (variance) => {
  if (!variance || variance === 0) return '✓'
  return '⚠️'
}

const printReport = () => {
  print_mode.value = true
  setTimeout(() => window.print(), 100)
}

const resetPrintMode = () => {
  print_mode.value = false
}

// Initial load
loadAccounts()
</script>

<template>
  <div class="bank-audit-report p-6 bg-gradient-to-br from-slate-50 to-slate-100 min-h-screen" :class="{ 'print:bg-white': print_mode }">
    <!-- Header -->
    <div v-if="!print_mode" class="mb-8">
      <h1 class="text-4xl font-bold text-slate-900 mb-2">Bank Account Reconciliation Report</h1>
      <p class="text-slate-600">Auditor-ready report with opening/closing balances and running balance</p>
    </div>

    <!-- Controls -->
    <div v-if="!print_mode" class="bg-white rounded-lg shadow-md p-6 mb-6 space-y-4">
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div>
          <label class="block text-sm font-semibold text-slate-700 mb-2">From Date</label>
          <input
            v-model="start_date"
            type="date"
            class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label class="block text-sm font-semibold text-slate-700 mb-2">To Date</label>
          <input
            v-model="end_date"
            type="date"
            class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label class="block text-sm font-semibold text-slate-700 mb-2">Bank Account (Optional)</label>
          <select
            v-model="selected_account"
            class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Accounts</option>
            <option v-for="acc in accounts_list" :key="acc.account_number" :value="acc.account_number">
              {{ acc.account_number }} - {{ acc.account_name }}
            </option>
          </select>
        </div>

        <div class="flex items-end gap-2">
          <button
            @click="generateReport"
            :disabled="loading"
            class="flex-1 px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-bold rounded-lg transition"
          >
            {{ loading ? '⏳ Loading...' : '📊 Generate Report' }}
          </button>
          <button
            v-if="report_data"
            @click="printReport"
            class="px-4 py-2 bg-slate-600 hover:bg-slate-700 text-white font-bold rounded-lg transition print:hidden"
          >
            🖨️ Print
          </button>
        </div>
      </div>
    </div>

    <!-- Report Title for Print -->
    <div v-if="report_data && print_mode" class="mb-6 text-center pb-4 border-b-2 border-slate-300">
      <h1 class="text-3xl font-bold text-slate-900 mb-1">Bank Account Reconciliation Report</h1>
      <p class="text-sm text-slate-600">
        Period: {{ formatDate(report_data.report_period.start_date) }} to {{ formatDate(report_data.report_period.end_date) }}
      </p>
      <p class="text-xs text-slate-500">Generated: {{ new Date().toLocaleString() }}</p>
    </div>

    <!-- Report Data -->
    <div v-if="report_data" class="space-y-6">
      <!-- Overall Summary (Print Version) -->
      <div v-if="print_mode" class="bg-slate-100 p-4 rounded border-2 border-slate-300 mb-6">
        <h2 class="text-lg font-bold text-slate-900 mb-3">Summary</h2>
        <div class="grid grid-cols-4 gap-4 text-sm">
          <div>
            <span class="text-slate-600">Total Accounts:</span>
            <p class="text-2xl font-bold text-blue-600">{{ report_data.account_count }}</p>
          </div>
          <div>
            <span class="text-slate-600">Linked Transactions:</span>
            <p class="text-2xl font-bold text-green-600">{{ report_data.total_linked }}</p>
          </div>
          <div>
            <span class="text-slate-600">Unlinked Transactions:</span>
            <p class="text-2xl font-bold text-orange-600">{{ report_data.total_unlinked }}</p>
          </div>
          <div>
            <span class="text-slate-600">Total Variance:</span>
            <p class="text-2xl font-bold" :class="getVarianceClass(report_data.total_variance)">
              {{ formatCurrency(report_data.total_variance) }}
            </p>
          </div>
        </div>
      </div>

      <!-- Bank Accounts -->
      <div v-for="account in report_data.accounts" :key="account.account_number" class="print:page-break-inside-avoid">
        <!-- Account Header -->
        <div class="bg-blue-900 text-white p-4 rounded-t-lg">
          <h2 class="text-2xl font-bold mb-1">{{ account.account_name || account.account_number }}</h2>
          <div class="grid grid-cols-3 gap-4 text-sm">
            <div>
              <span class="opacity-75">Account Number:</span>
              <p class="font-mono">{{ account.account_number }}</p>
            </div>
            <div>
              <span class="opacity-75">Institution:</span>
              <p>{{ account.institution_name }}</p>
            </div>
            <div>
              <span class="opacity-75">Period:</span>
              <p>{{ formatDate(report_data.report_period.start_date) }} to {{ formatDate(report_data.report_period.end_date) }}</p>
            </div>
          </div>
        </div>

        <!-- Account Summary -->
        <div class="bg-slate-50 p-4 grid grid-cols-3 gap-4 border-b-2 border-slate-300">
          <div class="bg-white p-3 rounded border border-slate-200">
            <p class="text-xs text-slate-600">Opening Balance</p>
            <p class="text-2xl font-bold text-blue-600">{{ formatCurrency(account.opening_balance) }}</p>
          </div>
          <div class="bg-white p-3 rounded border border-slate-200">
            <p class="text-xs text-slate-600">Closing Balance</p>
            <p class="text-2xl font-bold text-slate-900">{{ formatCurrency(account.closing_balance) }}</p>
          </div>
          <div class="bg-white p-3 rounded border border-slate-200" :class="account.variance === 0 ? 'border-green-300' : 'border-red-300'">
            <p class="text-xs text-slate-600">Variance</p>
            <p class="text-2xl font-bold" :class="getVarianceClass(account.variance)">
              {{ getVarianceIcon(account.variance) }} {{ formatCurrency(account.variance) }}
            </p>
          </div>
        </div>

        <!-- Transaction Statistics -->
        <div class="bg-white p-4 grid grid-cols-5 gap-2 border-b-2 border-slate-300 text-center text-sm">
          <div class="bg-green-50 p-2 rounded">
            <p class="text-slate-600">Credits</p>
            <p class="font-bold text-green-600">{{ formatCurrency(account.total_credits) }}</p>
          </div>
          <div class="bg-red-50 p-2 rounded">
            <p class="text-slate-600">Debits</p>
            <p class="font-bold text-red-600">{{ formatCurrency(account.total_debits) }}</p>
          </div>
          <div class="bg-blue-50 p-2 rounded">
            <p class="text-slate-600">Transactions</p>
            <p class="font-bold text-blue-600">{{ account.transaction_count }}</p>
          </div>
          <div class="bg-green-50 p-2 rounded">
            <p class="text-slate-600">Linked</p>
            <p class="font-bold text-green-600">{{ account.linked_count }}</p>
          </div>
          <div class="bg-orange-50 p-2 rounded">
            <p class="text-slate-600">Unlinked</p>
            <p class="font-bold text-orange-600">{{ account.unlinked_count }}</p>
          </div>
        </div>

        <!-- Transaction Detail Table -->
        <div class="bg-white rounded-b-lg overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-slate-200 border-b-2 border-slate-300">
              <tr class="text-left">
                <th class="px-3 py-2 font-bold text-slate-900">Date</th>
                <th class="px-3 py-2 font-bold text-slate-900">Description</th>
                <th class="px-3 py-2 font-bold text-right text-slate-900">Amount</th>
                <th class="px-3 py-2 font-bold text-right text-slate-900">Running Balance</th>
                <th class="px-3 py-2 font-bold text-slate-900">Vendor</th>
                <th class="px-3 py-2 font-bold text-slate-900">Linked</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(trans, idx) in account.transactions" :key="idx" class="border-b border-slate-200 hover:bg-slate-50" :class="trans.linked ? 'bg-green-50' : 'bg-yellow-50'">
                <td class="px-3 py-2 font-mono text-sm text-slate-700">{{ formatDate(trans.transaction_date) }}</td>
                <td class="px-3 py-2 text-slate-700 max-w-xs truncate" :title="trans.description">{{ trans.description }}</td>
                <td class="px-3 py-2 text-right font-mono" :class="trans.amount > 0 ? 'text-green-600' : 'text-red-600'">
                  {{ formatCurrency(trans.amount) }}
                </td>
                <td class="px-3 py-2 text-right font-mono font-bold text-slate-900 bg-blue-50">{{ formatCurrency(trans.running_balance) }}</td>
                <td class="px-3 py-2 text-slate-600 text-xs max-w-xs truncate">
                  {{ trans.receipt_vendor || '-' }}
                </td>
                <td class="px-3 py-2 text-center">
                  <span v-if="trans.linked" class="text-green-600 font-bold">✓ YES</span>
                  <span v-else class="text-orange-600 font-bold">⚠️ NO</span>
                </td>
              </tr>

              <!-- Account Total Row -->
              <tr class="bg-slate-200 font-bold border-t-2 border-slate-400">
                <td colspan="2" class="px-3 py-3 text-slate-900">Account Total</td>
                <td class="px-3 py-3 text-right text-slate-900">
                  {{ formatCurrency(account.total_credits - Math.abs(account.total_debits)) }}
                </td>
                <td class="px-3 py-3 text-right text-slate-900 text-lg">
                  {{ formatCurrency(account.closing_balance) }}
                </td>
                <td colspan="2" class="px-3 py-3"></td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Unlinked Transactions Alert -->
        <div v-if="account.unlinked_count > 0" class="bg-orange-50 border-2 border-orange-300 p-4 rounded-lg mt-4">
          <p class="text-sm font-semibold text-orange-900 mb-2">⚠️ Unlinked Transactions</p>
          <p class="text-sm text-orange-800">
            {{ account.unlinked_count }} transaction(s) totaling {{ formatCurrency(account.total_unlinked_amount) }} are not linked to receipts and require review.
          </p>
        </div>

        <!-- Variance Alert -->
        <div v-if="account.variance !== 0" class="bg-red-50 border-2 border-red-300 p-4 rounded-lg mt-4">
          <p class="text-sm font-semibold text-red-900 mb-2">⚠️ Reconciliation Variance</p>
          <p class="text-sm text-red-800">
            Calculated closing balance ({{ formatCurrency(account.closing_balance) }}) differs from bank statement by {{ formatCurrency(Math.abs(account.variance)) }}.
          </p>
        </div>

        <!-- Page Break for Print -->
        <div v-if="print_mode && account !== report_data.accounts[report_data.accounts.length - 1]" class="page-break mt-8 print:page-break-after"></div>
        <div v-else class="mt-8 mb-8 border-b-2 border-slate-300"></div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="!report_data && !loading" class="bg-white rounded-lg shadow-md p-12 text-center">
      <p class="text-slate-600 text-lg mb-4">👆 Select dates and click "Generate Report" to begin</p>
      <p class="text-slate-500 text-sm">This report provides auditor-ready reconciliation by bank account with opening/closing balances and running transaction balances.</p>
    </div>

    <!-- Print Footer -->
    <div v-if="print_mode" class="mt-12 pt-6 border-t-2 border-slate-300 text-center text-xs text-slate-500 print:block hidden">
      <p>This report was electronically generated on {{ new Date().toLocaleString() }}</p>
      <p>For audit purposes only. Bank Account Reconciliation Report.</p>
    </div>

    <!-- Close Print Mode Button -->
    <div v-if="print_mode" class="fixed bottom-4 right-4 print:hidden">
      <button
        @click="resetPrintMode"
        class="px-4 py-2 bg-slate-600 hover:bg-slate-700 text-white font-bold rounded-lg"
      >
        ✕ Close Print
      </button>
    </div>
  </div>
</template>

<style scoped>
.bank-audit-report {
  font-family: 'Courier New', monospace;
}

@media print {
  .page-break {
    page-break-after: always;
  }

  .print\:page-break-inside-avoid {
    page-break-inside: avoid;
  }

  .print\:hidden {
    display: none !important;
  }

  body {
    background: white;
  }

  .bank-audit-report {
    background: white;
    padding: 0;
  }

  table {
    page-break-inside: avoid;
  }
}
</style>
