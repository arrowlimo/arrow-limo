<script setup>
import { ref, computed, onMounted } from 'vue'
import { toast } from 'vue-sonner'

const startDate = ref(new Date(new Date().setDate(new Date().getDate() - 30)).toISOString().split('T')[0])
const endDate = ref(new Date().toISOString().split('T')[0])
const unlinkedOnly = ref(false)
const reportData = ref(null)
const loading = ref(false)
const sortColumn = ref('transaction_date')
const sortDesc = ref(true)
const editingCell = ref(null) // {lineId, field}
const editValue = ref('')

const generateReport = async () => {
  loading.value = true
  try {
    const response = await fetch(
      `/api/reconciliation/banking-receipt-report?start_date=${startDate.value}&end_date=${endDate.value}&unlinked_only=${unlinkedOnly.value}`
    )
    if (!response.ok) throw new Error('Failed to fetch report')
    reportData.value = await response.json()
    toast.success(`Loaded ${reportData.value.count} records`)
  } catch (error) {
    toast.error('Failed to generate report: ' + error.message)
  } finally {
    loading.value = false
  }
}

const sortedLines = computed(() => {
  if (!reportData.value) return []
  
  const sorted = [...reportData.value.lines]
  sorted.sort((a, b) => {
    let aVal = a[sortColumn.value]
    let bVal = b[sortColumn.value]
    
    if (aVal === null) aVal = sortColumn.value.includes('amount') ? 0 : ''
    if (bVal === null) bVal = sortColumn.value.includes('amount') ? 0 : ''
    
    if (typeof aVal === 'string') {
      aVal = aVal.toLowerCase()
      bVal = bVal.toLowerCase()
    }
    
    if (aVal < bVal) return sortDesc.value ? 1 : -1
    if (aVal > bVal) return sortDesc.value ? -1 : 1
    return 0
  })
  
  return sorted
})

const startEdit = (lineId, field, currentValue) => {
  editingCell.value = { lineId, field }
  editValue.value = currentValue || ''
}

const saveEdit = async (line) => {
  if (!editingCell.value) return
  
  try {
    const response = await fetch('/api/reconciliation/update-receipt-inline', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        receipt_id: line.receipt_id,
        field: editingCell.value.field,
        value: editValue.value
      })
    })
    
    if (!response.ok) throw new Error('Failed to save')
    
    // Update local data
    const field = editingCell.value.field
    if (field === 'receipt_gst') line.receipt_gst = parseFloat(editValue.value)
    else if (field === 'receipt_pst') line.receipt_pst = parseFloat(editValue.value)
    else if (field === 'receipt_vendor') line.receipt_vendor = editValue.value
    else if (field === 'receipt_category') line.receipt_category = editValue.value
    else if (field === 'receipt_gl_code') line.receipt_gl_code = editValue.value
    else if (field === 'receipt_type') line.receipt_type = editValue.value
    
    toast.success('Updated')
    editingCell.value = null
  } catch (error) {
    toast.error('Save failed: ' + error.message)
  }
}

const formatCurrency = (val) => {
  return new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(val || 0)
}

const formatDate = (d) => {
  return new Date(d).toLocaleDateString()
}

const getDuplicateCount = (lines, field, value) => {
  return lines.filter(l => l[field] === value).length
}

onMounted(() => {
  generateReport()
})
</script>

<template>
  <div class="banking-receipt-reconciliation p-6 bg-gradient-to-br from-slate-50 to-slate-100 min-h-screen">
    <h1 class="text-4xl font-bold text-slate-900 mb-6">Banking-Receipt Reconciliation Report</h1>

    <!-- Controls -->
    <div class="bg-white rounded-lg shadow-md p-6 mb-6">
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
        <div>
          <label class="block text-sm font-semibold text-slate-700 mb-2">Start Date</label>
          <input v-model="startDate" type="date" class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
        </div>
        <div>
          <label class="block text-sm font-semibold text-slate-700 mb-2">End Date</label>
          <input v-model="endDate" type="date" class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
        </div>
        <div>
          <label class="flex items-center gap-2 text-slate-700 font-semibold">
            <input v-model="unlinkedOnly" type="checkbox" class="w-4 h-4" />
            Unlinked Only
          </label>
        </div>
        <button @click="generateReport" :disabled="loading" class="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition disabled:opacity-50">
          {{ loading ? '⏳ Loading...' : '📊 Generate Report' }}
        </button>
      </div>
    </div>

    <!-- Summary Cards -->
    <div v-if="reportData" class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
      <div class="bg-white rounded-lg shadow p-4 border-l-4 border-blue-500">
        <p class="text-xs text-slate-600 uppercase font-semibold">Total Records</p>
        <p class="text-3xl font-bold text-blue-600">{{ reportData.count }}</p>
      </div>
      <div class="bg-white rounded-lg shadow p-4 border-l-4 border-green-500">
        <p class="text-xs text-slate-600 uppercase font-semibold">Linked</p>
        <p class="text-3xl font-bold text-green-600">{{ reportData.linked_count }}</p>
      </div>
      <div class="bg-white rounded-lg shadow p-4 border-l-4 border-orange-500">
        <p class="text-xs text-slate-600 uppercase font-semibold">Unlinked</p>
        <p class="text-3xl font-bold text-orange-600">{{ reportData.unlinked_count }}</p>
      </div>
      <div class="bg-white rounded-lg shadow p-4 border-l-4 border-purple-500">
        <p class="text-xs text-slate-600 uppercase font-semibold">Total Amount</p>
        <p class="text-2xl font-bold text-purple-600">{{ formatCurrency(reportData.total_banking) }}</p>
      </div>
    </div>

    <!-- Reconciliation Table -->
    <div v-if="reportData" class="bg-white rounded-lg shadow-lg overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-xs">
          <thead class="bg-slate-100 border-b-2 border-slate-300 sticky top-0">
            <tr>
              <th v-for="col in ['transaction_date', 'banking_description', 'banking_amount', 'receipt_vendor', 'receipt_total', 'receipt_gst', 'receipt_category', 'receipt_gl_code', 'receipt_type', 'linked']"
                  :key="col"
                  @click="sortColumn = col; sortDesc = !sortDesc"
                  class="px-3 py-2 text-left font-semibold text-slate-900 cursor-pointer hover:bg-slate-200 transition"
              >
                {{ col.replace(/_/g, ' ').toUpperCase() }}
                <span v-if="sortColumn === col" class="ml-1">{{ sortDesc ? '↓' : '↑' }}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(line, idx) in sortedLines" :key="line.id" :class="[
              'border-b border-slate-200 hover:bg-slate-50 transition',
              line.linked ? 'bg-green-50' : 'bg-yellow-50'
            ]">
              <td class="px-3 py-2">{{ formatDate(line.transaction_date) }}</td>
              <td class="px-3 py-2">{{ line.banking_description }}</td>
              <td class="px-3 py-2 text-right font-mono">{{ formatCurrency(line.banking_amount) }}</td>
              
              <!-- Receipt Vendor - Editable -->
              <td class="px-3 py-2 bg-blue-50" @dblclick="startEdit(line.id, 'receipt_vendor', line.receipt_vendor)">
                <input
                  v-if="editingCell?.lineId === line.id && editingCell?.field === 'receipt_vendor'"
                  v-model="editValue"
                  @blur="saveEdit(line)"
                  @keyup.enter="saveEdit(line)"
                  class="w-full px-2 py-1 border border-blue-500 rounded"
                  autofocus
                />
                <span v-else class="cursor-pointer hover:text-blue-600">{{ line.receipt_vendor || '—' }}</span>
              </td>
              
              <!-- Receipt Total -->
              <td class="px-3 py-2 text-right font-mono" :class="line.discrepancy ? 'text-red-600 font-bold' : ''">
                {{ formatCurrency(line.receipt_total) }}
                <span v-if="line.discrepancy" class="ml-1">⚠️</span>
              </td>
              
              <!-- GST - Editable -->
              <td class="px-3 py-2 bg-purple-50 text-right" @dblclick="startEdit(line.id, 'receipt_gst', line.receipt_gst)">
                <input
                  v-if="editingCell?.lineId === line.id && editingCell?.field === 'receipt_gst'"
                  v-model.number="editValue"
                  type="number"
                  step="0.01"
                  @blur="saveEdit(line)"
                  @keyup.enter="saveEdit(line)"
                  class="w-full px-2 py-1 border border-purple-500 rounded text-right"
                  autofocus
                />
                <span v-else class="cursor-pointer hover:text-purple-600">{{ formatCurrency(line.receipt_gst) }}</span>
              </td>
              
              <!-- Category - Editable -->
              <td class="px-3 py-2 bg-teal-50" @dblclick="startEdit(line.id, 'receipt_category', line.receipt_category)">
                <input
                  v-if="editingCell?.lineId === line.id && editingCell?.field === 'receipt_category'"
                  v-model="editValue"
                  @blur="saveEdit(line)"
                  @keyup.enter="saveEdit(line)"
                  class="w-full px-2 py-1 border border-teal-500 rounded"
                  autofocus
                />
                <span v-else class="cursor-pointer hover:text-teal-600">{{ line.receipt_category || '—' }}</span>
              </td>
              
              <!-- GL Code - Editable -->
              <td class="px-3 py-2 bg-indigo-50" @dblclick="startEdit(line.id, 'receipt_gl_code', line.receipt_gl_code)">
                <input
                  v-if="editingCell?.lineId === line.id && editingCell?.field === 'receipt_gl_code'"
                  v-model="editValue"
                  @blur="saveEdit(line)"
                  @keyup.enter="saveEdit(line)"
                  class="w-full px-2 py-1 border border-indigo-500 rounded"
                  autofocus
                />
                <span v-else class="cursor-pointer hover:text-indigo-600">{{ line.receipt_gl_code || '—' }}</span>
              </td>
              
              <!-- Type - Editable -->
              <td class="px-3 py-2 bg-orange-50" @dblclick="startEdit(line.id, 'receipt_type', line.receipt_type)">
                <select
                  v-if="editingCell?.lineId === line.id && editingCell?.field === 'receipt_type'"
                  v-model="editValue"
                  @blur="saveEdit(line)"
                  @change="saveEdit(line)"
                  class="w-full px-2 py-1 border border-orange-500 rounded"
                  autofocus
                >
                  <option value="">—</option>
                  <option value="BUSINESS">BUSINESS</option>
                  <option value="PERSONAL">PERSONAL</option>
                </select>
                <span v-else class="cursor-pointer hover:text-orange-600">{{ line.receipt_type || '—' }}</span>
              </td>
              
              <td class="px-3 py-2 text-center">
                <span v-if="line.linked" class="bg-green-100 text-green-800 px-2 py-1 rounded text-xs font-semibold">✓ LINKED</span>
                <span v-else class="bg-yellow-100 text-yellow-800 px-2 py-1 rounded text-xs font-semibold">⚠ UNLINKED</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      
      <div class="bg-slate-50 px-6 py-4 border-t border-slate-200 text-sm text-slate-600">
        💡 Double-click any cell to edit inline. Click column headers to sort. Green = linked, Yellow = unlinked
      </div>
    </div>

    <div v-else-if="!loading" class="text-center py-12 text-slate-600">
      Click "Generate Report" to load data
    </div>
  </div>
</template>

<style scoped>
.banking-receipt-reconciliation {
  font-family: system-ui, -apple-system, sans-serif;
}
</style>
