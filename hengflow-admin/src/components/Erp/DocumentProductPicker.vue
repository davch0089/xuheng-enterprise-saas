<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { skuSpec } from '@/utils/erp/product'
import type { EntryProduct } from '@/hooks/erp/useDocumentProductEntry'

defineOptions({ name: 'ErpDocumentProductPicker' })

const props = defineProps<{
  modelValue: boolean
  keyword: string
  rows: EntryProduct[]
  loading: boolean
  priceField?: 'default_purchase_price' | 'default_sale_price'
  priceLabel?: string
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'update:keyword': [value: string]
  search: []
  confirm: [products: EntryProduct[]]
}>()
const tableRef = ref<any>()
const selected = ref<EntryProduct[]>([])

watch(
  () => props.modelValue,
  async (visible) => {
    if (!visible) return
    selected.value = []
    await nextTick()
    tableRef.value?.clearSelection?.()
  }
)
watch(
  () => props.rows,
  async () => {
    selected.value = []
    await nextTick()
    tableRef.value?.clearSelection?.()
  }
)

/** 确认多选结果并交给开单页面从当前行批量插入。 */
const confirm = () => {
  if (!selected.value.length) return ElMessage.warning('请至少选择一个商品')
  emit('confirm', selected.value)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="选择商品"
    width="88%"
    top="6vh"
    append-to-body
    destroy-on-close
    class="document-product-picker"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="document-product-picker-toolbar">
      <el-input
        :model-value="keyword"
        clearable
        autofocus
        placeholder="输入商品编码、名称、条码或规格"
        @update:model-value="emit('update:keyword', $event)"
        @keyup.enter="emit('search')"
      />
      <el-button type="primary" @click="emit('search')">查询</el-button>
      <span>双击商品行可以勾选，支持一次添加多个 SKU</span>
    </div>
    <el-table
      ref="tableRef"
      v-loading="loading"
      :data="rows"
      row-key="id"
      border
      stripe
      height="56vh"
      @selection-change="selected = $event"
      @row-dblclick="tableRef?.toggleRowSelection($event)"
    >
      <el-table-column type="selection" width="48" reserve-selection />
      <el-table-column prop="code" label="商品编码" min-width="135" />
      <el-table-column prop="name" label="商品名称" min-width="190" show-overflow-tooltip />
      <el-table-column label="规格型号" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">{{ skuSpec(row) }}</template>
      </el-table-column>
      <el-table-column prop="barcode" label="条形码" min-width="150" />
      <el-table-column label="主单位" width="100">
        <template #default="{ row }">{{ row.units?.[0]?.unit_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="可用库存" width="110" align="right">
        <template #default="{ row }">{{
          row.available_quantity ?? row.stock_quantity ?? '-'
        }}</template>
      </el-table-column>
      <el-table-column
        v-if="priceField"
        :label="priceLabel || '参考价格'"
        width="120"
        align="right"
      >
        <template #default="{ row }">{{ Number(row[priceField!] || 0).toFixed(4) }}</template>
      </el-table-column>
    </el-table>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" @click="confirm">添加所选商品（{{ selected.length }}）</el-button>
    </template>
  </el-dialog>
</template>
