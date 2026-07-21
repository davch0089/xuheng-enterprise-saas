<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ContentWrap } from '@/components/ContentWrap'
import DocumentProductPicker from '@/components/Erp/DocumentProductPicker.vue'
import DocumentProductSelect from '@/components/Erp/DocumentProductSelect.vue'
import DocumentSerialEditor from '@/components/Erp/DocumentSerialEditor.vue'
import { useDocumentProductEntry } from '@/hooks/erp/useDocumentProductEntry'
import { skuSpec } from '@/utils/erp/product'
import '@/styles/erp-document.css'
import { getMasterOptionsApi } from '@/api/erp/master'
import {
  actionInventoryOperationApi,
  addInventoryOperationApi,
  delInventoryOperationApi,
  getInventoryOperationApi,
  getInventoryOperationListApi,
  putInventoryOperationApi,
  searchInboundProductsApi,
  type InventoryOperationKind
} from '@/api/erp/inventory'

const props = defineProps<{ kind: 'transfer' | 'other'; title: string }>()
const apiKind = computed<InventoryOperationKind>(() =>
  props.kind === 'transfer' ? 'transfers' : 'other-orders'
)
const loading = ref(false),
  saving = ref(false),
  visible = ref(false),
  readonly = ref(false)
const rows = ref<any[]>([]),
  total = ref(0)
const editingId = ref<number>(),
  query = reactive({ page: 1, limit: 20, keyword: '', status: '' })
const options = reactive<any>({ warehouses: [], employees: [] })
let key = 0
const form = reactive<any>({
  business_date: dayjs().format('YYYY-MM-DD'),
  transfer_date: dayjs().format('YYYY-MM-DD'),
  transfer_mode: 'one_step',
  direction: 'inbound',
  reason: '',
  warehouse_id: undefined,
  source_warehouse_id: undefined,
  destination_warehouse_id: undefined,
  employee_id: undefined,
  remark: '',
  lines: []
})
const statusMap: any = {
  draft: ['草稿', 'info'],
  in_transit: ['在途', 'warning'],
  completed: ['已完成', 'success'],
  approved: ['已审核', 'success']
}
const emptyLine = () => ({
  key: ++key,
  product_id: undefined,
  warehouse_id: props.kind === 'transfer' ? form.source_warehouse_id : form.warehouse_id,
  unit_id: undefined,
  quantity: 1,
  unit_price: 0,
  batch_no: '',
  serialText: '',
  remark: ''
})
/** 新单据按入库单习惯预置四行空白商品。 */
const defaultLines = () => Array.from({ length: 4 }, () => emptyLine())
/** 在当前商品行下方插入一行。 */
const addLineAfter = (index: number) => form.lines.splice(index + 1, 0, emptyLine())
/** 删除当前行；仅剩一行时保留一个新的空白行。 */
const removeLine = (index: number) => {
  if (form.lines.length === 1) form.lines.splice(0, 1, emptyLine())
  else form.lines.splice(index, 1)
}
const money = (v: any) => Number(v || 0).toFixed(2)
const serialValues = (value: string) =>
  String(value || '')
    .split(/[,，\n\s]+/)
    .filter(Boolean)
const changeSerials = (line: any, values: string[]) => {
  line.serialText = values.join(',')
  line.quantity = values.length
}
const productLineCount = computed(() => form.lines.filter((line: any) => line.product_id).length)
const quantityTotal = computed(() =>
  form.lines.reduce((sum: number, line: any) => sum + Number(line.quantity || 0), 0)
)
const amountTotal = computed(() =>
  form.lines.reduce(
    (sum: number, line: any) => sum + Number(line.quantity || 0) * Number(line.unit_price || 0),
    0
  )
)
const baseQuantity = (line: any) => {
  const unit = (line.product?.units || []).find((item: any) => item.unit_id === line.unit_id)
  return Number(line.quantity || 0) * Number(unit?.to_base_rate || 1)
}
/** 切换多单位时按换算率同步其他入库成本单价。 */
const changeUnit = (line: any) => {
  const unit = (line.product?.units || []).find((item: any) => item.unit_id === line.unit_id)
  if (line.product && unit && props.kind === 'other' && form.direction === 'inbound')
    line.unit_price = Number(
      (Number(line.product.default_purchase_price || 0) * Number(unit.to_base_rate || 1)).toFixed(6)
    )
}

const currentWarehouseId = () =>
  props.kind === 'transfer' ? form.source_warehouse_id : form.warehouse_id

/** 查询库存作业可选 SKU，并按当前调出仓或作业仓返回库存。 */
const searchProducts = async (keyword = '') => {
  const res = await searchInboundProductsApi({
    keyword: keyword || undefined,
    warehouse_id: currentWarehouseId(),
    limit: 100
  })
  return res.data || []
}

const productEntry = useDocumentProductEntry<any, any>({
  lines: () => form.lines,
  readonly,
  warehouseId: currentWarehouseId,
  createLine: emptyLine,
  search: searchProducts,
  navColumns: ['product', 'unit', 'quantity', 'unit_price', 'batch_no', 'serial'],
  columnAvailable: (line, column) => {
    if (column === 'unit_price') return props.kind === 'other' && form.direction === 'inbound'
    if (column === 'batch_no') return !!line.product?.batch_enabled
    if (column === 'serial') return !!line.product?.serial_enabled
    return true
  },
  applyProduct: (line, product) => {
    line.product = product
    line.product_id = product.id
    line.warehouse_id = currentWarehouseId()
    line.unit_id = product.base_unit_id
    line.unit_price = Number(product.default_purchase_price || 0)
    line.quantity = Number(line.quantity || 1)
    line.batch_no = ''
    line.serialText = ''
  }
})

/** 加载库存作业列表。 */
const loadList = async () => {
  loading.value = true
  try {
    const res = await getInventoryOperationListApi(apiKind.value, query)
    rows.value = res.data || []
    total.value = res.count || 0
  } finally {
    loading.value = false
  }
}
/** 加载商品及来源仓当前库存。 */
const loadProducts = async (keyword = '') => {
  await productEntry.loadProducts(keyword)
}
/** 重置库存作业表单。 */
const reset = () => {
  editingId.value = undefined
  readonly.value = false
  Object.assign(form, {
    business_date: dayjs().format('YYYY-MM-DD'),
    transfer_date: dayjs().format('YYYY-MM-DD'),
    transfer_mode: 'one_step',
    direction: 'inbound',
    reason: '',
    warehouse_id: options.warehouses[0]?.value,
    source_warehouse_id: options.warehouses[0]?.value,
    destination_warehouse_id: undefined,
    employee_id: undefined,
    remark: '',
    lines: defaultLines()
  })
}
/** 打开新增库存作业。 */
const create = async () => {
  reset()
  visible.value = true
  await loadProducts()
}
/** 打开库存作业详情。 */
const open = async (row: any) => {
  reset()
  const res = await getInventoryOperationApi(apiKind.value, row.id)
  Object.assign(form, res.data)
  editingId.value = row.id
  readonly.value = row.status !== 'draft'
  await loadProducts()
  form.lines = (res.data.lines || []).map((x: any) => ({
    ...x,
    key: ++key,
    warehouse_id: currentWarehouseId(),
    product: x.product,
    quantity: Number(x.quantity),
    unit_price: Number(x.unit_price || 0),
    serialText: (x.serial_numbers || []).join(',')
  }))
  visible.value = true
}
/** 组装后端库存作业输入。 */
const payload = () => {
  const lines = form.lines
    .filter((x: any) => x.product_id)
    .map((x: any) => ({
      product_id: x.product_id,
      unit_id: x.unit_id,
      quantity: Number(x.quantity),
      unit_price: Number(x.unit_price || 0),
      batch_no: x.batch_no || null,
      production_date: x.production_date || null,
      expiry_date: x.expiry_date || null,
      serial_numbers: x.serialText
        .split(/[，,\n]/)
        .map((s: string) => s.trim())
        .filter(Boolean),
      remark: x.remark || null
    }))
  return props.kind === 'transfer'
    ? {
        transfer_date: form.transfer_date,
        transfer_mode: form.transfer_mode,
        source_warehouse_id: form.source_warehouse_id,
        destination_warehouse_id: form.destination_warehouse_id,
        employee_id: form.employee_id || null,
        remark: form.remark || null,
        lines
      }
    : {
        business_date: form.business_date,
        direction: form.direction,
        reason: form.reason,
        warehouse_id: form.warehouse_id,
        employee_id: form.employee_id || null,
        remark: form.remark || null,
        lines
      }
}
/** 保存库存作业草稿。 */
const save = async () => {
  const enteredLines = form.lines.filter((x: any) => x.product_id)
  if (!enteredLines.length || enteredLines.some((x: any) => !x.unit_id || Number(x.quantity) <= 0))
    return ElMessage.warning('请完整填写商品明细')
  saving.value = true
  try {
    editingId.value
      ? await putInventoryOperationApi(apiKind.value, editingId.value, payload())
      : await addInventoryOperationApi(apiKind.value, payload())
    ElMessage.success('保存成功')
    visible.value = false
    await loadList()
  } finally {
    saving.value = false
  }
}
/** 执行审核、发运、收货或对应冲销动作。 */
const action = async (row: any, name: string, label: string) => {
  await ElMessageBox.confirm(`确定${label} ${row.transfer_no || row.order_no} 吗？`, label, {
    type: 'warning'
  })
  await actionInventoryOperationApi(apiKind.value, row.id, name)
  ElMessage.success(`${label}成功`)
  await loadList()
}
/** 删除库存作业草稿。 */
const remove = async (row: any) => {
  await ElMessageBox.confirm('确定删除该草稿吗？', '删除确认', { type: 'warning' })
  await delInventoryOperationApi(apiKind.value, [row.id])
  ElMessage.success('删除成功')
  await loadList()
}

onMounted(async () => {
  const [warehouses, employees] = await Promise.all([
    getMasterOptionsApi('warehouses'),
    getMasterOptionsApi('employees')
  ])
  options.warehouses = warehouses.data || []
  options.employees = employees.data || []
  reset()
  await loadList()
})
</script>

<template>
  <ContentWrap>
    <div class="toolbar"
      ><el-input v-model="query.keyword" placeholder="单据号" clearable /><el-select
        v-model="query.status"
        placeholder="状态"
        clearable
        ><el-option v-for="(v, k) in statusMap" :key="k" :label="v[0]" :value="k" /></el-select
      ><el-button type="primary" @click="loadList">查询</el-button
      ><el-button type="success" @click="create">新增{{ title }}</el-button></div
    >
    <el-table v-loading="loading" :data="rows" border stripe>
      <el-table-column
        :prop="kind === 'transfer' ? 'transfer_no' : 'order_no'"
        label="单据号"
        min-width="170"
      />
      <el-table-column
        :prop="kind === 'transfer' ? 'transfer_date' : 'business_date'"
        label="业务日期"
        width="115"
      />
      <el-table-column v-if="kind === 'transfer'" prop="transfer_mode" label="模式" width="100"
        ><template #default="s">{{
          s.row.transfer_mode === 'one_step' ? '一步调拨' : '两步调拨'
        }}</template></el-table-column
      >
      <el-table-column v-else prop="direction" label="方向" width="100"
        ><template #default="s">{{
          s.row.direction === 'inbound' ? '其他入库' : '其他出库'
        }}</template></el-table-column
      >
      <el-table-column
        prop="total_quantity"
        label="数量"
        width="120"
        align="right"
      /><el-table-column prop="total_amount" label="成本" width="120" align="right"
        ><template #default="s">¥ {{ money(s.row.total_amount) }}</template></el-table-column
      >
      <el-table-column prop="status" label="状态" width="100"
        ><template #default="s"
          ><el-tag :type="statusMap[s.row.status]?.[1]">{{
            statusMap[s.row.status]?.[0]
          }}</el-tag></template
        ></el-table-column
      >
      <el-table-column label="操作" min-width="300" fixed="right"
        ><template #default="s"
          ><el-button link type="primary" @click="open(s.row)">{{
            s.row.status === 'draft' ? '编辑' : '查看'
          }}</el-button
          ><template v-if="kind === 'transfer'"
            ><el-button
              v-if="s.row.status === 'draft'"
              link
              type="success"
              @click="action(s.row, 'dispatch', '发运')"
              >发运</el-button
            ><el-button
              v-if="s.row.status === 'in_transit' && s.row.transfer_mode === 'two_step'"
              link
              type="success"
              @click="action(s.row, 'receive', '收货')"
              >收货</el-button
            ><el-button
              v-if="s.row.status === 'completed' && s.row.transfer_mode === 'two_step'"
              link
              type="warning"
              @click="action(s.row, 'unreceive', '撤销收货')"
              >撤销收货</el-button
            ><el-button
              v-if="
                s.row.status === 'in_transit' ||
                (s.row.status === 'completed' && s.row.transfer_mode === 'one_step')
              "
              link
              type="warning"
              @click="action(s.row, 'undispatch', '撤销发运')"
              >撤销发运</el-button
            ></template
          ><template v-else
            ><el-button
              v-if="s.row.status === 'draft'"
              link
              type="success"
              @click="action(s.row, 'approve', '审核')"
              >审核</el-button
            ><el-button v-else link type="warning" @click="action(s.row, 'unapprove', '反审核')"
              >反审核</el-button
            ></template
          ><el-button v-if="s.row.status === 'draft'" link type="danger" @click="remove(s.row)"
            >删除</el-button
          ></template
        ></el-table-column
      > </el-table
    ><el-pagination
      v-model:current-page="query.page"
      v-model:page-size="query.limit"
      :total="total"
      layout="total, prev, pager, next"
      class="pager"
      @change="loadList"
    />
  </ContentWrap>
  <el-dialog
    v-model="visible"
    :title="title"
    fullscreen
    class="erp-document-dialog"
    @keydown.enter="productEntry.preventDocumentEnter"
  >
    <el-form label-width="90px" :disabled="readonly" class="erp-document-header"
      ><el-row :gutter="16">
        <template v-if="kind === 'transfer'"
          ><el-col :span="5"
            ><el-form-item label="调拨日期"
              ><el-date-picker
                v-model="form.transfer_date"
                value-format="YYYY-MM-DD" /></el-form-item></el-col
          ><el-col :span="5"
            ><el-form-item label="调拨模式"
              ><el-select v-model="form.transfer_mode"
                ><el-option label="一步调拨" value="one_step" /><el-option
                  label="两步调拨"
                  value="two_step" /></el-select></el-form-item></el-col
          ><el-col :span="5"
            ><el-form-item label="调出仓"
              ><el-select v-model="form.source_warehouse_id" filterable @change="loadProducts()"
                ><el-option
                  v-for="x in options.warehouses"
                  :key="x.value"
                  :label="x.label"
                  :value="x.value" /></el-select></el-form-item></el-col
          ><el-col :span="5"
            ><el-form-item label="调入仓"
              ><el-select v-model="form.destination_warehouse_id" filterable
                ><el-option
                  v-for="x in options.warehouses"
                  :key="x.value"
                  :label="x.label"
                  :value="x.value" /></el-select></el-form-item></el-col
        ></template>
        <template v-else
          ><el-col :span="6"
            ><el-form-item label="业务日期"
              ><el-date-picker
                v-model="form.business_date"
                value-format="YYYY-MM-DD" /></el-form-item></el-col
          ><el-col :span="6"
            ><el-form-item label="方向"
              ><el-select v-model="form.direction"
                ><el-option label="其他入库" value="inbound" /><el-option
                  label="其他出库"
                  value="outbound" /></el-select></el-form-item></el-col
          ><el-col :span="6"
            ><el-form-item label="仓库"
              ><el-select v-model="form.warehouse_id" filterable @change="loadProducts()"
                ><el-option
                  v-for="x in options.warehouses"
                  :key="x.value"
                  :label="x.label"
                  :value="x.value" /></el-select></el-form-item></el-col
          ><el-col :span="6"
            ><el-form-item label="原因"><el-input v-model="form.reason" /></el-form-item></el-col
        ></template> </el-row
    ></el-form>
    <div v-if="!readonly && productEntry.scanMode.value" class="document-scan-bar">
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
      <el-table :data="form.lines" border class="erp-document-table"
        ><el-table-column width="54" fixed="left" align="center">
          <template #default="s">
            <template v-if="!readonly">
              <el-button link type="primary" class="line-button" @click="addLineAfter(s.$index)"
                >＋</el-button
              >
              <el-button link type="danger" class="line-button" @click="removeLine(s.$index)"
                >－</el-button
              >
            </template>
            <span v-else>{{ s.$index + 1 }}</span>
          </template></el-table-column
        ><el-table-column min-width="260" fixed="left">
          <template #header>
            <div class="document-product-column-title">
              <span><i>*</i> 商品</span>
              <span v-if="!readonly" class="scan-switch">
                --扫码枪录入
                <el-switch v-model="productEntry.scanMode.value" size="small" />
              </span>
            </div>
          </template>
          <template #default="s">
            <div class="document-entry-cell" :data-entry-cell="`${s.row.key}-product`">
              <DocumentProductSelect
                v-model="s.row.product_id"
                :line-key="s.row.key"
                :row-index="s.$index"
                :products="productEntry.productOptions.value"
                :loading="productEntry.productLoading.value"
                :disabled="readonly"
                :scan-mode="productEntry.scanMode.value"
                @search="productEntry.loadProducts"
                @change="productEntry.chooseProduct(s.row, $event)"
                @picker="productEntry.openPicker(s.row)"
                @move="productEntry.moveCell(s.row, s.$index, 'product', $event)"
              />
            </div> </template></el-table-column
        ><el-table-column label="规格型号" width="110" show-overflow-tooltip
          ><template #default="s"
            ><div class="document-display-cell">{{ skuSpec(s.row.product) }}</div></template
          ></el-table-column
        ><el-table-column label="可用库存" width="88"
          ><template #default="s"
            ><div class="document-display-cell number-cell">{{
              s.row.product?.stock_quantity || 0
            }}</div></template
          ></el-table-column
        ><el-table-column label="商品单位" width="95"
          ><template #default="s">
            <div
              class="document-entry-cell"
              :data-entry-cell="`${s.row.key}-unit`"
              @keydown="productEntry.handleCellKeydown($event, s.row, s.$index, 'unit')"
              ><el-select v-model="s.row.unit_id" :disabled="readonly" @change="changeUnit(s.row)"
                ><el-option
                  v-for="u in s.row.product?.units || []"
                  :key="u.unit_id"
                  :label="u.unit_name"
                  :value="u.unit_id" /></el-select></div></template></el-table-column
        ><el-table-column label="数量 *" width="100"
          ><template #default="s">
            <div
              class="document-entry-cell"
              :data-entry-cell="`${s.row.key}-quantity`"
              @keydown="productEntry.handleCellKeydown($event, s.row, s.$index, 'quantity')"
              ><el-input-number
                v-model="s.row.quantity"
                :disabled="readonly"
                :min="0.000001"
                :controls="false" /></div></template></el-table-column
        ><el-table-column
          v-if="kind === 'other' && form.direction === 'inbound'"
          label="成本单价"
          width="110"
          ><template #default="s">
            <div
              class="document-entry-cell"
              :data-entry-cell="`${s.row.key}-unit_price`"
              @keydown="productEntry.handleCellKeydown($event, s.row, s.$index, 'unit_price')"
              ><el-input-number
                v-model="s.row.unit_price"
                :disabled="readonly"
                :min="0"
                :controls="false" /></div></template></el-table-column
        ><el-table-column
          v-if="kind === 'other' && form.direction === 'inbound'"
          label="成本金额"
          width="100"
          align="right"
          ><template #default="s"
            ><div class="document-display-cell number-cell">{{
              (Number(s.row.quantity || 0) * Number(s.row.unit_price || 0)).toFixed(2)
            }}</div></template
          ></el-table-column
        ><el-table-column label="基本数量" width="95" align="right"
          ><template #default="s"
            ><div class="document-display-cell number-cell">{{
              baseQuantity(s.row)
                .toFixed(6)
                .replace(/\.?0+$/, '')
            }}</div></template
          ></el-table-column
        ><el-table-column label="批次号" width="110"
          ><template #default="s">
            <div
              class="document-entry-cell"
              :class="{ 'is-disabled': !s.row.product?.batch_enabled }"
              :data-entry-cell="`${s.row.key}-batch_no`"
              @keydown="productEntry.handleCellKeydown($event, s.row, s.$index, 'batch_no')"
              ><el-input
                v-model="s.row.batch_no"
                :disabled="
                  readonly || !s.row.product?.batch_enabled
                " /></div></template></el-table-column
        ><el-table-column label="序列号" width="110"
          ><template #default="s">
            <div
              class="document-entry-cell"
              :class="{ 'is-disabled': !s.row.product?.serial_enabled }"
              :data-entry-cell="`${s.row.key}-serial`"
              @keydown="productEntry.handleCellKeydown($event, s.row, s.$index, 'serial')"
              ><DocumentSerialEditor
                v-if="s.row.product?.serial_enabled"
                :model-value="serialValues(s.row.serialText)"
                :disabled="readonly"
                @update:model-value="changeSerials(s.row, $event)"
              /><span v-else>不管理</span></div
            ></template
          ></el-table-column
        ></el-table
      >
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
        ><label>成本金额：</label><span>¥ {{ money(amountTotal) }}</span></div
      >
    </div>
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
    price-label="参考成本"
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
  width: 180px;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
