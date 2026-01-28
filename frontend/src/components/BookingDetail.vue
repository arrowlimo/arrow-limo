<template>
  <div class="booking-detail-modal" v-if="visible" @click.self="close">
    <div class="booking-detail-content">
      <div class="booking-detail-header">
        <h2>Reservation Details - {{ booking.reserve_number }}</h2>
        <button @click="close" class="close-btn">&times;</button>
      </div>
      
      <div class="booking-detail-tabs">
        <button 
          v-for="tab in tabs" 
          :key="tab.id"
          @click="activeTab = tab.id"
          :class="{ active: activeTab === tab.id }"
          class="tab-btn"
        >
          {{ tab.label }}
        </button>
      </div>
      
      <div class="booking-detail-body">
        <div v-if="activeTab === 'reservation'" class="tab-content">
          <div class="detail-section">
            <h3>Basic Information</h3>
            <div class="detail-grid">
              <div class="detail-item">
                <label>Reserve #:</label>
                <span>{{ booking.reserve_number }}</span>
              </div>
              <div class="detail-item">
                <label>Charter Date:</label>
                <span>{{ formatDate(booking.charter_date) }}</span>
              </div>
              <div class="detail-item">
                <label>Client:</label>
                <span>{{ booking.client_name }}</span>
              </div>
              <div class="detail-item">
                <label>Status:</label>
                <span>{{ booking.status || 'Active' }}</span>
              </div>
              <div class="detail-item">
                <label>Client Passengers:</label>
                <span>{{ booking.passenger_load || 'Not specified' }}</span>
              </div>
              <div class="detail-item">
                <label>Vehicle Capacity:</label>
                <span>{{ booking.vehicle_capacity ? booking.vehicle_capacity + ' passengers' : 'Vehicle not assigned' }}</span>
              </div>
            </div>
          </div>
        </div>
        
        <div v-if="activeTab === 'charges'" class="tab-content">
          <div class="detail-section">
            <h3>Financial Summary</h3>
            <div class="financial-summary">
              <div class="summary-item">
                <label>Total Charges:</label>
                <span class="amount">${{ financials.charges_total?.toFixed(2) || '0.00' }}</span>
              </div>
              <div class="summary-item">
                <label>Total Payments:</label>
                <span class="amount">${{ financials.payments_total?.toFixed(2) || '0.00' }}</span>
              </div>
              <div class="summary-item total">
                <label>Balance Due:</label>
                <span class="amount">${{ financials.balance_due?.toFixed(2) || '0.00' }}</span>
              </div>
            </div>
            
            <div class="section-header">
              <h3>Charges</h3>
              <button @click="showAddChargeForm = true" class="btn-small">Add Charge</button>
            </div>
            
            <div v-if="showAddChargeForm" class="add-form">
              <div class="form-grid">
                <div class="form-field">
                  <label>Type:</label>
                  <select v-model="newCharge.charge_type">
                    <option value="service_fee">Service Fee</option>
                    <option value="gst">GST</option>
                    <option value="gratuity">Gratuity</option>
                  </select>
                </div>
                <div class="form-field">
                  <label>Amount:</label>
                  <input v-model="newCharge.amount" type="number" step="0.01" />
                </div>
                <div class="form-field full-width">
                  <label>Description:</label>
                  <input v-model="newCharge.description" type="text" />
                </div>
              </div>
              <div class="form-actions">
                <button @click="addCharge" class="btn-primary">Add Charge</button>
                <button @click="showAddChargeForm = false" class="btn-secondary">Cancel</button>
              </div>
            </div>
            
            <div class="charges-table">
              <table v-if="charges.length">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Description</th>
                    <th>Amount</th>
                    <th>Date</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="c in charges" :key="c.charge_id">
                    <td v-if="editingChargeId !== c.charge_id">{{ c.charge_type }}</td>
                    <td v-else>
                      <select v-model="editingCharge.charge_type">
                        <option value="service_fee">Service Fee</option>
                        <option value="gst">GST</option>
                        <option value="gratuity">Gratuity</option>
                        <option value="other">Other</option>
                      </select>
                    </td>
                    <td v-if="editingChargeId !== c.charge_id">{{ c.description || '-' }}</td>
                    <td v-else><input type="text" v-model="editingCharge.description" /></td>
                    <td class="amount" v-if="editingChargeId !== c.charge_id">${{ parseFloat(c.amount || 0).toFixed(2) }}</td>
                    <td v-else><input type="number" step="0.01" v-model.number="editingCharge.amount" class="amount-input" /></td>
                    <td>{{ new Date(c.created_at).toLocaleDateString() }}</td>
                    <td class="row-actions">
                      <template v-if="editingChargeId === c.charge_id">
                        <button class="btn-small" @click="saveEditCharge(c)">Save</button>
                        <button class="btn-secondary btn-small" @click="cancelEditCharge">Cancel</button>
                      </template>
                      <template v-else>
                        <button class="btn-small" @click="startEditCharge(c)">Edit</button>
                        <button class="btn-danger btn-small" @click="deleteCharge(c)">Delete</button>
                      </template>
                    </td>
                  </tr>
                </tbody>
              </table>
              <p v-else class="no-data">No charges recorded</p>
            </div>
          </div>
        </div>

        <div v-if="activeTab === 'payments'" class="tab-content">
          <div class="detail-section">
            <h3>Payments</h3>

            <div class="section-header">
              <h3>Add Payment</h3>
            </div>
            <div class="add-form">
              <div class="form-grid">
                <div class="form-field">
                  <label>Amount</label>
                  <input v-model.number="newPayment.amount" type="number" step="0.01" />
                </div>
                <div class="form-field">
                  <label>Payment Date</label>
                  <input v-model="newPayment.payment_date" type="date" />
                </div>
                <div class="form-field">
                  <label>Method</label>
                  <select v-model="newPayment.payment_method">
                    <option value="credit_card">Credit Card</option>
                    <option value="debit">Debit</option>
                    <option value="cash">Cash</option>
                    <option value="e_transfer">e-Transfer</option>
                    <option value="cheque">Cheque</option>
                  </select>
                </div>
                <div class="form-field full-width">
                  <label>Notes</label>
                  <input v-model="newPayment.notes" type="text" />
                </div>
              </div>
              <div class="form-actions">
                <button @click="addPayment" class="btn-primary">Add Payment</button>
              </div>
            </div>

            <div class="charges-table">
              <table v-if="payments.length">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Method</th>
                    <th>Amount</th>
                    <th>Notes</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="p in payments" :key="p.payment_id">
                    <td v-if="editingPaymentId !== p.payment_id">{{ new Date(p.payment_date).toLocaleDateString() }}</td>
                    <td v-else><input type="date" v-model="editingPayment.payment_date" /></td>

                    <td v-if="editingPaymentId !== p.payment_id">{{ p.payment_method }}</td>
                    <td v-else>
                      <select v-model="editingPayment.payment_method">
                        <option value="credit_card">Credit Card</option>
                        <option value="debit">Debit</option>
                        <option value="cash">Cash</option>
                        <option value="e_transfer">e-Transfer</option>
                        <option value="cheque">Cheque</option>
                      </select>
                    </td>

                    <td class="amount" v-if="editingPaymentId !== p.payment_id">${{ parseFloat(p.amount || 0).toFixed(2) }}</td>
                    <td v-else><input type="number" step="0.01" v-model.number="editingPayment.amount" class="amount-input" /></td>

                    <td v-if="editingPaymentId !== p.payment_id">{{ p.notes || '-' }}</td>
                    <td v-else><input type="text" v-model="editingPayment.notes" /></td>

                    <td class="row-actions">
                      <template v-if="editingPaymentId === p.payment_id">
                        <button class="btn-small" @click="saveEditPayment(p)">Save</button>
                        <button class="btn-secondary btn-small" @click="cancelEditPayment">Cancel</button>
                      </template>
                      <template v-else>
                        <button class="btn-small" @click="startEditPayment(p)">Edit</button>
                        <button class="btn-danger btn-small" @click="deletePayment(p)">Delete</button>
                      </template>
                    </td>
                  </tr>
                </tbody>
              </table>
              <p v-else class="no-data">No payments recorded</p>
            </div>
          </div>
        </div>
      </div>
      
      <div class="booking-detail-footer">
        <button @click="close" class="btn-secondary">Close</button>
        <button @click="editBooking" class="btn-primary">Edit Booking</button>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, watch } from 'vue'
import { toast } from '@/toast/toastStore'
import { formatDate } from '@/utils/dateFormatter'

export default {
  name: 'BookingDetail',
  props: {
    booking: {
      type: Object,
      required: true
    },
    visible: {
      type: Boolean,
      default: false
    }
  },
  emits: ['close', 'edit'],
  setup(props, { emit }) {
    const activeTab = ref('reservation')
    const charges = ref([])
    const payments = ref([])
    const financials = ref({
      charges_total: 0,
      payments_total: 0,
      retainer: 0,
      balance_due: 0
    })
    const loading = ref(false)
    const editingPaymentId = ref(null)
    const editingPayment = ref({ amount: '', payment_date: '', payment_method: 'credit_card', notes: '' })
    
    const showAddChargeForm = ref(false)
    const newCharge = ref({
      charge_type: 'service_fee',
      amount: '',
      description: ''
    })
    const editingChargeId = ref(null)
    const editingCharge = ref({ charge_type: 'service_fee', amount: '', description: '' })

    const newPayment = ref({
      amount: '',
      payment_date: '',
      payment_method: 'credit_card',
      notes: ''
    })
    
    const tabs = [
      { id: 'reservation', label: 'Reservation' },
      { id: 'charges', label: 'Charges' },
      { id: 'payments', label: 'Payments' }
    ]
    
    const loadFinancialData = async () => {
      if (!props.booking?.charter_id) return
      
      loading.value = true
      try {
        const [chargesRes, paymentsRes, financialsRes] = await Promise.all([
          fetch(`/api/charters/${props.booking.charter_id}/charges`),
          fetch(`/api/charters/${props.booking.charter_id}/payments`),
          fetch(`/api/charters/${props.booking.charter_id}/financials`)
        ])
        
        if (chargesRes.ok) {
          const chargesData = await chargesRes.json()
          charges.value = chargesData.charges || []
        }

        if (paymentsRes.ok) {
          const paymentsData = await paymentsRes.json()
          payments.value = paymentsData.payments || []
        }
        
        if (financialsRes.ok) {
          financials.value = await financialsRes.json()
        }
      } catch (error) {
        console.error('Error loading financial data:', error)
      } finally {
        loading.value = false
      }
    }
    
    const addCharge = async () => {
      if (!newCharge.value.amount || !props.booking?.charter_id) return
      
      try {
        const response = await fetch(`/api/charters/${props.booking.charter_id}/charges`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newCharge.value)
        })
        
        if (response.ok) {
          newCharge.value = { charge_type: 'service_fee', amount: '', description: '' }
          showAddChargeForm.value = false
          await loadFinancialData()
        } else {
          toast.error('Failed to add charge')
        }
      } catch (error) {
        console.error('Error adding charge:', error)
        toast.error('Error adding charge')
      }
    }

    const addPayment = async () => {
      if (!newPayment.value.amount || !props.booking?.charter_id) return
      try {
        const response = await fetch(`/api/charters/${props.booking.charter_id}/payments`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newPayment.value)
        })
        if (response.ok) {
          newPayment.value = { amount: '', payment_date: '', payment_method: 'credit_card', notes: '' }
          await loadFinancialData()
        } else {
          toast.error('Failed to add payment')
        }
      } catch (e) {
        console.error('Error adding payment:', e)
        toast.error('Error adding payment')
      }
    }

    const startEditCharge = (c) => {
      editingChargeId.value = c.charge_id
      editingCharge.value = { charge_type: c.charge_type || 'service_fee', amount: c.amount, description: c.description || '' }
    }
    const cancelEditCharge = () => {
      editingChargeId.value = null
      editingCharge.value = { charge_type: 'service_fee', amount: '', description: '' }
    }
    const saveEditCharge = async (orig) => {
      try {
        const res = await fetch(`/api/charges/${orig.charge_id}`, {
          method: 'PATCH', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(editingCharge.value)
        })
        if (!res.ok) throw new Error('Failed to update charge')
        cancelEditCharge()
        await loadFinancialData()
      } catch (e) {
        console.error('saveEditCharge error', e)
        toast.error('Failed to update charge')
      }
    }
    const deleteCharge = async (c) => {
      if (!confirm('Delete this charge?')) return
      try {
        const res = await fetch(`/api/charges/${c.charge_id}`, { method: 'DELETE' })
        if (!res.ok) throw new Error('Failed to delete charge')
        await loadFinancialData()
      } catch (e) {
        console.error('deleteCharge error', e)
        toast.error('Failed to delete charge')
      }
    }

    const startEditPayment = (p) => {
      editingPaymentId.value = p.payment_id
      editingPayment.value = {
        amount: p.amount,
        payment_date: (p.payment_date || '').slice(0,10),
        payment_method: p.payment_method || 'credit_card',
        notes: p.notes || ''
      }
    }

    const cancelEditPayment = () => {
      editingPaymentId.value = null
      editingPayment.value = { amount: '', payment_date: '', payment_method: 'credit_card', notes: '' }
    }

    const saveEditPayment = async (orig) => {
      try {
        const res = await fetch(`/api/payments/${orig.payment_id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(editingPayment.value)
        })
        if (!res.ok) throw new Error('Failed to update payment')
        cancelEditPayment()
        await loadFinancialData()
      } catch (e) {
        console.error('saveEditPayment error', e)
        toast.error('Failed to update payment')
      }
    }

    const deletePayment = async (p) => {
      if (!confirm('Delete this payment?')) return
      try {
        const res = await fetch(`/api/payments/${p.payment_id}`, { method: 'DELETE' })
        if (!res.ok) throw new Error('Failed to delete payment')
        await loadFinancialData()
      } catch (e) {
        console.error('deletePayment error', e)
        toast.error('Failed to delete payment')
      }
    }
    
    const close = () => {
      emit('close')
    }
    
    const editBooking = () => {
      emit('edit', props.booking)
    }
    
    watch(() => props.booking?.charter_id, loadFinancialData, { immediate: true })
    watch(() => props.visible, (visible) => {
      if (visible) loadFinancialData()
    })
    
    return {
      activeTab,
      tabs,
      charges,
      financials,
      loading,
      showAddChargeForm,
      newCharge,
      newPayment,
      formatDate,
      close,
      editBooking,
      loadFinancialData,
      addCharge,
      addPayment,
      editingPaymentId, editingPayment, startEditPayment, cancelEditPayment, saveEditPayment, deletePayment,
      editingChargeId, editingCharge, startEditCharge, cancelEditCharge, saveEditCharge, deleteCharge
    }
  }
}
</script>

<style scoped>
.booking-detail-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.booking-detail-content {
  background: white;
  border-radius: 8px;
  width: 90%;
  max-width: 800px;
  max-height: 90%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.booking-detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid #e0e0e0;
  background: #f8f9fa;
}

.close-btn {
  background: none;
  border: none;
  font-size: 2rem;
  cursor: pointer;
  color: #666;
}

.booking-detail-tabs {
  display: flex;
  background: #f8f9fa;
  border-bottom: 1px solid #e0e0e0;
}

.tab-btn {
  background: none;
  border: none;
  padding: 1rem 1.5rem;
  cursor: pointer;
  border-bottom: 3px solid transparent;
}

.tab-btn.active {
  background: white;
  border-bottom-color: #007bff;
  color: #007bff;
}

.booking-detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

.detail-section {
  margin-bottom: 2rem;
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.detail-item {
  display: flex;
  flex-direction: column;
}

.detail-item label {
  font-weight: bold;
  color: #555;
  margin-bottom: 0.25rem;
}

.detail-item span {
  color: #333;
  padding: 0.5rem;
  background: #f8f9fa;
  border-radius: 4px;
}

.financial-summary {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 2rem;
  padding: 1rem;
  background: #f8f9fa;
  border-radius: 6px;
}

.summary-item {
  display: flex;
  justify-content: space-between;
}

.summary-item.total {
  grid-column: 1 / -1;
  border-top: 2px solid #dee2e6;
  padding-top: 0.5rem;
  font-weight: bold;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.btn-small {
  background: #28a745;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
}

.add-form {
  background: #f8f9fa;
  padding: 1rem;
  border-radius: 6px;
  margin-bottom: 1rem;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 1rem;
}

.form-field {
  display: flex;
  flex-direction: column;
}

.form-field.full-width {
  grid-column: 1 / -1;
}

.form-field label {
  font-weight: bold;
  margin-bottom: 0.25rem;
}

.form-field input,
.form-field select {
  padding: 0.5rem;
  border: 1px solid #ced4da;
  border-radius: 4px;
}

.form-actions {
  display: flex;
  gap: 0.5rem;
}

.charges-table table {
  width: 100%;
  border-collapse: collapse;
}

.charges-table th,
.charges-table td {
  padding: 0.75rem;
  text-align: left;
  border-bottom: 1px solid #e0e0e0;
}

.charges-table th {
  background: #f8f9fa;
  font-weight: bold;
}

.amount {
  text-align: right;
  font-family: monospace;
}

.no-data {
  color: #666;
  font-style: italic;
  text-align: center;
  padding: 2rem;
}

.booking-detail-footer {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  padding: 1rem 1.5rem;
  border-top: 1px solid #e0e0e0;
  background: #f8f9fa;
}

.btn-secondary {
  background: #6c757d;
  color: white;
  border: none;
  padding: 0.75rem 1.5rem;
  border-radius: 4px;
  cursor: pointer;
}

.btn-primary {
  background: #007bff;
  color: white;
  border: none;
  padding: 0.75rem 1.5rem;
  border-radius: 4px;
  cursor: pointer;
}
.btn-danger { background: #dc3545; color: #fff; border: none; padding: 0.5rem 0.75rem; border-radius: 4px; cursor: pointer; }
.btn-small { padding: 0.25rem 0.5rem; font-size: 0.9rem; }
.row-actions { white-space: nowrap; display: flex; gap: 0.5rem; align-items: center; }
.amount-input { width: 120px; text-align: right; }
</style>
