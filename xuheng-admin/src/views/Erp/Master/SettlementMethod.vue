<script setup lang="ts">
import MasterDataPage from './components/MasterDataPage.vue'
import { settlementMethodConfig as config } from './config'
defineOptions({ name: 'ErpMasterSettlementMethod' })
</script>
<template><MasterDataPage :config="config" /></template>
