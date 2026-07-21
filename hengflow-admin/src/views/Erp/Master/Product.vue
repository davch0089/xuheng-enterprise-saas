<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ContentWrap } from '@/components/ContentWrap'
import { BaseButton } from '@/components/Button'
import {
  addProductSpuApi,
  delProductSpuApi,
  getMasterOptionsApi,
  getProductAttributeOptionsApi,
  getProductSpuApi,
  getProductSpuListApi,
  putProductSpuApi
} from '@/api/erp/master'

defineOptions({ name: 'ErpMasterProduct' })

interface AttributeItem {
  name: string
  value: string
}

interface SkuForm {
  id?: number
  code: string
  barcode?: string
  variant_name?: string
  attributes: AttributeItem[]
  base_unit_id?: number
  multi_unit_enabled: boolean
  unit_group_id?: number
  specification?: string
  default_purchase_price: number
  default_sale_price: number
  tax_rate: number
  min_stock: number
  max_stock?: number
  costing_method: string
  batch_enabled: boolean
  serial_enabled: boolean
  shelf_life_days?: number
  is_default_sku: boolean
  is_active: boolean
  remark?: string
}

const loading = ref(false)
const saving = ref(false)
const rows = ref<any[]>([])
const total = ref(0)
const dialogVisible = ref(false)
const skuDialogVisible = ref(false)
const editingId = ref<number>()
const skuEditingIndex = ref<number>()
const query = reactive<any>({ page: 1, limit: 10, keyword: undefined, is_active: undefined })
const options = reactive<any>({ categories: [], units: [], unitGroups: [], attributes: [] })
const form = reactive<any>({})
const skuForm = reactive<SkuForm>({} as SkuForm)

/** 创建一个带默认计价和跟踪设置的空 SKU。 */
const emptySku = (): SkuForm => ({
  code: '',
  barcode: undefined,
  variant_name: undefined,
  attributes: [],
  base_unit_id: undefined,
  multi_unit_enabled: false,
  unit_group_id: undefined,
  specification: undefined,
  default_purchase_price: 0,
  default_sale_price: 0,
  tax_rate: 0,
  min_stock: 0,
  max_stock: undefined,
  costing_method: 'moving_average',
  batch_enabled: false,
  serial_enabled: false,
  shelf_life_days: undefined,
  is_default_sku: false,
  is_active: true,
  remark: undefined
})

/** 重置商品公共资料表单。 */
const resetForm = () => {
  Object.assign(form, {
    code: '',
    name: '',
    category_id: undefined,
    brand: undefined,
    is_active: true,
    remark: undefined,
    skus: []
  })
}

/** 加载分类、单位、多单位方案及属性历史选项。 */
const loadOptions = async () => {
  const [categories, units, groups, attributes] = await Promise.all([
    getMasterOptionsApi('product-categories'),
    getMasterOptionsApi('units'),
    getMasterOptionsApi('unit-conversions'),
    getProductAttributeOptionsApi()
  ])
  options.categories = categories.data || []
  options.units = units.data || []
  options.unitGroups = groups.data || []
  options.attributes = attributes.data || []
}

/** 分页加载商品 SPU 和 SKU 库存汇总。 */
const loadList = async () => {
  loading.value = true
  try {
    const res = await getProductSpuListApi({
      ...query,
      keyword: query.keyword || undefined
    })
    rows.value = res.data || []
    total.value = res.count || 0
  } finally {
    loading.value = false
  }
}

/** 清空查询条件并回到第一页。 */
const resetSearch = () => {
  Object.assign(query, { page: 1, keyword: undefined, is_active: undefined })
  loadList()
}

/** 打开新增商品窗口，并准备一个默认 SKU。 */
const create = () => {
  editingId.value = undefined
  resetForm()
  const sku = emptySku()
  sku.is_default_sku = true
  form.skus.push(sku)
  dialogVisible.value = true
}

/** 读取商品详情并打开编辑窗口。 */
const edit = async (row: any) => {
  const res = await getProductSpuApi(row.id)
  editingId.value = row.id
  resetForm()
  Object.assign(form, res.data, { skus: res.data?.skus || [] })
  dialogVisible.value = true
}

/** 删除没有业务历史的商品；有历史时后端会要求停用。 */
const remove = async (row: any) => {
  await ElMessageBox.confirm(`确定删除商品“${row.name}”及其全部 SKU 吗？`, '删除确认', {
    type: 'warning'
  })
  await delProductSpuApi(row.id)
  ElMessage.success('删除成功')
  await loadList()
}

/** 打开新增 SKU 窗口。 */
const addSku = () => {
  skuEditingIndex.value = undefined
  Object.assign(skuForm, emptySku())
  skuDialogVisible.value = true
}

/** 打开指定 SKU 的编辑窗口。 */
const editSku = (sku: SkuForm, index: number) => {
  skuEditingIndex.value = index
  Object.assign(skuForm, emptySku(), JSON.parse(JSON.stringify(sku)))
  skuDialogVisible.value = true
}

/** 从当前商品草稿中移除 SKU；最终是否允许删除由后端业务引用校验决定。 */
const removeSku = async (index: number) => {
  if (form.skus.length === 1) return ElMessage.warning('一个商品至少需要一个 SKU')
  await ElMessageBox.confirm('确定移除这个 SKU 吗？', '移除确认', { type: 'warning' })
  const removed = form.skus.splice(index, 1)[0]
  if (removed.is_default_sku && form.skus.length) form.skus[0].is_default_sku = true
}

/** 将指定 SKU 设置为商品的唯一默认 SKU。 */
const setDefaultSku = (index: number) => {
  form.skus.forEach((item: SkuForm, itemIndex: number) => {
    item.is_default_sku = itemIndex === index
  })
}

/** 向 SKU 增加一个规格属性输入行。 */
const addAttribute = () => skuForm.attributes.push({ name: '', value: '' })

/** 返回所选属性已有的值，仍允许录入新值。 */
const attributeValues = (name: string) =>
  options.attributes.find((item: any) => item.name === name)?.values || []

/** 根据属性值生成默认规格显示名称。 */
const generatedVariantName = computed(() =>
  skuForm.attributes
    .filter((item) => item.name && item.value)
    .map((item) => item.value)
    .join(' / ')
)

/** 校验并把 SKU 编辑结果写回商品草稿。 */
const saveSku = () => {
  if (!skuForm.code.trim()) return ElMessage.warning('请填写 SKU 编码')
  if (skuForm.multi_unit_enabled ? !skuForm.unit_group_id : !skuForm.base_unit_id)
    return ElMessage.warning('请选择 SKU 的单位或多单位方案')
  if (skuForm.attributes.some((item) => !item.name.trim() || !item.value.trim()))
    return ElMessage.warning('请完整填写规格属性和值')
  const names = skuForm.attributes.map((item) => item.name.trim().toLowerCase())
  if (new Set(names).size !== names.length) return ElMessage.warning('同一个 SKU 不能重复设置属性')
  const others = form.skus.filter((_: SkuForm, index: number) => index !== skuEditingIndex.value)
  if (others.some((item: SkuForm) => item.code.toLowerCase() === skuForm.code.toLowerCase()))
    return ElMessage.warning('SKU 编码不能重复')
  if (
    skuForm.barcode &&
    others.some((item: SkuForm) => item.barcode?.toLowerCase() === skuForm.barcode?.toLowerCase())
  )
    return ElMessage.warning('SKU 条形码不能重复')
  const data = JSON.parse(JSON.stringify(skuForm))
  data.variant_name = data.variant_name || generatedVariantName.value || '默认规格'
  data.base_unit_id = data.multi_unit_enabled ? undefined : data.base_unit_id
  data.unit_group_id = data.multi_unit_enabled ? data.unit_group_id : undefined
  if (skuEditingIndex.value === undefined) form.skus.push(data)
  else form.skus.splice(skuEditingIndex.value, 1, data)
  if (!form.skus.some((item: SkuForm) => item.is_default_sku)) form.skus[0].is_default_sku = true
  skuDialogVisible.value = false
}

/** 校验并保存一个 SPU 及其全部 SKU。 */
const save = async () => {
  if (!form.code?.trim() || !form.name?.trim() || !form.category_id)
    return ElMessage.warning('请填写商品编码、名称和分类')
  if (!form.skus.length) return ElMessage.warning('一个商品至少需要一个 SKU')
  saving.value = true
  try {
    editingId.value ? await putProductSpuApi(editingId.value, form) : await addProductSpuApi(form)
    ElMessage.success('商品和 SKU 保存成功')
    dialogVisible.value = false
    await Promise.all([loadList(), loadOptions()])
  } catch {
    // 请求层已经展示错误；保留弹窗和用户输入，允许直接修正后重新提交。
  } finally {
    saving.value = false
  }
}

const money = (value: any) => Number(value || 0).toFixed(2)
const categoryName = (id: number) =>
  options.categories.find((item: any) => item.value === id)?.label || `分类#${id}`
const unitName = (sku: any) =>
  sku.multi_unit_enabled
    ? options.unitGroups.find((item: any) => item.value === sku.unit_group_id)?.label
    : options.units.find((item: any) => item.value === sku.base_unit_id)?.label

onMounted(async () => {
  await loadOptions()
  await loadList()
})
</script>

<template>
  <ContentWrap>
    <div class="search-bar">
      <el-input
        v-model="query.keyword"
        clearable
        placeholder="SPU/SKU编码、名称、条形码或规格"
        @keyup.enter="loadList"
      />
      <el-select v-model="query.is_active" clearable placeholder="启用状态">
        <el-option label="启用" :value="true" />
        <el-option label="停用" :value="false" />
      </el-select>
      <BaseButton type="primary" @click="loadList">查询</BaseButton>
      <BaseButton @click="resetSearch">重置</BaseButton>
    </div>
    <div class="toolbar"><BaseButton type="primary" @click="create">新增商品</BaseButton></div>
    <el-table v-loading="loading" :data="rows" border stripe row-key="id">
      <el-table-column type="expand">
        <template #default="scope">
          <div class="sku-expand">
            <el-table :data="scope.row.skus" border size="small">
              <el-table-column prop="code" label="SKU编码" width="150" />
              <el-table-column prop="barcode" label="条形码" width="150" />
              <el-table-column prop="variant_name" label="规格" min-width="150" />
              <el-table-column label="单位" width="150">
                <template #default="skuScope">{{ unitName(skuScope.row) || '-' }}</template>
              </el-table-column>
              <el-table-column label="库存" width="110" align="right">
                <template #default="skuScope">{{ skuScope.row.stock_quantity }}</template>
              </el-table-column>
              <el-table-column label="库存价值" width="130" align="right">
                <template #default="skuScope">¥ {{ money(skuScope.row.inventory_value) }}</template>
              </el-table-column>
              <el-table-column label="默认" width="75">
                <template #default="skuScope">
                  <el-tag v-if="skuScope.row.is_default_sku" type="success">默认</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="75">
                <template #default="skuScope">
                  <el-tag :type="skuScope.row.is_active ? 'success' : 'info'">
                    {{ skuScope.row.is_active ? '启用' : '停用' }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="code" label="SPU编码" width="150" />
      <el-table-column prop="name" label="商品名称" min-width="190" />
      <el-table-column label="分类" width="170">
        <template #default="scope">{{ categoryName(scope.row.category_id) }}</template>
      </el-table-column>
      <el-table-column prop="brand" label="品牌" width="130" />
      <el-table-column prop="sku_count" label="SKU数" width="85" align="right" />
      <el-table-column label="库存汇总" width="115" align="right">
        <template #default="scope">{{ scope.row.stock_quantity }}</template>
      </el-table-column>
      <el-table-column label="库存价值" width="130" align="right">
        <template #default="scope">¥ {{ money(scope.row.inventory_value) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="scope">
          <el-tag :type="scope.row.is_active ? 'success' : 'info'">
            {{ scope.row.is_active ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="130" fixed="right">
        <template #default="scope">
          <BaseButton link type="primary" @click="edit(scope.row)">编辑</BaseButton>
          <BaseButton link type="danger" @click="remove(scope.row)">删除</BaseButton>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination
      v-model:current-page="query.page"
      v-model:page-size="query.limit"
      class="pagination"
      background
      layout="total, sizes, prev, pager, next, jumper"
      :total="total"
      @change="loadList"
    />
  </ContentWrap>

  <el-dialog
    v-model="dialogVisible"
    :title="editingId ? '编辑商品与SKU' : '新增商品与SKU'"
    width="1180px"
    destroy-on-close
  >
    <el-form label-width="95px">
      <el-row :gutter="16">
        <el-col :span="8"
          ><el-form-item label="SPU编码" required><el-input v-model="form.code" /></el-form-item
        ></el-col>
        <el-col :span="8"
          ><el-form-item label="商品名称" required><el-input v-model="form.name" /></el-form-item
        ></el-col>
        <el-col :span="8">
          <el-form-item label="商品分类" required>
            <el-select v-model="form.category_id" filterable style="width: 100%">
              <el-option v-for="item in options.categories" :key="item.value" v-bind="item" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="8"
          ><el-form-item label="品牌"><el-input v-model="form.brand" /></el-form-item
        ></el-col>
        <el-col :span="8"
          ><el-form-item label="启用"><el-switch v-model="form.is_active" /></el-form-item
        ></el-col>
        <el-col :span="24"
          ><el-form-item label="备注"
            ><el-input v-model="form.remark" type="textarea" /></el-form-item
        ></el-col>
      </el-row>
    </el-form>
    <div class="sku-title">
      <span>SKU 规格</span><BaseButton type="primary" @click="addSku">新增SKU</BaseButton>
    </div>
    <el-table :data="form.skus" border max-height="390">
      <el-table-column prop="code" label="SKU编码" width="145" />
      <el-table-column prop="barcode" label="条形码" width="145" />
      <el-table-column prop="variant_name" label="规格" min-width="150" />
      <el-table-column label="属性组合" min-width="190">
        <template #default="scope">
          {{
            scope.row.attributes?.map((item: any) => `${item.name}:${item.value}`).join(' / ') ||
            '默认规格'
          }}
        </template>
      </el-table-column>
      <el-table-column label="单位" width="140"
        ><template #default="scope">{{ unitName(scope.row) }}</template></el-table-column
      >
      <el-table-column label="进价" width="90" align="right"
        ><template #default="scope">{{
          money(scope.row.default_purchase_price)
        }}</template></el-table-column
      >
      <el-table-column label="售价" width="90" align="right"
        ><template #default="scope">{{
          money(scope.row.default_sale_price)
        }}</template></el-table-column
      >
      <el-table-column label="默认" width="75">
        <template #default="scope"
          ><el-radio
            :model-value="scope.row.is_default_sku"
            :value="true"
            @change="setDefaultSku(scope.$index)"
        /></template>
      </el-table-column>
      <el-table-column label="操作" width="125" fixed="right">
        <template #default="scope">
          <BaseButton link type="primary" @click="editSku(scope.row, scope.$index)"
            >编辑</BaseButton
          >
          <BaseButton link type="danger" @click="removeSku(scope.$index)">移除</BaseButton>
        </template>
      </el-table-column>
    </el-table>
    <template #footer>
      <BaseButton @click="dialogVisible = false">取消</BaseButton>
      <BaseButton type="primary" :loading="saving" @click="save">保存商品</BaseButton>
    </template>
  </el-dialog>

  <el-dialog
    v-model="skuDialogVisible"
    title="SKU资料"
    width="920px"
    append-to-body
    destroy-on-close
  >
    <el-form label-width="105px">
      <el-row :gutter="16">
        <el-col :span="8"
          ><el-form-item label="SKU编码" required><el-input v-model="skuForm.code" /></el-form-item
        ></el-col>
        <el-col :span="8"
          ><el-form-item label="条形码"><el-input v-model="skuForm.barcode" /></el-form-item
        ></el-col>
        <el-col :span="8"
          ><el-form-item label="规格名称"
            ><el-input
              v-model="skuForm.variant_name"
              :placeholder="generatedVariantName || '自动生成'" /></el-form-item
        ></el-col>
      </el-row>
      <div class="attribute-header"
        ><span>规格属性</span
        ><BaseButton link type="primary" @click="addAttribute">增加属性</BaseButton></div
      >
      <el-row
        v-for="(attribute, index) in skuForm.attributes"
        :key="index"
        :gutter="10"
        class="attribute-row"
      >
        <el-col :span="10">
          <el-select
            v-model="attribute.name"
            filterable
            allow-create
            placeholder="属性，如颜色"
            style="width: 100%"
          >
            <el-option
              v-for="item in options.attributes"
              :key="item.name"
              :label="item.name"
              :value="item.name"
            />
          </el-select>
        </el-col>
        <el-col :span="10">
          <el-select
            v-model="attribute.value"
            filterable
            allow-create
            placeholder="属性值，如红色"
            style="width: 100%"
          >
            <el-option
              v-for="value in attributeValues(attribute.name)"
              :key="value"
              :label="value"
              :value="value"
            />
          </el-select>
        </el-col>
        <el-col :span="4"
          ><BaseButton type="danger" link @click="skuForm.attributes.splice(index, 1)"
            >删除</BaseButton
          ></el-col
        >
      </el-row>
      <el-divider />
      <el-row :gutter="16">
        <el-col :span="8"
          ><el-form-item label="启用多单位"
            ><el-switch v-model="skuForm.multi_unit_enabled" /></el-form-item
        ></el-col>
        <el-col v-if="!skuForm.multi_unit_enabled" :span="8">
          <el-form-item label="基本单位" required
            ><el-select v-model="skuForm.base_unit_id" filterable style="width: 100%"
              ><el-option
                v-for="item in options.units"
                :key="item.value"
                v-bind="item" /></el-select
          ></el-form-item>
        </el-col>
        <el-col v-else :span="8">
          <el-form-item label="多单位方案" required
            ><el-select v-model="skuForm.unit_group_id" filterable style="width: 100%"
              ><el-option
                v-for="item in options.unitGroups"
                :key="item.value"
                v-bind="item" /></el-select
          ></el-form-item>
        </el-col>
        <el-col :span="8"
          ><el-form-item label="规格型号"><el-input v-model="skuForm.specification" /></el-form-item
        ></el-col>
        <el-col :span="8"
          ><el-form-item label="参考进价"
            ><el-input-number
              v-model="skuForm.default_purchase_price"
              :min="0"
              :precision="4" /></el-form-item
        ></el-col>
        <el-col :span="8"
          ><el-form-item label="参考售价"
            ><el-input-number
              v-model="skuForm.default_sale_price"
              :min="0"
              :precision="4" /></el-form-item
        ></el-col>
        <el-col :span="8"
          ><el-form-item label="税率(%)"
            ><el-input-number
              v-model="skuForm.tax_rate"
              :min="0"
              :max="100"
              :precision="4" /></el-form-item
        ></el-col>
        <el-col :span="8"
          ><el-form-item label="最低库存"
            ><el-input-number v-model="skuForm.min_stock" :min="0" :precision="4" /></el-form-item
        ></el-col>
        <el-col :span="8"
          ><el-form-item label="最高库存"
            ><el-input-number v-model="skuForm.max_stock" :min="0" :precision="4" /></el-form-item
        ></el-col>
        <el-col :span="8"
          ><el-form-item label="批次管理"
            ><el-switch v-model="skuForm.batch_enabled" /></el-form-item
        ></el-col>
        <el-col :span="8"
          ><el-form-item label="序列号管理"
            ><el-switch v-model="skuForm.serial_enabled" /></el-form-item
        ></el-col>
        <el-col :span="8"
          ><el-form-item label="保质期(天)"
            ><el-input-number v-model="skuForm.shelf_life_days" :min="0" /></el-form-item
        ></el-col>
        <el-col :span="8"
          ><el-form-item label="启用"><el-switch v-model="skuForm.is_active" /></el-form-item
        ></el-col>
        <el-col :span="24"
          ><el-form-item label="备注"
            ><el-input v-model="skuForm.remark" type="textarea" /></el-form-item
        ></el-col>
      </el-row>
    </el-form>
    <template #footer>
      <BaseButton @click="skuDialogVisible = false">取消</BaseButton>
      <BaseButton type="primary" @click="saveSku">确定</BaseButton>
    </template>
  </el-dialog>
</template>

<style scoped>
.search-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}
.search-bar .el-input {
  width: 340px;
}
.search-bar .el-select {
  width: 150px;
}
.toolbar {
  margin-bottom: 12px;
}
.pagination {
  justify-content: flex-end;
  margin-top: 16px;
}
.sku-expand {
  padding: 8px 42px;
}
.sku-title,
.attribute-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 4px 0 10px;
  font-weight: 600;
}
.attribute-row {
  margin-bottom: 8px;
}
</style>
