import Login from '../views/Login.vue'
const Drivers = () => import('../views/Drivers.vue')
const DriverHOSLog = () => import('../views/DriverHOSLog.vue')
const Support = () => import('../views/Support.vue')

export const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { requiresAuth: false }
  },
  {
    path: '/support',
    name: 'DriverSupport',
    component: Support,
    meta: { requiresAuth: true, modules: ['support_impersonation'] }
  },
  {
    path: '/',
    name: 'DriverPortal',
    component: Drivers,
    meta: { requiresAuth: true, modules: ['chauffeur_self_service'] }
  },
  { path: '/driver-hos', component: DriverHOSLog, meta: { requiresAuth: true, modules: ['chauffeur_self_service'] } },
  { path: '/:pathMatch(.*)*', redirect: '/' }
]
