<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ContentWrap } from '@/components/ContentWrap'
import '@/styles/erp-document.css'
import {
  addFundDocumentApi,
  approveFundDocumentApi,
  delFundDocumentsApi,
  getFinanceOptionsApi,
  getFundDocumentsApi,
  getFundLedgersApi,
  putFundDocumentApi,
  unapproveFundDocumentApi
} from '@/api/erp/finance'

defineOptions({ name: 'ErpFinanceFunds' })
const tab = ref('documents'),
  loading = ref(false),
  visible = ref(false)
const rows = ref<any[]>([]),
  total = ref(0),
  editingId = ref<number>()
const options = reactive<any>({ accounts: [] })
const query = reactive<any>({
  page: 1,
  limit: 20,
  document_type: '',
  status: '',
  account_id: undefined
})
const form = reactive<any>({
  document_type: 'receipt',
  business_date: dayjs().format('YYYY-MM-DD'),
  amount: 0,
  profit_category: 'none'
})
const types: any = { receipt: '收款', payment: '付款', transfer: '转账' }
const money = (v: any) => Number(v || 0).toFixed(2)
const accountName = (id: number) => options.accounts.find((x: any) => x.value === id)?.label || '-'
const loadOptions = async () => {
  const r = await getFinanceOptionsApi()
  options.accounts = r.data?.accounts || []
}
const load = async () => {
  loading.value = true
  try {
    if (tab.value === 'ledgers') {
      const r = await getFundLedgersApi(query)
      rows.value = r.data || []
      total.value = r.count || 0
    } else {
      const r = await getFundDocumentsApi(query)
      rows.value = r.data || []
      total.value = r.count || 0
    }
  } finally {
    loading.value = false
  }
}
const create = () => {
  editingId.value = undefined
  Object.assign(form, {
    document_type: 'receipt',
    business_date: dayjs().format('YYYY-MM-DD'),
    from_account_id: undefined,
    to_account_id: undefined,
    amount: 0,
    counterparty: '',
    profit_category: 'none',
    remark: ''
  })
  visible.value = true
}
const edit = (row: any) => {
  editingId.value = row.id
  Object.assign(form, row)
  visible.value = true
}
const save = async () => {
  editingId.value ? await putFundDocumentApi(editingId.value, form) : await addFundDocumentApi(form)
  ElMessage.success('保存成功')
  visible.value = false
  await load()
}
const action = async (row: any, approve: boolean) => {
  await ElMessageBox.confirm(
    `确定${approve ? '审核过账' : '反审核冲销'} ${row.document_no} 吗？`,
    '确认',
    { type: 'warning' }
  )
  approve ? await approveFundDocumentApi(row.id) : await unapproveFundDocumentApi(row.id)
  await Promise.all([loadOptions(), load()])
}
const remove = async (row: any) => {
  await ElMessageBox.confirm(`删除 ${row.document_no}？`, '确认', { type: 'warning' })
  await delFundDocumentsApi([row.id])
  await load()
}
onMounted(async () => {
  await loadOptions()
  await load()
})
</script>
<template>
  <ContentWrap>
    <el-tabs v-model="tab" @tab-change="load"
      ><el-tab-pane label="资金单据" name="documents" /><el-tab-pane
        label="不可变流水"
        name="ledgers"
    /></el-tabs>
    <div class="toolbar"
      ><el-select
        v-if="tab === 'documents'"
        v-model="query.document_type"
        clearable
        placeholder="单据类型"
        ><el-option
          v-for="(label, key) in types"
          :key="key"
          :label="label"
          :value="key" /></el-select
      ><el-select
        v-if="tab === 'ledgers'"
        v-model="query.account_id"
        clearable
        placeholder="资金账户"
        ><el-option v-for="x in options.accounts" :key="x.value" v-bind="x" /></el-select
      ><el-button type="primary" @click="load">查询</el-button
      ><el-button v-if="tab === 'documents'" type="success" @click="create"
        >新增收付/转账</el-button
      ></div
    >
    <el-table v-loading="loading" :data="rows" border stripe>
      <template v-if="tab === 'ledgers'"
        ><el-table-column prop="entry_no" label="流水号" min-width="200" /><el-table-column
          prop="occurred_at"
          label="发生时间"
          width="170"
        /><el-table-column prop="entry_type" label="类型" /><el-table-column label="账户"
          ><template #default="s">{{ accountName(s.row.account_id) }}</template></el-table-column
        ><el-table-column prop="source_no" label="来源单号" /><el-table-column
          label="金额"
          align="right"
          ><template #default="s">{{ money(s.row.amount) }}</template></el-table-column
        ><el-table-column label="余额" align="right"
          ><template #default="s">{{ money(s.row.balance_after) }}</template></el-table-column
        ></template
      >
      <template v-else
        ><el-table-column prop="document_no" label="单据号" min-width="170" /><el-table-column
          prop="business_date"
          label="日期"
        /><el-table-column label="类型"
          ><template #default="s">{{ types[s.row.document_type] }}</template></el-table-column
        ><el-table-column label="转出"
          ><template #default="s">{{
            accountName(s.row.from_account_id)
          }}</template></el-table-column
        ><el-table-column label="转入"
          ><template #default="s">{{ accountName(s.row.to_account_id) }}</template></el-table-column
        ><el-table-column label="金额" align="right"
          ><template #default="s">¥ {{ money(s.row.amount) }}</template></el-table-column
        ><el-table-column prop="status" label="状态" /><el-table-column label="操作" width="210"
          ><template #default="s"
            ><el-button v-if="s.row.status === 'draft'" link @click="edit(s.row)">编辑</el-button
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
        ></template
      > </el-table
    ><el-pagination
      v-model:current-page="query.page"
      v-model:page-size="query.limit"
      :total="total"
      layout="total, sizes, prev, pager, next"
      @change="load"
    />
  </ContentWrap>
  <el-dialog v-model="visible" title="资金单据" fullscreen class="erp-document-dialog"
    ><el-form label-width="100px" class="erp-document-header"
      ><el-form-item label="类型"
        ><el-select v-model="form.document_type"
          ><el-option
            v-for="(label, key) in types"
            :key="key"
            :label="label"
            :value="key" /></el-select></el-form-item
      ><el-form-item label="业务日期"
        ><el-date-picker v-model="form.business_date" value-format="YYYY-MM-DD" /></el-form-item
      ><el-form-item v-if="form.document_type !== 'receipt'" label="转出账户"
        ><el-select v-model="form.from_account_id"
          ><el-option
            v-for="x in options.accounts"
            :key="x.value"
            v-bind="x" /></el-select></el-form-item
      ><el-form-item v-if="form.document_type !== 'payment'" label="转入账户"
        ><el-select v-model="form.to_account_id"
          ><el-option
            v-for="x in options.accounts"
            :key="x.value"
            v-bind="x" /></el-select></el-form-item
      ><el-form-item label="金额"
        ><el-input-number v-model="form.amount" :min="0" :precision="2" /></el-form-item
      ><el-form-item v-if="form.document_type === 'payment'" label="利润分类"
        ><el-select v-model="form.profit_category"
          ><el-option label="不影响经营利润" value="none" /><el-option
            label="变动费用"
            value="variable_expense" /><el-option
            label="固定费用"
            value="fixed_expense" /></el-select></el-form-item
      ><el-form-item label="对方单位"><el-input v-model="form.counterparty" /></el-form-item
      ><el-form-item label="备注"
        ><el-input v-model="form.remark" type="textarea" /></el-form-item></el-form
    ><template #footer
      ><el-button @click="visible = false">取消</el-button
      ><el-button type="primary" @click="save">保存</el-button></template
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
