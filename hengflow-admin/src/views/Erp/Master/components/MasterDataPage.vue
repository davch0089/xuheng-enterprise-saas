<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import type { FormInstance } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ContentWrap } from '@/components/ContentWrap'
import { BaseButton } from '@/components/Button'
import {
  addMasterApi,
  delMasterApi,
  getMasterApi,
  getMasterListApi,
  getMasterOptionsApi,
  putMasterApi
} from '@/api/erp/master'
import type { MasterColumn, MasterOption, MasterPageConfig } from '../types'

const props = defineProps<{ config: MasterPageConfig }>()

const loading = ref(false)
const saving = ref(false)
const rows = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const limit = ref(10)
const search = reactive<{ keyword?: string; is_active?: boolean }>({})
const options = reactive<Record<string, MasterOption[]>>({})
const dialogVisible = ref(false)
const editingId = ref<number>()
const form = ref<Record<string, any>>({})
const formRef = ref<FormInstance>()

const dialogTitle = computed(() => `${editingId.value ? '编辑' : '新增'}${props.config.title}`)
const visibleFields = computed(() =>
  props.config.fields.filter(
    (item) => !item.showWhen || form.value[item.showWhen.field] === item.showWhen.value
  )
)
const rules = computed(() => {
  const result: Record<string, any[]> = {}
  visibleFields.value
    .filter((item) => item.required)
    .forEach((item) => {
      result[item.field] = [{ required: true, message: `请填写${item.label}`, trigger: 'change' }]
    })
  return result
})

const flattenOptions = (items: MasterOption[], level = 0): MasterOption[] =>
  items.flatMap((item) => [
    { label: `${'　'.repeat(level)}${item.label}`, value: item.value },
    ...(item.children ? flattenOptions(item.children, level + 1) : [])
  ])

const loadOptions = async () => {
  const resources = [
    ...new Set(props.config.fields.map((item) => item.optionResource).filter(Boolean))
  ] as string[]
  await Promise.all(
    resources.map(async (resource) => {
      const res = await getMasterOptionsApi(resource)
      options[resource] =
        resource === 'departments' ? flattenOptions(res.data || []) : res.data || []
    })
  )
}

const loadList = async () => {
  loading.value = true
  try {
    const res = await getMasterListApi(props.config.resource, {
      page: page.value,
      limit: limit.value,
      keyword: search.keyword || undefined,
      is_active: search.is_active
    })
    rows.value = res.data || []
    total.value = res.count || 0
  } finally {
    loading.value = false
  }
}

const resetSearch = () => {
  search.keyword = undefined
  search.is_active = undefined
  page.value = 1
  loadList()
}

const searchList = () => {
  page.value = 1
  loadList()
}

const changePageSize = () => {
  page.value = 1
  loadList()
}

const newForm = () =>
  Object.fromEntries(props.config.fields.map((item) => [item.field, item.default ?? null]))

const add = () => {
  editingId.value = undefined
  form.value = newForm()
  dialogVisible.value = true
}

const edit = async (row: any) => {
  const res = await getMasterApi(props.config.resource, row.id)
  editingId.value = row.id
  form.value = { ...newForm(), ...(res.data || {}) }
  dialogVisible.value = true
}

const save = async () => {
  await formRef.value?.validate()
  saving.value = true
  try {
    if (editingId.value) {
      await putMasterApi(props.config.resource, { ...form.value, id: editingId.value })
    } else {
      await addMasterApi(props.config.resource, form.value)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    await Promise.all([loadList(), loadOptions()])
  } finally {
    saving.value = false
  }
}

const remove = async (row: any) => {
  await ElMessageBox.confirm(`确定删除“${row.name || row.code || row.id}”吗？`, '删除确认', {
    type: 'warning'
  })
  await delMasterApi(props.config.resource, [row.id])
  ElMessage.success('删除成功')
  await loadList()
}

const display = (row: any, column: MasterColumn) => {
  const value = row[column.field]
  if (column.optionResource) {
    return (
      options[column.optionResource]?.find((item) => item.value === value)?.label || value || '-'
    )
  }
  if (value === null || value === undefined || value === '') return '-'
  if (column.type === 'money') return Number(value).toFixed(2)
  return value
}

onMounted(async () => {
  await loadOptions()
  await loadList()
})
</script>

<template>
  <ContentWrap>
    <div class="master-search">
      <el-input
        v-model="search.keyword"
        clearable
        placeholder="编码、名称或联系方式"
        @keyup.enter="loadList"
      />
      <el-select v-model="search.is_active" clearable placeholder="启用状态">
        <el-option label="启用" :value="true" />
        <el-option label="停用" :value="false" />
      </el-select>
      <BaseButton type="primary" @click="searchList">查询</BaseButton>
      <BaseButton @click="resetSearch">重置</BaseButton>
    </div>
    <div class="master-toolbar">
      <BaseButton type="primary" @click="add">新增{{ config.title }}</BaseButton>
    </div>
    <el-table v-loading="loading" :data="rows" border stripe>
      <el-table-column prop="id" label="ID" width="75" />
      <el-table-column
        v-for="column in config.columns"
        :key="column.field"
        :label="column.label"
        :width="column.width"
      >
        <template #default="{ row }">
          <el-switch
            v-if="column.type === 'boolean'"
            :model-value="Boolean(row[column.field])"
            disabled
          />
          <span v-else>{{ display(row, column) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="130" fixed="right">
        <template #default="{ row }">
          <BaseButton type="primary" link @click="edit(row)">编辑</BaseButton>
          <BaseButton type="danger" link @click="remove(row)">删除</BaseButton>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination
      v-model:current-page="page"
      v-model:page-size="limit"
      class="master-pagination"
      background
      layout="total, sizes, prev, pager, next, jumper"
      :total="total"
      @current-change="loadList"
      @size-change="changePageSize"
    />
  </ContentWrap>

  <el-dialog v-model="dialogVisible" :title="dialogTitle" width="820px" destroy-on-close>
    <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
      <el-row :gutter="18">
        <el-col v-for="field in visibleFields" :key="field.field" :span="field.span || 12">
          <el-form-item :label="field.label" :prop="field.field">
            <el-input
              v-if="!field.component || field.component === 'input'"
              v-model="form[field.field]"
              clearable
            />
            <el-input
              v-else-if="field.component === 'textarea'"
              v-model="form[field.field]"
              type="textarea"
              :rows="3"
            />
            <el-input-number
              v-else-if="field.component === 'number'"
              v-model="form[field.field]"
              :min="field.min"
              :max="field.max"
              :precision="field.precision"
              style="width: 100%"
            />
            <el-select
              v-else-if="field.component === 'select'"
              v-model="form[field.field]"
              clearable
              filterable
              style="width: 100%"
            >
              <el-option
                v-for="option in field.options || options[field.optionResource || ''] || []"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
            <el-tree-select
              v-else-if="field.component === 'tree-select'"
              v-model="form[field.field]"
              :data="options[field.optionResource || ''] || []"
              clearable
              check-strictly
              style="width: 100%"
            />
            <el-switch v-else-if="field.component === 'switch'" v-model="form[field.field]" />
          </el-form-item>
        </el-col>
      </el-row>
    </el-form>
    <template #footer>
      <BaseButton @click="dialogVisible = false">取消</BaseButton>
      <BaseButton type="primary" :loading="saving" @click="save">保存</BaseButton>
    </template>
  </el-dialog>
</template>

<style scoped>
.master-search {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}
.master-search .el-input {
  width: 260px;
}
.master-search .el-select {
  width: 150px;
}
.master-toolbar {
  margin-bottom: 12px;
}
.master-pagination {
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
