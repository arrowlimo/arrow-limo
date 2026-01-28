import { createRouter, createWebHistory } from 'vue-router'
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

const routes = [
  {
    path: '/',
    name: 'Main',
    component: Main
  },
  { path: '/dispatch', component: Dispatch },
  { path: '/charter', component: Charter },
  { path: '/vehicles', component: Vehicles },
  { path: '/employees', component: Employees },
  { path: '/customers', component: Customers },
  { path: '/accounting', component: Accounting },
  { path: '/receipts', component: ReceiptsView },
  { path: '/reports', component: Reports },
  { path: '/documents', component: Documents },
  { path: '/owe-david', component: OweDavid },
  { path: '/admin', component: Admin },
  { path: '/drivers', component: Drivers },
  { path: '/driver-hos', component: DriverHOSLog }
  ,{ path: '/booking', component: BookingPage }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
