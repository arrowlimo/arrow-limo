import { createRouter, createWebHistory } from 'vue-router'
import { routeLoading } from '@/loading/loadingStore'

// Lazy-load views to reduce initial bundle size
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

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', component: Dashboard },
  { path: '/dispatch', component: Dispatch },
  { path: '/charter', component: Charter },
  { path: '/vehicles', component: Vehicles },
  { path: '/employees', component: Employees },
  { path: '/customers', component: Customers },
  { path: '/accounting', component: Accounting },
  { path: '/owe-david', component: OweDavid },
  { path: '/admin', component: Admin },
  { path: '/reports', component: Reports },
  { path: '/beverage-order/print', component: BeverageOrderPrint },
  { path: '/documents', component: Documents },
  { path: '/drivers', component: Drivers },
  { path: '/driver-hos', component: DriverHOSLog }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Show a slim loading bar during async route (lazy chunk) fetches
router.beforeEach((to, from, next) => {
  routeLoading.start()
  next()
})

router.afterEach(() => {
  routeLoading.stop()
})

export default router
