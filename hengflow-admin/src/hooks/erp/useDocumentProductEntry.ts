import { nextTick, reactive, ref, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import { skuLabel } from '@/utils/erp/product'

export interface EntryProduct {
  id: number
  code: string
  name: string
  barcode?: string
  serial_enabled?: boolean
  [key: string]: any
}

export interface EntryLine {
  key: number
  product_id?: number
  product?: EntryProduct
  warehouse_id?: number
  quantity: number
  [key: string]: any
}

interface ProductEntryOptions<L extends EntryLine, P extends EntryProduct> {
  lines: () => L[]
  readonly: Ref<boolean>
  warehouseId: () => number | undefined
  createLine: () => L
  search: (keyword: string) => Promise<P[]>
  applyProduct: (line: L, product: P) => void
  incrementLine?: (line: L) => void
  navColumns: readonly string[]
  columnAvailable?: (line: L, column: string) => boolean
}

/** 为 ERP 明细表提供商品搜索、扫码、多选插入和 Excel 式键盘导航。 */
export const useDocumentProductEntry = <L extends EntryLine, P extends EntryProduct>(
  config: ProductEntryOptions<L, P>
) => {
  const productOptions = ref<P[]>([]) as Ref<P[]>
  const productLoading = ref(false)
  const scanMode = ref(false)
  const scanCode = ref('')
  const scanInput = ref<any>()
  const pickerVisible = ref(false)
  const pickerLoading = ref(false)
  const pickerRows = ref<P[]>([]) as Ref<P[]>
  const pickerKeyword = ref('')
  const pickerAnchorKey = ref<number>()
  const activeCell = reactive({ rowKey: 0, column: '' })

  /** 合并搜索结果和已选商品，避免编辑已有行时下拉项丢失。 */
  const mergeProducts = (items: P[], retainExisting = true) => {
    const selected = config
      .lines()
      .map((line) => line.product as P | undefined)
      .filter(Boolean) as P[]
    productOptions.value = Array.from(
      new Map(
        [...selected, ...(retainExisting ? productOptions.value : []), ...items].map((item) => [
          item.id,
          item
        ])
      ).values()
    )
  }

  /** 搜索商品下拉候选。 */
  const loadProducts = async (keyword = '') => {
    productLoading.value = true
    try {
      mergeProducts(await config.search(keyword), false)
    } finally {
      productLoading.value = false
    }
  }

  /** 按商品 ID 将完整 SKU 快照写入指定明细行。 */
  const chooseProduct = (line: L, productId: number) => {
    const product = productOptions.value.find((item) => item.id === productId)
    if (product) config.applyProduct(line, product)
  }

  /** 根据编码或条码精确扫码；非序列号商品重复扫描时累加数量。 */
  const scanProduct = async () => {
    const code = scanCode.value.trim()
    if (!code) return
    const found = await config.search(code)
    const product =
      found.find((item) => item.barcode === code || item.code === code) ||
      (found.length === 1 ? found[0] : undefined)
    if (!product) {
      ElMessage.warning('没有找到唯一匹配的 SKU，请使用商品搜索或“…”选择')
      return
    }
    mergeProducts([product])
    const existing = config
      .lines()
      .find(
        (line) =>
          line.product_id === product.id &&
          line.warehouse_id === config.warehouseId() &&
          !product.serial_enabled
      )
    if (existing) {
      if (config.incrementLine) config.incrementLine(existing)
      else existing.quantity = Number(existing.quantity || 0) + 1
    } else {
      const target = config.lines().find((line) => !line.product_id) || config.createLine()
      if (!config.lines().includes(target)) config.lines().push(target)
      config.applyProduct(target, product)
    }
    scanCode.value = ''
    ElMessage.success(`已录入：${skuLabel(product)}`)
    await nextTick()
    scanInput.value?.focus?.()
  }

  /** 打开商品多选弹窗并记住批量插入的起始行。 */
  const openPicker = async (line: L) => {
    pickerAnchorKey.value = line.key
    pickerKeyword.value = ''
    pickerVisible.value = true
    await searchPicker()
  }

  /** 查询商品多选弹窗。 */
  const searchPicker = async () => {
    pickerLoading.value = true
    try {
      pickerRows.value = await config.search(pickerKeyword.value)
    } finally {
      pickerLoading.value = false
    }
  }

  /** 从锚点行开始写入多选商品，其余商品自动插入新行。 */
  const applyPickedProducts = async (products: P[]) => {
    if (!products.length) return ElMessage.warning('请至少选择一个商品')
    const lines = config.lines()
    const anchorIndex = lines.findIndex((line) => line.key === pickerAnchorKey.value)
    if (anchorIndex < 0) return ElMessage.warning('原商品行已不存在，请重新选择')
    mergeProducts(products)
    products.forEach((product, index) => {
      const target = index === 0 ? lines[anchorIndex] : config.createLine()
      if (index > 0) lines.splice(anchorIndex + index, 0, target)
      config.applyProduct(target, product)
    })
    pickerVisible.value = false
    await focusCell(lines[anchorIndex], 'product')
  }

  const isAvailable = (line: L, column: string) => config.columnAvailable?.(line, column) ?? true
  const cellSelector = (line: L, column: string) => `[data-entry-cell="${line.key}-${column}"]`

  /** 聚焦明细单元格，并在数字字段中自动选中原值。 */
  const focusCell = async (line: L, column: string) => {
    activeCell.rowKey = line.key
    activeCell.column = column
    await nextTick()
    const cell = document.querySelector(cellSelector(line, column)) as HTMLElement | null
    const input = cell?.querySelector('input') as HTMLInputElement | null
    if (input) {
      input.focus()
      if (
        ['quantity', 'counted_quantity', 'unit_price', 'discount_rate', 'tax_rate'].includes(column)
      )
        input.select()
    } else cell?.focus()
  }

  /** 在明细网格中按方向移动，商品列向下越界时自动增加一行。 */
  const moveCell = async (line: L, rowIndex: number, column: string, direction: string) => {
    const columns = [...config.navColumns]
    const columnIndex = columns.indexOf(column)
    if (columnIndex < 0) return
    if (direction === 'up' || direction === 'down') {
      const targetIndex = rowIndex + (direction === 'down' ? 1 : -1)
      let target = config.lines()[targetIndex]
      if (!target && direction === 'down' && column === 'product' && !config.readonly.value) {
        target = config.createLine()
        config.lines().push(target)
      }
      if (!target) return
      const fallback = isAvailable(target, column)
        ? column
        : columns.find((candidate) => isAvailable(target, candidate))
      if (fallback) await focusCell(target, fallback)
      return
    }
    const delta = direction === 'right' ? 1 : -1
    let index = columnIndex + delta
    while (index >= 0 && index < columns.length && !isAvailable(line, columns[index]))
      index += delta
    if (index >= 0 && index < columns.length) await focusCell(line, columns[index])
  }

  /** 处理普通明细格的方向键和 Esc，保留文本光标在输入框内部的移动。 */
  const handleCellKeydown = (event: KeyboardEvent, line: L, rowIndex: number, column: string) => {
    if (config.readonly.value) return
    const target = event.target as HTMLElement
    const isDatePicker = !!target.closest('.el-date-editor')
    const input = event.target instanceof HTMLInputElement ? event.target : null
    if (isDatePicker && (event.key === 'ArrowLeft' || event.key === 'ArrowRight')) return
    if (event.key === 'ArrowLeft' && input?.selectionStart && input.selectionStart > 0) return
    if (
      event.key === 'ArrowRight' &&
      input?.selectionStart !== null &&
      input?.selectionStart !== undefined &&
      input.selectionStart < input.value.length
    )
      return
    const directions: Record<string, string> = {
      ArrowUp: 'up',
      ArrowDown: 'down',
      ArrowLeft: 'left',
      ArrowRight: 'right'
    }
    if (directions[event.key]) {
      event.preventDefault()
      moveCell(line, rowIndex, column, directions[event.key])
    } else if (event.key === 'Escape') {
      ;(event.target as HTMLElement).blur()
      activeCell.column = ''
    }
  }

  /** 防止开单弹窗中的 Enter 意外提交，扫码输入和备注除外。 */
  const preventDocumentEnter = (event: KeyboardEvent) => {
    const target = event.target as HTMLElement
    if (target.closest('.document-scan-bar') || target.tagName === 'TEXTAREA') return
    event.preventDefault()
    event.stopPropagation()
  }

  return {
    activeCell,
    productOptions,
    productLoading,
    scanMode,
    scanCode,
    scanInput,
    pickerVisible,
    pickerLoading,
    pickerRows,
    pickerKeyword,
    loadProducts,
    chooseProduct,
    scanProduct,
    openPicker,
    searchPicker,
    applyPickedProducts,
    focusCell,
    moveCell,
    handleCellKeydown,
    preventDocumentEnter
  }
}
