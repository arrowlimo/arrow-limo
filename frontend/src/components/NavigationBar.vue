<template>
  <header class="navbar">
    <div class="logo">Arrow Limousine</div>
    <nav>
              <router-link to="/" class="nav-link">Main</router-link>
      
      <!-- Driver-only sections -->
      <router-link v-if="canAccess('drivers')" to="/drivers">My Schedule</router-link>
      <router-link v-if="canAccess('driver-hos')" to="/driver-hos">HOS Log</router-link>
      
      <!-- Admin/Manager sections -->
      <router-link v-if="canAccess('dispatch')" to="/dispatch">Dispatch</router-link>
      <router-link v-if="canAccess('charter')" to="/charter">Charter</router-link>
      <router-link v-if="canAccess('quote-generator')" to="/quote-generator">Quote Generator</router-link>
      <router-link v-if="canAccess('vehicles')" to="/vehicles">Vehicles</router-link>
      <router-link v-if="canAccess('employees')" to="/employees">Employees</router-link>
      <router-link v-if="canAccess('customers')" to="/customers">Customers</router-link>
      <router-link v-if="canAccess('accounting')" to="/accounting">Accounting</router-link>
      <router-link v-if="canAccess('reports')" to="/reports">Reports</router-link>
      <router-link v-if="canAccess('documents')" to="/documents">Documents</router-link>
      <router-link v-if="canAccess('admin')" to="/admin">Admin</router-link>
    </nav>
  </header>
</template>

<script setup>
import { ref } from 'vue'

const userRole = ref(localStorage.getItem('user_role') || 'user')
const permissions = ref(JSON.parse(localStorage.getItem('user_permissions') || '{}'))

function canAccess(section) {
  // Driver role: only access driver sections
  if (userRole.value === 'driver' || userRole.value === 'operator') {
    return ['drivers', 'driver-hos'].includes(section)
  }
  
  // Admin/Superuser: access everything
  if (userRole.value === 'admin' || userRole.value === 'superuser') {
    return true
  }
  
  // Accountant: limited access including quote generator
  if (userRole.value === 'accountant') {
    return ['charter', 'quote-generator', 'accounting', 'reports', 'customers'].includes(section)
  }
  
  // Check permissions object
  if (permissions.value[section]) {
    return true
  }
  
  // Default deny
  return false
}
</script>

<style scoped>
.navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #667eea;
  color: white;
  padding: 1rem 2rem;
}
.logo {
  font-weight: bold;
  font-size: 1.5rem;
}
nav {
  display: flex;
  gap: 1.5rem;
}
nav a {
  color: white;
  text-decoration: none;
  font-weight: 500;
}
nav a.router-link-active {
  text-decoration: underline;
}
</style>
