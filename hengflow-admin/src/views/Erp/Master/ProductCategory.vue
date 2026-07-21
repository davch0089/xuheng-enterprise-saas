<script setup lang="ts">
import MasterDataPage from './components/MasterDataPage.vue'
import { productCategoryConfig as config } from './config'
defineOptions({ name: 'ErpMasterProductCategory' })
</script>
<template><MasterDataPage :config="config" /></template>
