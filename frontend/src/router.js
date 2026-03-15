import { createRouter, createWebHistory } from 'vue-router'
import Login from './views/Login.vue'
import Main from './views/Main.vue'
import Dispatch from './views/Dispatch.vue'
import Charter from './views/Charter.vue'
import Vehicles from './views/Vehicles.vue'
import Employees from './views/Employees.vue'
import Customers from './views/Customers.vue'
import Accounting from './views/Accounting.vue'
import Reports from './views/Reports.vue'
import OweDavid from './views/OweDavid.vue'
import Admin from './views/Admin.vue'
import Drivers from './views/Drivers.vue'
import DriverHOSLog from './views/DriverHOSLog.vue'
import ReceiptsView from './views/ReceiptsView.vue'
import BookingPage from './views/BookingPage.vue'
import QuoteGenerator from './views/QuoteGenerator.vue'
import TableManagement from './views/TableManagement.vue'
import T2DataEntry from './components/T2DataEntry.vue'
import ChequeBookManagement from './views/ChequeBookManagement.vue'
import ReceivedPayments from './views/ReceivedPayments.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    name: 'Main',
    component: Main,
    meta: { requiresAuth: true }
  },
  { path: '/dispatch', component: Dispatch, meta: { requiresAuth: true } },
  { path: '/charter', component: Charter, meta: { requiresAuth: true } },
  { path: '/quote-generator', component: QuoteGenerator, meta: { requiresAuth: true } },
  { path: '/vehicles', component: Vehicles, meta: { requiresAuth: true } },
  { path: '/employees', component: Employees, meta: { requiresAuth: true } },
  { path: '/customers', component: Customers, meta: { requiresAuth: true } },
  { path: '/accounting', component: Accounting, meta: { requiresAuth: true } },
  { path: '/t2-corporate-tax', component: T2DataEntry, meta: { requiresAuth: true } },
  { path: '/receipts', component: ReceiptsView, meta: { requiresAuth: true } },
  { path: '/reports', component: Reports, meta: { requiresAuth: true } },
  { path: '/owe-david', component: OweDavid, meta: { requiresAuth: true } },
  { path: '/admin', component: Admin, meta: { requiresAuth: true } },
  { path: '/table-management', component: TableManagement, meta: { requiresAuth: true } },
  { path: '/cheque-books', component: ChequeBookManagement, meta: { requiresAuth: true } },
  { path: '/received-payments', component: ReceivedPayments, meta: { requiresAuth: true } },
  { path: '/drivers', component: Drivers, meta: { requiresAuth: true } },
  { path: '/driver-hos', component: DriverHOSLog, meta: { requiresAuth: true } },
  { path: '/booking', component: BookingPage, meta: { requiresAuth: true } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Check if auto-login is enabled (for local development)
const checkAutoLogin = async () => {
  try {
    const response = await fetch('/auth/auto-login-check')
    if (response.ok) {
      const data = await response.json()
      if (data.auto_login && data.token) {
        // Auto-login enabled - store credentials
        localStorage.setItem('auth_token', data.token)
        localStorage.setItem('user', JSON.stringify(data.user || {}))
        localStorage.setItem('user_role', data.user?.role || 'admin')
        localStorage.setItem('user_permissions', JSON.stringify(data.user?.permissions || {}))
        console.log('Auto-login enabled for local development')
        return true
      }
    }
  } catch (err) {
    // Auto-login not available, proceed normally
  }
  return false
}

// Auth guard
router.beforeEach(async (to, from, next) => {
  const token = localStorage.getItem('auth_token')
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth)
  
  // If trying to access protected route without token, check auto-login first
  if (requiresAuth && !token) {
    const autoLoggedIn = await checkAutoLogin()
    if (autoLoggedIn) {
      next()
    } else {
      next('/login')
    }
  } 
  // If already logged in and trying to access login page, go to home
  else if (to.path === '/login' && token) {
    next('/')
  } 
  // Otherwise, proceed normally
  else {
    next()
  }
})

export default router
