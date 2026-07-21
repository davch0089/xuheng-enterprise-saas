<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ContentWrap } from '@/components/ContentWrap'
import { skuLabel, skuSpec } from '@/utils/erp/product'
import '@/styles/erp-document.css'
import { getMasterOptionsApi } from '@/api/erp/master'
import {
  actionAssemblyOrderApi,
  addAssemblyOrderApi,
  delAssemblyOrderApi,
  getAssemblyOrderApi,
  getAssemblyOrderListApi,
  getBomApi,
  getBomListApi,
  putAssemblyOrderApi,
  searchInboundProductsApi
} from '@/api/erp/inventory'

defineOptions({ name: 'ErpInventoryAssembly' })

const loading = ref(false)
const saving = ref(false)
const visible = ref(false)
const readonly = ref(false)
const rows = ref<any[]>([])
const total = ref(0)
const editingId = ref<number>()
const products = ref<any[]>([])
const boms = ref<any[]>([])
const bomDetail = ref<any>()
const options = reactive<any>({ warehouses: [], employees: [] })
const query = reactive({ page: 1, limit: 20, keyword: '', status: '' })
const form = reactive<any>({
  business_date: dayjs().format('YYYY-MM-DD'),
  order_type: 'assembly',
  bom_id: undefined,
  warehouse_id: undefined,
  employee_id: undefined,
  quantity: 1,
  tracking: {},
  actualCosts: {},
  remark: ''
})

/** 返回商品目录项。 */
const product = (id: number) => products.value.find((item) => item.id === id)
const warehouseName = (id: number) =>
  options.warehouses.find((item: any) => item.value === id)?.label || '-'
const bomName = (id: number) => {
  const item = boms.value.find((bom) => bom.id === id)
  return item ? `${item.code} ${item.name}` : '-'
}

/** 按工单数量展开 BOM；组装时将损耗率计入子件领用量。 */
const expandedLines = computed(() => {
  const bom = bomDetail.value
  if (!bom) return []
  const scale = Number(form.quantity || 0) / Number(bom.output_quantity || 1)
  const finished = bom.finished_product || product(bom.product_id)
  const result = [
    {
      role: 'finished',
      product_id: bom.product_id,
      product: finished,
      unit_id: bom.unit_id,
      unit_name: finished?.units?.find((unit: any) => unit.unit_id === bom.unit_id)?.unit_name,
      quantity: Number(form.quantity || 0),
      loss_rate: 0,
      actual_cost: form.actualCosts[bom.product_id] || 0
    }
  ]
  for (const line of bom.lines || []) {
    const item = line.product || product(line.component_product_id)
    let quantity = Number(line.quantity) * scale
    if (form.order_type === 'assembly') quantity *= 1 + Number(line.loss_rate || 0) / 100
    result.push({
      role: 'component',
      product_id: line.component_product_id,
      product: item,
      unit_id: line.unit_id,
      unit_name: item?.units?.find((unit: any) => unit.unit_id === line.unit_id)?.unit_name,
      quantity,
      loss_rate: line.loss_rate,
      actual_cost: form.actualCosts[line.component_product_id] || 0
    })
  }
  return result
})

/** 加载工单列表。 */
const loadList = async () => {
  loading.value = true
  try {
    const res = await getAssemblyOrderListApi(query)
    rows.value = res.data || []
    total.value = res.count || 0
  } finally {
    loading.value = false
  }
}

/** 初始化商品、BOM、仓库和经办人选项。 */
const loadOptions = async () => {
  const [productRes, bomRes, warehouseRes, employeeRes] = await Promise.all([
    searchInboundProductsApi({ limit: 100 }),
    getBomListApi({ page: 1, limit: 100, is_active: true }),
    getMasterOptionsApi('warehouses'),
    getMasterOptionsApi('employees')
  ])
  products.value = productRes.data || []
  boms.value = bomRes.data || []
  options.warehouses = warehouseRes.data || []
  options.employees = employeeRes.data || []
}

/** 确保每个跟踪商品都有独立的批次/序列号输入对象。 */
const initializeTracking = () => {
  for (const line of expandedLines.value) {
    if (!form.tracking[line.product_id]) {
      form.tracking[line.product_id] = {
        batch_no: '',
        production_date: '',
        expiry_date: '',
        serialText: ''
      }
    }
  }
}

/** 选择 BOM 后读取完整子件结构。 */
const chooseBom = async () => {
  bomDetail.value = undefined
  form.tracking = {}
  form.actualCosts = {}
  if (!form.bom_id) return
  const res = await getBomApi(form.bom_id)
  bomDetail.value = res.data
  initializeTracking()
}

/** 重置新增工单表单。 */
const reset = () => {
  editingId.value = undefined
  readonly.value = false
  bomDetail.value = undefined
  Object.assign(form, {
    business_date: dayjs().format('YYYY-MM-DD'),
    order_type: 'assembly',
    bom_id: undefined,
    warehouse_id: options.warehouses[0]?.value,
    employee_id: undefined,
    quantity: 1,
    tracking: {},
    actualCosts: {},
    remark: ''
  })
}

/** 打开新增组装或拆卸工单。 */
const create = () => {
  reset()
  visible.value = true
}

/** 打开工单详情，并还原固化的跟踪属性和实际成本。 */
const open = async (row: any) => {
  reset()
  const orderRes = await getAssemblyOrderApi(row.id)
  const order = orderRes.data
  const finished = (order.lines || []).find((line: any) => line.line_role === 'finished')
  const components = (order.lines || []).filter((line: any) => line.line_role === 'component')
  bomDetail.value = finished
    ? {
        id: order.bom_id,
        product_id: finished.product_id,
        finished_product: finished.product,
        unit_id: finished.unit_id,
        output_quantity: order.quantity,
        lines: components.map((line: any) => ({
          component_product_id: line.product_id,
          product: line.product,
          unit_id: line.unit_id,
          quantity: line.quantity,
          loss_rate: 0
        }))
      }
    : undefined
  Object.assign(form, {
    business_date: order.business_date,
    order_type: order.order_type,
    bom_id: order.bom_id,
    warehouse_id: order.warehouse_id,
    employee_id: order.employee_id,
    quantity: Number(order.quantity),
    remark: order.remark || '',
    tracking: {},
    actualCosts: {}
  })
  for (const line of order.lines || []) {
    form.tracking[line.product_id] = {
      batch_no: line.batch_no || '',
      production_date: line.production_date || '',
      expiry_date: line.expiry_date || '',
      serialText: (line.serial_numbers || []).join('\n')
    }
    form.actualCosts[line.product_id] = Number(line.actual_cost || 0)
  }
  initializeTracking()
  editingId.value = row.id
  readonly.value = row.status !== 'draft'
  visible.value = true
}

/** 组装符合后端输入的批次和序列号数组。 */
const payload = () => ({
  business_date: form.business_date,
  order_type: form.order_type,
  bom_id: form.bom_id,
  warehouse_id: form.warehouse_id,
  employee_id: form.employee_id || null,
  quantity: Number(form.quantity),
  remark: form.remark || null,
  tracking: expandedLines.value.map((line) => {
    const value = form.tracking[line.product_id] || {}
    return {
      product_id: line.product_id,
      batch_no: value.batch_no || null,
      production_date: value.production_date || null,
      expiry_date: value.expiry_date || null,
      serial_numbers: String(value.serialText || '')
        .split(/[,，\n]/)
        .map((item) => item.trim())
        .filter(Boolean)
    }
  })
})

/** 保存工单草稿；BOM 明细将在后端固化为工单快照。 */
const save = async () => {
  if (!form.business_date || !form.bom_id || !form.warehouse_id || Number(form.quantity) <= 0)
    return ElMessage.warning('请完整填写工单表头')
  initializeTracking()
  for (const line of expandedLines.value) {
    const value = form.tracking[line.product_id]
    if (line.product?.batch_enabled && !value?.batch_no)
      return ElMessage.warning(`商品 ${line.product.code} 必须填写批次`)
    const serials = String(value?.serialText || '')
      .split(/[,，\n]/)
      .map((item) => item.trim())
      .filter(Boolean)
    const baseRate = Number(
      line.product?.units?.find((unit: any) => unit.unit_id === line.unit_id)?.to_base_rate || 1
    )
    if (line.product?.serial_enabled && serials.length !== Math.round(line.quantity * baseRate))
      return ElMessage.warning(`商品 ${line.product.code} 的序列号数量不等于主单位数量`)
  }
  saving.value = true
  try {
    editingId.value
      ? await putAssemblyOrderApi(editingId.value, payload())
      : await addAssemblyOrderApi(payload())
    ElMessage.success('工单保存成功')
    visible.value = false
    await loadList()
  } finally {
    saving.value = false
  }
}

/** 审核时执行子件出库、成品入库与成本归集；反审核按相反顺序冲销。 */
const action = async (row: any, name: 'approve' | 'unapprove') => {
  const label = name === 'approve' ? '审核' : '反审核'
  const message =
    name === 'approve' ? '将同步过账库存并归集成本' : '将冲销本工单生成的全部库存与成本流水'
  await ElMessageBox.confirm(`${message}，确定${label} ${row.order_no} 吗？`, label, {
    type: 'warning'
  })
  await actionAssemblyOrderApi(row.id, name)
  ElMessage.success(`${label}成功`)
  await loadList()
}

/** 删除未审核工单。 */
const remove = async (row: any) => {
  await ElMessageBox.confirm(`确定删除工单 ${row.order_no} 吗？`, '删除确认', { type: 'warning' })
  await delAssemblyOrderApi([row.id])
  ElMessage.success('删除成功')
  await loadList()
}

onMounted(async () => {
  await Promise.all([loadOptions(), loadList()])
})
</script>

<template>
  <ContentWrap>
    <div class="toolbar">
      <el-input v-model="query.keyword" clearable placeholder="工单号" @keyup.enter="loadList" />
      <el-select v-model="query.status" clearable placeholder="状态"
        ><el-option label="草稿" value="draft" /><el-option label="已审核" value="approved"
      /></el-select>
      <el-button type="primary" @click="loadList">查询</el-button>
      <el-button type="success" @click="create">新增工单</el-button>
    </div>
    <el-table v-loading="loading" :data="rows" border stripe>
      <el-table-column prop="order_no" label="工单号" min-width="170" />
      <el-table-column prop="business_date" label="业务日期" width="115" />
      <el-table-column label="类型" width="90"
        ><template #default="scope"
          ><el-tag :type="scope.row.order_type === 'assembly' ? 'success' : 'warning'">{{
            scope.row.order_type === 'assembly' ? '组装' : '拆卸'
          }}</el-tag></template
        ></el-table-column
      >
      <el-table-column label="BOM" min-width="180"
        ><template #default="scope">{{ bomName(scope.row.bom_id) }}</template></el-table-column
      >
      <el-table-column label="仓库" width="140"
        ><template #default="scope">{{
          warehouseName(scope.row.warehouse_id)
        }}</template></el-table-column
      >
      <el-table-column prop="quantity" label="产出/拆卸数量" width="135" align="right" />
      <el-table-column prop="finished_cost" label="归集成本" width="120" align="right"
        ><template #default="scope">{{
          Number(scope.row.finished_cost || 0).toFixed(2)
        }}</template></el-table-column
      >
      <el-table-column label="状态" width="90"
        ><template #default="scope"
          ><el-tag :type="scope.row.status === 'approved' ? 'success' : 'info'">{{
            scope.row.status === 'approved' ? '已审核' : '草稿'
          }}</el-tag></template
        ></el-table-column
      >
      <el-table-column label="操作" width="245" fixed="right"
        ><template #default="scope">
          <el-button link type="primary" @click="open(scope.row)">{{
            scope.row.status === 'draft' ? '编辑' : '查看'
          }}</el-button>
          <el-button
            v-if="scope.row.status === 'draft'"
            link
            type="success"
            @click="action(scope.row, 'approve')"
            >审核</el-button
          >
          <el-button v-else link type="warning" @click="action(scope.row, 'unapprove')"
            >反审核</el-button
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
    :title="form.order_type === 'assembly' ? '组装工单' : '拆卸工单'"
    fullscreen
    class="erp-document-dialog"
    destroy-on-close
  >
    <el-form label-width="90px" :disabled="readonly" class="erp-document-header">
      <el-row :gutter="16">
        <el-col :span="5"
          ><el-form-item label="业务日期"
            ><el-date-picker v-model="form.business_date" value-format="YYYY-MM-DD" /></el-form-item
        ></el-col>
        <el-col :span="5"
          ><el-form-item label="作业类型"
            ><el-radio-group v-model="form.order_type"
              ><el-radio-button value="assembly">组装</el-radio-button
              ><el-radio-button value="disassembly">拆卸</el-radio-button></el-radio-group
            ></el-form-item
          ></el-col
        >
        <el-col :span="7"
          ><el-form-item label="BOM"
            ><el-select
              v-model="form.bom_id"
              filterable
              style="width: 100%"
              :disabled="!!editingId"
              @change="chooseBom"
              ><el-option
                v-for="item in boms"
                :key="item.id"
                :label="`${item.code} ${item.name} / ${skuLabel({
                  code: item.product_code,
                  name: item.product_name,
                  barcode: item.product_barcode,
                  variant_name: item.product_variant_name,
                  specification: item.product_specification
                })}`"
                :value="item.id" /></el-select></el-form-item
        ></el-col>
        <el-col :span="5"
          ><el-form-item label="数量"
            ><el-input-number
              v-model="form.quantity"
              :min="0.000001"
              :controls="false"
              @change="initializeTracking" /></el-form-item
        ></el-col>
        <el-col :span="7"
          ><el-form-item label="作业仓库"
            ><el-select v-model="form.warehouse_id" filterable style="width: 100%"
              ><el-option
                v-for="item in options.warehouses"
                :key="item.value"
                v-bind="item" /></el-select></el-form-item
        ></el-col>
        <el-col :span="7"
          ><el-form-item label="经办人"
            ><el-select v-model="form.employee_id" clearable filterable style="width: 100%"
              ><el-option
                v-for="item in options.employees"
                :key="item.value"
                v-bind="item" /></el-select></el-form-item
        ></el-col>
      </el-row>
    </el-form>
    <el-alert
      v-if="bomDetail"
      :title="
        form.order_type === 'assembly'
          ? '审核后：子件出库 → 按实际出库成本归集 → 成品入库'
          : '审核后：成品出库 → 按当前成本权重分摊 → 子件入库'
      "
      type="info"
      :closable="false"
      class="flow-tip"
    />
    <el-table :data="expandedLines" border class="erp-document-table">
      <el-table-column label="角色" width="85"
        ><template #default="scope"
          ><el-tag :type="scope.row.role === 'finished' ? 'success' : 'info'">{{
            scope.row.role === 'finished' ? '成品' : '子件'
          }}</el-tag></template
        ></el-table-column
      >
      <el-table-column label="SKU编码" width="135"
        ><template #default="scope">{{ scope.row.product?.code }}</template></el-table-column
      >
      <el-table-column label="商品名称" min-width="170"
        ><template #default="scope">{{ scope.row.product?.name }}</template></el-table-column
      >
      <el-table-column label="SKU规格" min-width="150"
        ><template #default="scope">{{ skuSpec(scope.row.product) }}</template></el-table-column
      >
      <el-table-column label="数量" width="120" align="right"
        ><template #default="scope"
          >{{
            Number(scope.row.quantity)
              .toFixed(6)
              .replace(/\.?0+$/, '')
          }}
          {{ scope.row.unit_name }}</template
        ></el-table-column
      >
      <el-table-column label="批次号" width="155"
        ><template #default="scope"
          ><el-input
            v-if="scope.row.product?.batch_enabled"
            v-model="form.tracking[scope.row.product_id].batch_no"
            :disabled="readonly"
          /><span v-else>-</span></template
        ></el-table-column
      >
      <el-table-column label="生产日期" width="145"
        ><template #default="scope"
          ><el-date-picker
            v-if="scope.row.product?.batch_enabled"
            v-model="form.tracking[scope.row.product_id].production_date"
            value-format="YYYY-MM-DD"
            :disabled="readonly"
            style="width: 130px"
          /><span v-else>-</span></template
        ></el-table-column
      >
      <el-table-column label="有效期至" width="145"
        ><template #default="scope"
          ><el-date-picker
            v-if="scope.row.product?.batch_enabled"
            v-model="form.tracking[scope.row.product_id].expiry_date"
            value-format="YYYY-MM-DD"
            :disabled="readonly"
            style="width: 130px"
          /><span v-else>-</span></template
        ></el-table-column
      >
      <el-table-column label="序列号" min-width="220"
        ><template #default="scope"
          ><el-input
            v-if="scope.row.product?.serial_enabled"
            v-model="form.tracking[scope.row.product_id].serialText"
            type="textarea"
            :rows="2"
            :disabled="readonly"
            placeholder="每行一个，也可用逗号分隔"
          /><span v-else>-</span></template
        ></el-table-column
      >
      <el-table-column v-if="readonly" label="实际成本" width="120" align="right"
        ><template #default="scope">{{
          Number(scope.row.actual_cost || 0).toFixed(2)
        }}</template></el-table-column
      >
    </el-table>
    <el-form label-width="90px" :disabled="readonly" class="remark"
      ><el-form-item label="备注"><el-input v-model="form.remark" type="textarea" /></el-form-item
    ></el-form>
    <template #footer
      ><el-button @click="visible = false">关闭</el-button
      ><el-button v-if="!readonly" type="primary" :loading="saving" @click="save"
        >保存草稿</el-button
      ></template
    >
  </el-dialog>
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
.flow-tip {
  margin-bottom: 12px;
}
.remark {
  margin-top: 14px;
}
</style>
