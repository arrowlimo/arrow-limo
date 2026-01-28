<template>
  <ProfessionalForm
    title="Customer Management"
    :mode="mode"
    v-model="formData"
    :tabs="formTabs"
    :is-valid="isValid"
    :validation-errors="validationErrors"
    @submit="handleSave"
    @delete="handleDelete"
    @print="handlePrint"
  >
    <!-- Contact Information Tab -->
    <template #tab-contact>
      <div class="form-grid">
        <FormField
          v-model="formData.client_name"
          type="text"
          label="Client Name (First & Last)"
          placeholder="John Smith"
          :required="true"
          :tabindex="10"
          :error="validationErrors.client_name"
          help-text="Full legal name"
          @blur="validateField('client_name')"
        />

        <FormField
          v-model="formData.client_type"
          type="select"
          label="Client Type"
          :options="clientTypeOptions"
          :required="true"
          :tabindex="11"
          @blur="validateField('client_type')"
        />

        <FormField
          v-model="formData.company_name"
          type="text"
          label="Company Name"
          placeholder="Optional for corporate clients"
          :tabindex="12"
          :disabled="formData.client_type !== 'Corporate'"
        />

        <FormField
          v-model="formData.contact_person"
          type="text"
          label="Contact Person"
          placeholder="Primary contact for corporate accounts"
          :tabindex="13"
          :disabled="formData.client_type !== 'Corporate'"
        />

        <FormField
          v-model="formData.phone"
          type="tel"
          label="Phone"
          placeholder="(555) 555-5555"
          :required="true"
          :tabindex="14"
          :maxlength="14"
          :error="validationErrors.phone"
          @input="formatPhone"
          @blur="validateField('phone')"
        />

        <FormField
          v-model="formData.email"
          type="email"
          label="Email"
          placeholder="customer@example.com"
          :required="true"
          :tabindex="15"
          :error="validationErrors.email"
          autocomplete="email"
          @blur="validateField('email')"
        />

        <FormField
          v-model="formData.account_number"
          type="text"
          label="Account Number"
          :readonly="true"
          :tabindex="-1"
          help-text="Auto-generated"
        />

        <FormField
          v-model="formData.client_id"
          type="text"
          label="Client ID"
          :readonly="true"
          :tabindex="-1"
          help-text="Auto-generated"
        />
      </div>
    </template>

    <!-- Billing Address Tab -->
    <template #tab-billing>
      <div class="form-grid">
        <FormField
          v-model="formData.billing_address"
          type="text"
          label="Street Address"
          placeholder="123 Main St"
          :required="true"
          :tabindex="20"
          :error="validationErrors.billing_address"
          class="full-width"
          @blur="validateField('billing_address')"
        />

        <FormField
          v-model="formData.city"
          type="text"
          label="City"
          placeholder="Calgary"
          :required="true"
          :tabindex="21"
          :error="validationErrors.city"
          @blur="validateField('city')"
        />

        <FormField
          v-model="formData.province"
          type="select"
          label="Province"
          :options="provinceOptions"
          :required="true"
          :tabindex="22"
          @blur="validateField('province')"
        />

        <FormField
          v-model="formData.postal_code"
          type="text"
          label="Postal Code"
          placeholder="T2X 1Y9"
          :required="true"
          :tabindex="23"
          :maxlength="7"
          :error="validationErrors.postal_code"
          @input="formatPostalCode"
          @blur="validateField('postal_code')"
        />
      </div>
    </template>

    <!-- Payment Information Tab -->
    <template #tab-payment>
      <div class="form-grid">
        <FormField
          v-model="formData.credit_card"
          type="text"
          label="Credit Card Number"
          placeholder="•••• •••• •••• 1234"
          :tabindex="30"
          :maxlength="19"
          help-text="Last 4 digits only for security"
          @input="formatCreditCard"
        />

        <FormField
          v-model="formData.exp"
          type="text"
          label="Expiry Date"
          placeholder="MM/YY"
          :tabindex="31"
          :maxlength="5"
          :error="validationErrors.exp"
          @input="formatExpiry"
          @blur="validateField('exp')"
        />

        <FormField
          v-model="formData.cvv"
          type="text"
          label="CVV"
          placeholder="123"
          :tabindex="32"
          :maxlength="4"
          help-text="Security code"
        />
      </div>
    </template>

    <!-- GST Exemption Tab -->
    <template #tab-gst>
      <div class="form-grid">
        <FormField
          v-model="formData.is_gst_exempt"
          type="checkbox"
          label="GST Exempt?"
          checkbox-label="This customer is exempt from GST"
          :tabindex="40"
        />

        <FormField
          v-model="formData.exemption_certificate_number"
          type="text"
          label="Exemption Certificate Number"
          :tabindex="41"
          :disabled="!formData.is_gst_exempt"
          class="full-width"
        />

        <FormField
          v-model="formData.exemption_type"
          type="select"
          label="Exemption Type"
          :options="exemptionTypeOptions"
          :tabindex="42"
          :disabled="!formData.is_gst_exempt"
        />

        <FormField
          v-model="formData.exemption_certificate_expiry"
          type="date"
          label="Certificate Expiry"
          :tabindex="43"
          :disabled="!formData.is_gst_exempt"
        />

        <FormField
          v-model="formData.exemption_notes"
          type="textarea"
          label="Exemption Notes"
          :tabindex="44"
          :rows="3"
          :disabled="!formData.is_gst_exempt"
          class="full-width"
        />
      </div>
    </template>

    <!-- Collections Tab -->
    <template #tab-collections>
      <div class="form-grid">
        <FormField
          v-model="formData.bad_debt_status"
          type="select"
          label="Bad Debt Status"
          :options="badDebtStatusOptions"
          :tabindex="50"
        />

        <FormField
          v-model="formData.collection_attempts_count"
          type="number"
          label="Collection Attempts"
          :tabindex="51"
          :min="0"
          :readonly="true"
        />

        <FormField
          v-model="formData.last_collection_date"
          type="date"
          label="Last Collection Date"
          :tabindex="52"
        />

        <FormField
          v-model="formData.first_overdue_date"
          type="date"
          label="First Overdue Date"
          :tabindex="53"
        />

        <FormField
          v-model="formData.writeoff_date"
          type="date"
          label="Writeoff Date"
          :tabindex="54"
        />

        <FormField
          v-model="formData.writeoff_amount"
          type="currency"
          label="Writeoff Amount"
          :tabindex="55"
        />

        <FormField
          v-model="formData.bankruptcy_status"
          type="select"
          label="Bankruptcy Status"
          :options="bankruptcyStatusOptions"
          :tabindex="56"
        />

        <FormField
          v-model="formData.recovery_probability"
          type="select"
          label="Recovery Probability"
          :options="recoveryProbabilityOptions"
          :tabindex="57"
        />

        <FormField
          v-model="formData.bad_debt_reason"
          type="textarea"
          label="Bad Debt Reason"
          :tabindex="58"
          :rows="3"
          class="full-width"
        />

        <FormField
          v-model="formData.collection_notes"
          type="textarea"
          label="Collection Notes"
          :tabindex="59"
          :rows="4"
          class="full-width"
        />
      </div>
    </template>

    <!-- Notes Tab -->
    <template #tab-notes>
      <div class="form-grid">
        <FormField
          v-model="formData.notes"
          type="textarea"
          label="General Notes"
          :tabindex="60"
          :rows="10"
          :maxlength="5000"
          class="full-width"
          help-text="Any additional information about this customer"
        />
      </div>
    </template>
  </ProfessionalForm>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { toast } from '@/toast/toastStore'
import ProfessionalForm from './ProfessionalForm.vue'
import FormField from './FormField.vue'

const props = defineProps({
  customerId: { type: String, default: null },
  initialMode: { type: String, default: 'create' }
})

const emit = defineEmits(['saved', 'deleted', 'cancelled'])

// Form data
const formData = ref({
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
  province: 'AB',
  postal_code: '',
  credit_card: '',
  exp: '',
  cvv: '',
  is_gst_exempt: false,
  exemption_certificate_number: '',
  exemption_certificate_expiry: '',
  exemption_type: '',
  exemption_notes: '',
  bad_debt_status: 'None',
  collection_attempts_count: 0,
  last_collection_date: '',
  first_overdue_date: '',
  writeoff_date: '',
  writeoff_amount: 0,
  bankruptcy_status: 'None',
  collection_notes: '',
  bad_debt_reason: '',
  recovery_probability: 'Unknown',
  notes: ''
})

const mode = ref(props.initialMode)
const validationErrors = ref({})

// Form tabs configuration
const formTabs = [
  { id: 'contact', label: 'Contact Info', icon: '👤' },
  { id: 'billing', label: 'Billing Address', icon: '📍' },
  { id: 'payment', label: 'Payment', icon: '💳' },
  { id: 'gst', label: 'GST Exemption', icon: '📋' },
  { id: 'collections', label: 'Collections', icon: '💰' },
  { id: 'notes', label: 'Notes', icon: '📝' }
]

// Options for select fields
const clientTypeOptions = [
  { value: 'Individual', label: 'Individual' },
  { value: 'Corporate', label: 'Corporate' }
]

const provinceOptions = [
  { value: 'AB', label: 'Alberta' },
  { value: 'BC', label: 'British Columbia' },
  { value: 'SK', label: 'Saskatchewan' },
  { value: 'MB', label: 'Manitoba' },
  { value: 'ON', label: 'Ontario' },
  { value: 'QC', label: 'Quebec' },
  { value: 'NB', label: 'New Brunswick' },
  { value: 'NS', label: 'Nova Scotia' },
  { value: 'PE', label: 'Prince Edward Island' },
  { value: 'NL', label: 'Newfoundland and Labrador' },
  { value: 'YT', label: 'Yukon' },
  { value: 'NT', label: 'Northwest Territories' },
  { value: 'NU', label: 'Nunavut' }
]

const exemptionTypeOptions = [
  { value: '', label: 'Select...' },
  { value: 'Government', label: 'Government' },
  { value: 'Diplomatic', label: 'Diplomatic' },
  { value: 'Indigenous', label: 'Indigenous Band' },
  { value: 'Charitable', label: 'Registered Charity' },
  { value: 'Other', label: 'Other' }
]

const badDebtStatusOptions = [
  { value: 'None', label: 'None' },
  { value: 'Warning', label: 'Warning' },
  { value: 'Collections', label: 'In Collections' },
  { value: 'Legal', label: 'Legal Action' },
  { value: 'Written Off', label: 'Written Off' },
  { value: 'Bankruptcy', label: 'Bankruptcy' }
]

const bankruptcyStatusOptions = [
  { value: 'None', label: 'None' },
  { value: 'Filed', label: 'Filed' },
  { value: 'Discharged', label: 'Discharged' },
  { value: 'Proposal', label: 'Consumer Proposal' }
]

const recoveryProbabilityOptions = [
  { value: 'Unknown', label: 'Unknown' },
  { value: 'High', label: 'High (>70%)' },
  { value: 'Medium', label: 'Medium (30-70%)' },
  { value: 'Low', label: 'Low (<30%)' },
  { value: 'None', label: 'None (0%)' }
]

// Validation
const isValid = computed(() => {
  return Object.keys(validationErrors.value).length === 0 &&
    formData.value.client_name &&
    formData.value.phone &&
    formData.value.email &&
    formData.value.billing_address &&
    formData.value.city &&
    formData.value.province &&
    formData.value.postal_code
})

function validateField(fieldName) {
  delete validationErrors.value[fieldName]

  switch (fieldName) {
    case 'client_name':
      if (!formData.value.client_name) {
        validationErrors.value.client_name = 'Client name is required'
      } else if (formData.value.client_name.length < 2) {
        validationErrors.value.client_name = 'Name must be at least 2 characters'
      }
      break

    case 'phone':
      if (!formData.value.phone) {
        validationErrors.value.phone = 'Phone number is required'
      } else if (formData.value.phone.replace(/\D/g, '').length !== 10) {
        validationErrors.value.phone = 'Phone must be 10 digits'
      }
      break

    case 'email':
      if (!formData.value.email) {
        validationErrors.value.email = 'Email is required'
      } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.value.email)) {
        validationErrors.value.email = 'Invalid email format'
      }
      break

    case 'postal_code':
      if (!formData.value.postal_code) {
        validationErrors.value.postal_code = 'Postal code is required'
      } else if (!/^[A-Z]\d[A-Z] \d[A-Z]\d$/.test(formData.value.postal_code)) {
        validationErrors.value.postal_code = 'Invalid postal code (A1A 1A1)'
      }
      break

    case 'exp':
      if (formData.value.exp && !/^\d{2}\/\d{2}$/.test(formData.value.exp)) {
        validationErrors.value.exp = 'Invalid expiry format (MM/YY)'
      }
      break

    case 'billing_address':
      if (!formData.value.billing_address) {
        validationErrors.value.billing_address = 'Billing address is required'
      }
      break

    case 'city':
      if (!formData.value.city) {
        validationErrors.value.city = 'City is required'
      }
      break
  }
}

// Input formatters
function formatPhone() {
  let x = formData.value.phone.replace(/\D/g, '')
  x = x.substring(0, 10)
  let formatted = ''
  if (x.length > 0) {
    formatted = '(' + x.substring(0, 3)
    if (x.length >= 4) formatted += ') ' + x.substring(3, 6)
    if (x.length >= 7) formatted += '-' + x.substring(6, 10)
  }
  formData.value.phone = formatted
}

function formatPostalCode() {
  let x = formData.value.postal_code.toUpperCase().replace(/[^A-Z0-9]/g, '')
  x = x.substring(0, 6)
  if (x.length > 3) {
    formData.value.postal_code = x.substring(0, 3) + ' ' + x.substring(3)
  } else {
    formData.value.postal_code = x
  }
}

function formatCreditCard() {
  let x = formData.value.credit_card.replace(/\D/g, '')
  x = x.substring(0, 16)
  formData.value.credit_card = x.match(/.{1,4}/g)?.join(' ') || x
}

function formatExpiry() {
  let x = formData.value.exp.replace(/\D/g, '')
  x = x.substring(0, 4)
  if (x.length >= 3) {
    formData.value.exp = x.substring(0, 2) + '/' + x.substring(2)
  } else {
    formData.value.exp = x
  }
}

// CRUD operations
async function handleSave() {
  // Validate all fields
  validateField('client_name')
  validateField('phone')
  validateField('email')
  validateField('billing_address')
  validateField('city')
  validateField('postal_code')
  
  if (!isValid.value) {
    toast.error('Please fix validation errors before saving')
    return
  }

  try {
    const url = mode.value === 'create' 
      ? '/api/clients' 
      : `/api/clients/${props.customerId}`
    
    const method = mode.value === 'create' ? 'POST' : 'PUT'
    
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData.value)
    })
    
    if (res.ok) {
      const saved = await res.json()
      toast.success(`Customer ${mode.value === 'create' ? 'created' : 'updated'} successfully!`)
      emit('saved', saved)
      if (mode.value === 'create') {
        mode.value = 'edit'
      }
    } else {
      const err = await res.text()
      toast.error('Save failed: ' + err)
    }
  } catch (e) {
    toast.error('Save failed: ' + e.message)
  }
}

async function handleDelete() {
  if (!props.customerId) return
  
  try {
    const res = await fetch(`/api/clients/${props.customerId}`, {
      method: 'DELETE'
    })
    
    if (res.ok) {
      toast.success('Customer deleted successfully!')
      emit('deleted')
    } else {
      const err = await res.text()
      toast.error('Delete failed: ' + err)
    }
  } catch (e) {
    toast.error('Delete failed: ' + e.message)
  }
}

function handlePrint() {
  window.print()
}

// Load existing customer data
onMounted(async () => {
  if (props.customerId && mode.value === 'edit') {
    try {
      const res = await fetch(`/api/clients/${props.customerId}`)
      if (res.ok) {
        const data = await res.json()
        Object.assign(formData.value, data)
      } else {
        toast.error('Failed to load customer data')
      }
    } catch (e) {
      toast.error('Failed to load customer: ' + e.message)
    }
  }
})
</script>

<style scoped>
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.full-width {
  grid-column: 1 / -1;
}

@media (max-width: 768px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
