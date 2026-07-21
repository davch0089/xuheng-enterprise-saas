<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ContentWrap } from '@/components/ContentWrap'
import { skuLabel, skuSpec } from '@/utils/erp/product'
import {
  addBomApi,
  delBomApi,
  getBomApi,
  getBomListApi,
  putBomApi,
  searchInboundProductsApi
} from '@/api/erp/inventory'

defineOptions({ name: 'ErpInventoryBom' })

const loading = ref(false)
const saving = ref(false)
const visible = ref(false)
const rows = ref<any[]>([])
const products = ref<any[]>([])
const total = ref(0)
const editingId = ref<number>()
const query = reactive({
  page: 1,
  limit: 20,
  keyword: '',
  is_active: undefined as boolean | undefined
})
const form = reactive<any>({
  code: '',
  name: '',
  product_id: undefined,
  unit_id: undefined,
  output_quantity: 1,
  version: '1.0',
  is_active: true,
  remark: '',
  lines: []
})

/** 返回指定商品及其可用计量单位。 */
const product = (id: number) => products.value.find((item) => item.id === id)
const units = (id: number) => product(id)?.units || []

/** 加载 BOM 列表。 */
const loadList = async () => {
  loading.value = true
  try {
    const res = await getBomListApi(query)
    rows.value = res.data || []
    total.value = res.count || 0
  } finally {
    loading.value = false
  }
}

/** 加载可维护 BOM 的商品目录。 */
const loadProducts = async (keyword = '') => {
  const res = await searchInboundProductsApi({ keyword, limit: 100 })
  products.value = res.data || []
}

/** 重置新增表单。 */
const reset = () => {
  editingId.value = undefined
  Object.assign(form, {
    code: '',
    name: '',
    product_id: undefined,
    unit_id: undefined,
    output_quantity: 1,
    version: '1.0',
    is_active: true,
    remark: '',
    lines: []
  })
}

/** 打开新增窗口。 */
const create = () => {
  reset()
  visible.value = true
}

/** 打开已有 BOM。 */
const open = async (row: any) => {
  const res = await getBomApi(row.id)
  const selected = [
    res.data.finished_product,
    ...(res.data.lines || []).map((line: any) => line.product)
  ].filter(Boolean)
  products.value = [...selected, ...products.value].filter(
    (item, index, all) => all.findIndex((candidate) => candidate.id === item.id) === index
  )
  Object.assign(form, res.data)
  form.output_quantity = Number(res.data.output_quantity)
  form.lines = (res.data.lines || []).map((line: any) => ({
    ...line,
    quantity: Number(line.quantity),
    loss_rate: Number(line.loss_rate)
  }))
  editingId.value = row.id
  visible.value = true
}

/** 成品变化时带入主单位。 */
const chooseFinished = () => {
  form.unit_id = product(form.product_id)?.base_unit_id
}

/** 新增一行 BOM 子件。 */
const addLine = () =>
  form.lines.push({
    component_product_id: undefined,
    unit_id: undefined,
    quantity: 1,
    loss_rate: 0,
    remark: ''
  })

/** 子件变化时带入主单位。 */
const chooseComponent = (line: any) => {
  line.unit_id = product(line.component_product_id)?.base_unit_id
}

/** 保存 BOM 并固化各单位换算率。 */
const save = async () => {
  if (
    !form.code ||
    !form.name ||
    !form.product_id ||
    !form.unit_id ||
    Number(form.output_quantity) <= 0
  )
    return ElMessage.warning('请完整填写 BOM 表头')
  if (
    !form.lines.length ||
    form.lines.some(
      (line: any) => !line.component_product_id || !line.unit_id || Number(line.quantity) <= 0
    )
  )
    return ElMessage.warning('请至少填写一个有效子件')
  saving.value = true
  try {
    const data = {
      code: form.code,
      name: form.name,
      product_id: form.product_id,
      unit_id: form.unit_id,
      output_quantity: Number(form.output_quantity),
      version: form.version || '1.0',
      is_active: form.is_active,
      remark: form.remark || null,
      lines: form.lines.map((line: any) => ({
        component_product_id: line.component_product_id,
        unit_id: line.unit_id,
        quantity: Number(line.quantity),
        loss_rate: Number(line.loss_rate || 0),
        remark: line.remark || null
      }))
    }
    editingId.value ? await putBomApi(editingId.value, data) : await addBomApi(data)
    ElMessage.success('BOM 保存成功')
    visible.value = false
    await loadList()
  } finally {
    saving.value = false
  }
}

/** 删除未被工单使用的 BOM。 */
const remove = async (row: any) => {
  await ElMessageBox.confirm(`确定删除 BOM ${row.code} 吗？`, '删除确认', { type: 'warning' })
  await delBomApi([row.id])
  ElMessage.success('删除成功')
  await loadList()
}

onMounted(async () => {
  await Promise.all([loadProducts(), loadList()])
})
</script>

<template>
  <ContentWrap>
    <div class="toolbar">
      <el-input
        v-model="query.keyword"
        clearable
        placeholder="BOM 编码或名称"
        @keyup.enter="loadList"
      />
      <el-select v-model="query.is_active" clearable placeholder="启用状态">
        <el-option label="启用" :value="true" />
        <el-option label="停用" :value="false" />
      </el-select>
      <el-button type="primary" @click="loadList">查询</el-button>
      <el-button type="success" @click="create">新增 BOM</el-button>
    </div>
    <el-table v-loading="loading" :data="rows" border stripe>
      <el-table-column prop="code" label="BOM 编码" min-width="150" />
      <el-table-column prop="name" label="BOM 名称" min-width="180" />
      <el-table-column prop="product_code" label="成品SKU编码" width="145" />
      <el-table-column prop="product_name" label="成品名称" min-width="180" />
      <el-table-column label="SKU规格" min-width="150"
        ><template #default="scope">{{
          skuSpec({
            variant_name: scope.row.product_variant_name,
            specification: scope.row.product_specification
          })
        }}</template></el-table-column
      >
      <el-table-column prop="version" label="版本" width="90" />
      <el-table-column prop="output_quantity" label="标准产出" width="110" align="right" />
      <el-table-column label="状态" width="90" align="center">
        <template #default="scope"
          ><el-tag :type="scope.row.is_active ? 'success' : 'info'">{{
            scope.row.is_active ? '启用' : '停用'
          }}</el-tag></template
        >
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="scope">
          <el-button link type="primary" @click="open(scope.row)">编辑</el-button>
          <el-button link type="danger" @click="remove(scope.row)">删除</el-button>
        </template>
      </el-table-column>
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
    v-model="visible"
    :title="editingId ? '编辑 BOM' : '新增 BOM'"
    width="92%"
    top="5vh"
    destroy-on-close
  >
    <el-form label-width="90px">
      <el-row :gutter="16">
        <el-col :span="6"
          ><el-form-item label="BOM 编码"><el-input v-model="form.code" /></el-form-item
        ></el-col>
        <el-col :span="7"
          ><el-form-item label="BOM 名称"><el-input v-model="form.name" /></el-form-item
        ></el-col>
        <el-col :span="5"
          ><el-form-item label="版本"><el-input v-model="form.version" /></el-form-item
        ></el-col>
        <el-col :span="4"
          ><el-form-item label="启用"><el-switch v-model="form.is_active" /></el-form-item
        ></el-col>
        <el-col :span="9"
          ><el-form-item label="成品"
            ><el-select
              v-model="form.product_id"
              filterable
              style="width: 100%"
              @change="chooseFinished"
              ><el-option
                v-for="item in products"
                :key="item.id"
                :label="skuLabel(item, { barcode: true })"
                :value="item.id" /></el-select></el-form-item
        ></el-col>
        <el-col :span="6"
          ><el-form-item label="产出数量"
            ><el-input-number
              v-model="form.output_quantity"
              :min="0.000001"
              :controls="false" /></el-form-item
        ></el-col>
        <el-col :span="6"
          ><el-form-item label="产出单位"
            ><el-select v-model="form.unit_id"
              ><el-option
                v-for="item in units(form.product_id)"
                :key="item.unit_id"
                :label="item.unit_name"
                :value="item.unit_id" /></el-select></el-form-item
        ></el-col>
      </el-row>
    </el-form>
    <div class="line-title"
      ><strong>子件用量</strong
      ><el-button type="primary" plain @click="addLine">添加子件</el-button></div
    >
    <el-table :data="form.lines" border max-height="430">
      <el-table-column type="index" width="50" />
      <el-table-column label="子件SKU / 规格" min-width="330"
        ><template #default="scope"
          ><el-select
            v-model="scope.row.component_product_id"
            filterable
            style="width: 100%"
            @change="chooseComponent(scope.row)"
            ><el-option
              v-for="item in products.filter((x) => x.id !== form.product_id)"
              :key="item.id"
              :label="skuLabel(item, { barcode: true })"
              :value="item.id" /></el-select></template
      ></el-table-column>
      <el-table-column label="单位" width="140"
        ><template #default="scope"
          ><el-select v-model="scope.row.unit_id"
            ><el-option
              v-for="item in units(scope.row.component_product_id)"
              :key="item.unit_id"
              :label="item.unit_name"
              :value="item.unit_id" /></el-select></template
      ></el-table-column>
      <el-table-column label="标准用量" width="150"
        ><template #default="scope"
          ><el-input-number
            v-model="scope.row.quantity"
            :min="0.000001"
            :controls="false" /></template
      ></el-table-column>
      <el-table-column label="损耗率(%)" width="140"
        ><template #default="scope"
          ><el-input-number
            v-model="scope.row.loss_rate"
            :min="0"
            :max="100"
            :controls="false" /></template
      ></el-table-column>
      <el-table-column label="备注" min-width="160"
        ><template #default="scope"><el-input v-model="scope.row.remark" /></template
      ></el-table-column>
      <el-table-column label="操作" width="75"
        ><template #default="scope"
          ><el-button link type="danger" @click="form.lines.splice(scope.$index, 1)"
            >移除</el-button
          ></template
        ></el-table-column
      >
    </el-table>
    <el-form label-width="90px" class="remark"
      ><el-form-item label="备注"><el-input v-model="form.remark" type="textarea" /></el-form-item
    ></el-form>
    <template #footer
      ><el-button @click="visible = false">取消</el-button
      ><el-button type="primary" :loading="saving" @click="save">保存</el-button></template
    >
  </el-dialog>
</template>

<style scoped>
.toolbar {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}
.toolbar .el-input,
.toolbar .el-select {
  width: 210px;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
.line-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 6px 0 10px;
}
.remark {
  margin-top: 14px;
}
</style>
