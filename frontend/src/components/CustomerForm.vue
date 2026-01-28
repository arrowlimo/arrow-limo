<template>
    <form @submit.prevent="submitForm">
      <h2>Customer Information</h2>
      <div class="container-row">
        <div class="container-box left-box">
          <div class="form-row">
            <label>Client Name (First & Last)</label>
            <input v-model="form.client_name" type="text" class="half-width" />
          </div>
          <div class="form-row">
            <label>Phone</label>
            <input v-model="form.phone" type="text" @input="onPhoneInput" placeholder="(555) 555-5555" maxlength="14" class="half-width" />
          </div>
          <div class="form-row">
            <label>Email</label>
            <input v-model="form.email" type="email" list="email-domains" @input="onEmailInput" class="half-width" />
            <datalist id="email-domains">
              <option value="@shaw.ca" />
              <option value="@telus.ca" />
              <option value="@gmail.ca" />
              <option value="@gmail.com" />
              <option value="@outlook.com" />
            </datalist>
          </div>
        </div>
        <!-- Credit Card & Address Container -->
        <div class="container-box right-box">
          <div class="form-row">
            <label>Credit Card</label>
            <input v-model="form.credit_card" type="text" maxlength="19" placeholder="Card Number" />
          </div>
          <div class="form-row">
            <label>Exp</label>
            <input v-model="form.exp" type="text" maxlength="5" placeholder="MM/YY" />
          </div>
          <div class="form-row">
            <label>CVV</label>
            <input v-model="form.cvv" type="text" maxlength="4" placeholder="CVV" />
          </div>
          <!-- Address fields below credit card fields -->
          <div class="form-row">
            <label>Billing Address</label>
            <input v-model="form.billing_address" type="text" />
          </div>
          <div class="form-row">
            <label>City</label>
            <input v-model="form.city" type="text" />
          </div>
          <div class="form-row">
            <label>Province</label>
            <input v-model="form.province" type="text" />
          </div>
          <div class="form-row">
            <label>Postal Code</label>
            <input v-model="form.postal_code" type="text" />
          </div>
        </div>
      </div>
    <div class="form-row">
      <label>Client Type</label>
      <select v-model="form.client_type">
        <option value="Individual">Individual</option>
        <option value="Corporate">Corporate</option>
      </select>
    </div>
    <div class="form-row">
      <label>Account Number</label>
      <input v-model="form.account_number" type="text" />
    </div>
    <div class="form-row">
      <label>Client ID</label>
      <input v-model="form.client_id" type="text" />
    </div>
    <div class="form-row">
      <label>Company Name</label>
      <input v-model="form.company_name" type="text" />
    </div>
    <div class="form-row">
      <label>Contact Person</label>
      <input v-model="form.contact_person" type="text" />
    </div>
    <div class="form-row">
      <label>Credit Card</label>
      <input v-model="form.credit_card" type="text" />
    </div>
    <div class="form-row">
      <label>Exp</label>
      <input v-model="form.exp" type="text" />
    </div>
    <div class="form-row">
      <label>CVV</label>
      <input v-model="form.cvv" type="text" />
    </div>
    <div class="form-row">
      <label>Created At</label>
      <input v-model="form.created_at" type="date" />
    </div>
    <div class="form-row">
      <label>Updated At</label>
      <input v-model="form.updated_at" type="date" />
    </div>
    <div class="form-row">
      <label>GST Exempt?</label>
      <input type="checkbox" v-model="form.is_gst_exempt" />
    </div>
    <div class="form-row">
      <label>Exemption Certificate Number</label>
      <input v-model="form.exemption_certificate_number" type="text" />
    </div>
    <div class="form-row">
      <label>Exemption Certificate Expiry</label>
      <input v-model="form.exemption_certificate_expiry" type="date" />
    </div>
    <div class="form-row">
      <label>Exemption Type</label>
      <input v-model="form.exemption_type" type="text" />
    </div>
    <div class="form-row">
      <label>Exemption Notes</label>
      <textarea v-model="form.exemption_notes"></textarea>
    </div>
    <div class="form-row">
      <label>Bad Debt Status</label>
      <input v-model="form.bad_debt_status" type="text" />
    </div>
    <div class="form-row">
      <label>Collection Attempts Count</label>
      <input v-model="form.collection_attempts_count" type="number" />
    </div>
    <div class="form-row">
      <label>Last Collection Date</label>
      <input v-model="form.last_collection_date" type="date" />
    </div>
    <div class="form-row">
      <label>First Overdue Date</label>
      <input v-model="form.first_overdue_date" type="date" />
    </div>
    <div class="form-row">
      <label>Writeoff Date</label>
      <input v-model="form.writeoff_date" type="date" />
    </div>
    <div class="form-row">
      <label>Writeoff Amount</label>
      <input v-model="form.writeoff_amount" type="number" step="0.01" />
    </div>
    <div class="form-row">
      <label>Bankruptcy Status</label>
      <input v-model="form.bankruptcy_status" type="text" />
    </div>
    <div class="form-row">
      <label>Collection Notes</label>
      <textarea v-model="form.collection_notes"></textarea>
    </div>
    <div class="form-row">
      <label>Bad Debt Reason</label>
      <input v-model="form.bad_debt_reason" type="text" />
    </div>
    <div class="form-row">
      <label>Recovery Probability</label>
      <input v-model="form.recovery_probability" type="text" />
    </div>
    <div class="form-row">
      <label>Notes</label>
      <textarea v-model="form.notes"></textarea>
    </div>
    <button type="submit">Save Customer</button>
  </form>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { toast } from '@/toast/toastStore'
const form = ref({
  client_type: 'Individual',
  account_number: '',
  client_id: '',
  client_name: '',
  company_name: '',
  contact_person: '',
  phone: '',
  email: '',
  billing_address: '',
  city: '',
  province: '',
  postal_code: '',
  credit_card: '',
  exp: '',
  cvv: '',
  created_at: '',
  updated_at: '',
  is_gst_exempt: false,
  exemption_certificate_number: '',
  exemption_certificate_expiry: '',
  exemption_type: '',
  exemption_notes: '',
  bad_debt_status: '',
  collection_attempts_count: 0,
  last_collection_date: '',
  first_overdue_date: '',
  writeoff_date: '',
  writeoff_amount: 0,
  bankruptcy_status: '',
  collection_notes: '',
  bad_debt_reason: '',
  recovery_probability: '',
  notes: ''
})

const clientList = ref([])
const nameSuggestions = ref([])
const emailSuggestions = ref([])
const phoneSuggestions = ref([])
const filteredNames = ref([])
const filteredEmails = ref([])
const filteredPhones = ref([])

onMounted(async () => {
  try {
  const res = await fetch('/api/clients')
    if (res.ok) {
      clientList.value = await res.json()
      nameSuggestions.value = clientList.value.map(c => c.client_name || c.name || '')
      emailSuggestions.value = clientList.value.map(c => c.email || '')
      phoneSuggestions.value = clientList.value.map(c => c.phone || '')
    } else {
      console.error('Failed to fetch clients:', res.status)
    }
  } catch (err) {
    console.error('Error fetching clients:', err)
  }
})

function onNameInput(e) {
  const val = e.target.value.toLowerCase()
  filteredNames.value = nameSuggestions.value.filter(n => n && n.toLowerCase().includes(val))
}
function onEmailInput(e) {
  const val = e.target.value.toLowerCase()
  filteredEmails.value = emailSuggestions.value.filter(n => n && n.toLowerCase().includes(val))
}
function onPhoneInput(e) {
  let x = e.target.value.replace(/\D/g, "");
  x = x.substring(0, 10);
  let formatted = "";
  if (x.length > 0) {
    formatted = "(" + x.substring(0, 3);
    if (x.length >= 4) formatted += ") " + x.substring(3, 6);
    if (x.length >= 7) formatted += "-" + x.substring(6, 10);
  }
  e.target.value = formatted;
  form.value.phone = formatted;
  const val = formatted.replace(/\D/g, "");
  filteredPhones.value = phoneSuggestions.value.filter(n => n && n.replace(/\D/g, "").includes(val))
}

async function submitForm() {
  try {
  const res = await fetch('/api/clients', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form.value)
    });
    if (res.ok) {
      toast.success('Customer saved!')
    } else {
      const err = await res.text();
      toast.error('Save failed: ' + err)
    }
  } catch (e) {
    toast.error('Save failed: ' + e)
  }
}

</script>

<style scoped>
.container-row {
  display: flex;
  flex-direction: row;
  gap: 2rem;
  justify-content: flex-start;
  align-items: flex-start;
}
.left-box {
  width: 47.5%;
  min-width: 190px;
  max-width: 286px;
}
.right-box {
  width: 60%;
  min-width: 220px;
  max-width: 400px;
}

.container-box {
  border: 2px solid #1976d2;
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 2rem;
  background: #f5f8ff;
  box-shadow: 0 2px 8px rgba(25, 118, 210, 0.08);
  width: 47.5%;
  min-width: 190px;
  max-width: 286px;
}

.half-width {
  width: 47.5%;
  min-width: 190px;
  max-width: 286px;
}
form {
  max-width: 700px;
  margin: 2rem auto;
  background: #fff;
  padding: 2rem;
  border-radius: 10px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
}
.form-row {
  display: flex;
  flex-direction: column;
  margin-bottom: 1rem;
}
label {
  font-weight: 500;
  margin-bottom: 0.3rem;
}
input, select, textarea {
  padding: 0.5rem;
  border-radius: 5px;
  border: 1px solid #ddd;
  font-size: 1rem;
}
button {
  margin-top: 1.5rem;
  padding: 0.75rem 2rem;
  background: #667eea;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 1.1rem;
  cursor: pointer;
}
button:hover {
  background: #4f46e5;
}
</style>
