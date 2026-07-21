<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ContentWrap } from '@/components/ContentWrap'
import DocumentPayment from '@/components/Erp/DocumentPayment.vue'
import DocumentProductPicker from '@/components/Erp/DocumentProductPicker.vue'
import DocumentProductSelect from '@/components/Erp/DocumentProductSelect.vue'
import DocumentSerialEditor from '@/components/Erp/DocumentSerialEditor.vue'
import { useDocumentProductEntry } from '@/hooks/erp/useDocumentProductEntry'
import { skuLabel, skuSpec } from '@/utils/erp/product'
import { documentProductName, documentUnitName, printBusinessDocument } from '@/utils/erp/printing'
import '@/styles/erp-document.css'
import {
  addSalesDocumentApi,
  approveSalesDocumentApi,
  delSalesDocumentApi,
  getSalesDocumentApi,
  getSalesDocumentListApi,
  getSalesOptionsApi,
  getSalesSourceDeliveriesApi,
  getSalesSourceOrdersApi,
  putSalesDocumentApi,
  searchSalesProductsApi,
  type SalesDocumentKind,
  unapproveSalesDocumentApi
} from '@/api/erp/sales'

const props = defineProps<{ kind: SalesDocumentKind; title: string }>()

interface Option {
  value: number
  label: string
  address?: string
  payment_days?: number
}

interface ProductUnit {
  unit_id: number
  unit_name: string
  unit_code: string
  to_base_rate: number
}

interface Product {
  id: number
  code: string
  name: string
  spu_name?: string
  barcode?: string
  variant_name?: string
  specification?: string
  default_sale_price: number
  tax_rate: number
  available_quantity: number
  batch_enabled: boolean
  serial_enabled: boolean
  base_unit_id: number
  units: ProductUnit[]
}

interface Line {
  key: number
  id?: number
  product_id?: number
  product?: Product
  warehouse_id?: number
  unit_id?: number
  quantity: number
  unit_price: number
  discount_rate: number
  tax_rate: number
  order_line_id?: number
  delivery_line_id?: number
  batch_no?: string
  serialText: string
  remark?: string
}

const loading = ref(false)
const saving = ref(false)
const rows = ref<any[]>([])
const total = ref(0)
const dialogVisible = ref(false)
const readonly = ref(false)
const editingId = ref<number>()
const sourceDocuments = ref<any[]>([])
const sourceLoading = ref(false)
const options = reactive<{
  customers: Option[]
  warehouses: Option[]
  employees: Option[]
  accounts: Option[]
  settlement_methods: Option[]
}>({
  customers: [],
  warehouses: [],
  employees: [],
  accounts: [],
  settlement_methods: []
})
const query = reactive({
  page: 1,
  limit: 20,
  keyword: '',
  status: '',
  customer_id: undefined as number | undefined
})
let lineKey = 0

const form = reactive<any>({
  business_date: dayjs().format('YYYY-MM-DD'),
  expected_delivery_date: '',
  due_date: '',
  customer_id: undefined,
  warehouse_id: undefined,
  employee_id: undefined,
  order_id: undefined,
  delivery_id: undefined,
  batch_selection_mode: 'auto',
  settlement_discount_rate: 100,
  rounding_amount: 0,
  current_payment_amount: 0,
  settlement_method_id: undefined,
  fund_account_id: undefined,
  delivery_address: '',
  remark: '',
  lines: [] as Line[]
})

const isOrder = computed(() => props.kind === 'orders')
const isDelivery = computed(() => props.kind === 'deliveries')
const isReturn = computed(() => props.kind === 'returns')
const statusMap: Record<string, { label: string; type: '' | 'success' | 'warning' | 'info' }> = {
  draft: { label: '草稿', type: 'info' },
  approved: { label: '已审核', type: 'success' },
  partial: { label: '部分履约', type: 'warning' },
  completed: { label: '已完成', type: 'success' }
}

/** 将金额统一格式化为两位小数。 */
const money = (value: any) => Number(value || 0).toFixed(2)
const serialValues = (value: string) =>
  String(value || '')
    .split(/[,，\n\s]+/)
    .filter(Boolean)
const changeSerials = (line: Line, values: string[]) => {
  line.serialText = values.join(',')
  line.quantity = values.length
}
/** 计算一行折扣后的未税商品金额。 */
const lineAmount = (line: Line) =>
  (Number(line.quantity || 0) * Number(line.unit_price || 0) * Number(line.discount_rate || 0)) /
  100
const baseQuantity = (line: Line) => {
  const unit = (line.product?.units || []).find((item) => item.unit_id === line.unit_id)
  return Number(line.quantity || 0) * Number(unit?.to_base_rate || 1)
}
const taxInclusiveTotal = computed(() =>
  form.lines.reduce(
    (sum: number, line: Line) => sum + lineAmount(line) * (1 + Number(line.tax_rate || 0) / 100),
    0
  )
)
const productLineCount = computed(() => form.lines.filter((line: Line) => line.product_id).length)
const quantityTotal = computed(() =>
  form.lines.reduce((sum: number, line: Line) => sum + Number(line.quantity || 0), 0)
)
/** 生成人类可读的商品行标题。 */
const productLabel = (line: Line) =>
  line.product ? skuLabel(line.product, { barcode: true }) : `SKU #${line.product_id || ''}`

/** 切换多单位时按换算率同步销售单价。 */
const changeUnit = (line: Line) => {
  const unit = (line.product?.units || []).find((item) => item.unit_id === line.unit_id)
  if (line.product && unit)
    line.unit_price = Number(
      (Number(line.product.default_sale_price || 0) * Number(unit.to_base_rate || 1)).toFixed(6)
    )
}

/** 创建带默认业务值的空白明细行。 */
const emptyLine = (): Line => ({
  key: ++lineKey,
  warehouse_id: form.warehouse_id,
  quantity: 1,
  unit_price: 0,
  discount_rate: 100,
  tax_rate: 0,
  serialText: ''
})

/** 新单据按入库单习惯预置四行空白商品。 */
const defaultLines = () => Array.from({ length: 4 }, () => emptyLine())

const canAddProducts = computed(() => isOrder.value || (isDelivery.value && !form.order_id))

/** 调用销售商品目录，为商品下拉、扫码和多选弹窗返回同一组 SKU。 */
const searchProducts = async (keyword = '') => {
  const res = await searchSalesProductsApi({
    keyword: keyword || undefined,
    warehouse_id: form.warehouse_id,
    limit: 100
  })
  return (res.data || []) as Product[]
}

const productEntry = useDocumentProductEntry<any, any>({
  lines: () => form.lines,
  readonly,
  warehouseId: () => form.warehouse_id,
  createLine: emptyLine,
  search: searchProducts,
  navColumns: [
    'product',
    'unit',
    'warehouse',
    'quantity',
    'unit_price',
    'discount_rate',
    'tax_rate',
    'batch_no',
    'serial',
    'remark'
  ],
  columnAvailable: (line, column) => {
    if (column === 'batch_no')
      return !isOrder.value && !!line.product?.batch_enabled && form.batch_selection_mode !== 'auto'
    if (column === 'serial') return !isOrder.value && !!line.product?.serial_enabled
    return true
  },
  applyProduct: (line, product) => {
    line.product = product
    line.product_id = product.id
    line.unit_id = product.base_unit_id
    line.unit_price = Number(product.default_sale_price || 0)
    line.tax_rate = Number(product.tax_rate || 0)
    line.quantity = Number(line.quantity || 1)
    line.warehouse_id = form.warehouse_id
    line.batch_no = ''
    line.serialText = ''
  }
})

/** 重置单据表单和编辑上下文。 */
const resetForm = () => {
  editingId.value = undefined
  readonly.value = false
  Object.assign(form, {
    business_date: dayjs().format('YYYY-MM-DD'),
    expected_delivery_date: '',
    due_date: '',
    customer_id: undefined,
    warehouse_id: options.warehouses[0]?.value,
    employee_id: undefined,
    order_id: undefined,
    delivery_id: undefined,
    batch_selection_mode: 'auto',
    settlement_discount_rate: 100,
    rounding_amount: 0,
    current_payment_amount: 0,
    settlement_method_id: undefined,
    fund_account_id: undefined,
    delivery_address: '',
    remark: '',
    lines: []
  })
  if (!isReturn.value) form.lines = defaultLines()
  sourceDocuments.value = []
}

/** 根据筛选条件读取当前类型的单据列表。 */
const loadList = async () => {
  loading.value = true
  try {
    const params: any = { page: query.page, limit: query.limit }
    if (query.keyword) params.keyword = query.keyword
    if (query.status) params.status = query.status
    if (query.customer_id) params.customer_id = query.customer_id
    const res = await getSalesDocumentListApi(props.kind, params)
    rows.value = res.data || []
    total.value = res.count || 0
  } finally {
    loading.value = false
  }
}

/** 从第一页执行列表查询。 */
const searchList = () => {
  query.page = 1
  loadList()
}

/** 清空列表筛选条件并重新查询。 */
const resetQuery = () => {
  Object.assign(query, { keyword: '', status: '', customer_id: undefined, page: 1 })
  loadList()
}

/** 加载客户、仓库和职员等销售表单选项。 */
const loadOptions = async () => {
  const res = await getSalesOptionsApi()
  Object.assign(options, res.data || {})
}

const loadProducts = productEntry.loadProducts

/** 在指定行后插入商品明细；未指定时追加到末尾。 */
const addLine = (index?: number) => {
  if (index === undefined) form.lines.push(emptyLine())
  else form.lines.splice(index + 1, 0, emptyLine())
}
/** 删除指定商品明细并保证普通单据至少保留一个空行。 */
const removeLine = (index: number) => {
  form.lines.splice(index, 1)
  if (!form.lines.length && !isReturn.value) addLine()
}

/** 打开新增单据弹窗。 */
const openCreate = async () => {
  resetForm()
  dialogVisible.value = true
  await loadProducts()
}

/** 将后端明细转换为可编辑的前端行模型。 */
const hydrateLines = async (data: any) => {
  await loadProducts()
  form.lines = (data.lines || []).map((item: any) => {
    const catalogProduct = productEntry.productOptions.value.find((x) => x.id === item.product_id)
    const product = catalogProduct ? { ...item.product, ...catalogProduct } : item.product
    return {
      ...item,
      key: ++lineKey,
      product,
      quantity: Number(item.quantity),
      unit_price: Number(item.unit_price || 0),
      discount_rate: Number(item.discount_rate ?? 100),
      tax_rate: Number(item.tax_rate || 0),
      serialText: Array.isArray(item.serial_numbers) ? item.serial_numbers.join(',') : ''
    } as Line
  })
}

/** 加载单据详情并按状态进入编辑或只读模式。 */
const openDocument = async (row: any, view = false) => {
  resetForm()
  const res = await getSalesDocumentApi(props.kind, row.id)
  const data = res.data
  editingId.value = row.id
  readonly.value = view || data.status !== 'draft'
  Object.assign(form, data)
  await hydrateLines(data)
  dialogVisible.value = true
}

/** 加载当前客户可用的来源订单或来源出库单。 */
const loadSources = async () => {
  if (!form.customer_id || isOrder.value) return
  sourceLoading.value = true
  try {
    const res = isDelivery.value
      ? await getSalesSourceOrdersApi({ customer_id: form.customer_id })
      : await getSalesSourceDeliveriesApi({ customer_id: form.customer_id })
    sourceDocuments.value = res.data || []
  } finally {
    sourceLoading.value = false
  }
}

/** 将来源单据剩余可履约明细带入当前表单。 */
const selectSource = async (sourceId: number) => {
  const source = sourceDocuments.value.find((x) => x.id === sourceId)
  if (!source) {
    if (isDelivery.value) form.lines = defaultLines()
    return
  }
  form.customer_id = source.customer_id
  form.warehouse_id = source.warehouse_id
  form.employee_id = source.employee_id
  form.delivery_address = source.delivery_address || ''
  await loadProducts()
  form.lines = (source.lines || []).map((item: any) => {
    const catalogProduct = productEntry.productOptions.value.find((x) => x.id === item.product_id)
    const product = catalogProduct ? { ...item.product, ...catalogProduct } : item.product
    const rate = Number(item.unit_to_base_rate || 1)
    return {
      key: ++lineKey,
      product_id: item.product_id,
      product,
      warehouse_id: item.warehouse_id || source.warehouse_id,
      unit_id: item.unit_id,
      quantity:
        Number(isDelivery.value ? item.remaining_quantity : item.returnable_quantity) / rate,
      unit_price: Number(item.unit_price || 0),
      discount_rate: Number(item.discount_rate ?? 100),
      tax_rate: Number(item.tax_rate || 0),
      order_line_id: isDelivery.value ? item.id : undefined,
      delivery_line_id: isReturn.value ? item.id : undefined,
      batch_no: item.batch_no || '',
      serialText: Array.isArray(item.serial_numbers) ? item.serial_numbers.join(',') : '',
      remark: ''
    } as Line
  })
}

/** 客户变化时带入地址并清空不再有效的来源单据。 */
const changeCustomer = () => {
  const customer = options.customers.find((x) => x.value === form.customer_id)
  form.delivery_address = customer?.address || ''
  form.order_id = undefined
  form.delivery_id = undefined
  sourceDocuments.value = []
  loadSources()
}

watch(
  () => form.warehouse_id,
  (value) => {
    form.lines.forEach((line: Line) => {
      if (!line.order_line_id && !line.delivery_line_id) line.warehouse_id = value
    })
  }
)

/** 校验保存前必填项和来源单据约束。 */
const validate = () => {
  const enteredLines = form.lines.filter((line: Line) => line.product_id)
  if (!form.customer_id || !form.warehouse_id || !form.business_date)
    return '请填写客户、仓库和业务日期'
  if (isDelivery.value && form.order_id && !enteredLines.every((x: Line) => x.order_line_id))
    return '订单出库的每一行都必须来自所选订单'
  if (isReturn.value && (!form.delivery_id || !enteredLines.length))
    return '退货单必须选择原销售出库单'
  if (!enteredLines.length || enteredLines.some((x: Line) => !x.unit_id || Number(x.quantity) <= 0))
    return '请完整填写商品、单位和数量'
  if (isDelivery.value && Number(form.current_payment_amount || 0) > 0 && !form.fund_account_id)
    return '本次收款大于 0 时请选择收款账号'
  return ''
}

/** 按订单、出库或退货输入模型组装请求数据。 */
const payload = () => {
  const common: any = {
    business_date: form.business_date,
    customer_id: form.customer_id,
    warehouse_id: form.warehouse_id,
    employee_id: form.employee_id || null,
    remark: form.remark || null
  }
  if (isOrder.value) {
    Object.assign(common, {
      expected_delivery_date: form.expected_delivery_date || null,
      delivery_address: form.delivery_address || null
    })
  } else if (isDelivery.value) {
    Object.assign(common, {
      order_id: form.order_id || null,
      due_date: form.due_date || null,
      batch_selection_mode: form.batch_selection_mode || 'auto',
      settlement_discount_rate: Number(form.settlement_discount_rate ?? 100),
      rounding_amount: Number(form.rounding_amount || 0),
      current_payment_amount: Number(form.current_payment_amount || 0),
      settlement_method_id: form.settlement_method_id || null,
      fund_account_id: form.fund_account_id || null,
      delivery_address: form.delivery_address || null
    })
  } else {
    common.delivery_id = form.delivery_id
  }
  common.lines = form.lines
    .filter((line: Line) => line.product_id)
    .map((line: Line) => {
      const serial_numbers = line.serialText
        .split(/[，,\n]/)
        .map((x) => x.trim())
        .filter(Boolean)
      if (isReturn.value)
        return {
          delivery_line_id: line.delivery_line_id,
          warehouse_id: line.warehouse_id || form.warehouse_id,
          unit_id: line.unit_id,
          quantity: Number(line.quantity),
          batch_no: line.batch_no || null,
          serial_numbers,
          remark: line.remark || null
        }
      return {
        product_id: line.product_id,
        warehouse_id: line.warehouse_id || form.warehouse_id,
        unit_id: line.unit_id,
        quantity: Number(line.quantity),
        unit_price: Number(line.unit_price),
        discount_rate: Number(line.discount_rate),
        tax_rate: Number(line.tax_rate),
        order_line_id: isDelivery.value ? line.order_line_id || null : null,
        batch_no: line.batch_no || null,
        serial_numbers,
        remark: line.remark || null
      }
    })
  return common
}

/** 新增或更新销售草稿单据。 */
const save = async () => {
  const error = validate()
  if (error) return ElMessage.warning(error)
  saving.value = true
  try {
    editingId.value
      ? await putSalesDocumentApi(props.kind, editingId.value, payload())
      : await addSalesDocumentApi(props.kind, payload())
    ElMessage.success('保存成功')
    dialogVisible.value = false
    await loadList()
  } finally {
    saving.value = false
  }
}

/** 审核单据并触发相应库存、成本和应收业务。 */
const approve = async (row: any) => {
  const message = isOrder.value
    ? '审核后将预占可用库存'
    : isDelivery.value
      ? '审核后将正式扣减库存、结转成本并生成应收'
      : '审核后将商品回库并冲减应收'
  await ElMessageBox.confirm(`${message}，确定继续吗？`, '审核确认', { type: 'warning' })
  await approveSalesDocumentApi(props.kind, row.id)
  ElMessage.success('审核成功')
  await loadList()
}

/** 反审核单据并冲销其下游业务影响。 */
const unapprove = async (row: any) => {
  await ElMessageBox.confirm('反审核将冲销该单据产生的业务记录，确定继续吗？', '反审核确认', {
    type: 'warning'
  })
  await unapproveSalesDocumentApi(props.kind, row.id)
  ElMessage.success('反审核成功')
  await loadList()
}

/** 删除尚未审核的草稿单据。 */
const remove = async (row: any) => {
  await ElMessageBox.confirm(`确定删除草稿 ${row.document_no} 吗？`, '删除确认', {
    type: 'warning'
  })
  await delSalesDocumentApi(props.kind, [row.id])
  ElMessage.success('删除成功')
  await loadList()
}

/** 使用最新数据库详情生成销售单据打印内容。 */
const printDocument = async (row: any) => {
  const businessType = {
    orders: 'sales_order',
    deliveries: 'sales_delivery',
    returns: 'sales_return'
  }[props.kind]
  await printBusinessDocument(businessType, async () => {
    const res = await getSalesDocumentApi(props.kind, row.id)
    const data = res.data
    const customer = options.customers.find((item) => item.value === data.customer_id)
    const employee = options.employees.find((item) => item.value === data.employee_id)
    return {
      title: props.title,
      document_no: data.order_no || data.delivery_no || data.return_no,
      document_date: data.business_date,
      partner_name: customer?.label || `客户 #${data.customer_id}`,
      lines: (data.lines || []).map((line: any) => ({
        product_name: documentProductName(line),
        specification: skuSpec(line.product),
        quantity: Number(line.quantity || 0)
          .toFixed(6)
          .replace(/\.?0+$/, ''),
        unit_name: documentUnitName(line),
        unit_price: money(line.unit_price),
        amount: money(
          line.tax_inclusive_amount ??
            Number(line.quantity || 0) *
              Number(line.unit_price || 0) *
              (Number(line.discount_rate ?? 100) / 100) *
              (1 + Number(line.tax_rate || 0) / 100)
        )
      })),
      total_amount: money(data.payable_amount),
      creator_name: employee?.label || '-',
      remark: data.remark || ''
    }
  })
}

onMounted(async () => {
  await loadOptions()
  await loadList()
})
</script>

<template>
  <ContentWrap>
    <div class="toolbar">
      <el-input
        v-model="query.keyword"
        placeholder="单据号"
        clearable
        class="search-item"
        @keyup.enter="loadList"
      />
      <el-select
        v-model="query.customer_id"
        placeholder="客户"
        clearable
        filterable
        class="search-item"
      >
        <el-option
          v-for="item in options.customers"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <el-select v-model="query.status" placeholder="状态" clearable class="search-item small">
        <el-option v-for="(item, key) in statusMap" :key="key" :label="item.label" :value="key" />
      </el-select>
      <el-button type="primary" @click="searchList">查询</el-button>
      <el-button @click="resetQuery">重置</el-button>
      <el-button type="success" @click="openCreate">新增{{ title }}</el-button>
    </div>

    <el-table v-loading="loading" :data="rows" border stripe>
      <el-table-column prop="document_no" label="单据号" min-width="170" />
      <el-table-column prop="business_date" label="业务日期" width="115" />
      <el-table-column prop="customer_name" label="客户" min-width="160" />
      <el-table-column prop="total_quantity" label="基本数量" width="110" align="right" />
      <el-table-column prop="payable_amount" label="价税合计" width="120" align="right">
        <template #default="scope">¥ {{ money(scope.row.payable_amount) }}</template>
      </el-table-column>
      <el-table-column v-if="isDelivery" label="本单现收" width="115" align="right">
        <template #default="scope">¥ {{ money(scope.row.current_payment_amount) }}</template>
      </el-table-column>
      <el-table-column
        v-if="isDelivery || isReturn"
        prop="total_cost"
        label="成本"
        width="110"
        align="right"
      >
        <template #default="scope">¥ {{ money(scope.row.total_cost) }}</template>
      </el-table-column>
      <el-table-column v-if="isDelivery" prop="gross_profit" label="毛利" width="110" align="right">
        <template #default="scope">¥ {{ money(scope.row.gross_profit) }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100" align="center">
        <template #default="scope"
          ><el-tag :type="statusMap[scope.row.status]?.type">{{
            statusMap[scope.row.status]?.label || scope.row.status
          }}</el-tag></template
        >
      </el-table-column>
      <el-table-column label="操作" width="310" fixed="right">
        <template #default="scope">
          <el-button
            link
            type="primary"
            @click="openDocument(scope.row, scope.row.status !== 'draft')"
            >{{ scope.row.status === 'draft' ? '编辑' : '查看' }}</el-button
          >
          <el-button link type="success" @click="printDocument(scope.row)">打印</el-button>
          <el-button
            v-if="scope.row.status === 'draft'"
            link
            type="success"
            @click="approve(scope.row)"
            >审核</el-button
          >
          <el-button v-else link type="warning" @click="unapprove(scope.row)">反审核</el-button>
          <el-button
            v-if="scope.row.status === 'draft'"
            link
            type="danger"
            @click="remove(scope.row)"
            >删除</el-button
          >
        </template>
      </el-table-column>
    </el-table>
    <el-pagination
      v-model:current-page="query.page"
      v-model:page-size="query.limit"
      :total="total"
      layout="total, sizes, prev, pager, next"
      class="pager"
      @change="loadList"
    />
  </ContentWrap>

  <el-dialog
    v-model="dialogVisible"
    :title="`${editingId ? (readonly ? '查看' : '编辑') : '新增'}${title}`"
    fullscreen
    class="erp-document-dialog"
    destroy-on-close
    @keydown.enter="productEntry.preventDocumentEnter"
  >
    <el-form label-width="90px" :disabled="readonly" class="erp-document-header">
      <el-row :gutter="16">
        <el-col :span="6"
          ><el-form-item label="客户" required
            ><el-select v-model="form.customer_id" filterable class="full" @change="changeCustomer"
              ><el-option
                v-for="item in options.customers"
                :key="item.value"
                :label="item.label"
                :value="item.value" /></el-select></el-form-item
        ></el-col>
        <el-col :span="6"
          ><el-form-item label="业务日期" required
            ><el-date-picker
              v-model="form.business_date"
              value-format="YYYY-MM-DD"
              class="full" /></el-form-item
        ></el-col>
        <el-col :span="6"
          ><el-form-item label="仓库" required
            ><el-select v-model="form.warehouse_id" filterable class="full" @change="loadProducts()"
              ><el-option
                v-for="item in options.warehouses"
                :key="item.value"
                :label="item.label"
                :value="item.value" /></el-select></el-form-item
        ></el-col>
        <el-col :span="6"
          ><el-form-item label="业务员"
            ><el-select v-model="form.employee_id" clearable filterable class="full"
              ><el-option
                v-for="item in options.employees"
                :key="item.value"
                :label="item.label"
                :value="item.value" /></el-select></el-form-item
        ></el-col>
        <el-col v-if="isDelivery" :span="8"
          ><el-form-item label="来源订单"
            ><el-select
              v-model="form.order_id"
              clearable
              filterable
              :loading="sourceLoading"
              class="full"
              @visible-change="(v) => v && loadSources()"
              @change="selectSource"
              ><el-option
                v-for="item in sourceDocuments"
                :key="item.id"
                :label="`${item.order_no} / ¥${money(item.payable_amount)}`"
                :value="item.id" /></el-select></el-form-item
        ></el-col>
        <el-col v-if="isReturn" :span="8"
          ><el-form-item label="原出库单" required
            ><el-select
              v-model="form.delivery_id"
              filterable
              :loading="sourceLoading"
              class="full"
              @visible-change="(v) => v && loadSources()"
              @change="selectSource"
              ><el-option
                v-for="item in sourceDocuments"
                :key="item.id"
                :label="`${item.delivery_no} / ¥${money(item.payable_amount)}`"
                :value="item.id" /></el-select></el-form-item
        ></el-col>
        <el-col v-if="isOrder" :span="6"
          ><el-form-item label="预计交期"
            ><el-date-picker
              v-model="form.expected_delivery_date"
              value-format="YYYY-MM-DD"
              class="full" /></el-form-item
        ></el-col>
        <el-col v-if="isDelivery" :span="6"
          ><el-form-item label="到期日"
            ><el-date-picker
              v-model="form.due_date"
              value-format="YYYY-MM-DD"
              class="full" /></el-form-item
        ></el-col>
        <el-col v-if="isDelivery" :span="8">
          <el-form-item label="出库批次">
            <el-radio-group v-model="form.batch_selection_mode" :disabled="readonly">
              <el-radio-button value="auto">自动分配</el-radio-button>
              <el-radio-button value="manual">手动选择</el-radio-button>
            </el-radio-group>
          </el-form-item>
        </el-col>
        <el-col v-if="!isReturn" :span="10"
          ><el-form-item label="送货地址"><el-input v-model="form.delivery_address" /></el-form-item
        ></el-col>
      </el-row>
    </el-form>

    <div
      v-if="!readonly && canAddProducts && productEntry.scanMode.value"
      class="document-scan-bar"
    >
      <span class="scan-label">扫码录入</span>
      <el-input
        :ref="(instance) => (productEntry.scanInput.value = instance)"
        v-model="productEntry.scanCode.value"
        placeholder="扫描条码或输入 SKU 编码后回车；重复扫描自动累加数量"
        clearable
        @keyup.enter="productEntry.scanProduct"
      />
      <el-button type="primary" @click="productEntry.scanProduct">录入</el-button>
      <span class="scan-tip">支持 SKU 编码、条码精确识别</span>
    </div>

    <div class="erp-document-table-wrap">
      <el-table :data="form.lines" border class="erp-document-table">
        <el-table-column width="54" fixed="left" align="center">
          <template #default="scope">
            <template v-if="canAddProducts && !readonly">
              <el-button link type="primary" class="line-button" @click="addLine(scope.$index)"
                >＋</el-button
              >
              <el-button link type="danger" class="line-button" @click="removeLine(scope.$index)"
                >－</el-button
              >
            </template>
            <span v-else>{{ scope.$index + 1 }}</span>
          </template>
        </el-table-column>
        <el-table-column min-width="260" fixed="left">
          <template #header>
            <div class="document-product-column-title">
              <span><i>*</i> 商品</span>
              <span v-if="canAddProducts && !readonly" class="scan-switch">
                --扫码枪录入
                <el-switch v-model="productEntry.scanMode.value" size="small" />
              </span>
            </div>
          </template>
          <template #default="scope">
            <div v-if="readonly || !canAddProducts" class="document-display-cell">
              {{ productLabel(scope.row) }}
            </div>
            <div
              v-else
              class="document-entry-cell"
              :class="{
                'is-active':
                  productEntry.activeCell.rowKey === scope.row.key &&
                  productEntry.activeCell.column === 'product'
              }"
              :data-entry-cell="`${scope.row.key}-product`"
            >
              <DocumentProductSelect
                v-model="scope.row.product_id"
                :line-key="scope.row.key"
                :row-index="scope.$index"
                :products="productEntry.productOptions.value"
                :loading="productEntry.productLoading.value"
                :scan-mode="productEntry.scanMode.value"
                @search="productEntry.loadProducts"
                @change="productEntry.chooseProduct(scope.row, $event)"
                @picker="productEntry.openPicker(scope.row)"
                @move="productEntry.moveCell(scope.row, scope.$index, 'product', $event)"
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column label="规格型号" width="110" show-overflow-tooltip>
          <template #default="scope">
            <div class="document-display-cell">{{ skuSpec(scope.row.product) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="可用库存" width="88" align="right"
          ><template #default="scope"
            ><div class="document-display-cell number-cell">{{
              scope.row.product?.available_quantity ?? '-'
            }}</div></template
          ></el-table-column
        >
        <el-table-column label="商品单位" width="95">
          <template #default="scope">
            <div
              class="document-entry-cell"
              :data-entry-cell="`${scope.row.key}-unit`"
              @keydown="productEntry.handleCellKeydown($event, scope.row, scope.$index, 'unit')"
              ><el-select
                v-model="scope.row.unit_id"
                :disabled="readonly"
                class="full"
                @change="changeUnit(scope.row)"
                ><el-option
                  v-for="unit in scope.row.product?.units || []"
                  :key="unit.unit_id"
                  :label="unit.unit_name"
                  :value="unit.unit_id" /></el-select></div
          ></template>
        </el-table-column>
        <el-table-column label="仓库" width="120">
          <template #default="scope">
            <div
              class="document-entry-cell"
              :data-entry-cell="`${scope.row.key}-warehouse`"
              @keydown="
                productEntry.handleCellKeydown($event, scope.row, scope.$index, 'warehouse')
              "
            >
              <el-select v-model="scope.row.warehouse_id" filterable :disabled="readonly">
                <el-option
                  v-for="item in options.warehouses"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="数量 *" width="100"
          ><template #default="scope">
            <div
              class="document-entry-cell"
              :data-entry-cell="`${scope.row.key}-quantity`"
              @keydown="productEntry.handleCellKeydown($event, scope.row, scope.$index, 'quantity')"
              ><el-input-number
                v-model="scope.row.quantity"
                :disabled="readonly"
                :min="0.000001"
                :precision="6"
                :controls="false"
                class="full" /></div></template
        ></el-table-column>
        <el-table-column v-if="!isReturn" label="销售单价" width="110"
          ><template #default="scope">
            <div
              class="document-entry-cell"
              :data-entry-cell="`${scope.row.key}-unit_price`"
              @keydown="
                productEntry.handleCellKeydown($event, scope.row, scope.$index, 'unit_price')
              "
              ><el-input-number
                v-model="scope.row.unit_price"
                :disabled="readonly"
                :min="0"
                :precision="4"
                :controls="false"
                class="full" /></div></template
        ></el-table-column>
        <el-table-column v-if="!isReturn" label="折扣%" width="95"
          ><template #default="scope">
            <div
              class="document-entry-cell"
              :data-entry-cell="`${scope.row.key}-discount_rate`"
              @keydown="
                productEntry.handleCellKeydown($event, scope.row, scope.$index, 'discount_rate')
              "
              ><el-input-number
                v-model="scope.row.discount_rate"
                :disabled="readonly"
                :min="0"
                :max="100"
                :controls="false"
                class="full" /></div></template
        ></el-table-column>
        <el-table-column v-if="!isReturn" label="税率%" width="90"
          ><template #default="scope">
            <div
              class="document-entry-cell"
              :data-entry-cell="`${scope.row.key}-tax_rate`"
              @keydown="productEntry.handleCellKeydown($event, scope.row, scope.$index, 'tax_rate')"
              ><el-input-number
                v-model="scope.row.tax_rate"
                :disabled="readonly"
                :min="0"
                :max="100"
                :controls="false"
                class="full" /></div></template
        ></el-table-column>
        <el-table-column v-if="!isReturn" label="销售金额" width="100" align="right"
          ><template #default="scope"
            ><div class="document-display-cell number-cell">{{
              money(lineAmount(scope.row))
            }}</div></template
          ></el-table-column
        >
        <el-table-column label="基本数量" width="95" align="right">
          <template #default="scope">
            <div class="document-display-cell number-cell">{{
              baseQuantity(scope.row)
                .toFixed(6)
                .replace(/\.?0+$/, '')
            }}</div>
          </template>
        </el-table-column>
        <el-table-column v-if="!isOrder" label="批次号" width="110"
          ><template #default="scope">
            <div
              class="document-entry-cell"
              :class="{ 'is-disabled': !scope.row.product?.batch_enabled }"
              :data-entry-cell="`${scope.row.key}-batch_no`"
              @keydown="productEntry.handleCellKeydown($event, scope.row, scope.$index, 'batch_no')"
              ><el-input
                v-model="scope.row.batch_no"
                :placeholder="
                  isDelivery && form.batch_selection_mode === 'auto' ? '保存时自动分配' : ''
                "
                :disabled="
                  readonly ||
                  !scope.row.product?.batch_enabled ||
                  (isDelivery && form.batch_selection_mode === 'auto')
                " /></div></template
        ></el-table-column>
        <el-table-column v-if="!isOrder" label="序列号" width="110"
          ><template #default="scope">
            <div
              class="document-entry-cell"
              :class="{ 'is-disabled': !scope.row.product?.serial_enabled }"
              :data-entry-cell="`${scope.row.key}-serial`"
              @keydown="productEntry.handleCellKeydown($event, scope.row, scope.$index, 'serial')"
              ><DocumentSerialEditor
                v-if="scope.row.product?.serial_enabled"
                :model-value="serialValues(scope.row.serialText)"
                :disabled="readonly"
                @update:model-value="changeSerials(scope.row, $event)"
              /><span v-else>不管理</span></div
            ></template
          ></el-table-column
        >
      </el-table>
    </div>
    <div class="document-summary-bar">
      <div
        ><label>商品行数：</label><span>{{ productLineCount }}</span></div
      >
      <div
        ><label>商品数量：</label
        ><span>{{ quantityTotal.toFixed(6).replace(/\.?0+$/, '') }}</span></div
      >
      <div class="summary-total"
        ><label>价税合计：</label><span>¥ {{ money(taxInclusiveTotal) }}</span></div
      >
    </div>
    <DocumentPayment
      v-if="isDelivery"
      :model-value="form"
      :total="taxInclusiveTotal"
      direction="receipt"
      :accounts="options.accounts"
      :settlement-methods="options.settlement_methods"
      :disabled="readonly"
      @update:model-value="Object.assign(form, $event)"
    />
    <el-input
      v-model="form.remark"
      class="document-remark"
      type="textarea"
      :rows="2"
      :disabled="readonly"
      placeholder="备注信息"
    />
    <template #footer
      ><el-button @click="dialogVisible = false">关闭</el-button
      ><el-button v-if="editingId" type="success" @click="printDocument({ id: editingId })"
        >打印</el-button
      >
      ><el-button v-if="!readonly" type="primary" :loading="saving" @click="save"
        >保存草稿</el-button
      ></template
    >
  </el-dialog>
  <DocumentProductPicker
    v-model="productEntry.pickerVisible.value"
    v-model:keyword="productEntry.pickerKeyword.value"
    :rows="productEntry.pickerRows.value"
    :loading="productEntry.pickerLoading.value"
    price-field="default_sale_price"
    price-label="参考售价"
    @search="productEntry.searchPicker"
    @confirm="productEntry.applyPickedProducts"
  />
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.search-item {
  width: 220px;
}
.search-item.small {
  width: 130px;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
.full {
  width: 100%;
}
</style>
