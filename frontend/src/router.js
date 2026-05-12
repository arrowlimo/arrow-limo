import { createRouter, createWebHistory } from 'vue-router'
import Login from './views/Login.vue'
import Main from './views/Main.vue'

const Dispatch = () => import('./views/Dispatch.vue')
const Charter = () => import('./views/Charter.vue')
const Vehicles = () => import('./views/Vehicles.vue')
const Employees = () => import('./views/Employees.vue')
const Customers = () => import('./views/Customers.vue')
const Accounting = () => import('./views/Accounting.vue')
const Reports = () => import('./views/Reports.vue')
const OweDavid = () => import('./views/OweDavid.vue')
const Admin = () => import('./views/Admin.vue')
const Drivers = () => import('./views/Drivers.vue')
const DriverHOSLog = () => import('./views/DriverHOSLog.vue')
const ReceiptsView = () => import('./views/ReceiptsView.vue')
const BookingPage = () => import('./views/BookingPage.vue')
const TableManagement = () => import('./views/TableManagement.vue')
const T2DataEntry = () => import('./components/T2DataEntry.vue')
const ChequeBookManagement = () => import('./views/ChequeBookManagement.vue')
const ReceivedPayments = () => import('./views/ReceivedPayments.vue')
const PayrollManagement = () => import('./views/PayrollManagement.vue')
const TaxManagement = () => import('./views/TaxManagement.vue')
const CashBoxManagement = () => import('./views/CashBoxManagement.vue')
const BeverageReconciliation = () => import('./views/BeverageReconciliation.vue')
const YearEndClose = () => import('./views/YearEndClose.vue')
const PayrollCompliance = () => import('./views/PayrollCompliance.vue')
const DocumentManagement = () => import('./views/DocumentManagement.vue')
const AuditCenter = () => import('./views/AuditCenter.vue')

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
  { path: '/charter/:id', component: Charter, meta: { requiresAuth: true } },
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
  { path: '/payroll', component: PayrollManagement, meta: { requiresAuth: true } },
  { path: '/tax-management', component: TaxManagement, meta: { requiresAuth: true } },
  { path: '/cash-box', component: CashBoxManagement, meta: { requiresAuth: true } },
  { path: '/beverage-reconciliation', component: BeverageReconciliation, meta: { requiresAuth: true } },
  { path: '/year-end-close', component: YearEndClose, meta: { requiresAuth: true } },
  { path: '/payroll-compliance', component: PayrollCompliance, meta: { requiresAuth: true } },
  { path: '/audit-center', component: AuditCenter, meta: { requiresAuth: true } },
  { path: '/documents', component: DocumentManagement, meta: { requiresAuth: true } },
  { path: '/drivers', component: Drivers, meta: { requiresAuth: true } },
  { path: '/driver-hos', component: DriverHOSLog, meta: { requiresAuth: true } },
  { path: '/booking', component: BookingPage, meta: { requiresAuth: true } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

let lastTokenValidationTs = 0
const TOKEN_VALIDATE_CACHE_MS = 60 * 1000

const clearAuthState = () => {
  localStorage.removeItem('auth_token')
  localStorage.removeItem('user')
  localStorage.removeItem('user_role')
  localStorage.removeItem('user_permissions')
}

const validateToken = async (token) => {
  if (!token) return false
  const now = Date.now()
  if (now - lastTokenValidationTs < TOKEN_VALIDATE_CACHE_MS) {
    return true
  }

  try {
    const response = await fetch('/auth/validate', {
      headers: {
        Authorization: `Bearer ${token}`
      }
    })
    if (!response.ok) {
      return false
    }
    const payload = await response.json()
    const user = payload.user || {}
    localStorage.setItem('user', JSON.stringify(user))
    localStorage.setItem('user_role', user.role || 'user')
    localStorage.setItem('user_permissions', JSON.stringify(user.permissions || {}))
    lastTokenValidationTs = now
    return true
  } catch (err) {
    console.warn('Token validation failed:', err)
    return false
  }
}

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
    console.warn('Auto-login check unavailable:', err)
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
  // Protected routes always require a currently valid token.
  else if (requiresAuth && token) {
    const valid = await validateToken(token)
    if (valid) {
      next()
    } else {
      clearAuthState()
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
