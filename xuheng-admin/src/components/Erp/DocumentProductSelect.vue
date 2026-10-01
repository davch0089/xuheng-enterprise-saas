<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { skuLabel, skuSpec } from '@/utils/erp/product'
import type { EntryProduct } from '@/hooks/erp/useDocumentProductEntry'

defineOptions({ name: 'ErpDocumentProductSelect' })

const props = defineProps<{
  modelValue?: number
  lineKey: number
  rowIndex: number
  products: EntryProduct[]
  loading: boolean
  disabled?: boolean
  scanMode?: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [value: number]
  search: [keyword: string]
  change: [value: number]
  picker: []
  move: [direction: 'up' | 'down']
}>()

const selectRef = ref<any>()
const dropdownOpen = ref(false)

/** 商品下拉关闭时上下键换行、Enter 打开；展开后让 Element Plus 选择候选项。 */
const handleKeydown = async (event: KeyboardEvent) => {
  if (props.disabled || dropdownOpen.value) return
  if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
    event.preventDefault()
    event.stopPropagation()
    emit('move', event.key === 'ArrowUp' ? 'up' : 'down')
  } else if (event.key === 'Enter') {
    event.preventDefault()
    event.stopPropagation()
    if (!props.products.length) emit('search', '')
    await nextTick()
    selectRef.value?.focus?.()
    selectRef.value?.toggleMenu?.()
  }
}
</script>

<template>
  <div class="document-product-cell" @keydown.capture="handleKeydown">
    <el-select
      ref="selectRef"
      :model-value="modelValue"
      filterable
      remote
      reserve-keyword
      :disabled="disabled"
      :remote-method="(keyword) => emit('search', keyword)"
      :loading="loading"
      placeholder="输入编码 / 名称 / 条码"
      popper-class="document-product-popper"
      @update:model-value="emit('update:modelValue', $event)"
      @change="emit('change', $event)"
      @visible-change="dropdownOpen = $event"
    >
      <el-option :value="-1" disabled class="document-product-option-header">
        <div class="document-product-option-grid">
          <b>商品编号</b><b>商品名称</b><b>规格型号</b><b>计量单位</b><b>库存数量</b>
        </div>
      </el-option>
      <el-option
        v-for="item in products"
        :key="item.id"
        :value="item.id"
        :label="skuLabel(item, { barcode: true })"
      >
        <div class="document-product-option-grid">
          <span>{{ item.code }}</span>
          <span>{{ item.name }}</span>
          <span>{{ skuSpec(item) }}</span>
          <span>{{ item.units?.[0]?.unit_name || '-' }}</span>
          <span>{{ item.available_quantity ?? item.stock_quantity ?? '-' }}</span>
        </div>
      </el-option>
    </el-select>
    <button
      v-if="!disabled && !scanMode"
      type="button"
      class="document-product-picker-trigger"
      title="选择多个商品"
      @mousedown.stop.prevent
      @click.stop="emit('picker')"
    >
      ···
    </button>
  </div>
</template>
