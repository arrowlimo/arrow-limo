const normalizeRole = (role) => {
  const aliases = {
    superuser: 'super_user'
  }
  const lowered = (role || 'user').toLowerCase()
  return aliases[lowered] || lowered
}

const roleModules = {
  admin: ['support_impersonation'],
  super_user: ['support_impersonation'],
  driver_support: ['support_impersonation'],
  driver: ['chauffeur_self_service'],
  operator: ['chauffeur_self_service']
}

const getPermissionModules = (permissions) => {
  const modules = new Set()
  if (Array.isArray(permissions?.modules)) {
    permissions.modules.forEach(moduleName => {
      if (typeof moduleName === 'string' && moduleName.trim()) {
        modules.add(moduleName.trim())
      }
    })
  }

  Object.entries(permissions || {}).forEach(([key, value]) => {
    if (value === true) {
      modules.add(key)
    }
  })

  return modules
}

export const hasRequiredModuleAccess = (requiredModules, role, permissions) => {
  if (!requiredModules?.length) {
    return true
  }

  const normalizedRole = normalizeRole(role)
  const grantedByRole = new Set(roleModules[normalizedRole] || [])
  if (grantedByRole.has('*')) {
    return true
  }

  const grantedByPermissions = getPermissionModules(permissions)
  if (grantedByPermissions.has('*')) {
    return true
  }

  return requiredModules.some(moduleName => grantedByRole.has(moduleName) || grantedByPermissions.has(moduleName))
}

export const getRoleHome = (role) => {
  const normalizedRole = normalizeRole(role)
  if (normalizedRole === 'driver' || normalizedRole === 'operator') {
    return '/'
  }
  if (normalizedRole === 'admin' || normalizedRole === 'super_user' || normalizedRole === 'driver_support') {
    return '/support'
  }
  return '/login'
}
