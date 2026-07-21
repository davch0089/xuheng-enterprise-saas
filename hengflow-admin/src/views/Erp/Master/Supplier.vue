<script setup lang="ts">
import MasterDataPage from './components/MasterDataPage.vue'
import { supplierConfig as config } from './config'
defineOptions({ name: 'ErpMasterSupplier' })
</script>
<template><MasterDataPage :config="config" /></template>
