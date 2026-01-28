<template>
  <div class="print-page">
    <div class="print-header">
      <h1>Beverage Order</h1>
      <div class="meta">
        <div><b>Charter #:</b> {{ header.charter_number || header.charter_id || header.run_id }}</div>
        <div><b>Client:</b> {{ header.client_name || '—' }}</div>
        <div><b>Date/Time:</b> {{ header.charter_date || '—' }}</div>
        <div><b>Vehicle:</b> {{ header.vehicle || '—' }}</div>
      </div>
    </div>

    <table class="items">
      <thead>
        <tr>
          <th style="width:60%; text-align:left;">Item</th>
          <th>Qty</th>
          <th>Price</th>
          <th>Line Total</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(it, idx) in items" :key="idx">
          <td>{{ it.name }}</td>
          <td style="text-align:center;">{{ fmt(it.qty) }}</td>
          <td style="text-align:right;">{{ money(it.price) }}</td>
          <td style="text-align:right;">{{ money(it.line_total) }}</td>
        </tr>
        <tr v-if="!items.length">
          <td colspan="4" class="no-items">No beverage items.</td>
        </tr>
      </tbody>
      <tfoot>
        <tr>
          <td colspan="3" style="text-align:right; font-weight:600;">Subtotal</td>
          <td style="text-align:right; font-weight:600;">{{ money(totals.subtotal) }}</td>
        </tr>
        <tr>
          <td colspan="3" style="text-align:right; font-weight:700;">Grand Total</td>
          <td style="text-align:right; font-weight:700;">{{ money(totals.grand_total) }}</td>
        </tr>
      </tfoot>
    </table>

    <div class="print-actions no-print">
      <button @click="window.print()">Print</button>
      <button @click="goBack">Close</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const header = ref({})
const items = ref([])
const totals = ref({ subtotal: 0, grand_total: 0 })

function fmt(v) { return typeof v === 'number' ? v.toString() : (v || '') }
function money(v) { return `$${Number(v || 0).toFixed(2)}` }

async function fetchData() {
  const params = new URLSearchParams()
  if (route.query.run_id) params.set('run_id', route.query.run_id)
  if (route.query.charter_id) params.set('charter_id', route.query.charter_id)
  const res = await fetch(`/api/beverage_order/print_data?${params}`)
  if (res.ok) {
    const data = await res.json()
    header.value = data.header || {}
    items.value = data.items || []
    totals.value = data.totals || { subtotal: 0, grand_total: 0 }
  }
}

function goBack() { router.back() }

onMounted(fetchData)
</script>

<style scoped>
.print-page { max-width: 900px; margin: 0 auto; background: #fff; color: #111; padding: 24px; }
.print-header { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #111; padding-bottom: 12px; margin-bottom: 16px; }
.print-header h1 { margin: 0; }
.meta { display: grid; grid-template-columns: repeat(2, minmax(200px, 1fr)); gap: 6px 16px; font-size: 14px; }
.items { width: 100%; border-collapse: collapse; }
.items th, .items td { border-bottom: 1px solid #ddd; padding: 8px; }
.items thead th { border-bottom: 2px solid #111; }
.no-items { text-align: center; color: #666; padding: 18px; }
.print-actions { margin-top: 18px; display: flex; gap: 8px; }
@media print { .no-print { display:none; } body { background: #fff; } }
</style>
