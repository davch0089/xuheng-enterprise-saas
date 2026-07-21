<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { EChartsOption } from 'echarts'
import { ElButton, ElEmpty, ElMessage, ElSkeleton } from 'element-plus'
import { Echart } from '@/components/Echart'
import { getErpDashboardApi } from '@/api/erp/dashboard'

interface DashboardData {
  generated_at?: string
  date_start?: string
  date_end?: string
  summary: Record<string, number>
  trend: any[]
  top_products: any[]
  warehouse_inventory: any[]
  risks: Record<string, any>
  recent_documents: any[]
}

const props = withDefaults(defineProps<{ title?: string }>(), {
  title: 'ERP 经营概览'
})

const loading = ref(false)
const days = ref(30)
const dashboard = ref<DashboardData>({
  summary: {},
  trend: [],
  top_products: [],
  warehouse_inventory: [],
  risks: { items: [] },
  recent_documents: []
})

/** 将金额格式化为带千分位的人民币金额。 */
const money = (value: unknown) =>
  `¥ ${Number(value || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })}`

/** 将数量格式化为最多两位小数。 */
const quantity = (value: unknown) =>
  Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 })

/** 根据当前统计周期生成核心经营指标卡片。 */
const summaryCards = computed(() => {
  const summary = dashboard.value.summary || {}
  return [
    {
      label: '销售净收入',
      value: money(summary.net_sales_revenue),
      note: `近 ${days.value} 天已审核销售`,
      icon: 'ant-design:rise-outlined',
      color: '#3478f6'
    },
    {
      label: '经营毛利',
      value: money(summary.gross_profit),
      note: `毛利率 ${Number(summary.gross_margin_rate || 0).toFixed(2)}%`,
      icon: 'ant-design:fund-outlined',
      color: '#11a879'
    },
    {
      label: '库存金额',
      value: money(summary.inventory_value),
      note: `库存数量 ${quantity(summary.inventory_quantity)}`,
      icon: 'ant-design:database-outlined',
      color: '#7a5af8'
    },
    {
      label: '资金余额',
      value: money(summary.fund_balance),
      note: '启用资金账户余额合计',
      icon: 'ant-design:wallet-outlined',
      color: '#e7891b'
    },
    {
      label: '应收余额',
      value: money(summary.receivable_outstanding),
      note: `逾期 ${money(summary.overdue_receivable)}`,
      icon: 'ant-design:account-book-outlined',
      color: '#e34d59'
    },
    {
      label: '应付余额',
      value: money(summary.payable_outstanding),
      note: `逾期 ${money(summary.overdue_payable)}`,
      icon: 'ant-design:credit-card-outlined',
      color: '#5c6ac4'
    }
  ]
})

/** 生成销售收入、毛利与采购金额的实际业务趋势图。 */
const trendOptions = computed<EChartsOption>(() => {
  const rows = dashboard.value.trend || []
  return {
    color: ['#3478f6', '#11a879', '#f0a020'],
    tooltip: { trigger: 'axis', valueFormatter: (value: any) => money(value) },
    legend: { top: 0, right: 8, data: ['销售净收入', '经营毛利', '采购净额'] },
    grid: { left: 18, right: 18, top: 42, bottom: 10, containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: rows.map((item: any) => String(item.date || '').slice(5)),
      axisLabel: { interval: days.value > 30 ? 6 : days.value > 14 ? 3 : 0 }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#edf0f5' } },
      axisLabel: { formatter: (value: number) => `${value / 10000}万` }
    },
    series: [
      {
        name: '销售净收入',
        type: 'line',
        smooth: true,
        symbol: 'none',
        areaStyle: { color: 'rgba(52, 120, 246, .10)' },
        data: rows.map((item: any) => Number(item.sales_revenue || 0))
      },
      {
        name: '经营毛利',
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: rows.map((item: any) => Number(item.gross_profit || 0))
      },
      {
        name: '采购净额',
        type: 'bar',
        barMaxWidth: 14,
        data: rows.map((item: any) => Number(item.purchase_amount || 0))
      }
    ]
  }
})

/** 生成各仓库库存金额和数量对比图。 */
const warehouseOptions = computed<EChartsOption>(() => {
  const rows = dashboard.value.warehouse_inventory || []
  return {
    color: ['#7a5af8', '#11a879'],
    tooltip: { trigger: 'axis' },
    legend: { top: 0, right: 8, data: ['库存金额', '库存数量'] },
    grid: { left: 16, right: 18, top: 42, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      data: rows.map((item: any) => item.warehouse_name),
      axisLabel: { width: 90, overflow: 'truncate' }
    },
    yAxis: [
      {
        type: 'value',
        splitLine: { lineStyle: { color: '#edf0f5' } },
        axisLabel: { formatter: (value: number) => `${value / 10000}万` }
      },
      { type: 'value', splitLine: { show: false } }
    ],
    series: [
      {
        name: '库存金额',
        type: 'bar',
        barMaxWidth: 24,
        data: rows.map((item: any) => Number(item.inventory_value || 0))
      },
      {
        name: '库存数量',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        data: rows.map((item: any) => Number(item.quantity || 0))
      }
    ]
  }
})

/** 将风险类型转换为可读的业务名称。 */
const riskLabel = (type: string) =>
  ({
    low_stock: '低库存',
    expiring_batch: '近效期',
    overdue_receivable: '应收逾期',
    overdue_payable: '应付逾期'
  })[type] || '业务预警'

/** 从 ERP 聚合接口加载当前统计周期的真实经营数据。 */
const loadDashboard = async () => {
  loading.value = true
  try {
    const res = await getErpDashboardApi(days.value)
    dashboard.value = res.data || dashboard.value
  } catch (error) {
    ElMessage.error('经营数据加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

/** 切换统计周期并重新查询实际业务数据。 */
const changePeriod = (value: number) => {
  if (days.value === value) return
  days.value = value
  loadDashboard()
}

onMounted(loadDashboard)
</script>

<template>
  <div class="erp-overview">
    <header class="overview-header">
      <div>
        <h1>{{ props.title }}</h1>
        <p>
          数据范围：{{ dashboard.date_start || '-' }} 至
          {{ dashboard.date_end || '-' }}，仅统计已审核业务单据
        </p>
      </div>
      <div class="header-actions">
        <div class="period-switch">
          <button
            v-for="item in [7, 30, 90]"
            :key="item"
            :class="{ active: days === item }"
            @click="changePeriod(item)"
          >
            {{ item }} 天
          </button>
        </div>
        <ElButton :loading="loading" @click="loadDashboard">
          <Icon icon="ant-design:reload-outlined" class="mr-5px" />刷新
        </ElButton>
      </div>
    </header>

    <ElSkeleton :loading="loading && !dashboard.generated_at" animated :rows="12">
      <section class="summary-grid">
        <article v-for="card in summaryCards" :key="card.label" class="summary-card">
          <div
            class="summary-icon"
            :style="{ color: card.color, backgroundColor: `${card.color}14` }"
          >
            <Icon :icon="card.icon" :size="24" />
          </div>
          <div>
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <small>{{ card.note }}</small>
          </div>
        </article>
      </section>

      <section class="overview-grid">
        <article class="overview-panel trend-panel">
          <div class="panel-title"><h2>经营趋势</h2><span>销售 · 毛利 · 采购</span></div>
          <Echart :options="trendOptions" height="330px" />
        </article>

        <article class="overview-panel product-panel">
          <div class="panel-title"><h2>SKU 销售排行</h2><span>按销售净收入</span></div>
          <div v-if="dashboard.top_products.length" class="rank-list">
            <div
              v-for="(item, index) in dashboard.top_products"
              :key="`${item.product_id}-${index}`"
              class="rank-row"
            >
              <b :class="{ top: index < 3 }">{{ index + 1 }}</b>
              <div>
                <strong>{{ item.product_name || item.product_code }}</strong>
                <small>{{ item.product_code }} {{ item.variant_name || '' }}</small>
              </div>
              <span>{{ money(item.net_sales_revenue) }}</span>
            </div>
          </div>
          <ElEmpty v-else description="统计周期内暂无销售数据" :image-size="72" />
        </article>

        <article class="overview-panel warehouse-panel">
          <div class="panel-title"><h2>仓库库存结构</h2><span>金额 / 数量</span></div>
          <Echart :options="warehouseOptions" height="300px" />
        </article>

        <article class="overview-panel risk-panel">
          <div class="panel-title">
            <h2>经营风险预警</h2>
            <span>{{ dashboard.risks.items?.length || 0 }} 项重点</span>
          </div>
          <div class="risk-summary">
            <span
              >低库存 <b>{{ dashboard.risks.low_stock_count || 0 }}</b></span
            >
            <span
              >近效期 <b>{{ dashboard.risks.expiring_batch_count || 0 }}</b></span
            >
            <span
              >应收逾期 <b>{{ dashboard.risks.overdue_receivable_count || 0 }}</b></span
            >
            <span
              >应付逾期 <b>{{ dashboard.risks.overdue_payable_count || 0 }}</b></span
            >
          </div>
          <div v-if="dashboard.risks.items?.length" class="risk-list">
            <div
              v-for="(item, index) in dashboard.risks.items"
              :key="`${item.type}-${index}`"
              class="risk-row"
            >
              <span class="risk-tag" :class="item.level">{{ riskLabel(item.type) }}</span>
              <div
                ><strong>{{ item.title }}</strong
                ><small>{{ item.description }}</small></div
              >
              <b>{{ item.amount ? money(item.amount) : quantity(item.quantity) }}</b>
            </div>
          </div>
          <ElEmpty v-else description="当前没有重点经营预警" :image-size="72" />
        </article>

        <article class="overview-panel document-panel">
          <div class="panel-title"><h2>最新业务动态</h2><span>最近审核过账单据</span></div>
          <div v-if="dashboard.recent_documents.length" class="document-table">
            <div class="document-row document-head">
              <span>业务类型</span><span>单据编号</span><span>业务日期</span><span>往来单位</span
              ><span>金额</span>
            </div>
            <div
              v-for="item in dashboard.recent_documents"
              :key="`${item.type}-${item.document_no}`"
              class="document-row"
            >
              <span>{{ item.type_label }}</span>
              <strong>{{ item.document_no }}</strong>
              <span>{{ item.business_date }}</span>
              <span>{{ item.partner }}</span>
              <b>{{ money(item.amount) }}</b>
            </div>
          </div>
          <ElEmpty v-else description="暂无已审核业务单据" :image-size="72" />
        </article>
      </section>
    </ElSkeleton>
  </div>
</template>

<style scoped lang="less">
.erp-overview {
  min-height: 100%;
  padding: 20px;
  box-sizing: border-box;
  background: var(--app-content-bg-color);
  color: var(--el-text-color-primary);
}
.overview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
  h1 {
    margin: 0;
    font-size: 24px;
    font-weight: 650;
  }
  p {
    margin: 7px 0 0;
    color: var(--el-text-color-secondary);
    font-size: 13px;
  }
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.period-switch {
  display: flex;
  padding: 3px;
  border-radius: 7px;
  background: var(--el-fill-color-light);
  button {
    padding: 7px 13px;
    border: 0;
    border-radius: 5px;
    color: var(--el-text-color-secondary);
    background: transparent;
    cursor: pointer;
  }
  button.active {
    color: var(--el-color-primary);
    background: var(--el-bg-color);
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  }
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 14px;
}
.summary-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 18px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 9px;
  background: var(--el-bg-color);
  box-shadow: 0 2px 10px rgba(31, 35, 41, 0.025);
  .summary-icon {
    display: grid;
    place-items: center;
    width: 42px;
    height: 42px;
    flex: 0 0 42px;
    border-radius: 9px;
  }
  div:last-child {
    min-width: 0;
  }
  span,
  small {
    display: block;
    color: var(--el-text-color-secondary);
    font-size: 12px;
  }
  strong {
    display: block;
    margin: 7px 0 6px;
    overflow: hidden;
    font-size: 18px;
    white-space: nowrap;
    text-overflow: ellipsis;
  }
}
.overview-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 14px;
}
.overview-panel {
  min-width: 0;
  padding: 18px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 9px;
  background: var(--el-bg-color);
}
.panel-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  h2 {
    margin: 0;
    font-size: 16px;
  }
  span {
    color: var(--el-text-color-secondary);
    font-size: 12px;
  }
}
.rank-list,
.risk-list {
  max-height: 330px;
  overflow: auto;
}
.rank-row {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  min-height: 38px;
  padding: 7px 0;
  border-bottom: 1px solid var(--el-border-color-extra-light);
  > b {
    display: grid;
    place-items: center;
    width: 22px;
    height: 22px;
    border-radius: 5px;
    color: var(--el-text-color-secondary);
    background: var(--el-fill-color-light);
  }
  > b.top {
    color: #fff;
    background: #3478f6;
  }
  div strong,
  div small {
    display: block;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }
  div strong {
    font-size: 13px;
    font-weight: 500;
  }
  div small {
    margin-top: 3px;
    color: var(--el-text-color-secondary);
    font-size: 11px;
  }
  > span {
    color: #3478f6;
    font-size: 13px;
    font-weight: 600;
  }
}
.risk-summary {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin: 12px 0;
}
.risk-summary span {
  padding: 9px;
  border-radius: 6px;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-light);
  text-align: center;
  font-size: 12px;
}
.risk-summary b {
  margin-left: 4px;
  color: #e34d59;
}
.risk-row {
  display: grid;
  grid-template-columns: 62px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid var(--el-border-color-extra-light);
  div strong,
  div small {
    display: block;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }
  div strong {
    font-size: 13px;
    font-weight: 500;
  }
  div small {
    margin-top: 3px;
    color: var(--el-text-color-secondary);
    font-size: 11px;
  }
  > b {
    font-size: 12px;
  }
}
.risk-tag {
  padding: 4px 6px;
  border-radius: 4px;
  color: #d97706;
  background: #fff7e6;
  text-align: center;
  font-size: 11px;
}
.risk-tag.high {
  color: #d03050;
  background: #fff0f1;
}
.document-panel {
  grid-column: 1 / -1;
}
.document-table {
  overflow-x: auto;
}
.document-row {
  display: grid;
  grid-template-columns: 120px 1.2fr 130px 1.4fr 150px;
  align-items: center;
  min-width: 760px;
  min-height: 42px;
  border-bottom: 1px solid var(--el-border-color-extra-light);
  font-size: 13px;
}
.document-row strong {
  color: #3478f6;
  font-weight: 500;
}
.document-row b {
  text-align: right;
}
.document-head {
  min-height: 38px;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-light);
}
.document-head span {
  padding: 0 8px;
}
@media (max-width: 1500px) {
  .summary-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}
@media (max-width: 900px) {
  .overview-header {
    align-items: flex-start;
    gap: 16px;
    flex-direction: column;
  }
  .summary-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .overview-grid {
    grid-template-columns: 1fr;
  }
  .document-panel {
    grid-column: auto;
  }
}
</style>
