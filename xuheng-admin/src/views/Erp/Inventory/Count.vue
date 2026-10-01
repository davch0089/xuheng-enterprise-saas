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
  getInventoryCountSnapshotApi,
  getInventoryOperationApi,
  getInventoryOperationListApi,
  putInventoryOperationApi,
  searchInboundProductsApi
} from '@/api/erp/inventory'

defineOptions({ name: 'ErpInventoryCount' })
const loading = ref(false),
  saving = ref(false),
  visible = ref(false),
  readonly = ref(false)
const rows = ref<any[]>([]),
  total = ref(0),
  editingId = ref<number>()
const query = reactive({ page: 1, limit: 20, keyword: '', status: '' })
const options = reactive<any>({ warehouses: [], employees: [] })
let lineKey = 0
const form = reactive<any>({
  count_date: dayjs().format('YYYY-MM-DD'),
  warehouse_id: undefined,
  employee_id: undefined,
  remark: '',
  lines: []
})
const statusMap: any = { draft: ['草稿', 'info'], approved: ['已审核', 'success'] }
const productLineCount = computed(() => form.lines.filter((line: any) => line.product_id).length)
const systemQuantityTotal = computed(() =>
  form.lines.reduce((sum: number, line: any) => sum + Number(line.system_quantity || 0), 0)
)
const countedQuantityTotal = computed(() =>
  form.lines.reduce((sum: number, line: any) => sum + Number(line.counted_quantity || 0), 0)
)
const changeCountSerials = (line: any, values: string[]) => {
  line.counted_serial_numbers = values
  line.counted_quantity = values.length
  line.quantity = values.length
}

/** 创建可用于扫码盘盈的空白盘点行。 */
const emptyLine = () => ({
  key: ++lineKey,
  product_id: undefined,
  product: undefined,
  warehouse_id: form.warehouse_id,
  quantity: 0,
  system_quantity: 0,
  counted_quantity: 0,
  batch_no: '',
  counted_serial_numbers: [],
  remark: ''
})
/** 新盘点单预置四行，也允许随后生成库存快照覆盖这些空行。 */
const defaultLines = () => Array.from({ length: 4 }, () => emptyLine())
/** 在当前盘点行下方插入一行。 */
const addLineAfter = (index: number) => form.lines.splice(index + 1, 0, emptyLine())
/** 删除当前盘点行；仅剩一行时保留一个空白行。 */
const removeLine = (index: number) => {
  if (form.lines.length === 1) form.lines.splice(0, 1, emptyLine())
  else form.lines.splice(index, 1)
}

/** 查询盘点仓库商品目录。 */
const searchProducts = async (keyword = '') => {
  const res = await searchInboundProductsApi({
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
  navColumns: ['product', 'batch_no', 'counted_quantity', 'serial'],
  columnAvailable: (line, column) => {
    if (column === 'batch_no') return !!line.product?.batch_enabled
    if (column === 'serial') return !!line.product?.serial_enabled
    return true
  },
  incrementLine: (line) => {
    line.counted_quantity = Number(line.counted_quantity || 0) + 1
    line.quantity = line.counted_quantity
  },
  applyProduct: (line, product) => {
    Object.assign(line, {
      product_id: product.id,
      product,
      product_code: product.code,
      product_name: product.name,
      warehouse_id: form.warehouse_id,
      quantity: 0,
      system_quantity: 0,
      counted_quantity: 0,
      batch_no: '',
      counted_serial_numbers: []
    })
  }
})

/** 加载盘点单列表。 */
const loadList = async () => {
  loading.value = true
  try {
    const res = await getInventoryOperationListApi('counts', query)
    rows.value = res.data || []
    total.value = res.count || 0
  } finally {
    loading.value = false
  }
}
/** 从当前库存余额生成盘点明细。 */
const loadSnapshot = async () => {
  if (!form.warehouse_id) return ElMessage.warning('请先选择仓库')
  const res = await getInventoryCountSnapshotApi(form.warehouse_id)
  const snapshot = res.data || []
  if (!snapshot.length) {
    form.lines = defaultLines()
    ElMessage.warning('该仓库暂无账面库存，可以通过扫码或商品选择录入盘盈商品')
    return
  }
  form.lines = snapshot.map((line: any) => ({
    ...line,
    key: ++lineKey,
    warehouse_id: form.warehouse_id,
    quantity: Number(line.counted_quantity || 0),
    product: {
      ...line,
      id: line.product_id,
      code: line.product_code,
      name: line.product_name
    }
  }))
  await productEntry.loadProducts()
}
/** 打开新增盘点单。 */
const create = () => {
  editingId.value = undefined
  readonly.value = false
  Object.assign(form, {
    count_date: dayjs().format('YYYY-MM-DD'),
    warehouse_id: options.warehouses[0]?.value,
    employee_id: undefined,
    remark: '',
    lines: defaultLines()
  })
  visible.value = true
  productEntry.loadProducts()
}
/** 打开盘点单详情。 */
const open = async (row: any) => {
  const res = await getInventoryOperationApi('counts', row.id)
  Object.assign(form, res.data)
  form.lines = (res.data.lines || []).map((line: any) => ({
    ...line,
    key: ++lineKey,
    warehouse_id: res.data.warehouse_id,
    quantity: Number(line.counted_quantity || 0),
    product: line.product
  }))
  await productEntry.loadProducts()
  editingId.value = row.id
  readonly.value = row.status !== 'draft'
  visible.value = true
}
/** 保存盘点草稿并刷新账面快照。 */
const save = async () => {
  const enteredLines = form.lines.filter((line: any) => line.product_id)
  if (!form.warehouse_id || !enteredLines.length)
    return ElMessage.warning('请选择仓库并录入盘点商品')
  saving.value = true
  try {
    const data = {
      count_date: form.count_date,
      warehouse_id: form.warehouse_id,
      employee_id: form.employee_id || null,
      remark: form.remark || null,
      lines: form.lines
        .filter((x: any) => x.product_id)
        .map((x: any) => ({
          product_id: x.product_id,
          batch_no: x.batch_no || null,
          counted_quantity: Number(x.counted_quantity),
          counted_serial_numbers: x.counted_serial_numbers || [],
          remark: x.remark || null
        }))
    }
    editingId.value
      ? await putInventoryOperationApi('counts', editingId.value, data)
      : await addInventoryOperationApi('counts', data)
    ElMessage.success('保存成功')
    visible.value = false
    await loadList()
  } finally {
    saving.value = false
  }
}
/** 审核或反审核盘点差异。 */
const action = async (row: any, name: string) => {
  const label = name === 'approve' ? '审核' : '反审核'
  await ElMessageBox.confirm(
    `${label}将${name === 'approve' ? '过账盘盈盘亏' : '冲销盘盈盘亏'}，确定继续吗？`,
    label,
    { type: 'warning' }
  )
  await actionInventoryOperationApi('counts', row.id, name)
  ElMessage.success(`${label}成功`)
  await loadList()
}
/** 删除盘点草稿。 */
const remove = async (row: any) => {
  await ElMessageBox.confirm('确定删除该盘点草稿吗？', '删除确认', { type: 'warning' })
  await delInventoryOperationApi('counts', [row.id])
  await loadList()
}

onMounted(async () => {
  const [warehouses, employees] = await Promise.all([
    getMasterOptionsApi('warehouses'),
    getMasterOptionsApi('employees')
  ])
  options.warehouses = warehouses.data || []
  options.employees = employees.data || []
  await loadList()
})
</script>
<template>
  <ContentWrap
    ><div class="toolbar"
      ><el-input v-model="query.keyword" placeholder="盘点单号" clearable /><el-select
        v-model="query.status"
        placeholder="状态"
        clearable
        ><el-option label="草稿" value="draft" /><el-option
          label="已审核"
          value="approved" /></el-select
      ><el-button type="primary" @click="loadList">查询</el-button
      ><el-button type="success" @click="create">新增盘点</el-button></div
    >
    <el-table v-loading="loading" :data="rows" border stripe
      ><el-table-column prop="count_no" label="盘点单号" min-width="170" /><el-table-column
        prop="count_date"
        label="盘点日期"
        width="115"
      /><el-table-column prop="total_lines" label="行数" width="80" /><el-table-column
        prop="total_system_quantity"
        label="账面数量"
        width="120"
        align="right"
      /><el-table-column
        prop="total_counted_quantity"
        label="实盘数量"
        width="120"
        align="right"
      /><el-table-column
        prop="total_gain_quantity"
        label="盘盈"
        width="100"
        align="right"
      /><el-table-column
        prop="total_loss_quantity"
        label="盘亏"
        width="100"
        align="right"
      /><el-table-column label="状态" width="100"
        ><template #default="s"
          ><el-tag :type="statusMap[s.row.status][1]">{{
            statusMap[s.row.status][0]
          }}</el-tag></template
        ></el-table-column
      ><el-table-column label="操作" width="240"
        ><template #default="s"
          ><el-button link type="primary" @click="open(s.row)">{{
            s.row.status === 'draft' ? '编辑' : '查看'
          }}</el-button
          ><el-button
            v-if="s.row.status === 'draft'"
            link
            type="success"
            @click="action(s.row, 'approve')"
            >审核</el-button
          ><el-button v-else link type="warning" @click="action(s.row, 'unapprove')"
            >反审核</el-button
          ><el-button v-if="s.row.status === 'draft'" link type="danger" @click="remove(s.row)"
            >删除</el-button
          ></template
        ></el-table-column
      ></el-table
    ><el-pagination
      v-model:current-page="query.page"
      :total="total"
      layout="total, prev, pager, next"
      class="pager"
      @change="loadList"
    />
  </ContentWrap>
  <el-dialog
    v-model="visible"
    title="库存盘点"
    fullscreen
    class="erp-document-dialog"
    @keydown.enter="productEntry.preventDocumentEnter"
    ><el-form label-width="90px" :disabled="readonly" class="erp-document-header"
      ><el-row :gutter="16"
        ><el-col :span="6"
          ><el-form-item label="盘点日期"
            ><el-date-picker
              v-model="form.count_date"
              value-format="YYYY-MM-DD" /></el-form-item></el-col
        ><el-col :span="8"
          ><el-form-item label="盘点仓库"
            ><el-select v-model="form.warehouse_id" filterable :disabled="!!editingId"
              ><el-option
                v-for="x in options.warehouses"
                :key="x.value"
                :label="x.label"
                :value="x.value" /></el-select></el-form-item></el-col
        ><el-col :span="5"
          ><el-button v-if="!readonly" type="primary" plain @click="loadSnapshot"
            >生成当前库存明细</el-button
          ></el-col
        ></el-row
      ></el-form
    >
    <div v-if="!readonly && productEntry.scanMode.value" class="document-scan-bar">
      <span class="scan-label">扫码盘点</span>
      <el-input
        :ref="(instance) => (productEntry.scanInput.value = instance)"
        v-model="productEntry.scanCode.value"
        placeholder="扫描条码或输入 SKU 编码后回车；重复扫描累加实盘数量"
        clearable
        @keyup.enter="productEntry.scanProduct"
      />
      <el-button type="primary" @click="productEntry.scanProduct">录入</el-button>
      <span class="scan-tip">扫码可以补充账面数量为零的盘盈商品</span>
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
        ><el-table-column label="批次" width="135"
          ><template #default="s">
            <div
              class="document-entry-cell"
              :data-entry-cell="`${s.row.key}-batch_no`"
              @keydown="productEntry.handleCellKeydown($event, s.row, s.$index, 'batch_no')"
              ><el-input
                v-model="s.row.batch_no"
                :disabled="readonly || !(s.row.batch_enabled || s.row.product?.batch_enabled)"
                :placeholder="
                  s.row.product?.batch_enabled ? '必填' : ''
                " /></div></template></el-table-column
        ><el-table-column prop="system_quantity" label="账面数量" width="110" align="right"
          ><template #default="s"
            ><div class="document-display-cell number-cell">{{
              Number(s.row.system_quantity || 0).toFixed(6)
            }}</div></template
          ></el-table-column
        ><el-table-column label="实盘数量" width="140"
          ><template #default="s">
            <div
              class="document-entry-cell"
              :data-entry-cell="`${s.row.key}-counted_quantity`"
              @keydown="productEntry.handleCellKeydown($event, s.row, s.$index, 'counted_quantity')"
              ><el-input-number
                v-model="s.row.counted_quantity"
                :disabled="readonly"
                :min="0"
                :controls="false" /></div></template></el-table-column
        ><el-table-column label="差异" width="100" align="right"
          ><template #default="s"
            ><div class="document-display-cell number-cell">{{
              (Number(s.row.counted_quantity) - Number(s.row.system_quantity)).toFixed(6)
            }}</div></template
          ></el-table-column
        ><el-table-column label="实盘序列号" min-width="220"
          ><template #default="s">
            <div
              class="document-entry-cell"
              :data-entry-cell="`${s.row.key}-serial`"
              @keydown="productEntry.handleCellKeydown($event, s.row, s.$index, 'serial')"
              ><DocumentSerialEditor
                v-if="s.row.serial_enabled || s.row.product?.serial_enabled"
                :model-value="s.row.counted_serial_numbers || []"
                :disabled="readonly"
                @update:model-value="changeCountSerials(s.row, $event)"
              /><span v-else>-</span></div
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
        ><label>账面数量：</label
        ><span>{{ systemQuantityTotal.toFixed(6).replace(/\.?0+$/, '') }}</span></div
      >
      <div class="summary-total"
        ><label>实盘数量：</label
        ><span>{{ countedQuantityTotal.toFixed(6).replace(/\.?0+$/, '') }}</span></div
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
    ><template #footer
      ><el-button @click="visible = false">关闭</el-button
      ><el-button v-if="!readonly" type="primary" :loading="saving" @click="save"
        >保存草稿</el-button
      ></template
    ></el-dialog
  >
  <DocumentProductPicker
    v-model="productEntry.pickerVisible.value"
    v-model:keyword="productEntry.pickerKeyword.value"
    :rows="productEntry.pickerRows.value"
    :loading="productEntry.pickerLoading.value"
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
