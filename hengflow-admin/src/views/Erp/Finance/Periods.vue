<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ContentWrap } from '@/components/ContentWrap'
import {
  addAccountingPeriodApi,
  closeAccountingPeriodApi,
  getAccountingPeriodsApi,
  reopenAccountingPeriodApi,
  validatePeriodCostApi
} from '@/api/erp/finance'
defineOptions({ name: 'ErpFinancePeriods' })
const rows = ref<any[]>([]),
  visible = ref(false),
  loading = ref(false)
const form = reactive<any>({
  period_code: dayjs().format('YYYY-MM'),
  start_date: dayjs().startOf('month').format('YYYY-MM-DD'),
  end_date: dayjs().endOf('month').format('YYYY-MM-DD'),
  remark: ''
})
const load = async () => {
  loading.value = true
  try {
    const r = await getAccountingPeriodsApi()
    rows.value = r.data || []
  } finally {
    loading.value = false
  }
}
const create = () => {
  Object.assign(form, {
    period_code: dayjs().format('YYYY-MM'),
    start_date: dayjs().startOf('month').format('YYYY-MM-DD'),
    end_date: dayjs().endOf('month').format('YYYY-MM-DD'),
    remark: ''
  })
  visible.value = true
}
const save = async () => {
  await addAccountingPeriodApi(form)
  ElMessage.success('会计期间已启用')
  visible.value = false
  await load()
}
const close = async (row: any) => {
  await ElMessageBox.confirm(
    '结账将禁止本期间业务修改和冲销，并执行成本期末校验，确定继续？',
    '结账确认',
    { type: 'warning' }
  )
  await closeAccountingPeriodApi(row.id)
  ElMessage.success('结账成功')
  await load()
}
const reopen = async (row: any) => {
  await ElMessageBox.confirm('确定反结账并重新开放本期间？', '反结账确认', { type: 'warning' })
  await reopenAccountingPeriodApi(row.id)
  ElMessage.success('反结账成功')
  await load()
}
const validate = async (row: any) => {
  const r = await validatePeriodCostApi(row.end_date)
  ElMessage.success(`成本校验通过，共检查 ${r.data?.checked_balances || 0} 个库存成本余额`)
}
onMounted(load)
</script>
<template>
  <ContentWrap
    ><div class="toolbar"><el-button type="primary" @click="create">启用会计期间</el-button></div
    ><el-alert
      title="启用第一个会计期间后，所有库存、成本、资金和核销过账都必须处于开放期间；结账前会检查未完成单据及库存成本一致性。"
      type="info"
      show-icon
    /><el-table v-loading="loading" :data="rows" border stripe
      ><el-table-column prop="period_code" label="期间" /><el-table-column
        prop="start_date"
        label="开始日期"
      /><el-table-column prop="end_date" label="结束日期" /><el-table-column label="状态"
        ><template #default="s"
          ><el-tag :type="s.row.status === 'open' ? 'success' : 'info'">{{
            s.row.status === 'open' ? '已启用' : '已结账'
          }}</el-tag></template
        ></el-table-column
      ><el-table-column prop="closed_at" label="结账时间" /><el-table-column
        label="操作"
        width="250"
        ><template #default="s"
          ><el-button link type="primary" @click="validate(s.row)">成本校验</el-button
          ><el-button v-if="s.row.status === 'open'" link type="success" @click="close(s.row)"
            >结账</el-button
          ><el-button v-else link type="warning" @click="reopen(s.row)">反结账</el-button></template
        ></el-table-column
      ></el-table
    ></ContentWrap
  ><el-dialog v-model="visible" title="启用会计期间" width="550px"
    ><el-form label-width="100px"
      ><el-form-item label="期间编码"><el-input v-model="form.period_code" /></el-form-item
      ><el-form-item label="开始日期"
        ><el-date-picker v-model="form.start_date" value-format="YYYY-MM-DD" /></el-form-item
      ><el-form-item label="结束日期"
        ><el-date-picker v-model="form.end_date" value-format="YYYY-MM-DD" /></el-form-item
      ><el-form-item label="备注"
        ><el-input v-model="form.remark" type="textarea" /></el-form-item></el-form
    ><template #footer
      ><el-button @click="visible = false">取消</el-button
      ><el-button type="primary" @click="save">启用</el-button></template
    ></el-dialog
  >
</template>
<style scoped>
.toolbar {
  margin-bottom: 12px;
}
.el-alert {
  margin-bottom: 14px;
}
</style>
