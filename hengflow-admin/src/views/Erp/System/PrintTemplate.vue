<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import type { FormInstance } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ContentWrap } from '@/components/ContentWrap'
import { BaseButton } from '@/components/Button'
import {
  addPrintTemplateApi,
  deletePrintTemplateApi,
  getPrintTemplatesApi,
  putPrintTemplateApi,
  renderPrintTemplateApi
} from '@/api/erp/documents'

const rows = ref<any[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const previewVisible = ref(false)
const saving = ref(false)
const editingId = ref<number>()
const formRef = ref<FormInstance>()
const previewFrame = ref<HTMLIFrameElement>()
const previewHtml = ref('')
const sampleDataText = ref('{}')
const form = ref<any>({})

/** 生成新增模板的默认表单。 */
const emptyForm = () => ({
  code: '',
  name: '',
  business_type: '',
  content_html: '',
  style_css: '',
  paper_size: 'A4',
  orientation: 'portrait',
  margin_mm: 10,
  is_default: false,
  is_active: true,
  remark: ''
})

const loadList = async () => {
  loading.value = true
  try {
    const res = await getPrintTemplatesApi()
    rows.value = res.data || []
  } finally {
    loading.value = false
  }
}

const add = () => {
  editingId.value = undefined
  form.value = emptyForm()
  sampleDataText.value = '{}'
  dialogVisible.value = true
}

const edit = (row: any) => {
  editingId.value = row.id
  form.value = { ...row }
  sampleDataText.value = JSON.stringify(row.sample_data || {}, null, 2)
  dialogVisible.value = true
}

/** 校验示例 JSON 并保存模板。 */
const save = async () => {
  await formRef.value?.validate()
  let sampleData: Record<string, any>
  try {
    sampleData = JSON.parse(sampleDataText.value || '{}')
  } catch {
    ElMessage.error('示例数据不是有效的 JSON')
    return
  }
  saving.value = true
  try {
    const payload = { ...form.value, sample_data: sampleData }
    delete payload.id
    delete payload.version
    if (editingId.value) await putPrintTemplateApi(editingId.value, payload)
    else await addPrintTemplateApi(payload)
    ElMessage.success('保存成功')
    dialogVisible.value = false
    await loadList()
  } finally {
    saving.value = false
  }
}

/** 以模板自带示例数据渲染安全预览。 */
const preview = async (row: any) => {
  const res = await renderPrintTemplateApi({ template_id: row.id, data: row.sample_data || {} })
  previewHtml.value = res.data
  previewVisible.value = true
  await nextTick()
}

const printPreview = () => previewFrame.value?.contentWindow?.print()

const remove = async (row: any) => {
  await ElMessageBox.confirm(`确定删除打印模板“${row.name}”吗？`, '删除确认', { type: 'warning' })
  await deletePrintTemplateApi(row.id)
  ElMessage.success('删除成功')
  await loadList()
}

onMounted(loadList)
</script>

<template>
  <ContentWrap>
    <div class="toolbar"><BaseButton type="primary" @click="add">新增模板</BaseButton></div>
    <el-table v-loading="loading" :data="rows" border stripe>
      <el-table-column prop="code" label="编码" width="190" />
      <el-table-column prop="name" label="名称" min-width="170" />
      <el-table-column prop="business_type" label="业务类型" width="150" />
      <el-table-column label="纸张" width="130">
        <template #default="{ row }"
          >{{ row.paper_size }} / {{ row.orientation === 'portrait' ? '纵向' : '横向' }}</template
        >
      </el-table-column>
      <el-table-column prop="version" label="版本" width="80" />
      <el-table-column label="默认" width="75"
        ><template #default="{ row }"
          ><el-tag v-if="row.is_default" type="success">默认</el-tag><span v-else>-</span></template
        ></el-table-column
      >
      <el-table-column label="启用" width="75"
        ><template #default="{ row }"><el-switch :model-value="row.is_active" disabled /></template
      ></el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <BaseButton type="success" link @click="preview(row)">预览</BaseButton>
          <BaseButton type="primary" link @click="edit(row)">编辑</BaseButton>
          <BaseButton type="danger" link @click="remove(row)">删除</BaseButton>
        </template>
      </el-table-column>
    </el-table>
  </ContentWrap>

  <el-dialog
    v-model="dialogVisible"
    :title="editingId ? '编辑打印模板' : '新增打印模板'"
    width="1080px"
    destroy-on-close
  >
    <el-form ref="formRef" :model="form" label-width="100px">
      <el-row :gutter="16">
        <el-col :span="8"
          ><el-form-item label="模板编码" prop="code" required
            ><el-input v-model="form.code" /></el-form-item
        ></el-col>
        <el-col :span="8"
          ><el-form-item label="模板名称" prop="name" required
            ><el-input v-model="form.name" /></el-form-item
        ></el-col>
        <el-col :span="8"
          ><el-form-item label="业务类型" prop="business_type" required
            ><el-input
              v-model="form.business_type"
              placeholder="如 purchase_receipt" /></el-form-item
        ></el-col>
        <el-col :span="6"
          ><el-form-item label="纸张"
            ><el-select v-model="form.paper_size"
              ><el-option label="A4" value="A4" /><el-option label="A5" value="A5" /><el-option
                label="Letter"
                value="Letter" /></el-select></el-form-item
        ></el-col>
        <el-col :span="6"
          ><el-form-item label="方向"
            ><el-select v-model="form.orientation"
              ><el-option label="纵向" value="portrait" /><el-option
                label="横向"
                value="landscape" /></el-select></el-form-item
        ></el-col>
        <el-col :span="6"
          ><el-form-item label="页边距"
            ><el-input-number v-model="form.margin_mm" :min="0" :max="50" /> mm</el-form-item
          ></el-col
        >
        <el-col :span="3"
          ><el-form-item label="默认"><el-switch v-model="form.is_default" /></el-form-item
        ></el-col>
        <el-col :span="3"
          ><el-form-item label="启用"><el-switch v-model="form.is_active" /></el-form-item
        ></el-col>
      </el-row>
      <el-form-item label="HTML 模板" prop="content_html" required>
        <el-input
          v-model="form.content_html"
          type="textarea"
          :rows="10"
          placeholder="支持 {{ field }} 和 {% for item in lines %}...{% endfor %}"
        />
      </el-form-item>
      <el-form-item label="CSS 样式"
        ><el-input v-model="form.style_css" type="textarea" :rows="5"
      /></el-form-item>
      <el-form-item label="示例 JSON"
        ><el-input v-model="sampleDataText" type="textarea" :rows="7"
      /></el-form-item>
      <el-form-item label="备注"><el-input v-model="form.remark" /></el-form-item>
    </el-form>
    <template #footer
      ><BaseButton @click="dialogVisible = false">取消</BaseButton
      ><BaseButton type="primary" :loading="saving" @click="save">保存</BaseButton></template
    >
  </el-dialog>

  <el-dialog v-model="previewVisible" title="打印预览" width="1000px" top="4vh">
    <iframe
      ref="previewFrame"
      class="preview-frame"
      :srcdoc="previewHtml"
      sandbox="allow-same-origin allow-modals"
    ></iframe>
    <template #footer
      ><BaseButton @click="previewVisible = false">关闭</BaseButton
      ><BaseButton type="primary" @click="printPreview">打印</BaseButton></template
    >
  </el-dialog>
</template>

<style scoped>
.toolbar {
  margin-bottom: 12px;
}
.preview-frame {
  width: 100%;
  height: 70vh;
  border: 1px solid var(--el-border-color);
  background: white;
}
</style>
