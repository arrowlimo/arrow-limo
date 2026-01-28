<template>
  <div class="form-wrapper">
    <!-- Form Header -->
    <div class="form-header">
      <h2 class="form-title">
        <slot name="title">{{ title }}</slot>
      </h2>
      <div class="form-actions-header">
        <slot name="header-actions"></slot>
      </div>
    </div>

    <!-- Form Body -->
    <form 
      @submit.prevent="handleSubmit" 
      class="professional-form"
      :class="{ 'form-loading': loading, 'form-disabled': disabled }"
    >
      <!-- Form Content - Tabbed or Single -->
      <div v-if="tabs.length > 0" class="form-tabs">
        <div class="tab-headers">
          <button
            v-for="(tab, index) in tabs"
            :key="tab.id"
            type="button"
            class="tab-header"
            :class="{ active: activeTab === index }"
            @click="activeTab = index"
            :tabindex="index === 0 ? 1 : -1"
          >
            <span class="tab-icon" v-if="tab.icon">{{ tab.icon }}</span>
            {{ tab.label }}
            <span v-if="tab.required" class="required-indicator">*</span>
          </button>
        </div>

        <div class="tab-content">
          <transition name="fade" mode="out-in">
            <div :key="activeTab" class="tab-panel">
              <slot :name="`tab-${tabs[activeTab].id}`">
                <slot></slot>
              </slot>
            </div>
          </transition>
        </div>
      </div>

      <!-- No Tabs - Direct Content -->
      <div v-else class="form-content">
        <slot></slot>
      </div>

      <!-- Form Footer with Action Buttons -->
      <div class="form-footer">
        <div class="form-status">
          <span v-if="isDirty" class="status-unsaved">● Unsaved changes</span>
          <span v-if="lastSaved" class="status-saved">✓ Saved {{ lastSaved }}</span>
        </div>

        <div class="form-actions">
          <slot name="custom-actions"></slot>

          <button
            v-if="showUndo && canUndo"
            type="button"
            class="btn btn-secondary"
            @click="handleUndo"
            :disabled="loading || !canUndo"
            :tabindex="100"
          >
            <span class="btn-icon">↶</span> Undo
          </button>

          <button
            v-if="showReset"
            type="button"
            class="btn btn-secondary"
            @click="handleReset"
            :disabled="loading || !isDirty"
            :tabindex="101"
          >
            <span class="btn-icon">⟲</span> Reset
          </button>

          <button
            v-if="showDelete && mode === 'edit'"
            type="button"
            class="btn btn-danger"
            @click="handleDelete"
            :disabled="loading || deleteDisabled"
            :tabindex="102"
          >
            <span class="btn-icon">🗑</span> Delete
          </button>

          <button
            v-if="showCancel"
            type="button"
            class="btn btn-secondary"
            @click="handleCancel"
            :disabled="loading"
            :tabindex="103"
          >
            Cancel
          </button>

          <button
            v-if="showSave"
            type="submit"
            class="btn btn-primary"
            :disabled="loading || !isValid || (!isDirty && mode === 'edit')"
            :tabindex="104"
          >
            <span v-if="loading" class="btn-spinner">⟳</span>
            <span v-else class="btn-icon">💾</span>
            {{ saveLabel }}
          </button>

          <button
            v-if="showPrint && mode === 'edit'"
            type="button"
            class="btn btn-secondary"
            @click="handlePrint"
            :disabled="loading"
            :tabindex="105"
          >
            <span class="btn-icon">🖨</span> Print
          </button>
        </div>
      </div>
    </form>

    <!-- Confirmation Dialogs -->
    <teleport to="body">
      <div v-if="showDeleteConfirm" class="modal-overlay" @click="showDeleteConfirm = false">
        <div class="modal-dialog" @click.stop>
          <div class="modal-header">
            <h3>Confirm Delete</h3>
          </div>
          <div class="modal-body">
            <p>Are you sure you want to delete this record? This action cannot be undone.</p>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" @click="showDeleteConfirm = false">
              Cancel
            </button>
            <button type="button" class="btn btn-danger" @click="confirmDelete">
              Delete
            </button>
          </div>
        </div>
      </div>

      <div v-if="showUnsavedConfirm" class="modal-overlay" @click="showUnsavedConfirm = false">
        <div class="modal-dialog" @click.stop>
          <div class="modal-header">
            <h3>Unsaved Changes</h3>
          </div>
          <div class="modal-body">
            <p>You have unsaved changes. Do you want to save them before leaving?</p>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" @click="discardChanges">
              Discard
            </button>
            <button type="button" class="btn btn-primary" @click="saveAndContinue">
              Save & Continue
            </button>
          </div>
        </div>
      </div>
    </teleport>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  title: { type: String, default: '' },
  mode: { type: String, default: 'create' }, // 'create' or 'edit'
  modelValue: { type: Object, default: () => ({}) },
  tabs: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  showSave: { type: Boolean, default: true },
  showCancel: { type: Boolean, default: true },
  showDelete: { type: Boolean, default: true },
  showReset: { type: Boolean, default: true },
  showUndo: { type: Boolean, default: true },
  showPrint: { type: Boolean, default: false },
  deleteDisabled: { type: Boolean, default: false },
  saveLabel: { type: String, default: '' },
  validation: { type: Object, default: () => ({}) }
})

const emit = defineEmits(['update:modelValue', 'submit', 'delete', 'cancel', 'print', 'reset', 'undo'])

// State
const activeTab = ref(0)
const showDeleteConfirm = ref(false)
const showUnsavedConfirm = ref(false)
const isDirty = ref(false)
const lastSaved = ref(null)
const history = ref([])
const historyIndex = ref(-1)

// Computed
const saveButtonLabel = computed(() => {
  if (props.saveLabel) return props.saveLabel
  return props.mode === 'create' ? 'Create' : 'Save'
})

const isValid = computed(() => {
  if (!props.validation || Object.keys(props.validation).length === 0) return true
  return Object.values(props.validation).every(v => v === true)
})

const canUndo = computed(() => historyIndex.value > 0)

// Watch for changes
watch(() => props.modelValue, (newVal, oldVal) => {
  if (JSON.stringify(newVal) !== JSON.stringify(oldVal)) {
    isDirty.value = true
    addToHistory(newVal)
  }
}, { deep: true })

// Methods
function addToHistory(state) {
  // Remove future history if we're not at the end
  if (historyIndex.value < history.value.length - 1) {
    history.value = history.value.slice(0, historyIndex.value + 1)
  }
  
  history.value.push(JSON.parse(JSON.stringify(state)))
  historyIndex.value = history.value.length - 1
  
  // Limit history to 50 items
  if (history.value.length > 50) {
    history.value.shift()
    historyIndex.value--
  }
}

function handleSubmit() {
  if (!isValid.value) return
  
  emit('submit', props.modelValue)
  isDirty.value = false
  lastSaved.value = new Date().toLocaleTimeString()
}

function handleDelete() {
  showDeleteConfirm.value = true
}

function confirmDelete() {
  showDeleteConfirm.value = false
  emit('delete', props.modelValue)
}

function handleCancel() {
  if (isDirty.value) {
    showUnsavedConfirm.value = true
  } else {
    emit('cancel')
  }
}

function discardChanges() {
  showUnsavedConfirm.value = false
  isDirty.value = false
  emit('cancel')
}

function saveAndContinue() {
  showUnsavedConfirm.value = false
  handleSubmit()
  emit('cancel')
}

function handleReset() {
  if (history.value.length > 0) {
    emit('update:modelValue', history.value[0])
    isDirty.value = false
  }
  emit('reset')
}

function handleUndo() {
  if (canUndo.value) {
    historyIndex.value--
    emit('update:modelValue', history.value[historyIndex.value])
  }
}

function handlePrint() {
  emit('print', props.modelValue)
}

// Keyboard shortcuts
function handleKeyboard(event) {
  // Ctrl+S to save
  if ((event.ctrlKey || event.metaKey) && event.key === 's') {
    event.preventDefault()
    if (isDirty.value && isValid.value) {
      handleSubmit()
    }
  }
  
  // Ctrl+Z to undo
  if ((event.ctrlKey || event.metaKey) && event.key === 'z' && !event.shiftKey) {
    event.preventDefault()
    if (canUndo.value) {
      handleUndo()
    }
  }
  
  // Esc to cancel
  if (event.key === 'Escape') {
    handleCancel()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyboard)
  if (props.modelValue) {
    addToHistory(props.modelValue)
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeyboard)
})
</script>

<style scoped>
.form-wrapper {
  background: #ffffff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.form-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid #e5e7eb;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.form-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
}

.professional-form {
  min-height: 400px;
}

.form-tabs {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.tab-headers {
  display: flex;
  border-bottom: 2px solid #e5e7eb;
  background: #f9fafb;
  padding: 0 24px;
  overflow-x: auto;
}

.tab-header {
  padding: 16px 24px;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 0.95rem;
  font-weight: 500;
  color: #6b7280;
  border-bottom: 3px solid transparent;
  transition: all 0.2s;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 8px;
}

.tab-header:hover {
  color: #111827;
  background: #f3f4f6;
}

.tab-header.active {
  color: #667eea;
  border-bottom-color: #667eea;
  background: white;
}

.tab-icon {
  font-size: 1.1rem;
}

.required-indicator {
  color: #ef4444;
  font-weight: bold;
}

.tab-content {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}

.form-content {
  padding: 24px;
}

.form-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  border-top: 1px solid #e5e7eb;
  background: #f9fafb;
}

.form-status {
  font-size: 0.875rem;
  color: #6b7280;
}

.status-unsaved {
  color: #f59e0b;
}

.status-saved {
  color: #10b981;
}

.form-actions {
  display: flex;
  gap: 12px;
}

.btn {
  padding: 10px 20px;
  border: none;
  border-radius: 6px;
  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: #667eea;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #5568d3;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.btn-secondary {
  background: #e5e7eb;
  color: #374151;
}

.btn-secondary:hover:not(:disabled) {
  background: #d1d5db;
}

.btn-danger {
  background: #ef4444;
  color: white;
}

.btn-danger:hover:not(:disabled) {
  background: #dc2626;
}

.btn-icon, .btn-spinner {
  font-size: 1.1rem;
}

.btn-spinner {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.form-loading {
  opacity: 0.6;
  pointer-events: none;
}

.form-disabled {
  opacity: 0.5;
  pointer-events: none;
}

/* Modal Styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.modal-dialog {
  background: white;
  border-radius: 8px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  max-width: 500px;
  width: 90%;
}

.modal-header {
  padding: 20px 24px;
  border-bottom: 1px solid #e5e7eb;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.25rem;
}

.modal-body {
  padding: 24px;
}

.modal-footer {
  padding: 16px 24px;
  border-top: 1px solid #e5e7eb;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

/* Transitions */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s;
}

.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

/* Responsive */
@media (max-width: 768px) {
  .form-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  
  .form-footer {
    flex-direction: column;
    gap: 12px;
  }
  
  .form-actions {
    width: 100%;
    flex-wrap: wrap;
  }
  
  .btn {
    flex: 1;
    min-width: 120px;
  }
}
</style>
