<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { FormInstance } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ContentWrap } from '@/components/ContentWrap'
import { BaseButton } from '@/components/Button'
import {
  addMasterApi,
  addUnitGroupItemApi,
  delMasterApi,
  delUnitGroupItemApi,
  getMasterListApi,
  getMasterOptionsApi,
  getUnitGroupItemsApi,
  putMasterApi,
  putUnitGroupItemApi
} from '@/api/erp/master'
import type { MasterOption } from './types'

defineOptions({ name: 'ErpMasterUnitConversion' })

interface UnitItem {
  id: number
  group_id: number
  unit_id: number
  parent_id: number | null
  factor: number
  order: number
  children?: UnitItem[]
}

const loading = ref(false)
const groups = ref<any[]>([])
const units = ref<MasterOption[]>([])
const items = ref<UnitItem[]>([])
const currentGroupId = ref<number>()

const currentGroup = computed(() => groups.value.find((item) => item.id === currentGroupId.value))
const unitLabel = (unitId?: number) =>
  units.value.find((item) => item.value === unitId)?.label || `单位 #${unitId}`

const itemTree = computed<UnitItem[]>(() => {
  const map = new Map<number, UnitItem>()
  items.value.forEach((item) => map.set(item.id, { ...item, children: [] }))
  const roots: UnitItem[] = []
  map.forEach((item) => {
    const parent = item.parent_id ? map.get(item.parent_id) : undefined
    if (parent) parent.children?.push(item)
    else roots.push(item)
  })
  return roots
})

const loadGroups = async (selectId?: number) => {
  loading.value = true
  try {
    const res = await getMasterListApi('unit-conversions', { page: 1, limit: 1000 })
    groups.value = res.data || []
    const target = selectId || currentGroupId.value
    currentGroupId.value = groups.value.some((item) => item.id === target)
      ? target
      : groups.value[0]?.id
    await loadItems()
  } finally {
    loading.value = false
  }
}

const loadItems = async () => {
  if (!currentGroupId.value) {
    items.value = []
    return
  }
  const res = await getUnitGroupItemsApi(currentGroupId.value)
  items.value = res.data || []
}

const selectGroup = async (row: any) => {
  currentGroupId.value = row.id
  await loadItems()
}

const groupDialog = ref(false)
const groupSaving = ref(false)
const groupFormRef = ref<FormInstance>()
const editingGroupId = ref<number>()
const groupForm = ref<any>({})
const groupRules = {
  name: [{ required: true, message: '请输入方案名称', trigger: 'blur' }],
  primary_unit_id: [{ required: true, message: '请选择主单位', trigger: 'change' }]
}

const addGroup = () => {
  editingGroupId.value = undefined
  groupForm.value = { name: '', primary_unit_id: null, is_active: true, remark: '' }
  groupDialog.value = true
}

const editGroup = (row: any) => {
  editingGroupId.value = row.id
  groupForm.value = { ...row }
  groupDialog.value = true
}

const saveGroup = async () => {
  await groupFormRef.value?.validate()
  groupSaving.value = true
  try {
    const res = editingGroupId.value
      ? await putMasterApi('unit-conversions', { ...groupForm.value, id: editingGroupId.value })
      : await addMasterApi('unit-conversions', groupForm.value)
    ElMessage.success('保存成功')
    groupDialog.value = false
    await loadGroups(res.data?.id || editingGroupId.value)
  } finally {
    groupSaving.value = false
  }
}

const removeGroup = async (row: any) => {
  await ElMessageBox.confirm(`确定删除多单位方案“${row.name}”吗？`, '删除确认', {
    type: 'warning'
  })
  await delMasterApi('unit-conversions', [row.id])
  ElMessage.success('删除成功')
  await loadGroups()
}

const itemDialog = ref(false)
const itemSaving = ref(false)
const itemFormRef = ref<FormInstance>()
const editingItemId = ref<number>()
const itemForm = ref<any>({})
const itemRules = {
  unit_id: [{ required: true, message: '请选择子单位', trigger: 'change' }],
  factor: [{ required: true, message: '请输入换算数量', trigger: 'change' }]
}

const parentOptions = computed(() =>
  items.value
    .filter((item) => item.id !== editingItemId.value)
    .map((item) => ({ value: item.id, label: unitLabel(item.unit_id) }))
)
const availableUnitOptions = computed(() => {
  const occupied = new Set(
    items.value.filter((item) => item.id !== editingItemId.value).map((item) => item.unit_id)
  )
  if (currentGroup.value?.primary_unit_id) occupied.add(currentGroup.value.primary_unit_id)
  return units.value.filter((item) => !occupied.has(Number(item.value)))
})
const factorParentLabel = computed(() => {
  if (!itemForm.value.parent_id) return unitLabel(currentGroup.value?.primary_unit_id)
  const parent = items.value.find((item) => item.id === itemForm.value.parent_id)
  return unitLabel(parent?.unit_id)
})

const addItem = (parent?: UnitItem) => {
  if (!currentGroupId.value) return ElMessage.warning('请先新增并选择多单位方案')
  editingItemId.value = undefined
  itemForm.value = { unit_id: null, parent_id: parent?.id || null, factor: 1, order: 0 }
  itemDialog.value = true
}

const editItem = (row: UnitItem) => {
  editingItemId.value = row.id
  itemForm.value = { ...row }
  itemDialog.value = true
}

const saveItem = async () => {
  await itemFormRef.value?.validate()
  if (!currentGroupId.value) return
  itemSaving.value = true
  try {
    if (editingItemId.value) {
      await putUnitGroupItemApi(currentGroupId.value, {
        ...itemForm.value,
        id: editingItemId.value
      })
    } else {
      await addUnitGroupItemApi(currentGroupId.value, itemForm.value)
    }
    ElMessage.success('保存成功')
    itemDialog.value = false
    await loadItems()
  } finally {
    itemSaving.value = false
  }
}

const removeItem = async (row: UnitItem) => {
  if (!currentGroupId.value) return
  await ElMessageBox.confirm(`确定删除子单位“${unitLabel(row.unit_id)}”吗？`, '删除确认', {
    type: 'warning'
  })
  await delUnitGroupItemApi(currentGroupId.value, [row.id])
  ElMessage.success('删除成功')
  await loadItems()
}

onMounted(async () => {
  const unitRes = await getMasterOptionsApi('units')
  units.value = unitRes.data || []
  await loadGroups()
})
</script>

<template>
  <ContentWrap>
    <el-alert
      title="换算规则：每一级填写“1 个上级单位 = N 个当前单位”。例如：箱 → 10 袋 → 10 盒，则 1 箱 = 100 盒。"
      type="info"
      :closable="false"
      class="unit-tip"
    />
    <el-row :gutter="16">
      <el-col :span="9">
        <div class="panel-header">
          <strong>多单位方案</strong>
          <BaseButton type="primary" @click="addGroup">新增方案</BaseButton>
        </div>
        <el-table
          v-loading="loading"
          :data="groups"
          highlight-current-row
          border
          @row-click="selectGroup"
        >
          <el-table-column prop="name" label="方案名称" min-width="140" />
          <el-table-column label="主单位" min-width="130">
            <template #default="{ row }">{{ unitLabel(row.primary_unit_id) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="115">
            <template #default="{ row }">
              <BaseButton type="primary" link @click.stop="editGroup(row)">编辑</BaseButton>
              <BaseButton type="danger" link @click.stop="removeGroup(row)">删除</BaseButton>
            </template>
          </el-table-column>
        </el-table>
      </el-col>
      <el-col :span="15">
        <div class="panel-header">
          <strong>{{ currentGroup ? `${currentGroup.name} · 单位层级` : '单位层级' }}</strong>
          <BaseButton type="primary" :disabled="!currentGroup" @click="addItem()">
            新增一级子单位
          </BaseButton>
        </div>
        <el-empty v-if="!currentGroup" description="请先选择多单位方案" />
        <el-table
          v-else
          :data="itemTree"
          row-key="id"
          default-expand-all
          border
          :tree-props="{ children: 'children' }"
        >
          <el-table-column label="单位" min-width="150">
            <template #default="{ row }">{{ unitLabel(row.unit_id) }}</template>
          </el-table-column>
          <el-table-column label="换算关系" min-width="230">
            <template #default="{ row }">
              1
              {{
                row.parent_id
                  ? unitLabel(items.find((item) => item.id === row.parent_id)?.unit_id)
                  : unitLabel(currentGroup.primary_unit_id)
              }}
              = {{ row.factor }} {{ unitLabel(row.unit_id) }}
            </template>
          </el-table-column>
          <el-table-column prop="order" label="排序" width="70" />
          <el-table-column label="操作" width="180">
            <template #default="{ row }">
              <BaseButton type="success" link @click="addItem(row)">加下级</BaseButton>
              <BaseButton type="primary" link @click="editItem(row)">编辑</BaseButton>
              <BaseButton type="danger" link @click="removeItem(row)">删除</BaseButton>
            </template>
          </el-table-column>
        </el-table>
      </el-col>
    </el-row>
  </ContentWrap>

  <el-dialog
    v-model="groupDialog"
    :title="editingGroupId ? '编辑多单位方案' : '新增多单位方案'"
    width="560px"
  >
    <el-form ref="groupFormRef" :model="groupForm" :rules="groupRules" label-width="100px">
      <el-form-item label="方案名称" prop="name">
        <el-input v-model="groupForm.name" placeholder="例如：食品多单位设置" />
      </el-form-item>
      <el-form-item label="主单位" prop="primary_unit_id">
        <el-select v-model="groupForm.primary_unit_id" filterable style="width: 100%">
          <el-option
            v-for="unit in units"
            :key="unit.value"
            :label="unit.label"
            :value="unit.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="groupForm.is_active" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="groupForm.remark" type="textarea" :rows="3" />
      </el-form-item>
    </el-form>
    <template #footer>
      <BaseButton @click="groupDialog = false">取消</BaseButton>
      <BaseButton type="primary" :loading="groupSaving" @click="saveGroup">保存</BaseButton>
    </template>
  </el-dialog>

  <el-dialog
    v-model="itemDialog"
    :title="editingItemId ? '编辑子单位' : '新增子单位'"
    width="580px"
  >
    <el-form ref="itemFormRef" :model="itemForm" :rules="itemRules" label-width="110px">
      <el-form-item label="上级单位">
        <el-select v-model="itemForm.parent_id" clearable style="width: 100%">
          <el-option :label="`主单位：${unitLabel(currentGroup?.primary_unit_id)}`" :value="null" />
          <el-option
            v-for="option in parentOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="当前单位" prop="unit_id">
        <el-select v-model="itemForm.unit_id" filterable style="width: 100%">
          <el-option
            v-for="unit in availableUnitOptions"
            :key="unit.value"
            :label="unit.label"
            :value="unit.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item :label="`1 ${factorParentLabel} =`" prop="factor">
        <el-input-number
          v-model="itemForm.factor"
          :min="0.00000001"
          :precision="8"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="排序">
        <el-input-number v-model="itemForm.order" :min="0" style="width: 100%" />
      </el-form-item>
    </el-form>
    <template #footer>
      <BaseButton @click="itemDialog = false">取消</BaseButton>
      <BaseButton type="primary" :loading="itemSaving" @click="saveItem">保存</BaseButton>
    </template>
  </el-dialog>
</template>

<style scoped>
.unit-tip {
  margin-bottom: 16px;
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 32px;
  margin-bottom: 12px;
}
</style>
