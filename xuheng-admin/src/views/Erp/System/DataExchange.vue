<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ContentWrap } from '@/components/ContentWrap'
import { BaseButton } from '@/components/Button'
import {
  downloadExchangeTemplateApi,
  exportExchangeResourceApi,
  getExchangeResourcesApi,
  getExchangeTasksApi,
  importExchangeResourceApi
} from '@/api/erp/documents'

const route = useRoute()
const resources = ref<{ label: string; value: string }[]>([])
const resource = ref('')
const mode = ref('upsert')
const selectedFile = ref<File>()
const fileInput = ref<HTMLInputElement>()
const importing = ref(false)
const tasks = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const limit = ref(20)

/** 从响应头解析文件名并触发浏览器保存。 */
const saveBlob = (response: any, fallback: string) => {
  const disposition = response.headers?.['content-disposition'] || ''
  const matched = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  const filename = matched ? decodeURIComponent(matched[1]) : fallback
  const url = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

/** 读取可交换资源并优先采用路由参数。 */
const loadResources = async () => {
  const res = await getExchangeResourcesApi()
  resources.value = res.data || []
  const requested = String(route.query.resource || '')
  resource.value = resources.value.some((item) => item.value === requested)
    ? requested
    : resources.value[0]?.value || ''
}

/** 查询最近导入导出结果。 */
const loadTasks = async () => {
  const res = await getExchangeTasksApi({ page: page.value, limit: limit.value })
  tasks.value = res.data || []
  total.value = res.count || 0
}

const downloadTemplate = async () => {
  if (!resource.value) return
  saveBlob(await downloadExchangeTemplateApi(resource.value), '导入模板.xlsx')
}

const exportData = async () => {
  if (!resource.value) return
  saveBlob(await exportExchangeResourceApi(resource.value), '数据导出.xlsx')
  ElMessage.success('导出成功')
  await loadTasks()
}

const chooseFile = () => fileInput.value?.click()

/** 保存用户选择的 xlsx 文件但不立即上传。 */
const selectFile = (event: Event) => {
  selectedFile.value = (event.target as HTMLInputElement).files?.[0]
}

/** 提交导入并展示成功/失败行统计。 */
const importData = async () => {
  if (!resource.value || !selectedFile.value) {
    ElMessage.warning('请先选择资源和 Excel 文件')
    return
  }
  importing.value = true
  try {
    const data = new FormData()
    data.append('file', selectedFile.value)
    data.append('mode', mode.value)
    const res = await importExchangeResourceApi(resource.value, data)
    const task = res.data
    ElMessage.success(`导入完成：成功 ${task.success_count} 行，失败 ${task.failure_count} 行`)
    selectedFile.value = undefined
    if (fileInput.value) fileInput.value.value = ''
    await loadTasks()
  } finally {
    importing.value = false
  }
}

const statusType = (status: string) =>
  status === 'success'
    ? 'success'
    : status === 'partial'
      ? 'warning'
      : status === 'failed'
        ? 'danger'
        : 'info'

onMounted(async () => {
  await Promise.all([loadResources(), loadTasks()])
})
</script>

<template>
  <ContentWrap>
    <div class="exchange-toolbar">
      <el-select v-model="resource" placeholder="选择资料类型" filterable style="width: 220px">
        <el-option
          v-for="item in resources"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <BaseButton @click="downloadTemplate">下载导入模板</BaseButton>
      <BaseButton type="success" @click="exportData">导出 Excel</BaseButton>
    </div>

    <el-alert
      title="导入以编码作为唯一键；覆盖更新会修改同编码资料，遇到错误的行会跳过并继续处理。"
      type="info"
      :closable="false"
      show-icon
    />
    <div class="import-box">
      <el-radio-group v-model="mode">
        <el-radio-button value="upsert">新增并覆盖同编码</el-radio-button>
        <el-radio-button value="create">仅新增</el-radio-button>
      </el-radio-group>
      <input ref="fileInput" class="hidden-file" type="file" accept=".xlsx" @change="selectFile" />
      <BaseButton @click="chooseFile">选择 Excel</BaseButton>
      <span class="file-name">{{ selectedFile?.name || '尚未选择文件' }}</span>
      <BaseButton type="primary" :loading="importing" @click="importData">开始导入</BaseButton>
    </div>
  </ContentWrap>

  <ContentWrap title="处理记录">
    <el-table :data="tasks" border stripe>
      <el-table-column prop="create_datetime" label="时间" width="180" />
      <el-table-column prop="resource" label="资源" width="160" />
      <el-table-column prop="task_type" label="类型" width="90">
        <template #default="{ row }">{{ row.task_type === 'import' ? '导入' : '导出' }}</template>
      </el-table-column>
      <el-table-column prop="file_name" label="文件" min-width="180" show-overflow-tooltip />
      <el-table-column label="状态" width="100">
        <template #default="{ row }"
          ><el-tag :type="statusType(row.status)">{{ row.status }}</el-tag></template
        >
      </el-table-column>
      <el-table-column prop="total_count" label="总数" width="80" />
      <el-table-column prop="success_count" label="成功" width="80" />
      <el-table-column prop="failure_count" label="失败" width="80" />
      <el-table-column label="错误明细" min-width="240">
        <template #default="{ row }">
          <el-popover
            v-if="row.error_details?.length"
            placement="left"
            :width="420"
            trigger="click"
          >
            <template #reference
              ><BaseButton type="danger" link
                >查看 {{ row.error_details.length }} 条</BaseButton
              ></template
            >
            <div
              v-for="error in row.error_details"
              :key="`${error.row}-${error.message}`"
              class="error-line"
            >
              第 {{ error.row || '-' }} 行：{{ error.message }}
            </div>
          </el-popover>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="operator_name" label="操作人" width="110" />
    </el-table>
    <el-pagination
      v-model:current-page="page"
      v-model:page-size="limit"
      class="pagination"
      background
      layout="total, sizes, prev, pager, next"
      :total="total"
      @current-change="loadTasks"
      @size-change="loadTasks"
    />
  </ContentWrap>
</template>

<style scoped>
.exchange-toolbar,
.import-box {
  display: flex;
  align-items: center;
  gap: 12px;
}
.exchange-toolbar {
  margin-bottom: 16px;
}
.import-box {
  margin-top: 18px;
  padding: 18px;
  border: 1px dashed var(--el-border-color);
  border-radius: 6px;
}
.hidden-file {
  display: none;
}
.file-name {
  min-width: 180px;
  color: var(--el-text-color-secondary);
}
.pagination {
  justify-content: flex-end;
  margin-top: 16px;
}
.error-line {
  padding: 4px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
</style>
