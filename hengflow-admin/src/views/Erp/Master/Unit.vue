<script setup lang="ts">
import MasterDataPage from './components/MasterDataPage.vue'
import { unitConfig as config } from './config'
defineOptions({ name: 'ErpMasterUnit' })
</script>
<template><MasterDataPage :config="config" /></template>
