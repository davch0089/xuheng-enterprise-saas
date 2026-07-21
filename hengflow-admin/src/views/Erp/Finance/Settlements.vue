<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ContentWrap } from '@/components/ContentWrap'
import '@/styles/erp-document.css'
import {
  addSettlementApi,
  approveSettlementApi,
  delSettlementsApi,
  getFinanceOpenItemsApi,
  getFinanceOptionsApi,
  getSettlementApi,
  getSettlementsApi,
  putSettlementApi,
  unapproveSettlementApi
} from '@/api/erp/finance'

defineOptions({ name: 'ErpFinanceSettlements' })
const loading = ref(false),
  visible = ref(false),
  readonly = ref(false),
  editingId = ref<number>(),
  rows = ref<any[]>([]),
  total = ref(0)
const query = reactive<any>({ page: 1, limit: 20, writeoff_type: '', status: '' })
const options = reactive<any>({
  customers: [],
  suppliers: [],
  receipts: [],
  payments: [],
  receivables: [],
  payables: []
})
const form = reactive<any>({})
const types: any = {
  advance_receipt_ar: '预收冲应收',
  advance_payment_ap: '预付冲应付',
  ar_ap_offset: '应收应付对冲'
}
const money = (v: any) => Number(v || 0).toFixed(2)
const reset = () =>
  Object.assign(form, {
    writeoff_type: 'advance_receipt_ar',
    business_date: dayjs().format('YYYY-MM-DD'),
    customer_id: undefined,
    supplier_id: undefined,
    source_receipt_id: undefined,
    source_payment_id: undefined,
    amount: 0,
    allocations: [],
    remark: ''
  })
const loadOptions = async () => {
  const r = await getFinanceOptionsApi()
  Object.assign(options, r.data || {})
}
const load = async () => {
  loading.value = true
  try {
    const r = await getSettlementsApi(query)
    rows.value = r.data || []
    total.value = r.count || 0
  } finally {
    loading.value = false
  }
}
const loadItems = async () => {
  const r = await getFinanceOpenItemsApi({
    customer_id: form.customer_id,
    supplier_id: form.supplier_id
  })
  Object.assign(options, r.data || {})
  form.allocations = [
    ...(options.receivables || []).map((x: any) => ({
      target_type: 'receivable',
      target_id: x.id,
      number: x.receivable_no,
      outstanding_amount: Number(x.outstanding_amount),
      amount: 0
    })),
    ...(options.payables || []).map((x: any) => ({
      target_type: 'payable',
      target_id: x.id,
      number: x.payable_no,
      outstanding_amount: Number(x.outstanding_amount),
      amount: 0
    }))
  ]
}
const create = async () => {
  editingId.value = undefined
  readonly.value = false
  reset()
  await loadItems()
  visible.value = true
}
const open = async (row: any) => {
  const r = await getSettlementApi(row.id)
  editingId.value = row.id
  readonly.value = r.data.status !== 'draft'
  Object.assign(form, r.data)
  await loadItems()
  const amounts = new Map(
    (r.data.allocations || []).map((x: any) => [
      `${x.target_type}:${x.target_id}`,
      Number(x.amount)
    ])
  )
  form.allocations.forEach(
    (x: any) => (x.amount = amounts.get(`${x.target_type}:${x.target_id}`) || 0)
  )
  visible.value = true
}
const changeType = async () => {
  form.source_receipt_id = undefined
  form.source_payment_id = undefined
  form.amount = 0
  await loadItems()
}
const save = async () => {
  const data = {
    ...form,
    allocations: form.allocations
      .filter((x: any) => Number(x.amount) > 0)
      .map((x: any) => ({
        target_type: x.target_type,
        target_id: x.target_id,
        amount: Number(x.amount)
      }))
  }
  editingId.value ? await putSettlementApi(editingId.value, data) : await addSettlementApi(data)
  ElMessage.success('保存成功')
  visible.value = false
  await load()
}
const action = async (row: any, approve: boolean) => {
  await ElMessageBox.confirm(
    `确定${approve ? '审核核销' : '反审核冲销'} ${row.document_no}？`,
    '确认',
    { type: 'warning' }
  )
  approve ? await approveSettlementApi(row.id) : await unapproveSettlementApi(row.id)
  await load()
}
const remove = async (row: any) => {
  await delSettlementsApi([row.id])
  await load()
}
const sourceChanged = () => {
  const list = form.writeoff_type === 'advance_receipt_ar' ? options.receipts : options.payments
  const id =
    form.writeoff_type === 'advance_receipt_ar' ? form.source_receipt_id : form.source_payment_id
  form.amount = Number(list.find((x: any) => x.id === id)?.unused_amount || 0)
}
onMounted(async () => {
  await loadOptions()
  await load()
})
</script>
<template>
  <ContentWrap
    ><div class="toolbar"
      ><el-select v-model="query.writeoff_type" clearable placeholder="核销类型"
        ><el-option
          v-for="(label, key) in types"
          :key="key"
          :label="label"
          :value="key" /></el-select
      ><el-select v-model="query.status" clearable placeholder="状态"
        ><el-option label="草稿" value="draft" /><el-option
          label="已审核"
          value="approved" /></el-select
      ><el-button type="primary" @click="load">查询</el-button
      ><el-button type="success" @click="create">新增核销</el-button></div
    ><el-table v-loading="loading" :data="rows" border stripe
      ><el-table-column prop="document_no" label="核销单号" min-width="180" /><el-table-column
        prop="business_date"
        label="日期"
      /><el-table-column label="核销类型"
        ><template #default="s">{{ types[s.row.writeoff_type] }}</template></el-table-column
      ><el-table-column label="金额" align="right"
        ><template #default="s">¥ {{ money(s.row.amount) }}</template></el-table-column
      ><el-table-column prop="status" label="状态" /><el-table-column label="操作" width="230"
        ><template #default="s"
          ><el-button link @click="open(s.row)">{{
            s.row.status === 'draft' ? '编辑' : '查看'
          }}</el-button
          ><el-button
            v-if="s.row.status === 'draft'"
            link
            type="success"
            @click="action(s.row, true)"
            >审核</el-button
          ><el-button v-else link type="warning" @click="action(s.row, false)">反审核</el-button
          ><el-button v-if="s.row.status === 'draft'" link type="danger" @click="remove(s.row)"
            >删除</el-button
          ></template
        ></el-table-column
      ></el-table
    ><el-pagination
      v-model:current-page="query.page"
      v-model:page-size="query.limit"
      :total="total"
      layout="total,sizes,prev,pager,next"
      @change="load"
  /></ContentWrap>
  <el-dialog v-model="visible" title="财务核销" fullscreen class="erp-document-dialog"
    ><el-form label-width="110px" :disabled="readonly" class="erp-document-header"
      ><el-row :gutter="16"
        ><el-col :span="8"
          ><el-form-item label="核销类型"
            ><el-select v-model="form.writeoff_type" @change="changeType"
              ><el-option
                v-for="(label, key) in types"
                :key="key"
                :label="label"
                :value="key" /></el-select></el-form-item></el-col
        ><el-col :span="8"
          ><el-form-item label="业务日期"
            ><el-date-picker
              v-model="form.business_date"
              value-format="YYYY-MM-DD" /></el-form-item></el-col
        ><el-col v-if="form.writeoff_type !== 'advance_payment_ap'" :span="8"
          ><el-form-item label="客户"
            ><el-select v-model="form.customer_id" filterable @change="loadItems"
              ><el-option
                v-for="x in options.customers"
                :key="x.value"
                v-bind="x" /></el-select></el-form-item></el-col
        ><el-col v-if="form.writeoff_type !== 'advance_receipt_ar'" :span="8"
          ><el-form-item label="供应商"
            ><el-select v-model="form.supplier_id" filterable @change="loadItems"
              ><el-option
                v-for="x in options.suppliers"
                :key="x.value"
                v-bind="x" /></el-select></el-form-item></el-col
        ><el-col v-if="form.writeoff_type === 'advance_receipt_ar'" :span="8"
          ><el-form-item label="预收来源"
            ><el-select v-model="form.source_receipt_id" @change="sourceChanged"
              ><el-option
                v-for="x in options.receipts"
                :key="x.id"
                :label="`${x.receipt_no} / 可用${money(x.unused_amount)}`"
                :value="x.id" /></el-select></el-form-item></el-col
        ><el-col v-if="form.writeoff_type === 'advance_payment_ap'" :span="8"
          ><el-form-item label="预付来源"
            ><el-select v-model="form.source_payment_id" @change="sourceChanged"
              ><el-option
                v-for="x in options.payments"
                :key="x.id"
                :label="`${x.payment_no} / 可用${money(x.unused_amount)}`"
                :value="x.id" /></el-select></el-form-item></el-col
        ><el-col :span="8"
          ><el-form-item label="核销金额"
            ><el-input-number
              v-model="form.amount"
              :min="0"
              :precision="2" /></el-form-item></el-col></el-row></el-form
    ><el-table :data="form.allocations" border class="erp-document-table"
      ><el-table-column prop="target_type" label="项目类型" width="100"
        ><template #default="s">{{
          s.row.target_type === 'receivable' ? '应收' : '应付'
        }}</template></el-table-column
      ><el-table-column prop="number" label="开放项目" /><el-table-column
        label="未结金额"
        align="right"
        ><template #default="s">{{ money(s.row.outstanding_amount) }}</template></el-table-column
      ><el-table-column label="本次核销" width="160"
        ><template #default="s"
          ><el-input-number
            v-model="s.row.amount"
            :min="0"
            :max="s.row.outstanding_amount"
            :precision="2"
            :disabled="readonly" /></template></el-table-column></el-table
    ><template #footer
      ><el-button @click="visible = false">关闭</el-button
      ><el-button v-if="!readonly" type="primary" @click="save">保存</el-button></template
    ></el-dialog
  >
</template>
<style scoped>
.toolbar {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
}
.toolbar .el-select {
  width: 190px;
}
.el-pagination {
  justify-content: flex-end;
  margin-top: 14px;
}
.el-form .el-select {
  width: 100%;
}
</style>
