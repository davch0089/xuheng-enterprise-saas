<script setup lang="ts">
import MasterDataPage from './components/MasterDataPage.vue'
import { employeeConfig as config } from './config'
defineOptions({ name: 'ErpMasterEmployee' })
</script>
<template><MasterDataPage :config="config" /></template>
