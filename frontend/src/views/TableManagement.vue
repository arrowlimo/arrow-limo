<template>
  <div class="table-management">
    <h1>📊 Master Data Table Management</h1>
    <p class="subtitle">Edit operational and accounting master tables (Archive only - no deletes)</p>
    
    <div class="tabs">
      <button 
        v-for="tab in tabs" 
        :key="tab.id"
        @click="activeTab = tab.id"
        :class="['tab-button', { active: activeTab === tab.id }]"
      >
        {{ tab.icon }} {{ tab.name }}
      </button>
    </div>
    
    <!-- Chart of Accounts Tab -->
    <div v-if="activeTab === 'coa'" class="tab-content">
      <div class="table-header">
        <h2>💰 Chart of Accounts</h2>
        <div class="actions">
          <button @click="addCoaRow" class="btn-add">➕ Add Account</button>
          <button @click="saveChartOfAccounts" class="btn-save">💾 Save Changes</button>
          <button @click="loadChartOfAccounts" class="btn-refresh">🔄 Refresh</button>
        </div>
      </div>
      
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th>Code</th>
              <th>Name</th>
              <th>Type</th>
              <th>Tax?</th>
              <th>Business?</th>
              <th>Linked?</th>
              <th>Vehicle?</th>
              <th>Employee?</th>
              <th>Active</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in coaData" :key="idx">
              <td><input v-model="row.account_code" /></td>
              <td><input v-model="row.account_name" class="wide" /></td>
              <td><input v-model="row.account_type" /></td>
              <td><input type="checkbox" v-model="row.is_tax_applicable" /></td>
              <td><input type="checkbox" v-model="row.is_business_expense" /></td>
              <td><input type="checkbox" v-model="row.is_linked_account" /></td>
              <td><input type="checkbox" v-model="row.requires_vehicle" /></td>
              <td><input type="checkbox" v-model="row.requires_employee" /></td>
              <td><input type="checkbox" v-model="row.is_active" /></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    
    <!-- Receipt Categories Tab -->
    <div v-if="activeTab === 'categories'" class="tab-content">
      <div class="table-header">
        <h2>🧾 Receipt Categories</h2>
        <div class="actions">
          <button @click="addCategoryRow" class="btn-add">➕ Add Category</button>
          <button @click="saveReceiptCategories" class="btn-save">💾 Save Changes</button>
          <button @click="loadReceiptCategories" class="btn-refresh">🔄 Refresh</button>
        </div>
      </div>
      
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th>Code</th>
              <th>Name</th>
              <th>GL Account</th>
              <th>Tax-Ded?</th>
              <th>Business?</th>
              <th>Req Vehicle?</th>
              <th>Req Employee?</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in categoryData" :key="idx">
              <td><input v-model="row.category_code" /></td>
              <td><input v-model="row.category_name" class="wide" /></td>
              <td><input v-model="row.gl_account_code" /></td>
              <td><input type="checkbox" v-model="row.is_tax_deductible" /></td>
              <td><input type="checkbox" v-model="row.is_business_expense" /></td>
              <td><input type="checkbox" v-model="row.requires_vehicle" /></td>
              <td><input type="checkbox" v-model="row.requires_employee" /></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    
    <!-- Charter Types Tab -->
    <div v-if="activeTab === 'charter-types'" class="tab-content">
      <div class="table-header">
        <h2>🚗 Charter Types</h2>
        <div class="actions">
          <button @click="addCharterTypeRow" class="btn-add">➕ Add Type</button>
          <button @click="saveCharterTypes" class="btn-save">💾 Save Changes</button>
          <button @click="loadCharterTypes" class="btn-refresh">🔄 Refresh</button>
        </div>
      </div>
      
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th>Code</th>
              <th>Name</th>
              <th>Display Order</th>
              <th>Active</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in charterTypeData" :key="idx">
              <td><input v-model="row.type_code" /></td>
              <td><input v-model="row.type_name" class="wide" /></td>
              <td><input v-model.number="row.display_order" type="number" /></td>
              <td><input type="checkbox" v-model="row.is_active" /></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    
    <!-- Vehicle Pricing Tab -->
    <div v-if="activeTab === 'pricing'" class="tab-content">
      <div class="table-header">
        <h2>💵 Vehicle Pricing Defaults</h2>
        <div class="actions">
          <button @click="addPricingRow" class="btn-add">➕ Add Pricing</button>
          <button @click="saveVehiclePricing" class="btn-save">💾 Save Changes</button>
          <button @click="loadVehiclePricing" class="btn-refresh">🔄 Refresh</button>
        </div>
      </div>
      
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th>Vehicle Type</th>
              <th>Charter Type</th>
              <th>Hourly Rate</th>
              <th>Package Rate</th>
              <th>Package Hrs</th>
              <th>Extra Time</th>
              <th>Standby</th>
              <th>Active</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in pricingData" :key="idx">
              <td><input v-model="row.vehicle_type" /></td>
              <td><input v-model="row.charter_type_code" /></td>
              <td><input v-model.number="row.hourly_rate" type="number" step="0.01" /></td>
              <td><input v-model.number="row.package_rate" type="number" step="0.01" /></td>
              <td><input v-model.number="row.package_hours" type="number" step="0.1" /></td>
              <td><input v-model.number="row.extra_time_rate" type="number" step="0.01" /></td>
              <td><input v-model.number="row.standby_rate" type="number" step="0.01" /></td>
              <td><input type="checkbox" v-model="row.is_active" /></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    
    <!-- Beverages Tab -->
    <div v-if="activeTab === 'beverages'" class="tab-content">
      <div class="table-header">
        <h2>🍷 Beverages</h2>
        <div class="actions">
          <button @click="addBeverageRow" class="btn-add">➕ Add Beverage</button>
          <button @click="saveBeverages" class="btn-save">💾 Save Changes</button>
          <button @click="loadBeverages" class="btn-refresh">🔄 Refresh</button>
        </div>
      </div>
      
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Category</th>
              <th>Price</th>
              <th>Stock</th>
              <th>Active</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in beverageData" :key="idx">
              <td><input v-model="row.name" class="wide" /></td>
              <td><input v-model="row.category" /></td>
              <td><input v-model.number="row.price" type="number" step="0.01" /></td>
              <td><input v-model.number="row.stock_quantity" type="number" /></td>
              <td><input type="checkbox" v-model="row.is_active" /></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { toast } from '../toast/toastStore';

const activeTab = ref('coa');
const tabs = [
  { id: 'coa', name: 'Chart of Accounts', icon: '💰' },
  { id: 'categories', name: 'Receipt Categories', icon: '🧾' },
  { id: 'charter-types', name: 'Charter Types', icon: '🚗' },
  { id: 'pricing', name: 'Vehicle Pricing', icon: '💵' },
  { id: 'beverages', name: 'Beverages', icon: '🍷' }
];

const coaData = ref([]);
const categoryData = ref([]);
const charterTypeData = ref([]);
const pricingData = ref([]);
const beverageData = ref([]);

onMounted(() => {
  loadChartOfAccounts();
  loadReceiptCategories();
  loadCharterTypes();
  loadVehiclePricing();
  loadBeverages();
});

// Chart of Accounts
async function loadChartOfAccounts() {
  try {
    const res = await fetch('/api/table-management/chart-of-accounts');
    coaData.value = await res.json();
  } catch (error) {
    toast.error('Failed to load chart of accounts: ' + error.message);
  }
}

function addCoaRow() {
  coaData.value.push({
    account_code: '',
    account_name: '',
    account_type: 'Asset',
    is_tax_applicable: false,
    is_business_expense: false,
    is_linked_account: false,
    requires_vehicle: false,
    requires_employee: false,
    is_active: true
  });
}

async function saveChartOfAccounts() {
  try {
    const res = await fetch('/api/table-management/chart-of-accounts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(coaData.value)
    });
    if (!res.ok) throw new Error('Save failed');
    toast.success('Chart of Accounts saved successfully!');
    loadChartOfAccounts();
  } catch (error) {
    toast.error('Failed to save: ' + error.message);
  }
}

// Receipt Categories
async function loadReceiptCategories() {
  try {
    const res = await fetch('/api/table-management/receipt-categories');
    categoryData.value = await res.json();
  } catch (error) {
    toast.error('Failed to load receipt categories: ' + error.message);
  }
}

function addCategoryRow() {
  categoryData.value.push({
    category_code: '',
    category_name: '',
    gl_account_code: '',
    is_tax_deductible: false,
    is_business_expense: false,
    requires_vehicle: false,
    requires_employee: false
  });
}

async function saveReceiptCategories() {
  try {
    const res = await fetch('/api/table-management/receipt-categories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(categoryData.value)
    });
    if (!res.ok) throw new Error('Save failed');
    toast.success('Receipt categories saved successfully!');
    loadReceiptCategories();
  } catch (error) {
    toast.error('Failed to save: ' + error.message);
  }
}

// Charter Types
async function loadCharterTypes() {
  try {
    const res = await fetch('/api/table-management/charter-types');
    charterTypeData.value = await res.json();
  } catch (error) {
    toast.error('Failed to load charter types: ' + error.message);
  }
}

function addCharterTypeRow() {
  charterTypeData.value.push({
    type_code: '',
    type_name: '',
    display_order: 0,
    is_active: true
  });
}

async function saveCharterTypes() {
  try {
    const res = await fetch('/api/table-management/charter-types', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(charterTypeData.value)
    });
    if (!res.ok) throw new Error('Save failed');
    toast.success('Charter types saved successfully!');
    loadCharterTypes();
  } catch (error) {
    toast.error('Failed to save: ' + error.message);
  }
}

// Vehicle Pricing
async function loadVehiclePricing() {
  try {
    const res = await fetch('/api/table-management/vehicle-pricing');
    pricingData.value = await res.json();
  } catch (error) {
    toast.error('Failed to load vehicle pricing: ' + error.message);
  }
}

function addPricingRow() {
  pricingData.value.push({
    vehicle_type: '',
    charter_type_code: '',
    hourly_rate: 0,
    package_rate: 0,
    package_hours: 0,
    extra_time_rate: 0,
    standby_rate: 0,
    is_active: true
  });
}

async function saveVehiclePricing() {
  try {
    const res = await fetch('/api/table-management/vehicle-pricing', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(pricingData.value)
    });
    if (!res.ok) throw new Error('Save failed');
    toast.success('Vehicle pricing saved successfully!');
    loadVehiclePricing();
  } catch (error) {
    toast.error('Failed to save: ' + error.message);
  }
}

// Beverages
async function loadBeverages() {
  try {
    const res = await fetch('/api/table-management/beverages');
    beverageData.value = await res.json();
  } catch (error) {
    toast.error('Failed to load beverages: ' + error.message);
  }
}

function addBeverageRow() {
  beverageData.value.push({
    name: '',
    category: '',
    price: 0,
    stock_quantity: 0,
    is_active: true
  });
}

async function saveBeverages() {
  try {
    const res = await fetch('/api/table-management/beverages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(beverageData.value)
    });
    if (!res.ok) throw new Error('Save failed');
    toast.success('Beverages saved successfully!');
    loadBeverages();
  } catch (error) {
    toast.error('Failed to save: ' + error.message);
  }
}
</script>

<style scoped>
.table-management {
  padding: 20px;
}

h1 {
  color: #333;
  margin-bottom: 5px;
}

.subtitle {
  color: #4d4d4d;
  font-size: 14px;
  margin-bottom: 20px;
}

.tabs {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
  border-bottom: 2px solid #ddd;
}

.tab-button {
  padding: 10px 20px;
  background: transparent;
  border: none;
  border-bottom: 3px solid transparent;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.3s;
}

.tab-button:hover {
  background: #f5f5f5;
}

.tab-button.active {
  border-bottom-color: #366092;
  font-weight: bold;
  color: #366092;
}

.tab-content {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.table-header h2 {
  margin: 0;
  color: #366092;
}

.actions {
  display: flex;
  gap: 10px;
}

button {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.3s;
}

.btn-add {
  background: #1e7e34;
  color: white;
}

.btn-save {
  background: #0056b3;
  color: white;
}

.btn-refresh {
  background: #545b62;
  color: white;
}

button:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

.table-container {
  overflow-x: auto;
  max-height: 600px;
  overflow-y: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.data-table th {
  background: #366092;
  color: white;
  padding: 12px;
  text-align: left;
  position: sticky;
  top: 0;
  z-index: 10;
}

.data-table td {
  padding: 8px;
  border: 1px solid #ddd;
}

.data-table tr:nth-child(even) {
  background: #f9f9f9;
}

.data-table input[type="text"],
.data-table input[type="number"] {
  width: 100%;
  padding: 6px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 14px;
}

.data-table input.wide {
  min-width: 200px;
}

.data-table input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
}
</style>
