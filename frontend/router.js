import { createRouter, createWebHistory } from 'vue-router'
import { routeLoading } from './src/loading/loadingStore'

// Use the production-ready src/views components, not the stubs in /views
const Dashboard = () => import(/* webpackChunkName: "dashboard" */ './src/views/Dashboard.vue')
const Dispatch = () => import(/* webpackChunkName: "dispatch" */ './src/views/Dispatch.vue')
const Charter = () => import(/* webpackChunkName: "charter" */ './src/views/Charter.vue')
const Vehicles = () => import(/* webpackChunkName: "vehicles" */ './src/views/Vehicles.vue')
const Employees = () => import(/* webpackChunkName: "employees" */ './src/views/Employees.vue')
const Customers = () => import(/* webpackChunkName: "customers" */ './src/views/Customers.vue')
const Accounting = () => import(/* webpackChunkName: "accounting" */ './src/views/Accounting.vue')
const OweDavid = () => import(/* webpackChunkName: "owedavid" */ './src/views/OweDavid.vue')
const Admin = () => import(/* webpackChunkName: "admin" */ './src/views/Admin.vue')
const Reports = () => import(/* webpackChunkName: "reports" */ './src/views/Reports.vue')
const Documents = () => import(/* webpackChunkName: "documents" */ './src/views/Documents.vue')
const Drivers = () => import(/* webpackChunkName: "drivers" */ './src/views/Drivers.vue')
const DriverHOSLog = () => import(/* webpackChunkName: "driver-hos" */ './src/views/DriverHOSLog.vue')
const BeverageOrderPrint = () => import(/* webpackChunkName: "bev-print" */ './src/views/BeverageOrderPrint.vue')
const Login = () => import(/* webpackChunkName: "login" */ './src/views/Login.vue')
const Main = () => import(/* webpackChunkName: "main" */ './src/views/Main.vue')
const ReceiptsView = () => import(/* webpackChunkName: "receipts" */ './src/views/ReceiptsView.vue')
const BookingPage = () => import(/* webpackChunkName: "booking" */ './src/views/BookingPage.vue')
const QuoteGenerator = () => import(/* webpackChunkName: "quote" */ './src/views/QuoteGenerator.vue')
const TableManagement = () => import(/* webpackChunkName: "tables" */ './src/views/TableManagement.vue')
const ChequeBookManagement = () => import(/* webpackChunkName: "cheques" */ './src/views/ChequeBookManagement.vue')
const ReceivedPayments = () => import(/* webpackChunkName: "payments" */ './src/views/ReceivedPayments.vue')

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
  { path: '/dashboard', component: Dashboard, meta: { requiresAuth: true } },
  { path: '/dispatch', component: Dispatch, meta: { requiresAuth: true } },
  { path: '/charter', component: Charter, meta: { requiresAuth: true } },
  { path: '/charter/:id', component: Charter, meta: { requiresAuth: true } },
  { path: '/quote-generator', component: QuoteGenerator, meta: { requiresAuth: true } },
  { path: '/vehicles', component: Vehicles, meta: { requiresAuth: true } },
  { path: '/employees', component: Employees, meta: { requiresAuth: true } },
  { path: '/customers', component: Customers, meta: { requiresAuth: true } },
  { path: '/accounting', component: Accounting, meta: { requiresAuth: true } },
  { path: '/receipts', component: ReceiptsView, meta: { requiresAuth: true } },
  { path: '/reports', component: Reports, meta: { requiresAuth: true } },
  { path: '/owe-david', component: OweDavid, meta: { requiresAuth: true } },
  { path: '/admin', component: Admin, meta: { requiresAuth: true } },
  { path: '/table-management', component: TableManagement, meta: { requiresAuth: true } },
  { path: '/cheque-books', component: ChequeBookManagement, meta: { requiresAuth: true } },
  { path: '/received-payments', component: ReceivedPayments, meta: { requiresAuth: true } },
  { path: '/drivers', component: Drivers, meta: { requiresAuth: true } },
  { path: '/driver-hos', component: DriverHOSLog, meta: { requiresAuth: true } },
  { path: '/booking', component: BookingPage, meta: { requiresAuth: true } },
  { path: '/beverage-order/print', component: BeverageOrderPrint, meta: { requiresAuth: true } },
  { path: '/documents', component: Documents, meta: { requiresAuth: true } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Authentication guard
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('auth_token')
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth)
  
  routeLoading.start()
  
  // If trying to access protected route without token, redirect to login
  if (requiresAuth && !token) {
    next('/login')
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

router.afterEach(() => {
  routeLoading.stop()
})

export default router
