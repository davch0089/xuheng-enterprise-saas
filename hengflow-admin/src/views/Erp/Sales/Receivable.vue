<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ContentWrap } from '@/components/ContentWrap'
import '@/styles/erp-document.css'
import {
  addSalesReceiptApi,
  approveSalesReceiptApi,
  delSalesReceiptApi,
  getReceivableListApi,
  getSalesOptionsApi,
  getSalesReceiptApi,
  getSalesReceiptListApi,
  putSalesReceiptApi,
  unapproveSalesReceiptApi
} from '@/api/erp/sales'
import { getFinanceOptionsApi } from '@/api/erp/finance'

defineOptions({ name: 'ErpSalesReceivable' })

interface Option {
  value: number
  label: string
}
interface Allocation {
  receivable_id: number
  receivable_no: string
  delivery_no: string
  outstanding_amount: number
  allocatable_amount: number
  amount: number
}

const activeTab = ref('receivables')
const loading = ref(false)
const saving = ref(false)
const rows = ref<any[]>([])
const total = ref(0)
const dialogVisible = ref(false)
const editingId = ref<number>()
const readonly = ref(false)
const options = reactive<{ customers: Option[]; settlement_methods: Option[]; accounts: Option[] }>(
  {
    customers: [],
    settlement_methods: [],
    accounts: []
  }
)
const query = reactive({
  page: 1,
  limit: 20,
  customer_id: undefined as number | undefined,
  status: ''
})
const form = reactive<any>({
  receipt_date: dayjs().format('YYYY-MM-DD'),
  customer_id: undefined,
  settlement_method_id: undefined,
  fund_account_id: undefined,
  amount: 0,
  remark: '',
  allocations: [] as Allocation[]
})

const money = (value: any) => Number(value || 0).toFixed(2)
const customerName = (id: number) =>
  options.customers.find((x) => x.value === id)?.label || `客户 #${id}`
const allocatedTotal = computed(() =>
  form.allocations.reduce((sum: number, item: Allocation) => sum + Number(item.amount || 0), 0)
)
const receiptStatus: Record<string, { label: string; type: 'info' | 'success' }> = {
  draft: { label: '草稿', type: 'info' },
  approved: { label: '已审核', type: 'success' }
}
const arStatus: Record<string, { label: string; type: 'warning' | 'success' | 'info' }> = {
  open: { label: '未结清', type: 'warning' },
  partial: { label: '部分核销', type: 'info' },
  settled: { label: '已结清', type: 'success' }
}

/** 加载客户和结算方式下拉选项。 */
const loadOptions = async () => {
  const [res, finance] = await Promise.all([getSalesOptionsApi(), getFinanceOptionsApi()])
  options.customers = res.data?.customers || []
  options.settlement_methods = res.data?.settlement_methods || []
  options.accounts = finance.data?.accounts || []
}

/** 加载应收开放项或销售收款单分页列表。 */
const loadList = async () => {
  loading.value = true
  try {
    const params: any = { page: query.page, limit: query.limit }
    if (query.customer_id) params.customer_id = query.customer_id
    if (query.status) params.status = query.status
    const res =
      activeTab.value === 'receivables'
        ? await getReceivableListApi(params)
        : await getSalesReceiptListApi(params)
    rows.value = res.data || []
    total.value = res.count || 0
  } finally {
    loading.value = false
  }
}

/** 从第一页执行当前页签的列表查询。 */
const searchList = () => {
  query.page = 1
  loadList()
}

/** 清空查询条件并重新加载列表。 */
const resetQuery = () => {
  Object.assign(query, { customer_id: undefined, status: '', page: 1 })
  loadList()
}

/** 页签切换后重置状态筛选并读取对应列表。 */
const tabChanged = () => {
  Object.assign(query, { page: 1, status: '' })
  loadList()
}

/** 重置收款单表单和编辑上下文。 */
const resetForm = () => {
  editingId.value = undefined
  readonly.value = false
  Object.assign(form, {
    receipt_date: dayjs().format('YYYY-MM-DD'),
    customer_id: undefined,
    settlement_method_id: undefined,
    fund_account_id: undefined,
    amount: 0,
    remark: '',
    allocations: []
  })
}

/** 加载开放应收，并合并当前收款单已经保存的核销明细。 */
const loadOpenReceivables = async (savedAllocations: any[] = []) => {
  form.allocations = []
  if (!form.customer_id) return
  const res = await getReceivableListApi({ page: 1, limit: 100, customer_id: form.customer_id })
  const receivables = res.data || []
  const receivableCatalog = new Map<number, any>(receivables.map((item: any) => [item.id, item]))
  const openAllocations = receivables
    .filter((x: any) => Number(x.outstanding_amount) > 0)
    .map((x: any) => ({
      receivable_id: x.id,
      receivable_no: x.receivable_no,
      delivery_no: x.delivery_no,
      outstanding_amount: Number(x.outstanding_amount),
      allocatable_amount: Number(x.outstanding_amount),
      amount: 0
    }))
  const allocationMap = new Map<number, Allocation>(
    openAllocations.map((item: Allocation) => [item.receivable_id, item])
  )
  savedAllocations.forEach((saved: any) => {
    const open = allocationMap.get(saved.receivable_id)
    const receivable = receivableCatalog.get(saved.receivable_id)
    const amount = Number(saved.amount || 0)
    const outstandingAmount = Number(
      open?.outstanding_amount ?? saved.outstanding_amount ?? receivable?.outstanding_amount ?? 0
    )
    allocationMap.set(saved.receivable_id, {
      receivable_id: saved.receivable_id,
      receivable_no:
        saved.receivable_no ||
        open?.receivable_no ||
        receivable?.receivable_no ||
        `应收 #${saved.receivable_id}`,
      delivery_no: saved.delivery_no || open?.delivery_no || receivable?.delivery_no || '-',
      outstanding_amount: outstandingAmount,
      allocatable_amount: readonly.value ? Math.max(outstandingAmount, amount) : outstandingAmount,
      amount
    })
  })
  const savedIds = new Set(savedAllocations.map((item: any) => item.receivable_id))
  form.allocations = [
    ...savedAllocations.map((item: any) => allocationMap.get(item.receivable_id)),
    ...(readonly.value
      ? []
      : openAllocations.filter((item: Allocation) => !savedIds.has(item.receivable_id)))
  ].filter(Boolean)
}

/** 打开新增收款单弹窗。 */
const openCreate = () => {
  resetForm()
  dialogVisible.value = true
}

/** 加载收款详情及已有核销分配。 */
const openReceipt = async (row: any, view = false) => {
  resetForm()
  const res = await getSalesReceiptApi(row.id)
  const data = res.data
  editingId.value = row.id
  readonly.value = view || data.status !== 'draft'
  Object.assign(form, data)
  await loadOpenReceivables(data.allocations || [])
  dialogVisible.value = true
}

/** 按到期顺序将收款金额自动分配到开放应收。 */
const fillAutomatically = () => {
  let remaining = Number(form.amount || 0)
  form.allocations.forEach((item: Allocation) => {
    item.amount = Math.min(remaining, item.outstanding_amount)
    remaining = Math.max(remaining - item.amount, 0)
  })
}

/** 保存新增或修改后的收款草稿。 */
const save = async () => {
  if (!form.customer_id || !form.receipt_date || Number(form.amount) <= 0)
    return ElMessage.warning('请填写客户、收款日期和收款金额')
  if (allocatedTotal.value > Number(form.amount))
    return ElMessage.warning('核销金额不能大于收款金额')
  saving.value = true
  try {
    const data = {
      receipt_date: form.receipt_date,
      customer_id: form.customer_id,
      settlement_method_id: form.settlement_method_id || null,
      fund_account_id: form.fund_account_id || null,
      amount: Number(form.amount),
      remark: form.remark || null,
      allocations: form.allocations
        .filter((x: Allocation) => Number(x.amount) > 0)
        .map((x: Allocation) => ({ receivable_id: x.receivable_id, amount: Number(x.amount) }))
    }
    editingId.value
      ? await putSalesReceiptApi(editingId.value, data)
      : await addSalesReceiptApi(data)
    ElMessage.success('保存成功')
    dialogVisible.value = false
    await loadList()
  } finally {
    saving.value = false
  }
}

/** 审核收款并正式核销应收。 */
const approve = async (row: any) => {
  await ElMessageBox.confirm('审核后将正式核销客户应收，确定继续吗？', '审核确认', {
    type: 'warning'
  })
  await approveSalesReceiptApi(row.id)
  ElMessage.success('审核成功')
  await loadList()
}

/** 反审核收款并撤销核销。 */
const unapprove = async (row: any) => {
  await ElMessageBox.confirm('反审核将撤销全部核销记录，确定继续吗？', '反审核确认', {
    type: 'warning'
  })
  await unapproveSalesReceiptApi(row.id)
  ElMessage.success('反审核成功')
  await loadList()
}

/** 删除尚未审核的收款草稿。 */
const remove = async (row: any) => {
  await ElMessageBox.confirm(`确定删除草稿 ${row.receipt_no} 吗？`, '删除确认', { type: 'warning' })
  await delSalesReceiptApi([row.id])
  ElMessage.success('删除成功')
  await loadList()
}

onMounted(async () => {
  await loadOptions()
  await loadList()
})
</script>

<template>
  <ContentWrap>
    <el-tabs v-model="activeTab" @tab-change="tabChanged">
      <el-tab-pane label="应收账款" name="receivables" />
      <el-tab-pane label="销售收款" name="receipts" />
    </el-tabs>
    <div class="toolbar">
      <el-select
        v-model="query.customer_id"
        placeholder="客户"
        filterable
        clearable
        class="customer"
        ><el-option
          v-for="item in options.customers"
          :key="item.value"
          :label="item.label"
          :value="item.value"
      /></el-select>
      <el-select v-model="query.status" placeholder="状态" clearable class="status">
        <el-option
          v-for="(item, key) in activeTab === 'receivables' ? arStatus : receiptStatus"
          :key="key"
          :label="item.label"
          :value="key"
        />
      </el-select>
      <el-button type="primary" @click="searchList">查询</el-button>
      <el-button @click="resetQuery">重置</el-button>
      <el-button v-if="activeTab === 'receipts'" type="success" @click="openCreate"
        >新增收款单</el-button
      >
    </div>

    <el-table v-if="activeTab === 'receivables'" v-loading="loading" :data="rows" border stripe>
      <el-table-column prop="receivable_no" label="应收单号" min-width="170" />
      <el-table-column prop="delivery_no" label="销售出库单" min-width="160" />
      <el-table-column label="客户" min-width="170"
        ><template #default="scope">{{
          customerName(scope.row.customer_id)
        }}</template></el-table-column
      >
      <el-table-column prop="business_date" label="业务日期" width="115" />
      <el-table-column prop="due_date" label="到期日" width="115" />
      <el-table-column label="原始应收" width="120" align="right"
        ><template #default="scope"
          >¥ {{ money(scope.row.original_amount) }}</template
        ></el-table-column
      >
      <el-table-column label="已退货" width="110" align="right"
        ><template #default="scope"
          >¥ {{ money(scope.row.returned_amount) }}</template
        ></el-table-column
      >
      <el-table-column label="已核销" width="110" align="right"
        ><template #default="scope"
          >¥ {{ money(scope.row.settled_amount) }}</template
        ></el-table-column
      >
      <el-table-column label="未结余额" width="120" align="right"
        ><template #default="scope"
          ><b>¥ {{ money(scope.row.outstanding_amount) }}</b></template
        ></el-table-column
      >
      <el-table-column label="状态" width="100"
        ><template #default="scope"
          ><el-tag :type="arStatus[scope.row.status]?.type">{{
            arStatus[scope.row.status]?.label || scope.row.status
          }}</el-tag></template
        ></el-table-column
      >
    </el-table>

    <el-table v-else v-loading="loading" :data="rows" border stripe>
      <el-table-column prop="receipt_no" label="收款单号" min-width="170" />
      <el-table-column prop="receipt_date" label="收款日期" width="115" />
      <el-table-column label="客户" min-width="180"
        ><template #default="scope">{{
          customerName(scope.row.customer_id)
        }}</template></el-table-column
      >
      <el-table-column label="收款金额" width="130" align="right"
        ><template #default="scope"
          ><b>¥ {{ money(scope.row.amount) }}</b></template
        ></el-table-column
      >
      <el-table-column prop="remark" label="备注" min-width="180" show-overflow-tooltip />
      <el-table-column label="状态" width="100"
        ><template #default="scope"
          ><el-tag :type="receiptStatus[scope.row.status]?.type">{{
            receiptStatus[scope.row.status]?.label
          }}</el-tag></template
        ></el-table-column
      >
      <el-table-column label="操作" width="250" fixed="right"
        ><template #default="scope">
          <el-button
            link
            type="primary"
            @click="openReceipt(scope.row, scope.row.status !== 'draft')"
            >{{ scope.row.status === 'draft' ? '编辑' : '查看' }}</el-button
          >
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
    v-model="dialogVisible"
    :title="`${editingId ? (readonly ? '查看' : '编辑') : '新增'}收款单`"
    fullscreen
    class="erp-document-dialog"
    destroy-on-close
  >
    <el-form label-width="90px" :disabled="readonly">
      <el-row :gutter="16">
        <el-col :span="12"
          ><el-form-item label="客户" required
            ><el-select
              v-model="form.customer_id"
              filterable
              class="full"
              @change="() => loadOpenReceivables()"
              ><el-option
                v-for="item in options.customers"
                :key="item.value"
                :label="item.label"
                :value="item.value" /></el-select></el-form-item
        ></el-col>
        <el-col :span="12"
          ><el-form-item label="收款日期" required
            ><el-date-picker
              v-model="form.receipt_date"
              value-format="YYYY-MM-DD"
              class="full" /></el-form-item
        ></el-col>
        <el-col :span="12"
          ><el-form-item label="结算方式"
            ><el-select v-model="form.settlement_method_id" clearable class="full"
              ><el-option
                v-for="item in options.settlement_methods"
                :key="item.value"
                :label="item.label"
                :value="item.value" /></el-select></el-form-item
        ></el-col>
        <el-col :span="12"
          ><el-form-item label="收款金额" required
            ><el-input-number
              v-model="form.amount"
              :min="0"
              :precision="2"
              :controls="false"
              class="full" /></el-form-item
        ></el-col>
        <el-col :span="12"
          ><el-form-item label="收款账户" required
            ><el-select v-model="form.fund_account_id" class="full"
              ><el-option
                v-for="item in options.accounts"
                :key="item.value"
                :label="item.label"
                :value="item.value" /></el-select></el-form-item
        ></el-col>
      </el-row>
      <el-form-item label="核销明细">
        <div class="allocation-box">
          <div class="allocation-head"
            ><span>不填写时，审核将按到期日 FIFO 自动核销。</span
            ><el-button v-if="!readonly" link type="primary" @click="fillAutomatically"
              >自动分配</el-button
            ></div
          >
          <el-table :data="form.allocations" border class="erp-document-table">
            <el-table-column prop="receivable_no" label="应收单号" min-width="160" />
            <el-table-column prop="delivery_no" label="出库单号" min-width="150" />
            <el-table-column label="未结余额" width="120" align="right"
              ><template #default="scope">{{
                money(scope.row.outstanding_amount)
              }}</template></el-table-column
            >
            <el-table-column label="本次核销" width="150"
              ><template #default="scope"
                ><el-input-number
                  v-model="scope.row.amount"
                  :disabled="readonly"
                  :min="0"
                  :max="scope.row.allocatable_amount"
                  :precision="2"
                  :controls="false"
                  class="full" /></template
            ></el-table-column>
          </el-table>
          <div class="allocation-total"
            >已分配 ¥ {{ money(allocatedTotal) }} / 收款 ¥ {{ money(form.amount) }}</div
          >
        </div>
      </el-form-item>
      <el-form-item label="备注"
        ><el-input v-model="form.remark" type="textarea" :rows="2"
      /></el-form-item>
    </el-form>
    <template #footer
      ><el-button @click="dialogVisible = false">关闭</el-button
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
.customer {
  width: 240px;
}
.status {
  width: 140px;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
.full {
  width: 100%;
}
.allocation-box {
  width: 100%;
}
.allocation-head,
.allocation-total {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}
.allocation-total {
  justify-content: flex-end;
  margin: 8px 0 0;
  font-weight: 600;
}
</style>
