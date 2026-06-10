import Login from '../views/Login.vue'
import Main from '../views/Main.vue'

const Dispatch = () => import('../views/Dispatch.vue')
const Charter = () => import('../views/Charter.vue')
const Vehicles = () => import('../views/Vehicles.vue')
const Employees = () => import('../views/Employees.vue')
const Customers = () => import('../views/Customers.vue')
const Accounting = () => import('../views/Accounting.vue')
const Reports = () => import('../views/Reports.vue')
const OweDavid = () => import('../views/OweDavid.vue')
const Admin = () => import('../views/Admin.vue')
const Drivers = () => import('../views/Drivers.vue')
const DriverHOSLog = () => import('../views/DriverHOSLog.vue')
const ReceiptsView = () => import('../views/ReceiptsView.vue')
const BookingPage = () => import('../views/BookingPage.vue')
const TableManagement = () => import('../views/TableManagement.vue')
const T2DataEntry = () => import('../components/T2DataEntry.vue')
const ChequeBookManagement = () => import('../views/ChequeBookManagement.vue')
const ReceivedPayments = () => import('../views/ReceivedPayments.vue')
const PayrollManagement = () => import('../views/PayrollManagement.vue')
const TaxManagement = () => import('../views/TaxManagement.vue')
const CashBoxManagement = () => import('../views/CashBoxManagement.vue')
const BeverageReconciliation = () => import('../views/BeverageReconciliation.vue')
const YearEndClose = () => import('../views/YearEndClose.vue')
const PayrollCompliance = () => import('../views/PayrollCompliance.vue')
const DocumentManagement = () => import('../views/DocumentManagement.vue')
const AuditCenter = () => import('../views/AuditCenter.vue')

export const routes = [
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
  { path: '/dispatch', component: Dispatch, meta: { requiresAuth: true, modules: ['dispatch'] } },
  { path: '/charter', component: Charter, meta: { requiresAuth: true, modules: ['dispatch', 'accounting'] } },
  { path: '/charter/:id', component: Charter, meta: { requiresAuth: true, modules: ['dispatch', 'accounting'] } },
  { path: '/vehicles', component: Vehicles, meta: { requiresAuth: true, modules: ['dispatch'] } },
  { path: '/employees', component: Employees, meta: { requiresAuth: true, modules: ['admin'] } },
  { path: '/customers', component: Customers, meta: { requiresAuth: true, modules: ['dispatch', 'accounting'] } },
  { path: '/accounting', component: Accounting, meta: { requiresAuth: true, modules: ['accounting'] } },
  { path: '/t2-corporate-tax', component: T2DataEntry, meta: { requiresAuth: true, modules: ['accounting'] } },
  { path: '/receipts', component: ReceiptsView, meta: { requiresAuth: true, modules: ['dispatch', 'accounting'] } },
  { path: '/reports', component: Reports, meta: { requiresAuth: true, modules: ['accounting'] } },
  { path: '/owe-david', component: OweDavid, meta: { requiresAuth: true, modules: ['accounting'] } },
  { path: '/admin', component: Admin, meta: { requiresAuth: true, modules: ['admin'] } },
  { path: '/table-management', component: TableManagement, meta: { requiresAuth: true, modules: ['admin'] } },
  { path: '/cheque-books', component: ChequeBookManagement, meta: { requiresAuth: true, modules: ['accounting'] } },
  { path: '/received-payments', component: ReceivedPayments, meta: { requiresAuth: true, modules: ['accounting'] } },
  { path: '/payroll', component: PayrollManagement, meta: { requiresAuth: true, modules: ['accounting'] } },
  { path: '/tax-management', component: TaxManagement, meta: { requiresAuth: true, modules: ['accounting'] } },
  { path: '/cash-box', component: CashBoxManagement, meta: { requiresAuth: true, modules: ['accounting'] } },
  { path: '/beverage-reconciliation', component: BeverageReconciliation, meta: { requiresAuth: true, modules: ['accounting'] } },
  { path: '/year-end-close', component: YearEndClose, meta: { requiresAuth: true, modules: ['accounting'] } },
  { path: '/payroll-compliance', component: PayrollCompliance, meta: { requiresAuth: true, modules: ['accounting'] } },
  { path: '/audit-center', component: AuditCenter, meta: { requiresAuth: true, modules: ['accounting'] } },
  { path: '/documents', component: DocumentManagement, meta: { requiresAuth: true, modules: ['accounting', 'chauffeur_self_service'] } },
  { path: '/drivers', component: Drivers, meta: { requiresAuth: true, modules: ['chauffeur_self_service'] } },
  { path: '/driver-hos', component: DriverHOSLog, meta: { requiresAuth: true, modules: ['chauffeur_self_service'] } },
  { path: '/booking', component: BookingPage, meta: { requiresAuth: true, modules: ['dispatch'] } }
]
