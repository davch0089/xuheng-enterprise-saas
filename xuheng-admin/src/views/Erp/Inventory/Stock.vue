<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { ContentWrap } from '@/components/ContentWrap'
import { BaseButton } from '@/components/Button'
import { skuSpec } from '@/utils/erp/product'
import { getMasterOptionsApi } from '@/api/erp/master'
import {
  getBatchAllocationApi,
  getSerialHistoryApi,
  getStockBatchListApi,
  getStockListApi,
  getStockMovementListApi,
  getStockSerialListApi
} from '@/api/erp/inventory'

defineOptions({ name: 'ErpInventoryStock' })

interface Option {
  label: string
  value: number
}

const activeTab = ref('balance')
const loading = ref(false)
const rows = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const limit = ref(20)
const warehouses = ref<Option[]>([])
const categories = ref<Option[]>([])
const summary = reactive({ stock_rows: 0, inventory_value: 0, negative_rows: 0, low_stock_rows: 0 })
const search = reactive<any>({ keyword: '', warehouse_id: undefined, date_range: [] })
const allocationVisible = ref(false)
const allocationLoading = ref(false)
const allocation = reactive<any>({ row: undefined, quantity: 1, items: [], shortage_quantity: 0 })
const historyVisible = ref(false)
const historyLoading = ref(false)
const serialCurrent = ref<any>()
const serialHistory = ref<any[]>([])

const tabPlaceholder = computed(() => {
  if (activeTab.value === 'movement') return '流水号、业务单号、商品编码或名称'
  if (activeTab.value === 'batch') return '批次号、商品编码或名称'
  if (activeTab.value === 'serial') return '序列号、入库单号、商品编码或名称'
  return '商品编码、名称、条码或规格'
})

const money = (value: unknown) => Number(value || 0).toFixed(2)
const quantity = (value: unknown) =>
  Number(value || 0)
    .toFixed(6)
    .replace(/\.?0+$/, '')
const datetime = (value: string | undefined) =>
  value ? dayjs(value).format('YYYY-MM-DD HH:mm:ss') : '-'
const movementLabels: Record<string, string> = {
  PURCHASE_IN: '采购入库',
  OTHER_IN: '其他入库',
  SALE_RETURN: '销售退货入库',
  STOCK_GAIN: '盘盈',
  PRODUCTION_IN: '生产入库',
  TRANSFER_IN: '调拨入库',
  SALE_OUT: '销售出库',
  OTHER_OUT: '其他出库',
  PURCHASE_RETURN: '采购退货出库',
  STOCK_LOSS: '盘亏',
  MATERIAL_OUT: '生产领料',
  TRANSFER_OUT: '调拨出库',
  REVERSAL: '冲销'
}
const movementLabel = (value: string) => movementLabels[value] || value

const loadOptions = async () => {
  const [warehouseRes, categoryRes] = await Promise.all([
    getMasterOptionsApi('warehouses'),
    getMasterOptionsApi('product-categories')
  ])
  warehouses.value = warehouseRes.data || []
  categories.value = categoryRes.data || []
}

const params = () => {
  const [date_start, date_end] = search.date_range || []
  return {
    page: page.value,
    limit: limit.value,
    keyword: search.keyword || undefined,
    warehouse_id: search.warehouse_id || undefined,
    category_id: search.category_id || undefined,
    stock_status: search.stock_status || undefined,
    direction: search.direction,
    date_start,
    date_end,
    expiry_status: search.expiry_status || undefined,
    status: search.serial_status || undefined
  }
}

const loadList = async () => {
  loading.value = true
  try {
    let res: IResponse
    if (activeTab.value === 'movement') res = await getStockMovementListApi(params())
    else if (activeTab.value === 'batch') res = await getStockBatchListApi(params())
    else if (activeTab.value === 'serial') res = await getStockSerialListApi(params())
    else res = await getStockListApi(params())
    if (activeTab.value === 'balance') {
      rows.value = res.data?.items || []
      Object.assign(summary, res.data?.summary || {})
    } else {
      rows.value = res.data || []
    }
    total.value = res.count || 0
  } finally {
    loading.value = false
  }
}

const searchList = () => {
  page.value = 1
  loadList()
}

const resetSearch = () => {
  Object.assign(search, {
    keyword: '',
    warehouse_id: undefined,
    category_id: undefined,
    stock_status: undefined,
    direction: undefined,
    date_range: [],
    expiry_status: undefined,
    serial_status: undefined
  })
  searchList()
}

const changeTab = () => {
  rows.value = []
  total.value = 0
  page.value = 1
  loadList()
}

const stockTag = (row: any) => {
  if (Number(row.quantity) < 0) return { label: '负库存', type: 'danger' }
  if (Number(row.min_stock) > 0 && Number(row.available_quantity) < Number(row.min_stock)) {
    return { label: '低库存', type: 'warning' }
  }
  return { label: '正常', type: 'success' }
}

const expiryTag = (days: number | null) => {
  if (days === null || days === undefined) return { label: '无有效期', type: 'info' }
  if (days < 0) return { label: `已过期 ${Math.abs(days)} 天`, type: 'danger' }
  if (days <= 30) return { label: `剩余 ${days} 天`, type: 'warning' }
  return { label: `剩余 ${days} 天`, type: 'success' }
}

/** 打开批次先进先出建议窗口。 */
const openAllocation = (row: any) => {
  Object.assign(allocation, {
    row,
    quantity: Math.max(1, Number(row.available_quantity || 1)),
    items: [],
    shortage_quantity: 0
  })
  allocationVisible.value = true
}

/** 按先到期先出、再先进先出顺序计算批次分配。 */
const loadAllocation = async () => {
  if (!allocation.row || Number(allocation.quantity) <= 0)
    return ElMessage.warning('请输入出库数量')
  allocationLoading.value = true
  try {
    const res = await getBatchAllocationApi({
      warehouse_id: allocation.row.warehouse_id,
      product_id: allocation.row.product_id,
      quantity: Number(allocation.quantity)
    })
    allocation.items = res.data?.items || []
    allocation.shortage_quantity = Number(res.data?.shortage_quantity || 0)
  } finally {
    allocationLoading.value = false
  }
}

/** 查询序列号从首次入库到当前状态的不可变移动履历。 */
const openSerialHistory = async (row: any) => {
  serialCurrent.value = row
  historyVisible.value = true
  historyLoading.value = true
  try {
    const res = await getSerialHistoryApi(row.id)
    serialHistory.value = res.data || []
  } finally {
    historyLoading.value = false
  }
}

onMounted(async () => {
  await loadOptions()
  await loadList()
})
</script>

<template>
  <ContentWrap>
    <el-tabs v-model="activeTab" class="stock-tabs" @tab-change="changeTab">
      <el-tab-pane label="库存余额" name="balance" />
      <el-tab-pane label="收发明细" name="movement" />
      <el-tab-pane label="批次库存" name="batch" />
      <el-tab-pane label="序列号库存" name="serial" />
    </el-tabs>

    <div class="search-bar">
      <el-input
        v-model="search.keyword"
        clearable
        :placeholder="tabPlaceholder"
        @keyup.enter="searchList"
      />
      <el-select v-model="search.warehouse_id" clearable filterable placeholder="仓库">
        <el-option v-for="item in warehouses" :key="item.value" v-bind="item" />
      </el-select>
      <template v-if="activeTab === 'balance'">
        <el-select v-model="search.category_id" clearable filterable placeholder="商品分类">
          <el-option v-for="item in categories" :key="item.value" v-bind="item" />
        </el-select>
        <el-select v-model="search.stock_status" clearable placeholder="库存状态">
          <el-option label="有库存" value="positive" />
          <el-option label="零库存" value="zero" />
          <el-option label="负库存" value="negative" />
          <el-option label="低于最低库存" value="low" />
        </el-select>
      </template>
      <template v-else-if="activeTab === 'movement'">
        <el-select v-model="search.direction" clearable placeholder="收发方向">
          <el-option label="收入" :value="1" />
          <el-option label="发出/冲销" :value="-1" />
        </el-select>
        <el-date-picker
          v-model="search.date_range"
          type="daterange"
          value-format="YYYY-MM-DD"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
        />
      </template>
      <el-select
        v-else-if="activeTab === 'batch'"
        v-model="search.expiry_status"
        clearable
        placeholder="效期状态"
      >
        <el-option label="正常" value="normal" />
        <el-option label="30天内到期" value="near" />
        <el-option label="已过期" value="expired" />
      </el-select>
      <el-select v-else v-model="search.serial_status" clearable placeholder="序列号状态">
        <el-option label="在库" value="in_stock" />
        <el-option label="已出库" value="outbound" />
        <el-option label="冻结" value="frozen" />
        <el-option label="已冲销" value="voided" />
      </el-select>
      <BaseButton type="primary" @click="searchList">查询</BaseButton>
      <BaseButton @click="resetSearch">重置</BaseButton>
    </div>

    <div v-if="activeTab === 'balance'" class="summary-grid">
      <div class="summary-card">
        <span>库存记录</span><strong>{{ summary.stock_rows }}</strong
        ><small>商品 × 仓库</small>
      </div>
      <div class="summary-card value">
        <span>库存成本</span><strong>¥ {{ money(summary.inventory_value) }}</strong
        ><small>移动平均成本口径</small>
      </div>
      <div class="summary-card warning">
        <span>低库存</span><strong>{{ summary.low_stock_rows }}</strong
        ><small>低于商品最低库存</small>
      </div>
      <div class="summary-card danger">
        <span>负库存</span><strong>{{ summary.negative_rows }}</strong
        ><small>需要及时处理</small>
      </div>
    </div>

    <el-table v-if="activeTab === 'balance'" v-loading="loading" :data="rows" border stripe>
      <el-table-column prop="product_code" label="SKU编码" width="130" fixed="left" />
      <el-table-column
        prop="product_name"
        label="商品名称"
        min-width="180"
        fixed="left"
        show-overflow-tooltip
      />
      <el-table-column label="SKU规格" min-width="150" show-overflow-tooltip
        ><template #default="{ row }">{{ skuSpec(row) }}</template></el-table-column
      >
      <el-table-column prop="barcode" label="条码" min-width="140" show-overflow-tooltip />
      <el-table-column prop="category_name" label="商品分类" width="120" />
      <el-table-column prop="warehouse_name" label="仓库" width="130" />
      <el-table-column prop="base_unit_name" label="基本单位" width="90" />
      <el-table-column label="账面数量" width="120" align="right">
        <template #default="{ row }">{{ quantity(row.quantity) }}</template>
      </el-table-column>
      <el-table-column label="多单位数量" min-width="160">
        <template #default="{ row }">{{ row.unit_breakdown }}</template>
      </el-table-column>
      <el-table-column label="预留数量" width="110" align="right">
        <template #default="{ row }">{{ quantity(row.reserved_quantity) }}</template>
      </el-table-column>
      <el-table-column label="冻结数量" width="110" align="right">
        <template #default="{ row }">{{ quantity(row.frozen_quantity) }}</template>
      </el-table-column>
      <el-table-column label="可用数量" width="120" align="right">
        <template #default="{ row }"
          ><b>{{ quantity(row.available_quantity) }}</b></template
        >
      </el-table-column>
      <el-table-column label="单位成本" width="120" align="right">
        <template #default="{ row }">{{ money(row.average_cost) }}</template>
      </el-table-column>
      <el-table-column label="库存成本" width="130" align="right">
        <template #default="{ row }">{{ money(row.inventory_value) }}</template>
      </el-table-column>
      <el-table-column label="库存状态" width="100" align="center">
        <template #default="{ row }"
          ><el-tag :type="stockTag(row).type">{{ stockTag(row).label }}</el-tag></template
        >
      </el-table-column>
      <el-table-column label="最后变动" width="170">
        <template #default="{ row }">{{ datetime(row.last_movement_at) }}</template>
      </el-table-column>
    </el-table>

    <el-table v-else-if="activeTab === 'movement'" v-loading="loading" :data="rows" border stripe>
      <el-table-column prop="occurred_at" label="发生时间" width="170">
        <template #default="{ row }">{{ datetime(row.occurred_at) }}</template>
      </el-table-column>
      <el-table-column prop="movement_no" label="流水号" min-width="225" show-overflow-tooltip />
      <el-table-column prop="business_no" label="业务单号" min-width="165" />
      <el-table-column label="业务类型" width="105"
        ><template #default="{ row }">{{
          movementLabel(row.movement_type)
        }}</template></el-table-column
      >
      <el-table-column prop="product_code" label="SKU编码" width="125" />
      <el-table-column prop="product_name" label="商品名称" min-width="170" show-overflow-tooltip />
      <el-table-column label="SKU规格" min-width="150" show-overflow-tooltip
        ><template #default="{ row }">{{ skuSpec(row) }}</template></el-table-column
      >
      <el-table-column prop="warehouse_name" label="仓库" width="120" />
      <el-table-column label="方向" width="80" align="center">
        <template #default="{ row }"
          ><el-tag :type="row.direction === 1 ? 'success' : 'danger'">{{
            row.direction === 1 ? '收入' : '发出'
          }}</el-tag></template
        >
      </el-table-column>
      <el-table-column label="变动数量" width="115" align="right"
        ><template #default="{ row }">{{ quantity(row.quantity) }}</template></el-table-column
      >
      <el-table-column label="变动成本" width="120" align="right"
        ><template #default="{ row }">{{ money(row.amount) }}</template></el-table-column
      >
      <el-table-column label="变动前数量" width="120" align="right"
        ><template #default="{ row }">{{
          quantity(row.balance_quantity_before)
        }}</template></el-table-column
      >
      <el-table-column label="变动后数量" width="120" align="right"
        ><template #default="{ row }">{{
          quantity(row.balance_quantity_after)
        }}</template></el-table-column
      >
      <el-table-column label="变动后成本" width="120" align="right"
        ><template #default="{ row }">{{
          money(row.average_cost_after)
        }}</template></el-table-column
      >
    </el-table>

    <el-table v-else-if="activeTab === 'batch'" v-loading="loading" :data="rows" border stripe>
      <el-table-column prop="batch_no" label="批次号" min-width="150" fixed="left" />
      <el-table-column prop="product_code" label="SKU编码" width="130" />
      <el-table-column prop="product_name" label="商品名称" min-width="180" show-overflow-tooltip />
      <el-table-column label="SKU规格" min-width="150" show-overflow-tooltip
        ><template #default="{ row }">{{ skuSpec(row) }}</template></el-table-column
      >
      <el-table-column prop="warehouse_name" label="仓库" width="130" />
      <el-table-column prop="production_date" label="生产日期" width="120" />
      <el-table-column prop="expiry_date" label="有效期至" width="120" />
      <el-table-column label="账面数量" width="120" align="right"
        ><template #default="{ row }">{{ quantity(row.quantity) }}</template></el-table-column
      >
      <el-table-column label="预留数量" width="110" align="right"
        ><template #default="{ row }">{{
          quantity(row.reserved_quantity)
        }}</template></el-table-column
      >
      <el-table-column label="冻结数量" width="110" align="right"
        ><template #default="{ row }">{{
          quantity(row.frozen_quantity)
        }}</template></el-table-column
      >
      <el-table-column label="可用数量" width="120" align="right"
        ><template #default="{ row }"
          ><b>{{ quantity(row.available_quantity) }}</b></template
        ></el-table-column
      >
      <el-table-column label="效期状态" width="135" align="center">
        <template #default="{ row }"
          ><el-tag :type="expiryTag(row.days_to_expiry).type">{{
            expiryTag(row.days_to_expiry).label
          }}</el-tag></template
        >
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }"
          ><el-button link type="primary" @click="openAllocation(row)"
            >出库建议</el-button
          ></template
        >
      </el-table-column>
    </el-table>

    <el-table v-else v-loading="loading" :data="rows" border stripe>
      <el-table-column prop="serial_no" label="序列号" min-width="190" fixed="left" />
      <el-table-column prop="product_code" label="SKU编码" width="130" />
      <el-table-column prop="product_name" label="商品名称" min-width="180" show-overflow-tooltip />
      <el-table-column label="SKU规格" min-width="150" show-overflow-tooltip
        ><template #default="{ row }">{{ skuSpec(row) }}</template></el-table-column
      >
      <el-table-column prop="warehouse_name" label="当前仓库" width="130" />
      <el-table-column label="状态" width="100" align="center">
        <template #default="{ row }"
          ><el-tag
            :type="
              row.status === 'in_stock' ? 'success' : row.status === 'frozen' ? 'warning' : 'info'
            "
            >{{
              row.status === 'in_stock'
                ? '在库'
                : row.status === 'frozen'
                  ? '冻结'
                  : row.status === 'voided'
                    ? '已冲销'
                    : '已出库'
            }}</el-tag
          ></template
        >
      </el-table-column>
      <el-table-column prop="inbound_receipt_no" label="入库单号" min-width="165" />
      <el-table-column label="入库时间" width="170"
        ><template #default="{ row }">{{ datetime(row.inbound_at) }}</template></el-table-column
      >
      <el-table-column label="操作" width="110" fixed="right">
        <template #default="{ row }"
          ><el-button link type="primary" @click="openSerialHistory(row)"
            >生命周期</el-button
          ></template
        >
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      v-model:page-size="limit"
      class="pagination"
      background
      layout="total, sizes, prev, pager, next, jumper"
      :total="total"
      @current-change="loadList"
      @size-change="searchList"
    />
  </ContentWrap>

  <el-dialog v-model="allocationVisible" title="批次出库建议（FEFO / FIFO）" width="760px">
    <el-alert
      title="优先选择最早到期批次；无效期或同效期时按先进先出排序。已过期批次会醒目标记，请按质量制度决定是否允许出库。"
      type="info"
      :closable="false"
    />
    <div class="allocation-form">
      <span
        >{{ allocation.row?.product_code }} {{ allocation.row?.product_name }} /
        {{ skuSpec(allocation.row) }} / {{ allocation.row?.warehouse_name }}</span
      >
      <el-input-number v-model="allocation.quantity" :min="0.000001" :controls="false" />
      <el-button type="primary" :loading="allocationLoading" @click="loadAllocation"
        >生成建议</el-button
      >
    </div>
    <el-table :data="allocation.items" border max-height="360">
      <el-table-column prop="priority" label="优先级" width="80" />
      <el-table-column prop="batch_no" label="批次号" min-width="145" />
      <el-table-column prop="expiry_date" label="有效期至" width="120" />
      <el-table-column label="效期" width="115"
        ><template #default="{ row }"
          ><el-tag :type="expiryTag(row.days_to_expiry).type">{{
            expiryTag(row.days_to_expiry).label
          }}</el-tag></template
        ></el-table-column
      >
      <el-table-column label="可用量" width="105" align="right"
        ><template #default="{ row }">{{
          quantity(row.available_quantity)
        }}</template></el-table-column
      >
      <el-table-column label="建议量" width="105" align="right"
        ><template #default="{ row }"
          ><b>{{ quantity(row.suggested_quantity) }}</b></template
        ></el-table-column
      >
    </el-table>
    <el-alert
      v-if="allocation.shortage_quantity > 0"
      class="allocation-warning"
      :title="`可用批次不足，缺口 ${quantity(allocation.shortage_quantity)}`"
      type="error"
      :closable="false"
    />
  </el-dialog>

  <el-dialog
    v-model="historyVisible"
    :title="`序列号生命周期：${serialCurrent?.serial_no || ''}`"
    width="820px"
  >
    <el-table v-loading="historyLoading" :data="serialHistory" border max-height="480">
      <el-table-column label="发生时间" width="170"
        ><template #default="{ row }">{{ datetime(row.occurred_at) }}</template></el-table-column
      >
      <el-table-column label="库存动作" width="120"
        ><template #default="{ row }">{{
          movementLabel(row.movement_type)
        }}</template></el-table-column
      >
      <el-table-column prop="source_no" label="业务单号" min-width="155" />
      <el-table-column label="状态变化" min-width="145"
        ><template #default="{ row }"
          >{{ row.from_status || '未入库' }} → {{ row.to_status }}</template
        ></el-table-column
      >
      <el-table-column label="仓库变化" min-width="180"
        ><template #default="{ row }"
          >{{ row.from_warehouse_name || '外部' }} → {{ row.to_warehouse_name || '外部' }}</template
        ></el-table-column
      >
      <el-table-column label="批次变化" min-width="145"
        ><template #default="{ row }"
          >{{ row.from_batch_no || '-' }} → {{ row.to_batch_no || '-' }}</template
        ></el-table-column
      >
    </el-table>
    <el-empty
      v-if="!historyLoading && !serialHistory.length"
      description="暂无生命周期流水；历史存量将在下一次库存移动后开始记录"
    />
  </el-dialog>
</template>

<style scoped>
.stock-tabs {
  margin-top: -8px;
}
.search-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 8px 0 16px;
}
.search-bar > .el-input {
  width: 290px;
}
.search-bar > .el-select {
  width: 150px;
}
.allocation-form {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 14px 0;
}
.allocation-form > span {
  flex: 1;
}
.allocation-warning {
  margin-top: 12px;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(180px, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}
.summary-card {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  padding: 16px 18px;
  background: #f5f8fc;
  border-left: 4px solid #409eff;
  border-radius: 4px;
}
.summary-card span {
  color: var(--el-text-color-regular);
}
.summary-card strong {
  color: #263445;
  font-size: 24px;
}
.summary-card small {
  grid-column: 1 / 3;
  margin-top: 6px;
  color: var(--el-text-color-secondary);
}
.summary-card.value {
  border-left-color: #67c23a;
}
.summary-card.warning {
  border-left-color: #e6a23c;
}
.summary-card.danger {
  border-left-color: #f56c6c;
}
.pagination {
  justify-content: flex-end;
  margin-top: 16px;
}
@media (max-width: 1000px) {
  .summary-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
