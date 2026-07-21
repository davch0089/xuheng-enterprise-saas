<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'
import type { FormInstance } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ContentWrap } from '@/components/ContentWrap'
import { BaseButton } from '@/components/Button'
import { skuLabel, skuSpec } from '@/utils/erp/product'
import { getMasterOptionsApi } from '@/api/erp/master'
import {
  addInboundApi,
  approveInboundApi,
  delInboundApi,
  getInboundApi,
  getInboundListApi,
  putInboundApi,
  searchInboundProductsApi,
  unapproveInboundApi
} from '@/api/erp/inventory'

defineOptions({ name: 'ErpInventoryInbound' })

interface Option {
  label: string
  value: number
}

interface ProductUnit {
  unit_id: number
  unit_name: string
  unit_code: string
  to_base_rate: number | string
  decimal_places: number
  level: number
}

interface ProductOption {
  id: number
  code: string
  name: string
  barcode?: string
  variant_name?: string
  specification?: string
  batch_enabled: boolean
  serial_enabled: boolean
  shelf_life_days?: number
  default_purchase_price: number | string
  stock_quantity: number | string
  base_unit_id: number
  units: ProductUnit[]
}

interface InboundLine {
  key: number
  product_id?: number
  product?: ProductOption
  warehouse_id?: number
  unit_id?: number
  quantity: number
  unit_price: number
  batch_no?: string
  production_date?: string
  expiry_date?: string
  serial_numbers: string[]
  remark?: string
}

interface ProductSelectExpose {
  toggleMenu: () => void
  focus?: () => void
  blur?: () => void
}

const businessTypes = [
  { label: '采购入库', value: 'purchase' },
  { label: '其他入库', value: 'other' },
  { label: '盘盈入库', value: 'stock_gain' },
  { label: '生产入库', value: 'production' },
  { label: '调拨入库', value: 'transfer' }
]
const statusMap: Record<string, { label: string; type: '' | 'success' | 'info' | 'warning' }> = {
  draft: { label: '草稿', type: 'info' },
  approved: { label: '已审核', type: 'success' },
  cancelled: { label: '已作废', type: 'warning' }
}

const loading = ref(false)
const saving = ref(false)
const rows = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const limit = ref(10)
const search = reactive<any>({ date_range: [] })
const options = reactive<Record<string, Option[]>>({ warehouses: [], suppliers: [], employees: [] })
const dialogVisible = ref(false)
const formRef = ref<FormInstance>()
const editingId = ref<number>()
const readonly = ref(false)
const productLoading = ref(false)
const productOptions = ref<ProductOption[]>([])
const scanMode = ref(false)
const scanCode = ref('')
const scanInput = ref<HTMLInputElement>()
const productSelectRefs = new Map<number, ProductSelectExpose>()
const openProductDropdowns = reactive(new Set<number>())
const productPickerVisible = ref(false)
const productPickerLoading = ref(false)
const productPickerKeyword = ref('')
const productPickerRows = ref<ProductOption[]>([])
const productPickerSelected = ref<ProductOption[]>([])
const productPickerAnchorKey = ref<number>()
const productPickerTable = ref<any>()
let lineKey = 0

const navColumns = [
  'product',
  'spec',
  'unit',
  'warehouse',
  'batch_no',
  'production_date',
  'expiry_date',
  'quantity',
  'unit_price',
  'serial',
  'remark'
] as const
type NavColumn = (typeof navColumns)[number]

const activeCell = reactive<{ rowKey: number; col: NavColumn | '' }>({ rowKey: 0, col: '' })

/** 将指定明细格设为当前 Excel 选区，但不主动改变控件打开状态。 */
const activateCell = (line: InboundLine, col: NavColumn) => {
  activeCell.rowKey = line.key
  activeCell.col = col
}

/** 判断指定明细格是否为当前 Excel 选区。 */
const isActiveCell = (line: InboundLine, col: NavColumn) =>
  activeCell.rowKey === line.key && activeCell.col === col

const columnAvailable = (line: InboundLine, col: NavColumn): boolean => {
  switch (col) {
    case 'batch_no':
    case 'production_date':
    case 'expiry_date':
      return !!line.product?.batch_enabled
    case 'serial':
      return !!line.product?.serial_enabled
    default:
      return true
  }
}

const getCellEl = (rowKey: number, col: string) =>
  document.querySelector(`[data-cell="${rowKey}-${col}"]`) as HTMLElement | null

const focusCell = async (rowKey: number, col: NavColumn | '') => {
  activeCell.rowKey = rowKey
  activeCell.col = col
  if (!col) return
  await nextTick()
  const cell = getCellEl(rowKey, col)
  const input = cell?.querySelector('input') as HTMLInputElement | null
  if (input) {
    input.focus()
    if (col === 'quantity' || col === 'unit_price') input.select()
  } else {
    cell?.focus()
  }
}

const findNavIndex = (col: string) => {
  const idx = navColumns.indexOf(col as NavColumn)
  if (idx === -1) return -1
  return idx
}

const moveCell = (
  line: InboundLine,
  rowIndex: number,
  col: NavColumn,
  dir: 'up' | 'down' | 'left' | 'right'
) => {
  const colIdx = findNavIndex(col)
  if (colIdx === -1) return

  if (dir === 'up' || dir === 'down') {
    const targetRowIdx = dir === 'up' ? rowIndex - 1 : rowIndex + 1
    let targetLine = form.lines[targetRowIdx]
    if (!targetLine && dir === 'down' && col === 'product' && !readonly.value) {
      targetLine = newLine()
      form.lines.push(targetLine)
    }
    if (!targetLine) return
    if (columnAvailable(targetLine, col)) {
      focusCell(targetLine.key, col)
    } else {
      // 上下移动到未启用的批次、效期或序列号列时，选择目标行中最近的可编辑列。
      const fallbackCol = navColumns
        .map((candidate, index) => ({ candidate, distance: Math.abs(index - colIdx) }))
        .filter(({ candidate }) => columnAvailable(targetLine, candidate))
        .sort((a, b) => a.distance - b.distance)[0]?.candidate
      if (fallbackCol) focusCell(targetLine.key, fallbackCol)
    }
  } else {
    const delta = dir === 'right' ? 1 : -1
    let nextIdx = colIdx + delta
    while (nextIdx >= 0 && nextIdx < navColumns.length) {
      const nextCol = navColumns[nextIdx]
      if (columnAvailable(line, nextCol)) {
        focusCell(line.key, nextCol)
        return
      }
      nextIdx += delta
    }
    if (dir === 'right' && nextIdx >= navColumns.length) {
      const nextLine = form.lines[rowIndex + 1]
      if (nextLine) {
        const firstCol = navColumns.find((c) => columnAvailable(nextLine, c))
        if (firstCol) focusCell(nextLine.key, firstCol)
      }
    } else if (dir === 'left' && nextIdx < 0) {
      const prevLine = form.lines[rowIndex - 1]
      if (prevLine) {
        const lastCol = navColumns.findLast((c) => columnAvailable(prevLine, c))
        if (lastCol) focusCell(prevLine.key, lastCol)
      }
    }
  }
}

/** 保存每一行商品下拉实例，用于回车键显式打开候选商品。 */
const setProductSelectRef = (rowKey: number, instance: unknown) => {
  if (instance) productSelectRefs.set(rowKey, instance as ProductSelectExpose)
  else productSelectRefs.delete(rowKey)
}

/** 记录商品下拉的展开状态，区分行导航和候选商品导航。 */
const handleProductDropdownVisible = (rowKey: number, visible: boolean) => {
  if (visible) openProductDropdowns.add(rowKey)
  else openProductDropdowns.delete(rowKey)
}

/** 商品框关闭时上下键切换行、回车打开下拉；展开后交给下拉框处理候选项。 */
const handleProductKeydownCapture = async (
  e: KeyboardEvent,
  line: InboundLine,
  rowIndex: number
) => {
  if (readonly.value || openProductDropdowns.has(line.key)) return
  if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
    e.preventDefault()
    e.stopPropagation()
    moveCell(line, rowIndex, 'product', e.key === 'ArrowUp' ? 'up' : 'down')
    return
  }
  if (e.key === 'Enter') {
    e.preventDefault()
    e.stopPropagation()
    if (!productOptions.value.length) await remoteProductSearch('')
    await nextTick()
    const select = productSelectRefs.get(line.key)
    if (select) {
      openProductDropdowns.add(line.key)
      select.focus?.()
      select.toggleMenu()
    }
  }
}

const handleCellKeydown = (
  e: KeyboardEvent,
  line: InboundLine,
  rowIndex: number,
  col: NavColumn
) => {
  if (readonly.value) return
  const target = e.target as HTMLElement
  const isDatePicker = target.closest('.el-date-editor') || target.closest('.el-picker-panel')
  const selectOpen = target.closest('.el-select-dropdown') || target.closest('.el-popper')

  if (selectOpen) return

  switch (e.key) {
    case 'ArrowUp':
      e.preventDefault()
      moveCell(line, rowIndex, col, 'up')
      break
    case 'ArrowDown':
      e.preventDefault()
      moveCell(line, rowIndex, col, 'down')
      break
    case 'ArrowLeft': {
      if (isDatePicker) break
      const input = target instanceof HTMLInputElement ? target : null
      if (input && input.selectionStart !== null && input.selectionStart > 0) break
      e.preventDefault()
      moveCell(line, rowIndex, col, 'left')
      break
    }
    case 'ArrowRight': {
      if (isDatePicker) break
      const input = target instanceof HTMLInputElement ? target : null
      if (input && input.selectionStart !== null && input.selectionStart < input.value.length) break
      e.preventDefault()
      moveCell(line, rowIndex, col, 'right')
      break
    }
    case 'Escape':
      ;(e.target as HTMLElement).blur()
      activeCell.col = ''
      break
  }
}

/** 禁止回车键触发开单表单提交，扫码输入框和多行备注保持原有行为。 */
const preventDocumentEnter = (e: KeyboardEvent) => {
  const target = e.target as HTMLElement
  if (target.closest('.scan-bar') || target.tagName === 'TEXTAREA') return
  e.preventDefault()
  e.stopPropagation()
}

const newLine = (): InboundLine => ({
  key: ++lineKey,
  warehouse_id: form.warehouse_id,
  quantity: 1,
  unit_price: 0,
  serial_numbers: []
})

const form = reactive<any>({
  receipt_no: '',
  receipt_date: dayjs().format('YYYY-MM-DD'),
  business_type: 'purchase',
  supplier_id: undefined,
  warehouse_id: undefined,
  employee_id: undefined,
  remark: '',
  status: 'draft',
  lines: [] as InboundLine[]
})

const totalQuantity = computed(() =>
  form.lines.reduce((sum: number, line: InboundLine) => sum + baseQuantity(line), 0)
)
const totalAmount = computed(() =>
  form.lines.reduce((sum: number, line: InboundLine) => sum + lineAmount(line), 0)
)

const rules = {
  receipt_date: [{ required: true, message: '请选择入库日期', trigger: 'change' }],
  business_type: [{ required: true, message: '请选择业务类型', trigger: 'change' }],
  warehouse_id: [{ required: true, message: '请选择默认仓库', trigger: 'change' }]
}

const numberValue = (value: unknown) => Number(value || 0)
const selectedUnit = (line: InboundLine) =>
  line.product?.units.find((unit) => unit.unit_id === line.unit_id)
const baseQuantity = (line: InboundLine) =>
  numberValue(line.quantity) * numberValue(selectedUnit(line)?.to_base_rate || 0)
const lineAmount = (line: InboundLine) => numberValue(line.quantity) * numberValue(line.unit_price)
const businessLabel = (value: string) =>
  businessTypes.find((item) => item.value === value)?.label || value

const loadOptions = async () => {
  const resources = ['warehouses', 'suppliers', 'employees']
  await Promise.all(
    resources.map(async (resource) => {
      const res = await getMasterOptionsApi(resource)
      options[resource] = res.data || []
    })
  )
}

const loadList = async () => {
  loading.value = true
  try {
    const [date_start, date_end] = search.date_range || []
    const res = await getInboundListApi({
      page: page.value,
      limit: limit.value,
      keyword: search.keyword || undefined,
      status: search.status || undefined,
      business_type: search.business_type || undefined,
      date_start,
      date_end
    })
    rows.value = res.data || []
    total.value = res.count || 0
  } finally {
    loading.value = false
  }
}

const resetSearch = () => {
  Object.assign(search, {
    keyword: undefined,
    status: undefined,
    business_type: undefined,
    date_range: []
  })
  page.value = 1
  loadList()
}

const resetForm = () => {
  Object.assign(activeCell, { rowKey: 0, col: '' })
  Object.assign(form, {
    receipt_no: '',
    receipt_date: dayjs().format('YYYY-MM-DD'),
    business_type: 'purchase',
    supplier_id: undefined,
    warehouse_id: options.warehouses[0]?.value,
    employee_id: undefined,
    remark: '',
    status: 'draft',
    lines: []
  })
  form.lines = [newLine(), newLine(), newLine(), newLine()]
}

const openAdd = async () => {
  editingId.value = undefined
  readonly.value = false
  resetForm()
  dialogVisible.value = true
  await remoteProductSearch('')
  await nextTick()
  scanInput.value?.focus()
}

const normalizeProduct = (line: any): ProductOption => ({
  ...line.product,
  default_purchase_price: line.base_unit_cost || 0,
  stock_quantity: line.product?.stock_quantity || 0,
  base_unit_id: line.product?.units?.[0]?.unit_id
})

const openReceipt = async (row: any, viewOnly = false) => {
  Object.assign(activeCell, { rowKey: 0, col: '' })
  const res = await getInboundApi(row.id)
  const data = res.data
  editingId.value = row.id
  readonly.value = viewOnly || data.status !== 'draft'
  Object.assign(form, data)
  form.lines = (data.lines || []).map((line: any) => {
    const product = normalizeProduct(line)
    return {
      ...line,
      key: ++lineKey,
      product,
      quantity: numberValue(line.quantity),
      unit_price: numberValue(line.unit_price),
      serial_numbers: line.serial_numbers || []
    }
  })
  productOptions.value = form.lines.map((line: InboundLine) => line.product).filter(Boolean)
  dialogVisible.value = true
}

const remoteProductSearch = async (keyword: string) => {
  productLoading.value = true
  try {
    const res = await searchInboundProductsApi({
      keyword: keyword || undefined,
      warehouse_id: form.warehouse_id,
      limit: 40
    })
    const selected = form.lines.map((line: InboundLine) => line.product).filter(Boolean)
    const merged = [...selected, ...(res.data || [])] as ProductOption[]
    productOptions.value = Array.from(new Map(merged.map((item) => [item.id, item])).values())
  } finally {
    productLoading.value = false
  }
}

const chooseProduct = (line: InboundLine, productId: number) => {
  const product = productOptions.value.find((item) => item.id === productId)
  if (!product) return
  line.product = product
  line.product_id = product.id
  line.unit_id = product.base_unit_id
  line.warehouse_id ||= form.warehouse_id
  line.unit_price = numberValue(product.default_purchase_price)
  line.quantity = 1
  line.batch_no = undefined
  line.production_date = undefined
  line.expiry_date = undefined
  line.serial_numbers = []
}

/** 查询商品多选弹窗的数据。 */
const loadProductPicker = async () => {
  productPickerLoading.value = true
  try {
    const res = await searchInboundProductsApi({
      keyword: productPickerKeyword.value || undefined,
      warehouse_id: form.warehouse_id,
      limit: 100
    })
    productPickerRows.value = res.data || []
    productPickerSelected.value = []
    await nextTick()
    productPickerTable.value?.clearSelection()
  } finally {
    productPickerLoading.value = false
  }
}

/** 从当前商品单元格打开可搜索、多选的商品选择弹窗。 */
const openProductPicker = async (line: InboundLine) => {
  productSelectRefs.get(line.key)?.blur?.()
  productPickerAnchorKey.value = line.key
  productPickerKeyword.value = ''
  productPickerVisible.value = true
  await loadProductPicker()
}

/** 同步商品多选弹窗当前勾选结果。 */
const handleProductPickerSelection = (selection: ProductOption[]) => {
  productPickerSelected.value = selection
}

/** 双击商品行时切换其勾选状态。 */
const togglePickerProduct = (product: ProductOption) => {
  productPickerTable.value?.toggleRowSelection(product)
}

/** 从锚点商品行开始批量写入选中的商品。 */
const applyPickedProducts = async () => {
  if (!productPickerSelected.value.length) {
    ElMessage.warning('请至少选择一个商品')
    return
  }
  const anchorIndex = form.lines.findIndex(
    (line: InboundLine) => line.key === productPickerAnchorKey.value
  )
  if (anchorIndex < 0) {
    ElMessage.warning('原商品行已不存在，请重新选择')
    return
  }

  productOptions.value = Array.from(
    new Map(
      [...productOptions.value, ...productPickerSelected.value].map((item) => [item.id, item])
    ).values()
  )
  productPickerSelected.value.forEach((product, index) => {
    const target = index === 0 ? form.lines[anchorIndex] : newLine()
    if (index > 0) form.lines.splice(anchorIndex + index, 0, target)
    chooseProduct(target, product.id)
  })
  const firstLine = form.lines[anchorIndex]
  productPickerVisible.value = false
  await focusCell(firstLine.key, 'product')
}

const changeUnit = (line: InboundLine) => {
  const unit = selectedUnit(line)
  if (line.product && unit) {
    line.unit_price = Number(
      (numberValue(line.product.default_purchase_price) * numberValue(unit.to_base_rate)).toFixed(6)
    )
  }
}

const changeDefaultWarehouse = async (warehouseId: number) => {
  form.lines.forEach((line: InboundLine) => {
    if (!line.product_id) line.warehouse_id = warehouseId
  })
  await remoteProductSearch('')
}

const addLine = (index?: number) => {
  const line = newLine()
  if (index === undefined) form.lines.push(line)
  else form.lines.splice(index + 1, 0, line)
}

const removeLine = (index: number) => {
  if (form.lines.length === 1) {
    form.lines.splice(0, 1, newLine())
  } else {
    form.lines.splice(index, 1)
  }
}

const changeProductionDate = (line: InboundLine) => {
  if (line.production_date && line.product?.shelf_life_days !== undefined) {
    line.expiry_date = dayjs(line.production_date)
      .add(line.product.shelf_life_days || 0, 'day')
      .format('YYYY-MM-DD')
  }
}

const scanProduct = async () => {
  const code = scanCode.value.trim()
  if (!code) return
  const res = await searchInboundProductsApi({
    keyword: code,
    warehouse_id: form.warehouse_id,
    limit: 20
  })
  const products: ProductOption[] = res.data || []
  const product =
    products.find((item) => item.barcode === code || item.code === code) ||
    (products.length === 1 ? products[0] : undefined)
  if (!product) {
    ElMessage.warning('没有找到唯一匹配的商品，请使用明细中的商品搜索')
    return
  }
  productOptions.value = Array.from(
    new Map([...productOptions.value, product].map((item) => [item.id, item])).values()
  )
  const existing = form.lines.find(
    (line: InboundLine) =>
      line.product_id === product.id &&
      line.warehouse_id === form.warehouse_id &&
      !product.serial_enabled
  )
  if (existing) {
    existing.quantity = numberValue(existing.quantity) + 1
  } else {
    const empty = form.lines.find((line: InboundLine) => !line.product_id) || newLine()
    if (!form.lines.includes(empty)) form.lines.push(empty)
    chooseProduct(empty, product.id)
  }
  scanCode.value = ''
  ElMessage.success(`已录入：${skuLabel(product)}`)
}

const serialDialogVisible = ref(false)
const serialText = ref('')
const serialLine = ref<InboundLine>()
const serialGenerator = reactive({ prefix: '', start: '001', increment: 1, count: 1 })

const openSerials = (line: InboundLine) => {
  serialLine.value = line
  serialText.value = line.serial_numbers.join('\n')
  serialDialogVisible.value = true
}

const generateSerials = () => {
  const start = Number(serialGenerator.start)
  const width = serialGenerator.start.length
  const generated = Array.from({ length: Math.max(0, serialGenerator.count) }, (_, index) => {
    const value = start + index * serialGenerator.increment
    return `${serialGenerator.prefix}${String(value).padStart(width, '0')}`
  })
  const current = serialText.value
    .split(/[\s,，;；]+/)
    .map((item) => item.trim())
    .filter(Boolean)
  serialText.value = Array.from(new Set([...current, ...generated])).join('\n')
}

const applySerials = () => {
  if (!serialLine.value) return
  const values = serialText.value
    .split(/[\s,，;；]+/)
    .map((item) => item.trim())
    .filter(Boolean)
  if (values.length !== new Set(values).size) {
    ElMessage.warning('存在重复序列号，请检查')
    return
  }
  serialLine.value.serial_numbers = values
  const rate = numberValue(selectedUnit(serialLine.value)?.to_base_rate || 1)
  serialLine.value.quantity = rate ? Number((values.length / rate).toFixed(6)) : values.length
  serialDialogVisible.value = false
}

const validateLines = () => {
  const lines = form.lines.filter((line: InboundLine) => line.product_id)
  if (!lines.length) throw new Error('请至少录入一行商品')
  for (const [index, line] of lines.entries()) {
    if (!line.warehouse_id || !line.unit_id) throw new Error(`第 ${index + 1} 行仓库或单位未选择`)
    if (numberValue(line.quantity) <= 0) throw new Error(`第 ${index + 1} 行数量必须大于 0`)
    if (numberValue(line.unit_price) < 0) throw new Error(`第 ${index + 1} 行单价不能小于 0`)
    if (line.product?.batch_enabled && !line.batch_no)
      throw new Error(`第 ${index + 1} 行必须填写批次号`)
    if (
      line.product?.serial_enabled &&
      line.serial_numbers.length !== Math.round(baseQuantity(line))
    ) {
      throw new Error(`第 ${index + 1} 行序列号数量与主单位数量不一致`)
    }
  }
  return lines
}

const payload = (lines: InboundLine[]) => ({
  receipt_no: form.receipt_no || null,
  receipt_date: form.receipt_date,
  business_type: form.business_type,
  supplier_id: form.business_type === 'purchase' ? form.supplier_id : null,
  warehouse_id: form.warehouse_id,
  employee_id: form.employee_id || null,
  remark: form.remark || null,
  lines: lines.map((line) => ({
    product_id: line.product_id,
    warehouse_id: line.warehouse_id,
    unit_id: line.unit_id,
    quantity: numberValue(line.quantity),
    unit_price: numberValue(line.unit_price),
    batch_no: line.batch_no || null,
    production_date: line.production_date || null,
    expiry_date: line.expiry_date || null,
    serial_numbers: line.serial_numbers,
    remark: line.remark || null
  }))
})

const save = async (approveAfter = false) => {
  try {
    await formRef.value?.validate()
    if (form.business_type === 'purchase' && !form.supplier_id)
      throw new Error('采购入库必须选择供应商')
    const lines = validateLines()
    saving.value = true
    const res = editingId.value
      ? await putInboundApi(editingId.value, payload(lines))
      : await addInboundApi(payload(lines))
    const savedId = res.data.id
    if (approveAfter) await approveInboundApi(savedId)
    ElMessage.success(approveAfter ? '保存并审核成功，库存已更新' : '草稿保存成功')
    dialogVisible.value = false
    await loadList()
  } catch (error: any) {
    if (error?.message) ElMessage.warning(error.message)
  } finally {
    saving.value = false
  }
}

const approveRow = async (row: any) => {
  await ElMessageBox.confirm(`审核后将正式增加库存，确定审核 ${row.receipt_no} 吗？`, '审核确认', {
    type: 'warning'
  })
  await approveInboundApi(row.id)
  ElMessage.success('审核成功，库存已更新')
  await loadList()
}

const unapproveRow = async (row: any) => {
  await ElMessageBox.confirm(
    `反审核将冲销本单库存和成本；若商品已有后续业务，系统会拒绝。确定继续吗？`,
    '反审核确认',
    { type: 'warning' }
  )
  await unapproveInboundApi(row.id)
  ElMessage.success('反审核成功，单据已恢复为草稿')
  await loadList()
}

const removeRow = async (row: any) => {
  await ElMessageBox.confirm(`确定删除草稿 ${row.receipt_no} 吗？`, '删除确认', { type: 'warning' })
  await delInboundApi([row.id])
  ElMessage.success('删除成功')
  await loadList()
}

onMounted(async () => {
  await Promise.all([loadOptions(), loadList()])
})
</script>

<template>
  <ContentWrap>
    <div class="search-bar">
      <el-input v-model="search.keyword" clearable placeholder="入库单号" @keyup.enter="loadList" />
      <el-select v-model="search.business_type" clearable placeholder="业务类型">
        <el-option v-for="item in businessTypes" :key="item.value" v-bind="item" />
      </el-select>
      <el-select v-model="search.status" clearable placeholder="单据状态">
        <el-option label="草稿" value="draft" />
        <el-option label="已审核" value="approved" />
      </el-select>
      <el-date-picker
        v-model="search.date_range"
        type="daterange"
        value-format="YYYY-MM-DD"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
      />
      <BaseButton type="primary" @click="loadList">查询</BaseButton>
      <BaseButton @click="resetSearch">重置</BaseButton>
    </div>
    <div class="toolbar">
      <BaseButton type="primary" @click="openAdd">新增入库单</BaseButton>
    </div>
    <el-table v-loading="loading" :data="rows" border stripe>
      <el-table-column prop="receipt_date" label="入库日期" width="115" />
      <el-table-column prop="receipt_no" label="入库单号" min-width="165" />
      <el-table-column label="业务类型" width="105">
        <template #default="{ row }">{{ businessLabel(row.business_type) }}</template>
      </el-table-column>
      <el-table-column prop="supplier_name" label="供应商" min-width="150" show-overflow-tooltip />
      <el-table-column prop="warehouse_name" label="默认仓库" min-width="120" />
      <el-table-column prop="employee_name" label="经办人" width="100" />
      <el-table-column label="主单位数量" width="125" align="right">
        <template #default="{ row }">{{
          numberValue(row.total_quantity)
            .toFixed(6)
            .replace(/\.?0+$/, '')
        }}</template>
      </el-table-column>
      <el-table-column label="入库成本" width="125" align="right">
        <template #default="{ row }">¥ {{ numberValue(row.total_amount).toFixed(2) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="statusMap[row.status]?.type">{{
            statusMap[row.status]?.label || row.status
          }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="245" fixed="right">
        <template #default="{ row }">
          <BaseButton type="primary" link @click="openReceipt(row, row.status !== 'draft')">
            {{ row.status === 'draft' ? '编辑' : '查看' }}
          </BaseButton>
          <BaseButton v-if="row.status === 'draft'" type="success" link @click="approveRow(row)"
            >审核</BaseButton
          >
          <BaseButton
            v-if="row.status === 'approved'"
            type="warning"
            link
            @click="unapproveRow(row)"
            >反审核</BaseButton
          >
          <BaseButton v-if="row.status === 'draft'" type="danger" link @click="removeRow(row)"
            >删除</BaseButton
          >
        </template>
      </el-table-column>
    </el-table>
    <el-pagination
      v-model:current-page="page"
      v-model:page-size="limit"
      class="pagination"
      background
      layout="total, sizes, prev, pager, next, jumper"
      :total="total"
      @current-change="loadList"
      @size-change="loadList"
    />
  </ContentWrap>

  <el-dialog
    v-model="dialogVisible"
    :title="
      readonly
        ? `查看入库单 ${form.receipt_no}`
        : editingId
          ? `编辑入库单 ${form.receipt_no}`
          : '新增入库单'
    "
    fullscreen
    destroy-on-close
    class="inbound-dialog"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="88px"
      :disabled="readonly"
      @keydown.enter="preventDocumentEnter"
    >
      <div class="document-header">
        <el-row :gutter="28">
          <el-col :xs="24" :sm="12" :xl="4">
            <el-form-item label="入库单号">
              <el-input v-model="form.receipt_no" placeholder="留空自动生成" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12" :xl="4">
            <el-form-item label="供应商" :required="form.business_type === 'purchase'">
              <el-select v-model="form.supplier_id" filterable clearable style="width: 100%">
                <el-option v-for="item in options.suppliers" :key="item.value" v-bind="item" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12" :xl="4">
            <el-form-item label="入库日期" prop="receipt_date">
              <el-date-picker
                v-model="form.receipt_date"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12" :xl="4">
            <el-form-item label="业务类型" prop="business_type">
              <el-select v-model="form.business_type" style="width: 100%">
                <el-option v-for="item in businessTypes" :key="item.value" v-bind="item" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12" :xl="4">
            <el-form-item label="默认仓库" prop="warehouse_id">
              <el-select
                v-model="form.warehouse_id"
                filterable
                style="width: 100%"
                @change="changeDefaultWarehouse"
              >
                <el-option v-for="item in options.warehouses" :key="item.value" v-bind="item" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12" :xl="4">
            <el-form-item label="经办人">
              <el-select v-model="form.employee_id" filterable clearable style="width: 100%">
                <el-option v-for="item in options.employees" :key="item.value" v-bind="item" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
      </div>

      <div v-if="!readonly && scanMode" class="scan-bar">
        <span class="scan-label">扫码录入</span>
        <el-input
          ref="scanInput"
          v-model="scanCode"
          placeholder="扫描条码或输入商品编码后回车；重复扫描自动累加数量"
          clearable
          @keyup.enter="scanProduct"
        />
        <BaseButton type="primary" @click="scanProduct">录入</BaseButton>
        <span class="scan-tip">明细商品框支持编码、名称、条码、规格模糊搜索</span>
      </div>

      <div class="detail-table-wrap">
        <el-table
          :data="form.lines"
          border
          class="detail-table"
          row-key="key"
          :row-style="{ height: '31px' }"
        >
          <el-table-column width="54" fixed="left" align="center">
            <template #default="{ $index }">
              <template v-if="!readonly">
                <BaseButton type="primary" link class="line-button" @click="addLine($index)"
                  >＋</BaseButton
                >
                <BaseButton type="danger" link class="line-button" @click="removeLine($index)"
                  >－</BaseButton
                >
              </template>
              <span v-else>{{ $index + 1 }}</span>
            </template>
          </el-table-column>
          <el-table-column min-width="260" fixed="left">
            <template #header>
              <div class="product-column-title">
                <span><i>*</i> 商品</span>
                <span v-if="!readonly" class="scan-switch">
                  --扫码枪录入
                  <el-switch v-model="scanMode" size="small" />
                </span>
              </div>
            </template>
            <template #default="{ row, $index }">
              <div
                class="excel-cell product-excel-cell"
                :class="{ 'is-active': isActiveCell(row, 'product') }"
                :data-cell="`${row.key}-product`"
                @click="focusCell(row.key, 'product')"
                @focusin="activateCell(row, 'product')"
                @keydown.capture="handleProductKeydownCapture($event, row, $index)"
                @keydown="handleCellKeydown($event, row, $index, 'product')"
              >
                <el-select
                  :ref="(instance) => setProductSelectRef(row.key, instance)"
                  v-model="row.product_id"
                  filterable
                  remote
                  reserve-keyword
                  :remote-method="remoteProductSearch"
                  :loading="productLoading"
                  placeholder="输入编码 / 名称 / 条码"
                  style="width: 100%"
                  popper-class="inbound-product-popper"
                  @change="chooseProduct(row, $event)"
                  @visible-change="handleProductDropdownVisible(row.key, $event)"
                >
                  <el-option :value="-1" disabled class="product-dropdown-header">
                    <div class="product-option-grid">
                      <b>商品编号</b><b>商品名称</b><b>规格型号</b><b>计量单位</b><b>库存数量</b>
                    </div>
                  </el-option>
                  <el-option
                    v-for="item in productOptions"
                    :key="item.id"
                    :value="item.id"
                    :label="skuLabel(item, { barcode: true })"
                  >
                    <div class="product-option">
                      <span>{{ item.code }}</span>
                      <span>{{ item.name }}</span>
                      <span>{{ skuSpec(item) }}</span>
                      <span>{{ item.units?.[0]?.unit_name || '-' }}</span>
                      <span>{{ item.stock_quantity }}</span>
                    </div>
                  </el-option>
                </el-select>
                <button
                  v-if="!readonly && !scanMode"
                  type="button"
                  class="product-picker-trigger"
                  title="选择多个商品"
                  @mousedown.stop.prevent
                  @click.stop="openProductPicker(row)"
                >
                  ···
                </button>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="规格型号" width="110" show-overflow-tooltip>
            <template #default="{ row, $index }">
              <div
                class="excel-cell excel-readonly-cell"
                :class="{ 'is-active': isActiveCell(row, 'spec') }"
                :data-cell="`${row.key}-spec`"
                tabindex="-1"
                @click="focusCell(row.key, 'spec')"
                @focus="activateCell(row, 'spec')"
                @keydown="handleCellKeydown($event, row, $index, 'spec')"
              >
                {{ skuSpec(row.product) }}
              </div>
            </template>
          </el-table-column>
          <el-table-column label="商品单位" width="95">
            <template #default="{ row, $index }">
              <div
                class="excel-cell"
                :class="{ 'is-active': isActiveCell(row, 'unit') }"
                :data-cell="`${row.key}-unit`"
                @click="focusCell(row.key, 'unit')"
                @focusin="activateCell(row, 'unit')"
                @keydown="handleCellKeydown($event, row, $index, 'unit')"
              >
                <el-select v-model="row.unit_id" style="width: 100%" @change="changeUnit(row)">
                  <el-option
                    v-for="unit in row.product?.units || []"
                    :key="unit.unit_id"
                    :value="unit.unit_id"
                    :label="`${'　'.repeat(unit.level)}${unit.unit_name}`"
                  />
                </el-select>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="仓库" width="120">
            <template #default="{ row, $index }">
              <div
                class="excel-cell"
                :class="{ 'is-active': isActiveCell(row, 'warehouse') }"
                :data-cell="`${row.key}-warehouse`"
                @click="focusCell(row.key, 'warehouse')"
                @focusin="activateCell(row, 'warehouse')"
                @keydown="handleCellKeydown($event, row, $index, 'warehouse')"
              >
                <el-select v-model="row.warehouse_id" filterable style="width: 100%">
                  <el-option v-for="item in options.warehouses" :key="item.value" v-bind="item" />
                </el-select>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="可用库存" width="88" align="right">
            <template #default="{ row }"
              ><div class="excel-display-cell number-cell">{{
                row.product?.stock_quantity ?? '-'
              }}</div></template
            >
          </el-table-column>
          <el-table-column label="批次号" width="110">
            <template #default="{ row, $index }">
              <div
                class="excel-cell"
                :class="{
                  'is-active': isActiveCell(row, 'batch_no'),
                  'is-disabled': !row.product?.batch_enabled
                }"
                :data-cell="`${row.key}-batch_no`"
                @click="row.product?.batch_enabled && focusCell(row.key, 'batch_no')"
                @focusin="activateCell(row, 'batch_no')"
                @keydown="handleCellKeydown($event, row, $index, 'batch_no')"
              >
                <el-input
                  v-if="row.product?.batch_enabled"
                  v-model="row.batch_no"
                  placeholder="必填"
                />
                <span v-else class="muted">不管理</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="生产日期" width="120">
            <template #default="{ row, $index }">
              <div
                class="excel-cell"
                :class="{
                  'is-active': isActiveCell(row, 'production_date'),
                  'is-disabled': !row.product?.batch_enabled
                }"
                :data-cell="`${row.key}-production_date`"
                @click="row.product?.batch_enabled && focusCell(row.key, 'production_date')"
                @focusin="activateCell(row, 'production_date')"
                @keydown="handleCellKeydown($event, row, $index, 'production_date')"
              >
                <el-date-picker
                  v-if="row.product?.batch_enabled"
                  v-model="row.production_date"
                  value-format="YYYY-MM-DD"
                  style="width: 100%"
                  @change="changeProductionDate(row)"
                />
                <span v-else class="muted">-</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="有效期至" width="120">
            <template #default="{ row, $index }">
              <div
                class="excel-cell"
                :class="{
                  'is-active': isActiveCell(row, 'expiry_date'),
                  'is-disabled': !row.product?.batch_enabled
                }"
                :data-cell="`${row.key}-expiry_date`"
                @click="row.product?.batch_enabled && focusCell(row.key, 'expiry_date')"
                @focusin="activateCell(row, 'expiry_date')"
                @keydown="handleCellKeydown($event, row, $index, 'expiry_date')"
              >
                <el-date-picker
                  v-if="row.product?.batch_enabled"
                  v-model="row.expiry_date"
                  value-format="YYYY-MM-DD"
                  style="width: 100%"
                />
                <span v-else class="muted">-</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="数量 *" width="100">
            <template #default="{ row, $index }">
              <div
                class="excel-cell number-editor"
                :class="{ 'is-active': isActiveCell(row, 'quantity') }"
                :data-cell="`${row.key}-quantity`"
                @click="focusCell(row.key, 'quantity')"
                @focusin="activateCell(row, 'quantity')"
                @keydown="handleCellKeydown($event, row, $index, 'quantity')"
              >
                <el-input-number
                  v-model="row.quantity"
                  :min="0"
                  :precision="selectedUnit(row)?.decimal_places ?? 6"
                  :controls="false"
                  style="width: 100%"
                />
              </div>
            </template>
          </el-table-column>
          <el-table-column label="入库单价" width="110">
            <template #default="{ row, $index }">
              <div
                class="excel-cell number-editor"
                :class="{ 'is-active': isActiveCell(row, 'unit_price') }"
                :data-cell="`${row.key}-unit_price`"
                @click="focusCell(row.key, 'unit_price')"
                @focusin="activateCell(row, 'unit_price')"
                @keydown="handleCellKeydown($event, row, $index, 'unit_price')"
              >
                <el-input-number
                  v-model="row.unit_price"
                  :min="0"
                  :precision="4"
                  :controls="false"
                  style="width: 100%"
                />
              </div>
            </template>
          </el-table-column>
          <el-table-column label="入库金额" width="100" align="right">
            <template #default="{ row }"
              ><div class="excel-display-cell number-cell">{{
                lineAmount(row).toFixed(2)
              }}</div></template
            >
          </el-table-column>
          <el-table-column label="基本数量" width="95" align="right">
            <template #default="{ row }"
              ><div class="excel-display-cell number-cell">{{
                baseQuantity(row)
                  .toFixed(6)
                  .replace(/\.?0+$/, '')
              }}</div></template
            >
          </el-table-column>
          <el-table-column label="序列号" width="110">
            <template #default="{ row, $index }">
              <div
                class="excel-cell"
                :class="{
                  'is-active': isActiveCell(row, 'serial'),
                  'is-disabled': !row.product?.serial_enabled
                }"
                :data-cell="`${row.key}-serial`"
                @click="row.product?.serial_enabled && activateCell(row, 'serial')"
                @keydown="handleCellKeydown($event, row, $index, 'serial')"
              >
                <BaseButton
                  v-if="row.product?.serial_enabled"
                  type="primary"
                  link
                  @click="openSerials(row)"
                >
                  录入（{{ row.serial_numbers.length }}）
                </BaseButton>
                <span v-else class="muted">不管理</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="备注" min-width="140">
            <template #default="{ row, $index }">
              <div
                class="excel-cell"
                :class="{ 'is-active': isActiveCell(row, 'remark') }"
                :data-cell="`${row.key}-remark`"
                @click="focusCell(row.key, 'remark')"
                @focusin="activateCell(row, 'remark')"
                @keydown="handleCellKeydown($event, row, $index, 'remark')"
              >
                <el-input v-model="row.remark" />
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <el-input
        v-model="form.remark"
        class="document-remark"
        type="textarea"
        :rows="2"
        placeholder="备注信息"
      />
      <div class="summary-bar">
        <div
          ><label>商品行数：</label
          ><span>{{ form.lines.filter((line: InboundLine) => line.product_id).length }}</span></div
        >
        <div
          ><label>基本数量：</label
          ><span>{{ totalQuantity.toFixed(6).replace(/\.?0+$/, '') }}</span></div
        >
        <div class="summary-total"
          ><label>入库金额：</label><span>¥ {{ totalAmount.toFixed(2) }}</span></div
        >
      </div>
    </el-form>
    <template #footer>
      <BaseButton @click="dialogVisible = false">关闭</BaseButton>
      <template v-if="!readonly">
        <BaseButton :loading="saving" @click="save(false)">保存草稿</BaseButton>
        <BaseButton type="primary" :loading="saving" @click="save(true)">保存并审核</BaseButton>
      </template>
    </template>
  </el-dialog>

  <el-dialog
    v-model="productPickerVisible"
    title="选择商品"
    width="88%"
    top="6vh"
    append-to-body
    destroy-on-close
    class="inbound-product-picker"
  >
    <div class="product-picker-toolbar">
      <el-input
        v-model="productPickerKeyword"
        clearable
        autofocus
        placeholder="输入商品编码、名称、条码或规格"
        @keyup.enter="loadProductPicker"
      />
      <BaseButton type="primary" @click="loadProductPicker">查询</BaseButton>
      <span>双击商品行也可以勾选，支持一次添加多个 SKU</span>
    </div>
    <el-table
      ref="productPickerTable"
      v-loading="productPickerLoading"
      :data="productPickerRows"
      row-key="id"
      border
      stripe
      height="56vh"
      @selection-change="handleProductPickerSelection"
      @row-dblclick="togglePickerProduct"
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
      <el-table-column prop="stock_quantity" label="可用库存" width="110" align="right" />
      <el-table-column label="参考进价" width="120" align="right">
        <template #default="{ row }">{{
          numberValue(row.default_purchase_price).toFixed(4)
        }}</template>
      </el-table-column>
    </el-table>
    <template #footer>
      <BaseButton @click="productPickerVisible = false">取消</BaseButton>
      <BaseButton type="primary" @click="applyPickedProducts">
        添加所选商品（{{ productPickerSelected.length }}）
      </BaseButton>
    </template>
  </el-dialog>

  <el-dialog v-model="serialDialogVisible" title="序列号录入" width="760px" append-to-body>
    <el-alert
      title="一行一个序列号，也可用逗号或空格分隔；确认后自动按序列号数量回填商品数量。"
      type="info"
      :closable="false"
    />
    <div class="serial-generator">
      <el-input v-model="serialGenerator.prefix" placeholder="前缀（可空）" />
      <el-input v-model="serialGenerator.start" placeholder="起始号，如 001" />
      <el-input-number v-model="serialGenerator.increment" :min="1" placeholder="递增量" />
      <el-input-number v-model="serialGenerator.count" :min="1" placeholder="个数" />
      <BaseButton type="primary" @click="generateSerials">批量生成</BaseButton>
    </div>
    <el-input v-model="serialText" type="textarea" :rows="14" placeholder="SN0001&#10;SN0002" />
    <template #footer>
      <BaseButton @click="serialDialogVisible = false">取消</BaseButton>
      <BaseButton type="primary" @click="applySerials">确认录入</BaseButton>
    </template>
  </el-dialog>
</template>

<style scoped>
.search-bar,
.toolbar,
.scan-bar,
.summary-bar,
.serial-generator,
.product-picker-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
}
.search-bar {
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.search-bar .el-input {
  width: 210px;
}
.search-bar .el-select {
  width: 135px;
}
.toolbar {
  margin-bottom: 12px;
}
.pagination {
  justify-content: flex-end;
  margin-top: 16px;
}
.document-header {
  padding: 12px 16px 0;
  background: #fff;
}
.document-header :deep(.el-form-item) {
  margin-bottom: 10px;
}
.document-header :deep(.el-form-item__label) {
  color: #222;
  font-size: 13px;
  font-weight: 500;
}
.scan-bar {
  padding: 8px 14px;
  color: var(--el-text-color-regular);
  background: #f7f9fb;
  border: 1px solid #dcdfe6;
  border-bottom: 0;
}
.scan-bar .el-input {
  width: 430px;
}
.scan-label {
  font-weight: 600;
}
.scan-tip {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.detail-table-wrap {
  width: 100%;
  overflow: hidden;
}
.detail-table :deep(.el-table__cell) {
  height: 31px;
  padding: 0;
  border-color: #b9c0c8;
}
.detail-table :deep(th.el-table__cell) {
  height: 33px;
  padding: 0;
  color: #24292f;
  font-size: 12px;
  font-weight: 600;
  background: #e9edf2;
  border-color: #aeb6c0;
}
.detail-table :deep(.el-table__header .cell),
.detail-table :deep(.el-table__body .cell) {
  height: 100%;
  padding: 0;
  line-height: 30px;
}
.detail-table :deep(.el-table__row:hover > td.el-table__cell) {
  background-color: #f7fbf8;
}
.detail-table :deep(.el-table__fixed-column--left),
.detail-table :deep(.el-table-fixed-column--right) {
  background: #fff;
}
.detail-table :deep(.el-table__inner-wrapper::before) {
  height: 1px;
  background-color: #9fa8b3;
}
.detail-table :deep(.el-input__wrapper),
.detail-table :deep(.el-select__wrapper) {
  min-height: 29px;
  height: 29px;
  padding: 0 6px;
  background: transparent !important;
  border-radius: 0;
  box-shadow: none !important;
}
.detail-table :deep(.el-input-number .el-input__wrapper) {
  box-shadow: none !important;
}
.detail-table :deep(.el-input__inner),
.detail-table :deep(.el-select__selected-item),
.detail-table :deep(.el-date-editor .el-range-input) {
  color: #20252b;
  font-size: 12px;
}
.detail-table :deep(.el-input__inner::placeholder) {
  color: #9aa3ad;
}
.detail-table :deep(.el-select__suffix),
.detail-table :deep(.el-input__suffix),
.detail-table :deep(.el-input__prefix) {
  opacity: 0;
  transition: opacity 0.12s ease;
}
.detail-table .excel-cell:hover :deep(.el-select__suffix),
.detail-table .excel-cell:hover :deep(.el-input__suffix),
.detail-table .excel-cell:hover :deep(.el-input__prefix),
.detail-table .excel-cell.is-active :deep(.el-select__suffix),
.detail-table .excel-cell.is-active :deep(.el-input__suffix),
.detail-table .excel-cell.is-active :deep(.el-input__prefix) {
  opacity: 1;
}
.detail-table :deep(.el-input-number .el-input__inner) {
  text-align: right;
}
.excel-cell,
.excel-display-cell {
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
  height: 30px;
  min-width: 0;
  padding: 0 6px;
  line-height: 30px;
  box-sizing: border-box;
}
.excel-cell {
  padding: 0;
  cursor: cell;
  background: transparent;
}
.product-excel-cell {
  padding-right: 28px;
}
.product-excel-cell :deep(.el-select__suffix) {
  display: none;
}
.product-picker-trigger {
  position: absolute;
  z-index: 7;
  top: 4px;
  right: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 23px;
  height: 22px;
  padding: 0;
  color: #4e5965;
  font-size: 15px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: -1px;
  cursor: pointer;
  background: transparent;
  border: 0;
  border-radius: 2px;
}
.product-picker-trigger:hover {
  color: #217346;
  background: #e7f2eb;
}
.excel-readonly-cell {
  padding: 0 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  outline: none;
}
.excel-cell::after {
  position: absolute;
  z-index: 5;
  inset: -1px;
  border: 2px solid transparent;
  pointer-events: none;
  content: '';
}
.excel-cell.is-active {
  z-index: 3;
  background: rgba(33, 115, 70, 0.035);
}
.excel-cell.is-active::after {
  border-color: #217346;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.75);
}
.excel-cell.is-active::before {
  position: absolute;
  z-index: 6;
  right: -3px;
  bottom: -3px;
  width: 5px;
  height: 5px;
  background: #217346;
  content: '';
}
.excel-cell.is-disabled {
  justify-content: center;
  padding: 0 6px;
  color: #a5adb6;
  cursor: default;
  background: #f6f7f8;
}
.number-cell {
  justify-content: flex-end;
  font-variant-numeric: tabular-nums;
}
.number-editor {
  font-variant-numeric: tabular-nums;
}
.product-column-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 8px;
}
.product-column-title i {
  color: #e53935;
  font-style: normal;
}
.scan-switch {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: #222;
  font-size: 12px;
  font-weight: 500;
}
.product-picker-toolbar {
  margin-bottom: 12px;
}
.product-picker-toolbar .el-input {
  width: 420px;
}
.product-picker-toolbar > span {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.line-button {
  min-width: 18px;
  height: 28px;
  padding: 0;
  margin: 0 1px;
  color: #303133;
  font-size: 16px;
}
.product-option {
  display: grid;
  grid-template-columns: 105px minmax(240px, 1fr) 160px 90px 100px;
  min-width: 720px;
}
.product-option > span,
.product-option-grid > * {
  padding: 0 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  border-right: 1px solid #d9dde3;
}
.product-option-grid {
  display: grid;
  grid-template-columns: 105px minmax(240px, 1fr) 160px 90px 100px;
  min-width: 720px;
}
.muted {
  color: var(--el-text-color-placeholder);
  font-size: 11px;
}
.document-remark {
  display: block;
  margin-top: 12px;
}
.document-remark :deep(.el-textarea__inner) {
  min-height: 58px !important;
  border-radius: 0;
  box-shadow: 0 0 0 1px #d9dde3 inset;
}
.summary-bar {
  justify-content: space-between;
  padding: 8px 24px;
  margin-top: 8px;
  background: #fafafa;
  border-top: 1px solid #d9dde3;
  border-bottom: 1px solid #d9dde3;
  font-size: 14px;
}
.summary-bar > div {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 260px;
}
.summary-bar label {
  color: #222;
  font-weight: 500;
}
.summary-bar span {
  display: inline-flex;
  align-items: center;
  min-width: 180px;
  height: 28px;
  padding: 0 12px;
  background: #f0f0f0;
  border: 1px solid #d9dde3;
}
.summary-total span {
  color: var(--el-color-danger);
  font-size: 16px;
  font-weight: 600;
}
.serial-generator {
  margin: 14px 0;
}
.serial-generator .el-input {
  width: 150px;
}
.serial-generator .el-input-number {
  width: 120px;
}

:global(.inbound-dialog) {
  display: flex;
  flex-direction: column;
  background: #fff;
}
:global(.inbound-dialog .el-dialog__header) {
  height: 54px;
  padding: 0 20px;
  margin: 0;
  color: #fff;
  background: #2f4358;
}
:global(.inbound-dialog .el-dialog__title) {
  color: #fff;
  font-size: 16px;
  font-weight: 500;
  line-height: 54px;
}
:global(.inbound-dialog .el-dialog__headerbtn) {
  top: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 54px;
  height: 54px;
  padding: 0;
  line-height: 1;
}
:global(.inbound-dialog .el-dialog__headerbtn .el-dialog__close) {
  display: block;
  color: #fff;
  font-size: 20px;
}
:global(.inbound-dialog .el-dialog__body) {
  flex: 1;
  padding: 0 16px 16px;
  overflow: auto;
}
:global(.inbound-dialog .el-dialog__footer) {
  padding: 12px 20px;
  border-top: 1px solid #d9dde3;
}
:global(.inbound-product-popper) {
  width: 760px !important;
}
:global(.inbound-product-popper .el-select-dropdown__item) {
  height: 36px;
  padding: 0;
  line-height: 36px;
  border-bottom: 1px solid #d9dde3;
}
:global(.inbound-product-popper .product-dropdown-header) {
  color: #222 !important;
  background: #e6e7e9 !important;
  opacity: 1;
}
:global(.inbound-product-popper .el-select-dropdown__wrap) {
  max-height: 320px;
}
</style>
