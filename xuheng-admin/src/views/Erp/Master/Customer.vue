<script setup lang="ts">
import MasterDataPage from './components/MasterDataPage.vue'
import { customerConfig as config } from './config'
defineOptions({ name: 'ErpMasterCustomer' })
</script>
<template><MasterDataPage :config="config" /></template>
