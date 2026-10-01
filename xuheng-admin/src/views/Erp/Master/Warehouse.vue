<script setup lang="ts">
import MasterDataPage from './components/MasterDataPage.vue'
import { warehouseConfig as config } from './config'
defineOptions({ name: 'ErpMasterWarehouse' })
</script>
<template><MasterDataPage :config="config" /></template>
