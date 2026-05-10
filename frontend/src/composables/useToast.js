import { showToast as pushToast } from '@/toast/toastStore'

export function useToast() {
  const showToast = (message, type = 'info', timeout = 3000) => {
    pushToast({ message, type, timeout })
  }

  return { showToast }
}
