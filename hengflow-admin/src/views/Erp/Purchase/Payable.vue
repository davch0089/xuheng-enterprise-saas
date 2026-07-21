<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ContentWrap } from '@/components/ContentWrap'
import '@/styles/erp-document.css'
import {
  addPurchasePaymentApi,
  approvePurchasePaymentApi,
  delPurchasePaymentApi,
  getPayableListApi,
  getPurchaseOptionsApi,
  getPurchasePaymentApi,
  getPurchasePaymentListApi,
  putPurchasePaymentApi,
  unapprovePurchasePaymentApi
} from '@/api/erp/purchase'
import { getFinanceOptionsApi } from '@/api/erp/finance'

defineOptions({ name: 'ErpPurchasePayable' })

const activeTab = ref('payables')
const loading = ref(false)
const saving = ref(false)
const visible = ref(false)
const readonly = ref(false)
const rows = ref<any[]>([])
const total = ref(0)
const editingId = ref<number>()
const options = reactive<any>({ suppliers: [], settlement_methods: [], accounts: [] })
const query = reactive({ page: 1, limit: 20, supplier_id: undefined, status: '' })
const form = reactive<any>({
  payment_date: dayjs().format('YYYY-MM-DD'),
  supplier_id: undefined,
  settlement_method_id: undefined,
  fund_account_id: undefined,
  amount: 0,
  remark: '',
  allocations: []
})

const money = (value: any) => Number(value || 0).toFixed(2)
const supplierName = (id: number) =>
  options.suppliers.find((x: any) => x.value === id)?.label || `供应商 #${id}`
const allocatedTotal = computed(() =>
  form.allocations.reduce((sum: number, item: any) => sum + Number(item.amount || 0), 0)
)
const payableStatus: any = {
  open: ['未结清', 'warning'],
  partial: ['部分核销', 'info'],
  settled: ['已结清', 'success'],
  voided: ['已冲销', 'info']
}

/** 加载供应商和结算方式选项。 */
const loadOptions = async () => {
  const [res, finance] = await Promise.all([getPurchaseOptionsApi(), getFinanceOptionsApi()])
  options.suppliers = res.data?.suppliers || []
  options.settlement_methods = res.data?.settlement_methods || []
  options.accounts = finance.data?.accounts || []
}

/** 加载应付开放项或供应商付款单。 */
const loadList = async () => {
  loading.value = true
  try {
    const params = { ...query }
    const res =
      activeTab.value === 'payables'
        ? await getPayableListApi(params)
        : await getPurchasePaymentListApi(params)
    rows.value = res.data || []
    total.value = res.count || 0
  } finally {
    loading.value = false
  }
}

/** 切换页签后重置分页和状态。 */
const tabChanged = () => {
  Object.assign(query, { page: 1, status: '' })
  loadList()
}

/** 重置付款单表单。 */
const reset = () => {
  editingId.value = undefined
  readonly.value = false
  Object.assign(form, {
    payment_date: dayjs().format('YYYY-MM-DD'),
    supplier_id: undefined,
    settlement_method_id: undefined,
    fund_account_id: undefined,
    amount: 0,
    remark: '',
    allocations: []
  })
}

/** 加载指定供应商全部未付项目。 */
const loadOpenPayables = async () => {
  form.allocations = []
  if (!form.supplier_id) return
  const res = await getPayableListApi({ page: 1, limit: 100, supplier_id: form.supplier_id })
  form.allocations = (res.data || [])
    .filter((x: any) => Number(x.outstanding_amount) > 0)
    .map((x: any) => ({
      payable_id: x.id,
      payable_no: x.payable_no,
      receipt_no: x.receipt_no,
      due_date: x.due_date,
      outstanding_amount: Number(x.outstanding_amount),
      amount: 0
    }))
}

/** 打开新增付款单。 */
const create = () => {
  reset()
  visible.value = true
}

/** 打开付款单详情并还原核销分配。 */
const open = async (row: any) => {
  reset()
  const res = await getPurchasePaymentApi(row.id)
  const data = res.data
  editingId.value = row.id
  readonly.value = data.status !== 'draft'
  Object.assign(form, data)
  const savedAllocations = data.allocations || []
  await loadOpenPayables()
  const amounts = new Map(savedAllocations.map((x: any) => [x.payable_id, Number(x.amount)]))
  savedAllocations.forEach((saved: any) => {
    if (!form.allocations.some((item: any) => item.payable_id === saved.payable_id)) {
      form.allocations.push({
        ...saved,
        outstanding_amount: Number(saved.outstanding_amount || 0)
      })
    }
  })
  form.allocations.forEach((x: any) => {
    x.amount = amounts.get(x.payable_id) || 0
  })
  visible.value = true
}

/** 按到期日顺序自动分配付款金额。 */
const fillAutomatically = () => {
  let remaining = Number(form.amount || 0)
  form.allocations.forEach((item: any) => {
    item.amount = Math.min(remaining, item.outstanding_amount)
    remaining = Math.max(remaining - item.amount, 0)
  })
}

/** 保存付款草稿。 */
const save = async () => {
  if (!form.payment_date || !form.supplier_id || Number(form.amount) <= 0)
    return ElMessage.warning('请填写供应商、付款日期和金额')
  if (allocatedTotal.value > Number(form.amount))
    return ElMessage.warning('核销金额不能大于付款金额')
  const data = {
    payment_date: form.payment_date,
    supplier_id: form.supplier_id,
    settlement_method_id: form.settlement_method_id || null,
    fund_account_id: form.fund_account_id || null,
    amount: Number(form.amount),
    remark: form.remark || null,
    allocations: form.allocations
      .filter((x: any) => Number(x.amount) > 0)
      .map((x: any) => ({ payable_id: x.payable_id, amount: Number(x.amount) }))
  }
  saving.value = true
  try {
    editingId.value
      ? await putPurchasePaymentApi(editingId.value, data)
      : await addPurchasePaymentApi(data)
    ElMessage.success('保存成功')
    visible.value = false
    await loadList()
  } finally {
    saving.value = false
  }
}

/** 审核或反审核付款及全部应付核销。 */
const action = async (row: any, approve: boolean) => {
  const label = approve ? '审核' : '反审核'
  await ElMessageBox.confirm(
    `${label}将${approve ? '正式核销' : '撤销'}供应商应付，确定继续吗？`,
    `${label}确认`,
    { type: 'warning' }
  )
  approve ? await approvePurchasePaymentApi(row.id) : await unapprovePurchasePaymentApi(row.id)
  ElMessage.success(`${label}成功`)
  await loadList()
}

/** 删除付款草稿。 */
const remove = async (row: any) => {
  await ElMessageBox.confirm(`确定删除 ${row.payment_no} 吗？`, '删除确认', { type: 'warning' })
  await delPurchasePaymentApi([row.id])
  await loadList()
}

onMounted(async () => {
  await loadOptions()
  await loadList()
})
</script>

<template>
  <ContentWrap>
    <el-tabs v-model="activeTab" @tab-change="tabChanged"
      ><el-tab-pane label="应付账款" name="payables" /><el-tab-pane
        label="采购付款"
        name="payments"
    /></el-tabs>
    <div class="toolbar">
      <el-select v-model="query.supplier_id" placeholder="供应商" filterable clearable
        ><el-option v-for="item in options.suppliers" :key="item.value" v-bind="item"
      /></el-select>
      <el-select v-model="query.status" placeholder="状态" clearable
        ><template v-if="activeTab === 'payables'"
          ><el-option label="未结清" value="open" /><el-option
            label="部分核销"
            value="partial" /><el-option label="已结清" value="settled" /></template
        ><template v-else
          ><el-option label="草稿" value="draft" /><el-option
            label="已审核"
            value="approved" /></template
      ></el-select>
      <el-button type="primary" @click="loadList">查询</el-button
      ><el-button v-if="activeTab === 'payments'" type="success" @click="create"
        >新增付款</el-button
      >
    </div>
    <el-table v-if="activeTab === 'payables'" v-loading="loading" :data="rows" border stripe>
      <el-table-column prop="payable_no" label="应付单号" min-width="180" /><el-table-column
        prop="receipt_no"
        label="采购收货单"
        min-width="170"
      /><el-table-column label="供应商" min-width="190"
        ><template #default="scope">{{
          supplierName(scope.row.supplier_id)
        }}</template></el-table-column
      ><el-table-column prop="business_date" label="业务日期" width="115" /><el-table-column
        prop="due_date"
        label="到期日"
        width="115"
      /><el-table-column label="原始金额" width="120" align="right"
        ><template #default="scope"
          >¥ {{ money(scope.row.original_amount) }}</template
        ></el-table-column
      ><el-table-column label="已退金额" width="115" align="right"
        ><template #default="scope"
          >¥ {{ money(scope.row.returned_amount) }}</template
        ></el-table-column
      ><el-table-column label="已付金额" width="115" align="right"
        ><template #default="scope"
          >¥ {{ money(scope.row.settled_amount) }}</template
        ></el-table-column
      ><el-table-column label="未付金额" width="125" align="right"
        ><template #default="scope"
          ><b>¥ {{ money(scope.row.outstanding_amount) }}</b></template
        ></el-table-column
      ><el-table-column label="状态" width="100"
        ><template #default="scope"
          ><el-tag :type="payableStatus[scope.row.status]?.[1]">{{
            payableStatus[scope.row.status]?.[0]
          }}</el-tag></template
        ></el-table-column
      >
    </el-table>
    <el-table v-else v-loading="loading" :data="rows" border stripe>
      <el-table-column prop="payment_no" label="付款单号" min-width="180" /><el-table-column
        prop="payment_date"
        label="付款日期"
        width="115"
      /><el-table-column label="供应商" min-width="190"
        ><template #default="scope">{{
          supplierName(scope.row.supplier_id)
        }}</template></el-table-column
      ><el-table-column label="金额" width="130" align="right"
        ><template #default="scope">¥ {{ money(scope.row.amount) }}</template></el-table-column
      ><el-table-column label="状态" width="100"
        ><template #default="scope"
          ><el-tag :type="scope.row.status === 'approved' ? 'success' : 'info'">{{
            scope.row.status === 'approved' ? '已审核' : '草稿'
          }}</el-tag></template
        ></el-table-column
      ><el-table-column label="操作" width="245"
        ><template #default="scope"
          ><el-button link type="primary" @click="open(scope.row)">{{
            scope.row.status === 'draft' ? '编辑' : '查看'
          }}</el-button
          ><el-button
            v-if="scope.row.status === 'draft'"
            link
            type="success"
            @click="action(scope.row, true)"
            >审核</el-button
          ><el-button v-else link type="warning" @click="action(scope.row, false)">反审核</el-button
          ><el-button
            v-if="scope.row.status === 'draft'"
            link
            type="danger"
            @click="remove(scope.row)"
            >删除</el-button
          ></template
        ></el-table-column
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
    title="供应商付款"
    fullscreen
    destroy-on-close
    class="erp-document-dialog"
  >
    <el-form label-width="90px" :disabled="readonly" class="erp-document-header"
      ><el-row :gutter="16"
        ><el-col :span="12"
          ><el-form-item label="付款日期"
            ><el-date-picker
              v-model="form.payment_date"
              value-format="YYYY-MM-DD" /></el-form-item></el-col
        ><el-col :span="12"
          ><el-form-item label="供应商"
            ><el-select
              v-model="form.supplier_id"
              filterable
              style="width: 100%"
              :disabled="!!editingId"
              @change="loadOpenPayables"
              ><el-option
                v-for="item in options.suppliers"
                :key="item.value"
                v-bind="item" /></el-select></el-form-item></el-col
        ><el-col :span="12"
          ><el-form-item label="结算方式"
            ><el-select v-model="form.settlement_method_id" clearable style="width: 100%"
              ><el-option
                v-for="item in options.settlement_methods"
                :key="item.value"
                v-bind="item" /></el-select></el-form-item></el-col
        ><el-col :span="12"
          ><el-form-item label="付款金额"
            ><el-input-number v-model="form.amount" :min="0" :controls="false" /><el-button
              link
              type="primary"
              @click="fillAutomatically"
              >自动核销</el-button
            ></el-form-item
          ></el-col
        ><el-col :span="12"
          ><el-form-item label="付款账户"
            ><el-select v-model="form.fund_account_id" style="width: 100%"
              ><el-option
                v-for="item in options.accounts"
                :key="item.value"
                v-bind="item" /></el-select></el-form-item></el-col></el-row
    ></el-form>
    <el-table :data="form.allocations" border class="erp-document-table"
      ><el-table-column prop="payable_no" label="应付单号" min-width="170" /><el-table-column
        prop="receipt_no"
        label="收货单号"
        min-width="160" /><el-table-column
        prop="due_date"
        label="到期日"
        width="115" /><el-table-column label="未付金额" width="120" align="right"
        ><template #default="scope">{{
          money(scope.row.outstanding_amount)
        }}</template></el-table-column
      ><el-table-column label="本次核销" width="145"
        ><template #default="scope"
          ><el-input-number
            v-model="scope.row.amount"
            :min="0"
            :max="scope.row.outstanding_amount"
            :controls="false"
            :disabled="readonly" /></template></el-table-column
    ></el-table>
    <div class="allocated"
      >已分配：¥ {{ money(allocatedTotal) }} / 付款：¥ {{ money(form.amount) }}</div
    >
    <el-form label-width="90px" :disabled="readonly"
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
.toolbar .el-select {
  width: 210px;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
.allocated {
  margin: 12px 0;
  text-align: right;
  font-weight: 600;
}
</style>
