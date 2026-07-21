<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ContentWrap } from '@/components/ContentWrap'
import { BaseButton } from '@/components/Button'
import {
  deleteAttachmentApi,
  downloadAttachmentApi,
  getAttachmentDownloadUrlApi,
  getAttachmentsApi,
  uploadAttachmentApi
} from '@/api/erp/documents'

const businessType = ref('generic')
const businessId = ref<number>()
const rows = ref<any[]>([])
const loading = ref(false)
const uploading = ref(false)
const storageType = ref('local')
const description = ref('')
const selectedFile = ref<File>()
const fileInput = ref<HTMLInputElement>()

/** 查询指定业务对象的附件。 */
const loadList = async () => {
  if (!businessType.value || !businessId.value) {
    ElMessage.warning('请输入业务类型和业务 ID')
    return
  }
  loading.value = true
  try {
    const res = await getAttachmentsApi({
      business_type: businessType.value,
      business_id: businessId.value
    })
    rows.value = res.data || []
  } finally {
    loading.value = false
  }
}

const selectFile = (event: Event) => {
  selectedFile.value = (event.target as HTMLInputElement).files?.[0]
}

/** 上传到选定存储并关联当前业务对象。 */
const upload = async () => {
  if (!businessType.value || !businessId.value || !selectedFile.value) {
    ElMessage.warning('请填写业务对象并选择附件')
    return
  }
  uploading.value = true
  try {
    const data = new FormData()
    data.append('business_type', businessType.value)
    data.append('business_id', String(businessId.value))
    data.append('storage_type', storageType.value)
    data.append('description', description.value)
    data.append('file', selectedFile.value)
    await uploadAttachmentApi(data)
    ElMessage.success('上传成功')
    selectedFile.value = undefined
    description.value = ''
    if (fileInput.value) fileInput.value.value = ''
    await loadList()
  } finally {
    uploading.value = false
  }
}

/** 下载受鉴权保护的附件文件流。 */
const download = async (row: any) => {
  if (row.storage_type === 'oss') {
    const res = await getAttachmentDownloadUrlApi(row.id)
    window.open(res.data, '_blank', 'noopener,noreferrer')
    return
  }
  const response = await downloadAttachmentApi(row.id)
  const url = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = row.file_name
  link.click()
  URL.revokeObjectURL(url)
}

const remove = async (row: any) => {
  await ElMessageBox.confirm(`确定删除附件“${row.file_name}”吗？`, '删除确认', { type: 'warning' })
  await deleteAttachmentApi(row.id)
  ElMessage.success('删除成功')
  await loadList()
}

const fileSize = (size: number) =>
  size < 1024
    ? `${size} B`
    : size < 1024 * 1024
      ? `${(size / 1024).toFixed(1)} KB`
      : `${(size / 1024 / 1024).toFixed(1)} MB`
</script>

<template>
  <ContentWrap>
    <el-alert
      title="业务类型用于区分单据种类（如 purchase_order），业务 ID 是该单据主键。"
      type="info"
      :closable="false"
      show-icon
    />
    <div class="query-bar">
      <el-input v-model="businessType" placeholder="业务类型" style="width: 220px" />
      <el-input-number v-model="businessId" :min="1" placeholder="业务 ID" />
      <BaseButton type="primary" @click="loadList">查询附件</BaseButton>
    </div>
    <div class="upload-bar">
      <el-select v-model="storageType" style="width: 130px"
        ><el-option label="本地存储" value="local" /><el-option label="阿里云 OSS" value="oss"
      /></el-select>
      <input ref="fileInput" type="file" @change="selectFile" />
      <el-input v-model="description" placeholder="附件说明（可选）" style="width: 260px" />
      <BaseButton type="success" :loading="uploading" @click="upload">上传并关联</BaseButton>
    </div>
    <el-table v-loading="loading" :data="rows" border stripe>
      <el-table-column prop="file_name" label="文件名" min-width="230" show-overflow-tooltip />
      <el-table-column prop="description" label="说明" min-width="180" />
      <el-table-column label="大小" width="100"
        ><template #default="{ row }">{{ fileSize(row.file_size) }}</template></el-table-column
      >
      <el-table-column label="存储" width="100"
        ><template #default="{ row }"
          ><el-tag>{{ row.storage_type === 'oss' ? 'OSS' : '本地' }}</el-tag></template
        ></el-table-column
      >
      <el-table-column prop="uploaded_by_name" label="上传人" width="110" />
      <el-table-column prop="create_datetime" label="上传时间" width="180" />
      <el-table-column label="操作" width="130" fixed="right"
        ><template #default="{ row }"
          ><BaseButton type="primary" link @click="download(row)">下载</BaseButton
          ><BaseButton type="danger" link @click="remove(row)">删除</BaseButton></template
        ></el-table-column
      >
    </el-table>
  </ContentWrap>
</template>

<style scoped>
.query-bar,
.upload-bar {
  display: flex;
  align-items: center;
  gap: 12px;
}
.query-bar {
  margin: 18px 0;
}
.upload-bar {
  padding: 14px;
  margin-bottom: 16px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}
</style>
