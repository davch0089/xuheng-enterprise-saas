<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { addProductApi, getProductsApi, getTenantsApi, receiveStockApi } from '@/api/xuheng'

defineOptions({ name: 'XuhengProduct' })

const tenants = ref<any[]>([])
const tenantId = ref<number>()
const rows = ref<any[]>([])
const form = reactive({ code: '', name: '', sale_price: '0', opening_quantity: 0 })
const receive = reactive({ product_id: undefined as number | undefined, quantity: 1 })

const load = async () => {
  if (!tenantId.value) {
    rows.value = []
    return
  }
  const res = await getProductsApi(tenantId.value)
  rows.value = res?.data || []
}

const create = async () => {
  if (!tenantId.value) {
    ElMessage.warning('请先选择企业')
    return
  }
  const res = await addProductApi({
    tenant_id: tenantId.value,
    code: form.code,
    name: form.name,
    sale_price: form.sale_price,
    opening_quantity: form.opening_quantity
  })
  if (res) {
    ElMessage.success('商品已保存')
    form.code = ''
    form.name = ''
    await load()
  }
}

const addStock = async () => {
  if (!tenantId.value || !receive.product_id) {
    ElMessage.warning('请选择企业和商品')
    return
  }
  const res = await receiveStockApi({
    tenant_id: tenantId.value,
    product_id: receive.product_id,
    quantity: receive.quantity
  })
  if (res) {
    ElMessage.success('已按数量入库')
    await load()
  }
}

onMounted(async () => {
  const res = await getTenantsApi()
  tenants.value = res?.data || []
  tenantId.value = tenants.value[0]?.id
  await load()
})
</script>

<template>
  <div class="p-20px">
    <el-form inline>
      <el-form-item label="企业">
        <el-select v-model="tenantId" placeholder="选择企业" @change="load">
          <el-option v-for="item in tenants" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="编码"><el-input v-model="form.code" /></el-form-item>
      <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
      <el-form-item label="售价"><el-input v-model="form.sale_price" /></el-form-item>
      <el-form-item label="期初数量"
        ><el-input-number v-model="form.opening_quantity" :min="0"
      /></el-form-item>
      <el-form-item><el-button type="primary" @click="create">新增商品</el-button></el-form-item>
    </el-form>
    <el-form inline>
      <el-form-item label="入库商品">
        <el-select v-model="receive.product_id" placeholder="选择商品">
          <el-option v-for="item in rows" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="数量"
        ><el-input-number v-model="receive.quantity" :min="1"
      /></el-form-item>
      <el-form-item><el-button @click="addStock">数量入库</el-button></el-form-item>
    </el-form>
    <el-table :data="rows" border>
      <el-table-column prop="code" label="编码" />
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="sale_price" label="售价" />
      <el-table-column prop="quantity" label="当前数量" />
    </el-table>
  </div>
</template>
