<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ContentWrap } from '@/components/ContentWrap'
import DocumentPayment from '@/components/Erp/DocumentPayment.vue'
import DocumentProductPicker from '@/components/Erp/DocumentProductPicker.vue'
import DocumentProductSelect from '@/components/Erp/DocumentProductSelect.vue'
import DocumentSerialEditor from '@/components/Erp/DocumentSerialEditor.vue'
import { useDocumentProductEntry } from '@/hooks/erp/useDocumentProductEntry'
import { skuSpec } from '@/utils/erp/product'
import { documentProductName, documentUnitName, printBusinessDocument } from '@/utils/erp/printing'
import '@/styles/erp-document.css'
import {
  addPurchaseDocumentApi,
  approvePurchaseDocumentApi,
  delPurchaseDocumentApi,
  getPurchaseDocumentApi,
  getPurchaseDocumentListApi,
  getPurchaseOptionsApi,
  getPurchaseSourceOrdersApi,
  getPurchaseSourceReceiptsApi,
  putPurchaseDocumentApi,
  searchPurchaseProductsApi,
  type PurchaseDocumentKind,
  unapprovePurchaseDocumentApi
} from '@/api/erp/purchase'

const props = defineProps<{ kind: PurchaseDocumentKind; title: string }>()
const route = useRoute()
const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const visible = ref(false)
const readonly = ref(false)
const rows = ref<any[]>([])
const total = ref(0)
const sources = ref<any[]>([])
const editingId = ref<number>()
const options = reactive<any>({ suppliers: [], warehouses: [], employees: [] })
const query = reactive({ page: 1, limit: 20, keyword: '', status: '', supplier_id: undefined })
let key = 0
const form = reactive<any>({
  business_date: dayjs().format('YYYY-MM-DD'),
  expected_receipt_date: '',
  due_date: '',
  supplier_id: undefined,
  warehouse_id: undefined,
  employee_id: undefined,
  order_id: undefined,
  receipt_id: undefined,
  status: undefined,
  settlement_discount_rate: 100,
  rounding_amount: 0,
  current_payment_amount: 0,
  settlement_method_id: undefined,
  fund_account_id: undefined,
  remark: '',
  lines: []
})

const isOrder = computed(() => props.kind === 'orders')
const isReceipt = computed(() => props.kind === 'receipts')
const isReturn = computed(() => props.kind === 'returns')
const numberField = computed(() =>
  isOrder.value ? 'order_no' : isReceipt.value ? 'receipt_no' : 'return_no'
)
const statusMap: any = {
  draft: ['草稿', 'info'],
  approved: ['已审核', 'success'],
  partial: ['部分收货', 'warning'],
  completed: ['已完成', 'success']
}
const money = (value: any) => Number(value || 0).toFixed(2)
const serialValues = (value: string) =>
  String(value || '')
    .split(/[,，\n\s]+/)
    .filter(Boolean)
const changeSerials = (line: any, values: string[]) => {
  line.serialText = values.join(',')
  line.quantity = values.length
}
const amountTotal = computed(() =>
  form.lines.reduce(
    (sum: number, line: any) =>
      sum +
      Number(line.quantity || 0) *
        Number(line.unit_price || 0) *
        (1 + Number(line.tax_rate || 0) / 100),
    0
  )
)
const productLineCount = computed(() => form.lines.filter((line: any) => line.product_id).length)
const quantityTotal = computed(() =>
  form.lines.reduce((sum: number, line: any) => sum + Number(line.quantity || 0), 0)
)
const units = (line: any) => line.product?.units || []
const selectedUnit = (line: any) => units(line).find((item: any) => item.unit_id === line.unit_id)
const lineAmount = (line: any) => Number(line.quantity || 0) * Number(line.unit_price || 0)
const baseQuantity = (line: any) =>
  Number(line.quantity || 0) * Number(selectedUnit(line)?.to_base_rate || 1)
/** 切换多单位时按换算率同步采购单价。 */
const changeUnit = (line: any) => {
  const unit = units(line).find((item: any) => item.unit_id === line.unit_id)
  if (line.product && unit)
    line.unit_price = Number(
      (Number(line.product.default_purchase_price || 0) * Number(unit.to_base_rate || 1)).toFixed(6)
    )
}
/** 批次商品填写生产日期后按保质期自动计算有效期。 */
const changeProductionDate = (line: any) => {
  if (line.production_date && line.product?.shelf_life_days !== undefined)
    line.expiry_date = dayjs(line.production_date)
      .add(Number(line.product.shelf_life_days || 0), 'day')
      .format('YYYY-MM-DD')
}

/** 创建采购商品空白行。 */
const emptyLine = () => ({
  key: ++key,
  product_id: undefined,
  warehouse_id: form.warehouse_id,
  unit_id: undefined,
  quantity: 1,
  unit_price: 0,
  tax_rate: 0,
  batch_no: '',
  production_date: '',
  expiry_date: '',
  serialText: '',
  remark: ''
})

/** 新单据按入库单习惯预置四行空白商品。 */
const defaultLines = () => Array.from({ length: 4 }, () => emptyLine())

/** 在当前商品行下方插入一行。 */
const addLineAfter = (index: number) => form.lines.splice(index + 1, 0, emptyLine())

/** 删除当前商品行；只剩一行时用空白行替换。 */
const removeLine = (index: number) => {
  if (form.lines.length === 1) form.lines.splice(0, 1, emptyLine())
  else form.lines.splice(index, 1)
}

const canAddProducts = computed(() => isOrder.value || (isReceipt.value && !form.order_id))

/** 调用采购商品目录并返回可直接用于扫码和多选的 SKU。 */
const searchProducts = async (keyword = '') => {
  const res = await searchPurchaseProductsApi({
    keyword: keyword || undefined,
    warehouse_id: form.warehouse_id,
    limit: 100
  })
  return res.data || []
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
    'tax_rate',
    'batch_no',
    'production_date',
    'expiry_date',
    'serial'
  ],
  columnAvailable: (line, column) => {
    if (['batch_no', 'production_date', 'expiry_date'].includes(column))
      return !isOrder.value && !!line.product?.batch_enabled
    if (column === 'serial') return !isOrder.value && !!line.product?.serial_enabled
    return true
  },
  applyProduct: (line, product) => {
    line.product = product
    line.product_id = product.id
    line.warehouse_id ||= form.warehouse_id
    line.unit_id = product.base_unit_id
    line.unit_price = Number(product.default_purchase_price || 0)
    line.tax_rate = Number(product.tax_rate || 0)
    line.quantity = Number(line.quantity || 1)
  }
})

/** 加载当前采购单据列表。 */
const loadList = async () => {
  loading.value = true
  try {
    const res = await getPurchaseDocumentListApi(props.kind, query)
    rows.value = res.data || []
    total.value = res.count || 0
  } finally {
    loading.value = false
  }
}

/** 加载采购基础资料。 */
const loadOptions = async () => {
  const res = await getPurchaseOptionsApi()
  Object.assign(options, res.data || {})
}

const loadProducts = productEntry.loadProducts

/** 重置采购单据编辑上下文。 */
const reset = () => {
  editingId.value = undefined
  readonly.value = false
  Object.assign(form, {
    business_date: dayjs().format('YYYY-MM-DD'),
    expected_receipt_date: '',
    due_date: '',
    supplier_id: undefined,
    warehouse_id: options.warehouses[0]?.value,
    employee_id: undefined,
    order_id: undefined,
    receipt_id: undefined,
    status: undefined,
    settlement_discount_rate: 100,
    rounding_amount: 0,
    current_payment_amount: 0,
    settlement_method_id: undefined,
    fund_account_id: undefined,
    remark: '',
    lines: []
  })
  if (!isReturn.value) form.lines = defaultLines()
  sources.value = []
}

/** 打开新增采购单据。 */
const create = async () => {
  reset()
  visible.value = true
  await loadProducts()
}

/** 从采购订单进入采购入库页面，并让目标页面自动加载该订单的未收明细。 */
const createReceiptFromOrder = async (row: any) => {
  const receiptPath = route.path.replace(/purchase-orders\/?$/, 'purchase-receipts')
  await router.push({
    path: receiptPath,
    query: { order_id: String(row.id) }
  })
}

/** 按供应商读取可收货订单或可退货收货单。 */
const loadSources = async () => {
  sources.value = []
  form.order_id = undefined
  form.receipt_id = undefined
  if (!form.supplier_id || isOrder.value) return
  const res = isReceipt.value
    ? await getPurchaseSourceOrdersApi({ supplier_id: form.supplier_id })
    : await getPurchaseSourceReceiptsApi({ supplier_id: form.supplier_id })
  sources.value = res.data || []
}

/** 将来源单据未履约明细带入当前单据。 */
const chooseSource = () => {
  const sourceId = isReceipt.value ? form.order_id : form.receipt_id
  const source = sources.value.find((item) => item.id === sourceId)
  if (!source) {
    if (isReceipt.value) form.lines = defaultLines()
    return
  }
  form.warehouse_id = source.warehouse_id
  form.lines = (source.lines || []).map((line: any) => {
    const catalogProduct = productEntry.productOptions.value.find(
      (product) => product.id === line.product_id
    )
    const item = catalogProduct ? { ...line.product, ...catalogProduct } : line.product
    const baseQuantity = Number(
      isReceipt.value ? line.remaining_quantity : line.returnable_quantity
    )
    const rate = Number(line.unit_to_base_rate || 1)
    return {
      ...line,
      key: ++key,
      product: item,
      order_line_id: isReceipt.value ? line.id : undefined,
      receipt_line_id: isReturn.value ? line.id : undefined,
      quantity: baseQuantity / rate,
      unit_price: Number(line.unit_price || 0),
      tax_rate: Number(line.tax_rate || 0),
      serialText: isReturn.value ? (line.serial_numbers || []).join('\n') : '',
      production_date: isReturn.value ? '' : line.production_date || '',
      expiry_date: isReturn.value ? '' : line.expiry_date || ''
    }
  })
}

/** 根据路由中的订单编号直接打开采购入库开单弹框。 */
const openReceiptFromRoute = async () => {
  if (!isReceipt.value) return
  const rawOrderId = Array.isArray(route.query.order_id)
    ? route.query.order_id[0]
    : route.query.order_id
  const orderId = Number(rawOrderId)
  if (!Number.isInteger(orderId) || orderId <= 0) return

  reset()
  const res = await getPurchaseSourceOrdersApi()
  sources.value = res.data || []
  const source = sources.value.find((item) => item.id === orderId)
  if (!source) {
    ElMessage.warning('该采购订单不存在、尚未审核或已经全部入库')
    await router.replace({ path: route.path })
    return
  }

  form.supplier_id = source.supplier_id
  form.warehouse_id = source.warehouse_id
  form.order_id = source.id
  await loadProducts()
  chooseSource()
  visible.value = true
  await router.replace({ path: route.path })
}

/** 打开已有采购单据详情。 */
const open = async (row: any) => {
  reset()
  const res = await getPurchaseDocumentApi(props.kind, row.id)
  Object.assign(form, res.data)
  editingId.value = row.id
  readonly.value = row.status !== 'draft'
  form.lines = (res.data.lines || []).map((line: any) => ({
    ...line,
    key: ++key,
    product: line.product,
    quantity: Number(line.quantity),
    unit_price: Number(line.unit_price),
    tax_rate: Number(line.tax_rate),
    serialText: (line.serial_numbers || []).join('\n')
  }))
  await loadProducts()
  if (isReceipt.value && form.order_id) {
    const sourceRes = await getPurchaseSourceOrdersApi({ supplier_id: form.supplier_id })
    sources.value = sourceRes.data || []
    if (!sources.value.some((item) => item.id === form.order_id)) {
      sources.value.unshift({
        id: form.order_id,
        order_no: res.data.order_no || `订单 #${form.order_id}`,
        payable_amount: res.data.payable_amount
      })
    }
  } else if (isReturn.value && form.receipt_id) {
    const sourceRes = await getPurchaseSourceReceiptsApi({ supplier_id: form.supplier_id })
    sources.value = sourceRes.data || []
    if (!sources.value.some((item) => item.id === form.receipt_id)) {
      sources.value.unshift({
        id: form.receipt_id,
        receipt_no: res.data.receipt_no || `收货单 #${form.receipt_id}`,
        payable_amount: res.data.payable_amount
      })
    }
  }
  visible.value = true
}

/** 生成后端采购单据输入。 */
const payload = () => {
  const common: any = {
    business_date: form.business_date,
    supplier_id: form.supplier_id,
    warehouse_id: form.warehouse_id,
    employee_id: form.employee_id || null,
    remark: form.remark || null,
    lines: form.lines
      .filter((line: any) => line.product_id)
      .map((line: any) => ({
        product_id: line.product_id,
        warehouse_id: line.warehouse_id || form.warehouse_id,
        unit_id: line.unit_id,
        quantity: Number(line.quantity),
        unit_price: Number(line.unit_price || 0),
        tax_rate: Number(line.tax_rate || 0),
        order_line_id: line.order_line_id || null,
        receipt_line_id: line.receipt_line_id || null,
        batch_no: line.batch_no || null,
        production_date: line.production_date || null,
        expiry_date: line.expiry_date || null,
        serial_numbers: String(line.serialText || '')
          .split(/[,，\n]/)
          .map((x) => x.trim())
          .filter(Boolean),
        remark: line.remark || null
      }))
  }
  if (isOrder.value) common.expected_receipt_date = form.expected_receipt_date || null
  if (isReceipt.value)
    Object.assign(common, {
      order_id: form.order_id || null,
      due_date: form.due_date || null,
      settlement_discount_rate: Number(form.settlement_discount_rate ?? 100),
      rounding_amount: Number(form.rounding_amount || 0),
      current_payment_amount: Number(form.current_payment_amount || 0),
      settlement_method_id: form.settlement_method_id || null,
      fund_account_id: form.fund_account_id || null
    })
  if (isReturn.value) common.receipt_id = form.receipt_id
  return common
}

/** 保存采购单据草稿。 */
const save = async () => {
  const enteredLines = form.lines.filter((line: any) => line.product_id)
  if (!form.business_date || !form.supplier_id || !form.warehouse_id || !enteredLines.length)
    return ElMessage.warning('请完整填写采购单据表头和明细')
  if (isReturn.value && !form.receipt_id) return ElMessage.warning('采购退货必须选择原收货单')
  if (isReceipt.value && Number(form.current_payment_amount || 0) > 0 && !form.fund_account_id)
    return ElMessage.warning('填写本次付款后必须选择付款账号')
  if (enteredLines.some((line: any) => !line.unit_id || Number(line.quantity) <= 0))
    return ElMessage.warning('请完整填写商品明细')
  saving.value = true
  try {
    editingId.value
      ? await putPurchaseDocumentApi(props.kind, editingId.value, payload())
      : await addPurchaseDocumentApi(props.kind, payload())
    ElMessage.success('保存成功')
    visible.value = false
    await loadList()
  } finally {
    saving.value = false
  }
}

/** 审核或反审核采购单据及其下游余额。 */
const action = async (row: any, approve: boolean) => {
  const label = approve ? '审核' : '反审核'
  await ElMessageBox.confirm(`确定${label} ${row[numberField.value]} 吗？`, `${label}确认`, {
    type: 'warning'
  })
  approve
    ? await approvePurchaseDocumentApi(props.kind, row.id)
    : await unapprovePurchaseDocumentApi(props.kind, row.id)
  ElMessage.success(`${label}成功`)
  await loadList()
}

/** 删除采购单据草稿。 */
const remove = async (row: any) => {
  await ElMessageBox.confirm(`确定删除 ${row[numberField.value]} 吗？`, '删除确认', {
    type: 'warning'
  })
  await delPurchaseDocumentApi(props.kind, [row.id])
  await loadList()
}

/** 使用最新数据库详情生成采购单据打印内容。 */
const printDocument = async (row: any) => {
  const businessType = {
    orders: 'purchase_order',
    receipts: 'purchase_receipt',
    returns: 'purchase_return'
  }[props.kind]
  await printBusinessDocument(businessType, async () => {
    const res = await getPurchaseDocumentApi(props.kind, row.id)
    const data = res.data
    const partner = options.suppliers.find((item: any) => item.value === data.supplier_id)
    const employee = options.employees.find((item: any) => item.value === data.employee_id)
    return {
      title: props.title,
      document_no: data[numberField.value],
      document_date: data.business_date,
      partner_name: partner?.label || `供应商 #${data.supplier_id}`,
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
  await openReceiptFromRoute()
})
</script>

<template>
  <ContentWrap>
    <div class="toolbar">
      <el-input v-model="query.keyword" placeholder="单据号" clearable />
      <el-select v-model="query.supplier_id" placeholder="供应商" filterable clearable
        ><el-option v-for="item in options.suppliers" :key="item.value" v-bind="item"
      /></el-select>
      <el-select v-model="query.status" placeholder="状态" clearable
        ><el-option label="草稿" value="draft" /><el-option
          label="已审核"
          value="approved" /><el-option v-if="isOrder" label="部分收货" value="partial" /><el-option
          v-if="isOrder"
          label="已完成"
          value="completed"
      /></el-select>
      <el-button type="primary" @click="loadList">查询</el-button
      ><el-button type="success" @click="create">新增{{ title }}</el-button>
    </div>
    <el-table v-loading="loading" :data="rows" border stripe>
      <el-table-column :prop="numberField" label="单据号" min-width="175" />
      <el-table-column prop="business_date" label="业务日期" width="115" />
      <el-table-column prop="supplier_name" label="供应商" min-width="180" />
      <el-table-column
        v-if="isReceipt || isReturn"
        prop="source_document_no"
        :label="isReceipt ? '来源采购订单' : '来源采购入库'"
        min-width="175"
      />
      <el-table-column prop="total_quantity" label="主单位数量" width="120" align="right" />
      <el-table-column label="价税合计" width="125" align="right"
        ><template #default="scope"
          >¥ {{ money(scope.row.payable_amount) }}</template
        ></el-table-column
      >
      <el-table-column v-if="isReceipt" label="本单现付" width="115" align="right">
        <template #default="scope">¥ {{ money(scope.row.current_payment_amount) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100"
        ><template #default="scope"
          ><el-tag :type="statusMap[scope.row.status]?.[1]">{{
            statusMap[scope.row.status]?.[0] || scope.row.status
          }}</el-tag></template
        ></el-table-column
      >
      <el-table-column label="操作" width="340" fixed="right"
        ><template #default="scope">
          <el-button link type="primary" @click="open(scope.row)">{{
            scope.row.status === 'draft' ? '编辑' : '查看'
          }}</el-button>
          <el-button link type="success" @click="printDocument(scope.row)">打印</el-button>
          <el-button
            v-if="scope.row.status === 'draft'"
            link
            type="success"
            @click="action(scope.row, true)"
            >审核</el-button
          >
          <el-button
            v-else-if="scope.row.status === 'approved'"
            link
            type="warning"
            @click="action(scope.row, false)"
            >反审核</el-button
          >
          <el-button
            v-if="isOrder && ['approved', 'partial'].includes(scope.row.status)"
            link
            type="primary"
            @click="createReceiptFromOrder(scope.row)"
            >入库</el-button
          >
          <el-button
            v-if="scope.row.status === 'draft'"
            link
            type="danger"
            @click="remove(scope.row)"
            >删除</el-button
          >
        </template></el-table-column
      >
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
    v-model="visible"
    :title="title"
    fullscreen
    destroy-on-close
    class="erp-document-dialog"
    @keydown.enter="productEntry.preventDocumentEnter"
  >
    <el-form label-width="90px" :disabled="readonly" class="erp-document-header">
      <el-row :gutter="16">
        <el-col :span="5"
          ><el-form-item label="业务日期"
            ><el-date-picker v-model="form.business_date" value-format="YYYY-MM-DD" /></el-form-item
        ></el-col>
        <el-col :span="7"
          ><el-form-item label="供应商"
            ><el-select
              v-model="form.supplier_id"
              filterable
              style="width: 100%"
              :disabled="!!editingId"
              @change="loadSources"
              ><el-option
                v-for="item in options.suppliers"
                :key="item.value"
                v-bind="item" /></el-select></el-form-item
        ></el-col>
        <el-col :span="6"
          ><el-form-item label="默认仓库"
            ><el-select v-model="form.warehouse_id" filterable style="width: 100%"
              ><el-option
                v-for="item in options.warehouses"
                :key="item.value"
                v-bind="item" /></el-select></el-form-item
        ></el-col>
        <el-col :span="6"
          ><el-form-item label="经办人"
            ><el-select v-model="form.employee_id" clearable filterable style="width: 100%"
              ><el-option
                v-for="item in options.employees"
                :key="item.value"
                v-bind="item" /></el-select></el-form-item
        ></el-col>
        <el-col v-if="isOrder" :span="6"
          ><el-form-item label="预计到货"
            ><el-date-picker
              v-model="form.expected_receipt_date"
              value-format="YYYY-MM-DD" /></el-form-item
        ></el-col>
        <el-col v-if="isReceipt" :span="8"
          ><el-form-item label="来源订单"
            ><el-select
              v-model="form.order_id"
              clearable
              filterable
              style="width: 100%"
              @change="chooseSource"
              ><el-option
                v-for="item in sources"
                :key="item.id"
                :label="`${item.order_no} / ¥${money(item.payable_amount)}`"
                :value="item.id" /></el-select></el-form-item
        ></el-col>
        <el-col v-if="isReceipt" :span="6"
          ><el-form-item label="应付日期"
            ><el-date-picker v-model="form.due_date" value-format="YYYY-MM-DD" /></el-form-item
        ></el-col>
        <el-col v-if="isReturn" :span="9"
          ><el-form-item label="原收货单"
            ><el-select
              v-model="form.receipt_id"
              filterable
              style="width: 100%"
              @change="chooseSource"
              ><el-option
                v-for="item in sources"
                :key="item.id"
                :label="`${item.receipt_no} / ¥${money(item.payable_amount)}`"
                :value="item.id" /></el-select></el-form-item
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
              <el-button link type="primary" class="line-button" @click="addLineAfter(scope.$index)"
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
            <div
              class="document-entry-cell"
              :class="{
                'is-active':
                  productEntry.activeCell.rowKey === scope.row.key &&
                  productEntry.activeCell.column === 'product'
              }"
              :data-entry-cell="`${scope.row.key}-product`"
              @focusin="
                Object.assign(productEntry.activeCell, { rowKey: scope.row.key, column: 'product' })
              "
            >
              <DocumentProductSelect
                v-model="scope.row.product_id"
                :line-key="scope.row.key"
                :row-index="scope.$index"
                :products="productEntry.productOptions.value"
                :loading="productEntry.productLoading.value"
                :disabled="readonly || !canAddProducts"
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
        <el-table-column label="商品单位" width="95"
          ><template #default="scope">
            <div
              class="document-entry-cell"
              :data-entry-cell="`${scope.row.key}-unit`"
              @keydown="productEntry.handleCellKeydown($event, scope.row, scope.$index, 'unit')"
              ><el-select
                v-model="scope.row.unit_id"
                :disabled="readonly || !canAddProducts"
                @change="changeUnit(scope.row)"
                ><el-option
                  v-for="item in units(scope.row)"
                  :key="item.unit_id"
                  :label="item.unit_name"
                  :value="item.unit_id" /></el-select></div></template
        ></el-table-column>
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
                <el-option v-for="item in options.warehouses" :key="item.value" v-bind="item" />
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
                :min="0.000001"
                :controls="false"
                :disabled="readonly" /></div></template
        ></el-table-column>
        <el-table-column label="采购单价" width="110"
          ><template #default="scope">
            <div
              class="document-entry-cell"
              :data-entry-cell="`${scope.row.key}-unit_price`"
              @keydown="
                productEntry.handleCellKeydown($event, scope.row, scope.$index, 'unit_price')
              "
              ><el-input-number
                v-model="scope.row.unit_price"
                :min="0"
                :controls="false"
                :disabled="readonly || isReturn" /></div></template
        ></el-table-column>
        <el-table-column label="税率%" width="90"
          ><template #default="scope">
            <div
              class="document-entry-cell"
              :data-entry-cell="`${scope.row.key}-tax_rate`"
              @keydown="productEntry.handleCellKeydown($event, scope.row, scope.$index, 'tax_rate')"
              ><el-input-number
                v-model="scope.row.tax_rate"
                :min="0"
                :max="100"
                :controls="false"
                :disabled="readonly || isReturn" /></div></template
        ></el-table-column>
        <el-table-column label="采购金额" width="100" align="right">
          <template #default="scope">
            <div class="document-display-cell number-cell">{{
              lineAmount(scope.row).toFixed(2)
            }}</div>
          </template>
        </el-table-column>
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
                v-if="scope.row.product?.batch_enabled"
                v-model="scope.row.batch_no"
                :disabled="readonly || isReturn"
              /><span v-else>-</span></div
            ></template
          ></el-table-column
        >
        <el-table-column v-if="isReceipt" label="生产日期" width="120"
          ><template #default="scope">
            <div
              class="document-entry-cell"
              :class="{ 'is-disabled': !scope.row.product?.batch_enabled }"
              :data-entry-cell="`${scope.row.key}-production_date`"
              @keydown="
                productEntry.handleCellKeydown($event, scope.row, scope.$index, 'production_date')
              "
              ><el-date-picker
                v-if="scope.row.product?.batch_enabled"
                v-model="scope.row.production_date"
                value-format="YYYY-MM-DD"
                :disabled="readonly"
                style="width: 100%"
                @change="changeProductionDate(scope.row)"
              /><span v-else>-</span></div
            ></template
          ></el-table-column
        >
        <el-table-column v-if="isReceipt" label="有效期至" width="120"
          ><template #default="scope">
            <div
              class="document-entry-cell"
              :class="{ 'is-disabled': !scope.row.product?.batch_enabled }"
              :data-entry-cell="`${scope.row.key}-expiry_date`"
              @keydown="
                productEntry.handleCellKeydown($event, scope.row, scope.$index, 'expiry_date')
              "
              ><el-date-picker
                v-if="scope.row.product?.batch_enabled"
                v-model="scope.row.expiry_date"
                value-format="YYYY-MM-DD"
                :disabled="readonly"
                style="width: 100%"
              /><span v-else>-</span></div
            ></template
          ></el-table-column
        >
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
        ><label>价税合计：</label><span>¥ {{ money(amountTotal) }}</span></div
      >
    </div>
    <DocumentPayment
      v-if="isReceipt"
      :model-value="form"
      :total="amountTotal"
      direction="payment"
      :accounts="options.accounts || []"
      :settlement-methods="options.settlement_methods || []"
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
      ><el-button @click="visible = false">关闭</el-button
      ><el-button v-if="editingId" type="success" @click="printDocument({ id: editingId })"
        >打印</el-button
      >
      ><el-button
        v-if="isOrder && readonly && ['approved', 'partial'].includes(form.status)"
        type="success"
        @click="createReceiptFromOrder(form)"
        >生成采购入库</el-button
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
    price-field="default_purchase_price"
    price-label="参考进价"
    @search="productEntry.searchPicker"
    @confirm="productEntry.applyPickedProducts"
  />
</template>

<style scoped>
.toolbar {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}
.toolbar .el-input,
.toolbar .el-select {
  width: 200px;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
