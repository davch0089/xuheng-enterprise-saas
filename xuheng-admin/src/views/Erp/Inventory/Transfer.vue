<script setup lang="ts">
import StockOperationPage from './components/StockOperationPage.vue'
defineOptions({ name: 'ErpInventoryTransfer' })
</script>
<template><StockOperationPage kind="transfer" title="库存调拨" /></template>
