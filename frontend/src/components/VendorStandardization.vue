<script setup>
import { ref, computed } from 'vue'
import { toast } from 'vue-sonner'

const tab = ref('list') // 'list', 'merge', 'capitalize'
const vendors = ref([])
const vendor_search = ref('')
const loading = ref(false)
const merge_sources = ref([])
const merge_target = ref('')
const dryRunResults = ref(null)
const consolidation_ready = ref(false)

const loadVendors = async () => {
  loading.value = true
  try {
    const response = await fetch('/api/vendors/list-all?min_receipts=1')
    vendors.value = await response.json()
    toast.success(`Loaded ${vendors.value.length} vendors`)
  } catch (error) {
    toast.error('Failed to load vendors: ' + error.message)
  } finally {
    loading.value = false
  }
}

const filteredVendors = computed(() => {
  if (!vendor_search.value) return vendors.value
  return vendors.value.filter(v => 
    v.vendor_name.toLowerCase().includes(vendor_search.value.toLowerCase())
  )
})

const toggleSourceSelection = (vendor) => {
  const idx = merge_sources.value.findIndex(s => s === vendor.vendor_name)
  if (idx > -1) {
    merge_sources.value.splice(idx, 1)
  } else {
    merge_sources.value.push(vendor.vendor_name)
  }
}

const isSourceSelected = (vendorName) => {
  return merge_sources.value.includes(vendorName)
}

const prepareMerge = () => {
  if (merge_sources.value.length === 0) {
    toast.warning('Select at least one vendor to merge')
    return
  }
  if (!merge_target.value.trim()) {
    toast.warning('Enter target vendor name')
    return
  }
  consolidation_ready.value = true
}

const executeMerge = async (dry = true) => {
  if (merge_sources.value.length === 0 || !merge_target.value) {
    toast.warning('Select vendors and target name')
    return
  }

  loading.value = true
  try {
    const response = await fetch('/api/vendors/merge-vendors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_vendors: merge_sources.value,
        target_vendor: merge_target.value.toUpperCase()
      })
    })

    if (!response.ok) throw new Error('Merge failed')
    const result = await response.json()
    
    toast.success(`✓ Merged ${result.affected_receipts} receipts to "${result.canonical_name}"`)
    
    merge_sources.value = []
    merge_target.value = ''
    consolidation_ready.value = false
    
    // Reload vendors
    await loadVendors()
  } catch (error) {
    toast.error('Merge failed: ' + error.message)
  } finally {
    loading.value = false
  }
}

const previewCapitalize = async () => {
  loading.value = true
  try {
    const response = await fetch('/api/vendors/capitalize-all?dry_run=true')
    dryRunResults.value = await response.json()
  } catch (error) {
    toast.error('Preview failed: ' + error.message)
  } finally {
    loading.value = false
  }
}

const applyCapitalize = async () => {
  loading.value = true
  try {
    const response = await fetch('/api/vendors/capitalize-all?dry_run=false', { method: 'POST' })
    const result = await response.json()
    toast.success(`✓ Capitalized ${result.affected_receipts} vendor names`)
    dryRunResults.value = null
    await loadVendors()
  } catch (error) {
    toast.error('Capitalization failed: ' + error.message)
  } finally {
    loading.value = false
  }
}

const formatCurrency = (val) => {
  return new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(val || 0)
}

// Initial load
loadVendors()
</script>

<template>
  <div class="vendor-standardization p-6 bg-gradient-to-br from-slate-50 to-slate-100 min-h-screen">
    <h1 class="text-4xl font-bold text-slate-900 mb-6">Vendor Standardization Tool</h1>
    <p class="text-slate-600 mb-8">Clean up vendor names: merge variations, capitalize, remove typos</p>

    <!-- Tabs -->
    <div class="flex gap-4 mb-6 border-b border-slate-200">
      <button
        @click="tab = 'list'"
        :class="[
          'px-6 py-3 font-semibold border-b-2 transition',
          tab === 'list' 
            ? 'text-blue-600 border-blue-600' 
            : 'text-slate-600 border-transparent hover:text-slate-900'
        ]"
      >
        📋 Vendor List
      </button>
      <button
        @click="tab = 'merge'; consolidation_ready = false"
        :class="[
          'px-6 py-3 font-semibold border-b-2 transition',
          tab === 'merge' 
            ? 'text-blue-600 border-blue-600' 
            : 'text-slate-600 border-transparent hover:text-slate-900'
        ]"
      >
        🔀 Merge Vendors
      </button>
      <button
        @click="tab = 'capitalize'"
        :class="[
          'px-6 py-3 font-semibold border-b-2 transition',
          tab === 'capitalize' 
            ? 'text-blue-600 border-blue-600' 
            : 'text-slate-600 border-transparent hover:text-slate-900'
        ]"
      >
        🔤 Capitalize All
      </button>
    </div>

    <!-- TAB 1: Vendor List -->
    <div v-if="tab === 'list'" class="space-y-4">
      <div class="bg-white rounded-lg shadow-md p-4">
        <input
          v-model="vendor_search"
          type="text"
          placeholder="🔍 Search vendors..."
          class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <p class="text-sm text-slate-600">Found {{ filteredVendors.length }} vendors</p>

      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        <div v-for="v in filteredVendors" :key="v.vendor_name" class="bg-white rounded-lg shadow p-4 hover:shadow-md transition">
          <h3 class="font-bold text-slate-900 mb-2 text-lg break-words">{{ v.vendor_name }}</h3>
          <div class="space-y-1 text-sm text-slate-600">
            <p>📋 {{ v.receipt_count }} receipts</p>
            <p>💰 Total: {{ formatCurrency(v.total_amount) }}</p>
            <p v-if="v.last_used" class="text-xs">Last: {{ new Date(v.last_used).toLocaleDateString() }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 2: Merge Vendors -->
    <div v-if="tab === 'merge'" class="space-y-6">
      <!-- Source Selection -->
      <div class="bg-white rounded-lg shadow-md p-6">
        <h2 class="text-xl font-bold text-slate-900 mb-4">Step 1: Select Vendors to Merge</h2>
        <p class="text-slate-600 mb-4">Click vendors to select them ({{ merge_sources.length }} selected)</p>

        <input
          v-model="vendor_search"
          type="text"
          placeholder="🔍 Search..."
          class="w-full px-4 py-2 border border-slate-300 rounded-lg mb-4 focus:ring-2 focus:ring-blue-500"
        />

        <div class="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-96 overflow-y-auto">
          <div
            v-for="v in filteredVendors"
            :key="v.vendor_name"
            @click="toggleSourceSelection(v)"
            :class="[
              'p-3 rounded-lg border-2 cursor-pointer transition',
              isSourceSelected(v.vendor_name)
                ? 'border-blue-600 bg-blue-50'
                : 'border-slate-200 bg-white hover:border-slate-300'
            ]"
          >
            <div class="flex items-start justify-between">
              <div class="flex-1">
                <p class="font-semibold text-slate-900">{{ v.vendor_name }}</p>
                <p class="text-xs text-slate-600">{{ v.receipt_count }} receipts</p>
              </div>
              <span v-if="isSourceSelected(v.vendor_name)" class="text-2xl">✓</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Target Name -->
      <div v-if="merge_sources.length > 0" class="bg-white rounded-lg shadow-md p-6">
        <h2 class="text-xl font-bold text-slate-900 mb-4">Step 2: Enter New Vendor Name</h2>
        <p class="text-slate-600 mb-4">All selected vendors will be renamed to this (will be CAPITALIZED)</p>

        <input
          v-model="merge_target"
          type="text"
          placeholder="E.g., SHELL CANADA"
          class="w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-green-500 text-lg"
        />

        <div class="mt-4 p-4 bg-slate-50 rounded-lg">
          <p class="text-sm text-slate-700 font-semibold">Will merge:</p>
          <ul class="mt-2 space-y-1">
            <li v-for="s in merge_sources" :key="s" class="text-sm text-slate-600">
              ❌ {{ s }} → ✅ {{ merge_target.toUpperCase() || '(new name)' }}
            </li>
          </ul>
        </div>

        <button
          @click="prepareMerge"
          :disabled="!merge_target"
          class="w-full mt-4 px-6 py-3 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white font-bold rounded-lg transition"
        >
          ✓ Confirm Merge
        </button>
      </div>

      <!-- Confirmation -->
      <div v-if="consolidation_ready" class="bg-green-50 rounded-lg shadow-md p-6 border-2 border-green-500">
        <h2 class="text-xl font-bold text-green-900 mb-4">Ready to Merge</h2>
        <p class="text-green-800 mb-6">This will merge {{ merge_sources.length }} vendor names into one canonical name.</p>
        <button
          @click="executeMerge()"
          :disabled="loading"
          class="w-full px-6 py-3 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white font-bold rounded-lg transition"
        >
          {{ loading ? '⏳ Merging...' : '🔀 Execute Merge' }}
        </button>
      </div>
    </div>

    <!-- TAB 3: Capitalize All -->
    <div v-if="tab === 'capitalize'" class="space-y-6">
      <div class="bg-white rounded-lg shadow-md p-6">
        <h2 class="text-xl font-bold text-slate-900 mb-4">Capitalize All Vendor Names</h2>
        <p class="text-slate-600 mb-6">Convert all vendor names to UPPER CASE for consistency</p>

        <p class="text-sm text-slate-600 mb-4">Total vendors in system: {{ vendors.length }}</p>

        <button
          @click="previewCapitalize"
          :disabled="loading"
          class="w-full px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-bold rounded-lg transition mb-4"
        >
          {{ loading ? '⏳ Previewing...' : '👁️ Preview Changes' }}
        </button>

        <div v-if="dryRunResults" class="mt-6 p-6 bg-slate-50 rounded-lg border border-slate-300">
          <p class="text-sm font-semibold text-slate-900 mb-4">
            Will affect <span class="text-2xl font-bold text-orange-600">{{ dryRunResults.changes_to_apply }}</span> vendor names
          </p>

          <div v-if="dryRunResults.preview.length > 0" class="space-y-2 mb-6 max-h-64 overflow-y-auto">
            <div v-for="change in dryRunResults.preview.slice(0, 5)" :key="change.current" class="flex items-center justify-between text-sm">
              <span class="text-slate-600">{{ change.current }}</span>
              <span class="text-slate-400 mx-2">→</span>
              <span class="font-semibold text-blue-600">{{ change.will_become }}</span>
            </div>
            <p v-if="dryRunResults.preview.length > 5" class="text-xs text-slate-500">
              ...and {{ dryRunResults.changes_to_apply - 5 }} more
            </p>
          </div>

          <button
            @click="applyCapitalize"
            :disabled="loading"
            class="w-full px-6 py-3 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white font-bold rounded-lg transition"
          >
            {{ loading ? '⏳ Capitalizing...' : '✓ Apply Capitalization' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.vendor-standardization {
  font-family: system-ui, -apple-system, sans-serif;
}
</style>
