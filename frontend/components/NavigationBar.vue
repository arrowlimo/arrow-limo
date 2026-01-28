<template>
  <header class="navbar">
    <div class="logo">Arrow Limousine</div>
    <nav>
      <router-link to="/dashboard">Dashboard</router-link>
      <router-link to="/dispatch">Dispatch</router-link>
      <router-link to="/charter">Charter</router-link>
      <router-link to="/vehicles">Vehicles</router-link>
      <router-link to="/employees">Employees</router-link>
      <router-link to="/customers">Customers</router-link>
    </nav>
  </header>
</template>

<script setup>
// Navigation logic if needed
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
