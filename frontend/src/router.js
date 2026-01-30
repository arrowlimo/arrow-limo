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
import Documents from './views/Documents.vue'
import OweDavid from './views/OweDavid.vue'
import Admin from './views/Admin.vue'
import Drivers from './views/Drivers.vue'
import DriverHOSLog from './views/DriverHOSLog.vue'
import ReceiptsView from './views/ReceiptsView.vue'
import BookingPage from './views/BookingPage.vue'
import QuoteGenerator from './views/QuoteGenerator.vue'

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
  { path: '/receipts', component: ReceiptsView, meta: { requiresAuth: true } },
  { path: '/reports', component: Reports, meta: { requiresAuth: true } },
  { path: '/documents', component: Documents, meta: { requiresAuth: true } },
  { path: '/owe-david', component: OweDavid, meta: { requiresAuth: true } },
  { path: '/admin', component: Admin, meta: { requiresAuth: true } },
  { path: '/drivers', component: Drivers, meta: { requiresAuth: true } },
  { path: '/driver-hos', component: DriverHOSLog, meta: { requiresAuth: true } },
  { path: '/booking', component: BookingPage, meta: { requiresAuth: true } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Auth guard
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('auth_token')
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth)
  
  if (requiresAuth && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/')
  } else {
    next()
  }
})

export default router
