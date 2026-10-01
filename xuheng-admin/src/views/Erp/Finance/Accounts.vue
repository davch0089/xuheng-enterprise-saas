<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ContentWrap } from '@/components/ContentWrap'
import { addFundAccountApi, getFundAccountsApi, putFundAccountApi } from '@/api/erp/finance'

defineOptions({ name: 'ErpFinanceAccounts' })

const loading = ref(false)
const saving = ref(false)
const visible = ref(false)
const editingId = ref<number>()
const rows = ref<any[]>([])
const query = reactive({ keyword: '', account_type: '', active: '' })
const form = reactive<any>({})
const accountTypes: Record<string, string> = {
  bank: '银行账户',
  cash: '现金账户',
  third_party: '第三方支付'
}

/** 格式化资金金额。 */
const money = (value: any) => Number(value || 0).toFixed(2)

/** 读取账户，并在前端完成轻量筛选。 */
const load = async () => {
  loading.value = true
  try {
    const res = await getFundAccountsApi()
    const keyword = query.keyword.trim().toLowerCase()
    rows.value = (res.data || []).filter((item: any) => {
      const matchesKeyword =
        !keyword ||
        [item.code, item.name, item.bank_name, item.account_no]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(keyword))
      const matchesType = !query.account_type || item.account_type === query.account_type
      const matchesActive = query.active === '' || item.is_active === (query.active === 'true')
      return matchesKeyword && matchesType && matchesActive
    })
  } finally {
    loading.value = false
  }
}

/** 重置筛选条件。 */
const resetQuery = () => {
  Object.assign(query, { keyword: '', account_type: '', active: '' })
  load()
}

/** 打开新增资金账户弹窗。 */
const createAccount = () => {
  editingId.value = undefined
  Object.assign(form, {
    code: '',
    name: '',
    account_type: 'bank',
    currency: 'CNY',
    bank_name: '',
    account_no: '',
    opening_balance: 0,
    is_active: true,
    remark: ''
  })
  visible.value = true
}

/** 打开账户编辑弹窗；余额只展示且不允许直接调整。 */
const editAccount = (row: any) => {
  editingId.value = row.id
  Object.assign(form, row, { opening_balance: Number(row.balance || 0) })
  visible.value = true
}

/** 校验并保存资金账户，失败时保留弹窗和用户输入。 */
const saveAccount = async () => {
  if (!form.code?.trim() || !form.name?.trim()) {
    return ElMessage.warning('请填写账户编码和账户名称')
  }
  saving.value = true
  try {
    const payload = {
      ...form,
      code: form.code.trim(),
      name: form.name.trim(),
      bank_name: form.bank_name?.trim() || null,
      account_no: form.account_no?.trim() || null,
      remark: form.remark?.trim() || null
    }
    editingId.value
      ? await putFundAccountApi(editingId.value, payload)
      : await addFundAccountApi(payload)
    ElMessage.success('资金账户保存成功')
    visible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <ContentWrap>
    <div class="toolbar">
      <el-input
        v-model="query.keyword"
        clearable
        placeholder="账户编码、名称、开户行或账号"
        @keyup.enter="load"
      />
      <el-select v-model="query.account_type" clearable placeholder="账户类型">
        <el-option
          v-for="(label, value) in accountTypes"
          :key="value"
          :label="label"
          :value="value"
        />
      </el-select>
      <el-select v-model="query.active" clearable placeholder="启用状态">
        <el-option label="启用" value="true" />
        <el-option label="停用" value="false" />
      </el-select>
      <el-button type="primary" @click="load">查询</el-button>
      <el-button @click="resetQuery">重置</el-button>
      <el-button type="success" @click="createAccount">新增账户</el-button>
    </div>

    <el-alert
      title="账户余额不能直接修改，请通过收款、付款或转账单调整，以保留完整资金流水。"
      type="info"
      :closable="false"
      class="notice"
    />
    <el-table v-loading="loading" :data="rows" border stripe>
      <el-table-column prop="code" label="账户编码" min-width="120" />
      <el-table-column prop="name" label="账户名称" min-width="150" />
      <el-table-column label="类型" width="120">
        <template #default="scope">{{
          accountTypes[scope.row.account_type] || scope.row.account_type
        }}</template>
      </el-table-column>
      <el-table-column prop="currency" label="币种" width="80" />
      <el-table-column
        prop="bank_name"
        label="开户行 / 平台"
        min-width="150"
        show-overflow-tooltip
      />
      <el-table-column prop="account_no" label="账号" min-width="170" show-overflow-tooltip />
      <el-table-column label="余额" width="140" align="right">
        <template #default="scope">¥ {{ money(scope.row.balance) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="85" align="center">
        <template #default="scope">
          <el-tag :type="scope.row.is_active ? 'success' : 'info'">
            {{ scope.row.is_active ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="scope">
          <el-button link type="primary" @click="editAccount(scope.row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>
  </ContentWrap>

  <el-dialog v-model="visible" :title="editingId ? '编辑资金账户' : '新增资金账户'" width="680px">
    <el-form label-width="110px">
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="账户编码" required><el-input v-model="form.code" /></el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="账户名称" required><el-input v-model="form.name" /></el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="账户类型">
            <el-select v-model="form.account_type" class="full">
              <el-option
                v-for="(label, value) in accountTypes"
                :key="value"
                :label="label"
                :value="value"
              />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="币种"
            ><el-input v-model="form.currency" maxlength="10"
          /></el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="开户行 / 平台"><el-input v-model="form.bank_name" /></el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="账号"><el-input v-model="form.account_no" /></el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item :label="editingId ? '当前余额' : '开户余额'">
            <el-input-number
              v-model="form.opening_balance"
              :disabled="!!editingId"
              :precision="2"
              :controls="false"
              class="full"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="启用"><el-switch v-model="form.is_active" /></el-form-item>
        </el-col>
        <el-col :span="24">
          <el-form-item label="备注"
            ><el-input v-model="form.remark" type="textarea" :rows="3"
          /></el-form-item>
        </el-col>
      </el-row>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="saveAccount">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.toolbar {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
}
.toolbar .el-input {
  width: 280px;
}
.toolbar .el-select {
  width: 150px;
}
.notice {
  margin-bottom: 14px;
}
.full {
  width: 100%;
}
</style>
