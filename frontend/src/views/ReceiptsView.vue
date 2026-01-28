<template>
  <div class="receipts-view">
    <ReceiptForm />
  </div>
</template>

<script>
import ReceiptForm from '@/components/ReceiptForm.vue';

export default {
  name: 'ReceiptsView',
  components: {
    ReceiptForm
  }
};
</script>

<style scoped>
.receipts-view {
  padding: 20px;
  background: #f5f5f5;
  min-height: 100vh;
}
</style>
