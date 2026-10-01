<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  addOrderApi,
  getOrdersApi,
  getProductsApi,
  getTenantsApi,
  orderActionApi
} from '@/api/xuheng'

defineOptions({ name: 'XuhengOrder' })

const tenants = ref<any[]>([])
const products = ref<any[]>([])
const rows = ref<any[]>([])
const tenantId = ref<number>()
const form = reactive({
  customer_name: '',
  remark: '',
  product_id: undefined as number | undefined,
  quantity: 1
})

const loadProducts = async () => {
  if (!tenantId.value) {
    products.value = []
    return
  }
  const res = await getProductsApi(tenantId.value)
  products.value = res?.data || []
}

const load = async () => {
  if (!tenantId.value) {
    rows.value = []
    return
  }
  const res = await getOrdersApi(tenantId.value)
  rows.value = res?.data || []
  await loadProducts()
}

const create = async () => {
  if (!tenantId.value || !form.customer_name || !form.product_id) {
    ElMessage.warning('请选择企业、客户和商品')
    return
  }
  const res = await addOrderApi({
    tenant_id: tenantId.value,
    customer_name: form.customer_name,
    remark: form.remark,
    lines: [{ product_id: form.product_id, quantity: form.quantity }]
  })
  if (res) {
    ElMessage.success('订单已创建，状态为待确认')
    form.customer_name = ''
    await load()
  }
}

const act = async (row: any, action: string) => {
  const res = await orderActionApi(row.id, row.tenant_id, action)
  if (res) {
    ElMessage.success(res.data?.status_label || '已更新')
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
    <el-alert
      title="订单从待确认到待发货，发货时按数量减库存，退货时把数量加回。不经过采购入库单和成本过账。"
      type="info"
      :closable="false"
      class="mb-16px"
    />
    <el-form inline>
      <el-form-item label="企业">
        <el-select v-model="tenantId" @change="load">
          <el-option v-for="item in tenants" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="客户"><el-input v-model="form.customer_name" /></el-form-item>
      <el-form-item label="商品">
        <el-select v-model="form.product_id">
          <el-option
            v-for="item in products"
            :key="item.id"
            :label="`${item.name}（库存 ${item.quantity}）`"
            :value="item.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="数量"><el-input-number v-model="form.quantity" :min="1" /></el-form-item>
      <el-form-item><el-button type="primary" @click="create">创建订单</el-button></el-form-item>
    </el-form>
    <el-table :data="rows" border>
      <el-table-column prop="order_no" label="单号" min-width="180" />
      <el-table-column prop="customer_name" label="客户" />
      <el-table-column prop="status_label" label="状态" />
      <el-table-column label="明细">
        <template #default="{ row }">
          <span v-for="line in row.lines" :key="line.product_id">
            商品{{ line.product_id }} × {{ line.quantity }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="操作" min-width="260">
        <template #default="{ row }">
          <el-button
            v-if="row.status === 'pending_confirm'"
            link
            type="primary"
            @click="act(row, 'confirm')"
          >
            确认
          </el-button>
          <el-button
            v-if="row.status === 'pending_ship'"
            link
            type="primary"
            @click="act(row, 'ship')"
          >
            发货
          </el-button>
          <el-button
            v-if="row.status === 'pending_confirm' || row.status === 'pending_ship'"
            link
            @click="act(row, 'close')"
          >
            关闭
          </el-button>
          <el-button
            v-if="row.status === 'completed'"
            link
            type="warning"
            @click="act(row, 'return')"
          >
            退货
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
