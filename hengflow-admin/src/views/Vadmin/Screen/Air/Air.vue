<script lang="ts" setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import type { EChartsOption } from 'echarts'
import { FullScreenContainer } from '@kjgl77/datav-vue3'
import { Echart } from '@/components/Echart'
import { getErpDashboardApi } from '@/api/erp/dashboard'

defineOptions({ name: 'ErpOperatingCockpit' })

interface Summary {
  net_sales_revenue: number
  gross_profit: number
  gross_margin_rate: number
  purchase_amount: number
  inventory_quantity: number
  inventory_value: number
  fund_balance: number
  receivable_outstanding: number
  payable_outstanding: number
  overdue_receivable: number
  overdue_payable: number
}

const loading = ref(false)
const days = ref(30)
const now = ref(new Date())
const dashboard = ref<any>({
  summary: {} as Summary,
  trend: [],
  top_products: [],
  warehouse_inventory: [],
  risks: { items: [] },
  recent_documents: []
})
let clockTimer: number | undefined
let refreshTimer: number | undefined

/** 将金额格式化为适合大屏阅读的万元或亿元单位。 */
const compactMoney = (value: any) => {
  const amount = Number(value || 0)
  if (Math.abs(amount) >= 100000000) return `¥ ${(amount / 100000000).toFixed(2)} 亿`
  if (Math.abs(amount) >= 10000) return `¥ ${(amount / 10000).toFixed(2)} 万`
  return `¥ ${amount.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`
}

/** 将表格金额格式化为带千分位的人民币金额。 */
const money = (value: any) =>
  `¥ ${Number(value || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })}`

/** 格式化库存数量并保留最多两位小数。 */
const quantity = (value: any) =>
  Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 })

/** 格式化大屏右上角实时日期和时间。 */
const currentTime = computed(() =>
  now.value.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  })
)

/** 读取 ERP 聚合指标；页面保留上一份数据直到新请求完成。 */
const loadDashboard = async () => {
  loading.value = true
  try {
    const res = await getErpDashboardApi(days.value)
    dashboard.value = res.data || dashboard.value
  } finally {
    loading.value = false
  }
}

/** 切换统计周期并立即刷新全部指标。 */
const changePeriod = (value: number) => {
  days.value = value
  loadDashboard()
}

/** 生成顶部六项核心经营指标。 */
const summaryCards = computed(() => {
  const summary = dashboard.value.summary || {}
  return [
    {
      label: '销售净收入',
      value: compactMoney(summary.net_sales_revenue),
      note: `近 ${days.value} 天`,
      tone: 'cyan'
    },
    {
      label: '经营毛利',
      value: compactMoney(summary.gross_profit),
      note: `毛利率 ${Number(summary.gross_margin_rate || 0).toFixed(1)}%`,
      tone: 'green'
    },
    {
      label: '库存金额',
      value: compactMoney(summary.inventory_value),
      note: `库存数量 ${quantity(summary.inventory_quantity)}`,
      tone: 'blue'
    },
    {
      label: '资金余额',
      value: compactMoney(summary.fund_balance),
      note: '启用资金账户合计',
      tone: 'gold'
    },
    {
      label: '应收余额',
      value: compactMoney(summary.receivable_outstanding),
      note: `逾期 ${compactMoney(summary.overdue_receivable)}`,
      tone: 'orange'
    },
    {
      label: '应付余额',
      value: compactMoney(summary.payable_outstanding),
      note: `逾期 ${compactMoney(summary.overdue_payable)}`,
      tone: 'violet'
    }
  ]
})

/** 构建销售收入、毛利和采购额的日趋势图。 */
const trendOptions = computed<EChartsOption>(() => {
  const rows = dashboard.value.trend || []
  return {
    color: ['#25d7ff', '#37e2a4', '#ffc857'],
    tooltip: { trigger: 'axis', valueFormatter: (value: any) => money(value) },
    legend: {
      right: 10,
      top: 0,
      textStyle: { color: '#91a9c9' },
      data: ['销售净收入', '毛利', '采购净额']
    },
    grid: { left: 18, right: 18, top: 38, bottom: 10, containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: rows.map((item: any) => String(item.date).slice(5)),
      axisLine: { lineStyle: { color: '#27496d' } },
      axisLabel: { color: '#7892b2', interval: days.value > 30 ? 6 : days.value > 14 ? 3 : 0 }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(62, 105, 151, .22)' } },
      axisLabel: { color: '#7892b2', formatter: (value: number) => `${value / 10000}万` }
    },
    series: [
      {
        name: '销售净收入',
        type: 'line',
        smooth: true,
        symbol: 'none',
        areaStyle: { color: 'rgba(37, 215, 255, .12)' },
        data: rows.map((item: any) => Number(item.sales_revenue || 0))
      },
      {
        name: '毛利',
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: rows.map((item: any) => Number(item.gross_profit || 0))
      },
      {
        name: '采购净额',
        type: 'bar',
        barMaxWidth: 12,
        data: rows.map((item: any) => Number(item.purchase_amount || 0))
      }
    ]
  }
})

/** 构建资金、往来余额和库存价值对比图。 */
const capitalOptions = computed<EChartsOption>(() => {
  const summary = dashboard.value.summary || {}
  return {
    color: ['#37e2a4'],
    tooltip: { trigger: 'axis', valueFormatter: (value: any) => money(value) },
    grid: { left: 12, right: 18, top: 10, bottom: 8, containLabel: true },
    xAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(62, 105, 151, .2)' } },
      axisLabel: { color: '#7892b2', formatter: (value: number) => `${value / 10000}万` }
    },
    yAxis: {
      type: 'category',
      data: ['库存金额', '应付余额', '应收余额', '资金余额'],
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#9cb4d3' }
    },
    series: [
      {
        type: 'bar',
        barWidth: 13,
        showBackground: true,
        backgroundStyle: { color: 'rgba(41, 73, 112, .22)', borderRadius: 8 },
        itemStyle: {
          borderRadius: 8,
          color: (params: any) => ['#4d8dff', '#a777ff', '#ff9f43', '#37e2a4'][params.dataIndex]
        },
        label: {
          show: true,
          position: 'right',
          color: '#d9e9ff',
          formatter: ({ value }: any) => compactMoney(value)
        },
        data: [
          Number(summary.inventory_value || 0),
          Number(summary.payable_outstanding || 0),
          Number(summary.receivable_outstanding || 0),
          Number(summary.fund_balance || 0)
        ]
      }
    ]
  }
})

/** 构建销售额排名靠前的 SKU 横向柱状图。 */
const productOptions = computed<EChartsOption>(() => {
  const rows = [...(dashboard.value.top_products || [])].reverse()
  return {
    color: ['#25d7ff'],
    tooltip: { trigger: 'axis', valueFormatter: (value: any) => money(value) },
    grid: { left: 8, right: 24, top: 5, bottom: 8, containLabel: true },
    xAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(62, 105, 151, .18)' } },
      axisLabel: { color: '#7892b2', formatter: (value: number) => `${value / 10000}万` }
    },
    yAxis: {
      type: 'category',
      data: rows.map((item: any) => `${item.product_code} ${item.variant_name || ''}`),
      axisLabel: { color: '#9cb4d3', width: 120, overflow: 'truncate' },
      axisLine: { show: false },
      axisTick: { show: false }
    },
    series: [
      {
        type: 'bar',
        barWidth: 11,
        itemStyle: { borderRadius: 8, color: '#25d7ff' },
        data: rows.map((item: any) => Number(item.net_sales_revenue || 0))
      }
    ]
  }
})

/** 构建各仓库库存金额和数量的组合图。 */
const warehouseOptions = computed<EChartsOption>(() => {
  const rows = dashboard.value.warehouse_inventory || []
  return {
    color: ['#4d8dff', '#37e2a4'],
    tooltip: { trigger: 'axis' },
    legend: { top: 0, right: 4, textStyle: { color: '#91a9c9' }, data: ['库存金额', '库存数量'] },
    grid: { left: 12, right: 12, top: 38, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      data: rows.map((item: any) => item.warehouse_name),
      axisLabel: { color: '#7892b2', width: 80, overflow: 'truncate' },
      axisLine: { lineStyle: { color: '#27496d' } }
    },
    yAxis: [
      {
        type: 'value',
        splitLine: { lineStyle: { color: 'rgba(62, 105, 151, .18)' } },
        axisLabel: { color: '#7892b2', formatter: (value: number) => `${value / 10000}万` }
      },
      { type: 'value', splitLine: { show: false }, axisLabel: { color: '#7892b2' } }
    ],
    series: [
      {
        name: '库存金额',
        type: 'bar',
        barMaxWidth: 22,
        itemStyle: { borderRadius: [5, 5, 0, 0] },
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

/** 把预警类型转换成业务标签。 */
const riskLabel = (type: string) =>
  ({
    low_stock: '低库存',
    expiring_batch: '近效期',
    overdue_receivable: '应收逾期',
    overdue_payable: '应付逾期'
  })[type] || '业务预警'

onMounted(() => {
  loadDashboard()
  clockTimer = window.setInterval(() => (now.value = new Date()), 1000)
  refreshTimer = window.setInterval(loadDashboard, 5 * 60 * 1000)
})

onBeforeUnmount(() => {
  if (clockTimer) window.clearInterval(clockTimer)
  if (refreshTimer) window.clearInterval(refreshTimer)
})
</script>

<template>
  <div id="erp-cockpit">
    <FullScreenContainer>
      <main
        v-loading="loading"
        class="cockpit-shell"
        element-loading-background="rgba(2, 10, 24, .76)"
      >
        <header class="cockpit-header">
          <div class="header-side header-left">
            <span class="system-mark">HENGFLOW · ERP</span>
            <span class="period-text">{{ dashboard.date_start }} — {{ dashboard.date_end }}</span>
          </div>
          <div class="header-title">
            <span class="title-line"></span>
            <div>
              <h1>ERP 经营驾驶舱</h1>
              <p>OPERATIONS INTELLIGENCE CENTER</p>
            </div>
            <span class="title-line reverse"></span>
          </div>
          <div class="header-side header-right">
            <div class="period-switch">
              <button
                v-for="item in [7, 30, 90]"
                :key="item"
                :class="{ active: days === item }"
                @click="changePeriod(item)"
              >
                {{ item }}天
              </button>
            </div>
            <button class="refresh-button" @click="loadDashboard">刷新</button>
            <span class="clock">{{ currentTime }}</span>
          </div>
        </header>

        <section class="metric-grid">
          <article
            v-for="card in summaryCards"
            :key="card.label"
            class="metric-card"
            :class="card.tone"
          >
            <div class="metric-glow"></div>
            <span class="metric-label">{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <span class="metric-note">{{ card.note }}</span>
          </article>
        </section>

        <section class="dashboard-grid">
          <article class="panel trend-panel span-2">
            <div class="panel-header"><h2>经营趋势</h2><span>销售 · 毛利 · 采购</span></div>
            <div class="chart"><Echart :options="trendOptions" height="100%" /></div>
          </article>

          <article class="panel capital-panel">
            <div class="panel-header"><h2>资产与往来</h2><span>实时余额</span></div>
            <div class="chart"><Echart :options="capitalOptions" height="100%" /></div>
          </article>

          <article class="panel product-panel">
            <div class="panel-header"><h2>SKU 销售 TOP</h2><span>按销售净收入</span></div>
            <div v-if="dashboard.top_products?.length" class="chart"
              ><Echart :options="productOptions" height="100%"
            /></div>
            <div v-else class="empty-state">统计周期内暂无已审核销售</div>
          </article>

          <article class="panel warehouse-panel">
            <div class="panel-header"><h2>仓库库存结构</h2><span>金额 / 数量</span></div>
            <div class="chart"><Echart :options="warehouseOptions" height="100%" /></div>
          </article>

          <article class="panel risk-panel">
            <div class="panel-header">
              <h2>经营风险预警</h2>
              <span>{{ dashboard.risks?.items?.length || 0 }} 项重点</span>
            </div>
            <div class="risk-stats">
              <span
                >低库存 <b>{{ dashboard.risks?.low_stock_count || 0 }}</b></span
              >
              <span
                >近效期 <b>{{ dashboard.risks?.expiring_batch_count || 0 }}</b></span
              >
              <span
                >应收逾期 <b>{{ dashboard.risks?.overdue_receivable_count || 0 }}</b></span
              >
              <span
                >应付逾期 <b>{{ dashboard.risks?.overdue_payable_count || 0 }}</b></span
              >
            </div>
            <div class="risk-list">
              <div
                v-for="(item, index) in dashboard.risks?.items || []"
                :key="`${item.type}-${index}`"
                class="risk-item"
              >
                <span class="risk-tag" :class="item.level">{{ riskLabel(item.type) }}</span>
                <div class="risk-copy"
                  ><strong>{{ item.title }}</strong
                  ><small>{{ item.description }}</small></div
                >
                <span v-if="item.amount" class="risk-value">{{ compactMoney(item.amount) }}</span>
                <span v-else-if="item.quantity" class="risk-value">{{
                  quantity(item.quantity)
                }}</span>
              </div>
              <div v-if="!dashboard.risks?.items?.length" class="empty-state compact"
                >当前没有重点经营预警</div
              >
            </div>
          </article>

          <article class="panel recent-panel span-3">
            <div class="panel-header"><h2>最新业务动态</h2><span>最近审核过账单据</span></div>
            <div class="document-table">
              <div class="document-row table-head">
                <span>业务类型</span><span>单据编号</span><span>业务日期</span><span>往来单位</span
                ><span>金额</span>
              </div>
              <div
                v-for="item in dashboard.recent_documents || []"
                :key="`${item.type}-${item.document_no}`"
                class="document-row"
              >
                <span><i :class="item.type"></i>{{ item.type_label }}</span>
                <span class="document-no">{{ item.document_no }}</span>
                <span>{{ item.business_date }}</span>
                <span class="partner">{{ item.partner }}</span>
                <strong>{{ money(item.amount) }}</strong>
              </div>
              <div v-if="!dashboard.recent_documents?.length" class="empty-state compact"
                >暂无已审核业务单据</div
              >
            </div>
          </article>
        </section>

        <footer class="cockpit-footer">
          数据口径：已审核业务单据、实时库存成本余额及资金账户余额
          <span
            >自动刷新：5 分钟 · 最近更新
            {{ dashboard.generated_at?.replace('T', ' ').slice(0, 19) || '-' }}</span
          >
        </footer>
      </main>
    </FullScreenContainer>
  </div>
</template>

<style lang="less">
#erp-cockpit {
  width: 100%;
  height: 100%;
  color: #dcecff;
  background: #020814;

  #dv-full-screen-container {
    overflow: auto;
    background: radial-gradient(circle at 50% -10%, rgba(20, 100, 180, 0.3), transparent 38%),
      linear-gradient(rgba(10, 30, 56, 0.36) 1px, transparent 1px),
      linear-gradient(90deg, rgba(10, 30, 56, 0.36) 1px, transparent 1px), #020814;
    background-size:
      auto,
      42px 42px,
      42px 42px,
      auto;
  }
}

.cockpit-shell {
  min-width: 1280px;
  min-height: 100vh;
  padding: 14px 20px 10px;
  box-sizing: border-box;
}

.cockpit-header {
  height: 72px;
  display: grid;
  grid-template-columns: 1fr 1.2fr 1fr;
  align-items: center;
  border-bottom: 1px solid rgba(59, 149, 224, 0.35);
  background: linear-gradient(90deg, transparent, rgba(14, 63, 110, 0.24), transparent);
}

.header-side {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 13px;
  color: #7892b2;
}
.header-right {
  justify-content: flex-end;
}
.system-mark {
  color: #25d7ff;
  letter-spacing: 2px;
  font-weight: 700;
}
.clock {
  min-width: 158px;
  text-align: right;
  color: #b7cce6;
}

.header-title {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 18px;
  text-align: center;
  h1 {
    margin: 0;
    color: #e9f7ff;
    font-size: 27px;
    letter-spacing: 6px;
    text-shadow: 0 0 18px rgba(37, 215, 255, 0.65);
  }
  p {
    margin: 3px 0 0;
    color: #4e789f;
    font-size: 9px;
    letter-spacing: 4px;
  }
}
.title-line {
  width: 72px;
  height: 1px;
  background: linear-gradient(90deg, transparent, #25d7ff);
  position: relative;
}
.title-line::after {
  content: '';
  position: absolute;
  right: 0;
  top: -2px;
  width: 5px;
  height: 5px;
  background: #25d7ff;
  transform: rotate(45deg);
}
.title-line.reverse {
  transform: rotate(180deg);
}

.period-switch {
  display: flex;
  border: 1px solid rgba(60, 132, 194, 0.35);
  border-radius: 4px;
  overflow: hidden;
  button {
    padding: 5px 9px;
    color: #7892b2;
    background: rgba(8, 31, 57, 0.72);
    border: 0;
    cursor: pointer;
  }
  button.active {
    color: #e4f7ff;
    background: rgba(37, 215, 255, 0.2);
  }
}
.refresh-button {
  padding: 5px 10px;
  border: 1px solid rgba(55, 226, 164, 0.45);
  border-radius: 4px;
  color: #37e2a4;
  background: rgba(55, 226, 164, 0.08);
  cursor: pointer;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  margin: 13px 0;
}
.metric-card {
  position: relative;
  min-height: 86px;
  padding: 13px 15px;
  overflow: hidden;
  border: 1px solid rgba(59, 130, 190, 0.3);
  border-radius: 6px;
  background: linear-gradient(135deg, rgba(12, 39, 70, 0.78), rgba(4, 18, 36, 0.78));
  box-sizing: border-box;
  &::before {
    content: '';
    position: absolute;
    left: 0;
    top: 16px;
    width: 2px;
    height: 45px;
    background: var(--tone);
    box-shadow: 0 0 12px var(--tone);
  }
  strong {
    display: block;
    margin: 5px 0 3px;
    color: #f2f9ff;
    font-size: 22px;
    font-weight: 650;
    letter-spacing: 0.5px;
  }
}
.metric-card.cyan {
  --tone: #25d7ff;
}
.metric-card.green {
  --tone: #37e2a4;
}
.metric-card.blue {
  --tone: #4d8dff;
}
.metric-card.gold {
  --tone: #ffc857;
}
.metric-card.orange {
  --tone: #ff8c5a;
}
.metric-card.violet {
  --tone: #a777ff;
}
.metric-label {
  color: #8ea9c8;
  font-size: 13px;
}
.metric-note {
  color: #587594;
  font-size: 11px;
}
.metric-glow {
  position: absolute;
  width: 70px;
  height: 70px;
  right: -25px;
  top: -25px;
  border-radius: 50%;
  background: var(--tone);
  opacity: 0.07;
  filter: blur(8px);
}

.dashboard-grid {
  display: grid;
  grid-template-columns: 1.15fr 1.15fr 0.9fr;
  grid-template-rows: 285px 285px 245px;
  gap: 12px;
}
.span-2 {
  grid-column: span 2;
}
.span-3 {
  grid-column: span 3;
}
.panel {
  position: relative;
  min-width: 0;
  padding: 12px 14px;
  border: 1px solid rgba(52, 124, 184, 0.3);
  border-radius: 6px;
  background: linear-gradient(145deg, rgba(8, 30, 56, 0.88), rgba(3, 15, 31, 0.9));
  box-shadow: inset 0 0 24px rgba(25, 104, 164, 0.06);
  box-sizing: border-box;
  overflow: hidden;
  &::before,
  &::after {
    content: '';
    position: absolute;
    width: 18px;
    height: 18px;
    border-color: #25d7ff;
    opacity: 0.55;
  }
  &::before {
    left: -1px;
    top: -1px;
    border-left: 2px solid;
    border-top: 2px solid;
  }
  &::after {
    right: -1px;
    bottom: -1px;
    border-right: 2px solid;
    border-bottom: 2px solid;
  }
}
.panel-header {
  height: 27px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  border-bottom: 1px solid rgba(59, 130, 190, 0.16);
}
.panel-header h2 {
  margin: 0;
  padding-left: 10px;
  color: #dcecff;
  font-size: 15px;
  letter-spacing: 1px;
  border-left: 2px solid #25d7ff;
}
.panel-header span {
  color: #557596;
  font-size: 11px;
}
.chart {
  height: calc(100% - 27px);
}

.risk-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 5px;
  margin: 8px 0;
}
.risk-stats span {
  padding: 5px;
  text-align: center;
  color: #6786a7;
  font-size: 10px;
  border: 1px solid rgba(55, 112, 164, 0.22);
  background: rgba(12, 42, 73, 0.45);
}
.risk-stats b {
  color: #ff9f68;
  font-size: 13px;
}
.risk-list {
  height: calc(100% - 77px);
  overflow: hidden;
}
.risk-item {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 37px;
  padding: 4px 0;
  border-bottom: 1px dashed rgba(68, 115, 158, 0.2);
}
.risk-tag {
  flex: 0 0 48px;
  padding: 3px 4px;
  border-radius: 3px;
  text-align: center;
  color: #ffc857;
  font-size: 9px;
  background: rgba(255, 200, 87, 0.1);
}
.risk-tag.high {
  color: #ff8069;
  background: rgba(255, 94, 87, 0.1);
}
.risk-copy {
  min-width: 0;
  flex: 1;
  strong,
  small {
    display: block;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }
  strong {
    color: #b9cde3;
    font-size: 11px;
  }
  small {
    margin-top: 2px;
    color: #52708f;
    font-size: 9px;
  }
}
.risk-value {
  color: #ff9f68;
  font-size: 10px;
  white-space: nowrap;
}

.document-table {
  height: calc(100% - 28px);
  overflow: hidden;
}
.document-row {
  display: grid;
  grid-template-columns: 0.8fr 1.2fr 0.8fr 1.5fr 0.8fr;
  align-items: center;
  min-height: 31px;
  padding: 0 12px;
  color: #8fa9c6;
  font-size: 11px;
  border-bottom: 1px solid rgba(57, 105, 150, 0.14);
}
.document-row:nth-child(odd):not(.table-head) {
  background: rgba(23, 63, 100, 0.13);
}
.document-row strong {
  text-align: right;
  color: #c9e2f8;
}
.document-row i {
  display: inline-block;
  width: 5px;
  height: 5px;
  margin-right: 7px;
  border-radius: 50%;
  background: #25d7ff;
  box-shadow: 0 0 6px #25d7ff;
}
.document-row i.purchase_receipt {
  background: #ffc857;
  box-shadow: 0 0 6px #ffc857;
}
.document-row i.fund_payment {
  background: #ff8069;
  box-shadow: 0 0 6px #ff8069;
}
.document-row i.fund_receipt {
  background: #37e2a4;
  box-shadow: 0 0 6px #37e2a4;
}
.table-head {
  min-height: 27px;
  color: #527493;
  background: rgba(22, 73, 117, 0.2);
}
.table-head span:last-child {
  text-align: right;
}
.document-no {
  color: #50bfe8;
}
.partner {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.empty-state {
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  color: #496987;
  font-size: 12px;
}
.empty-state.compact {
  height: 60px;
}

.cockpit-footer {
  display: flex;
  justify-content: space-between;
  padding: 8px 4px 0;
  color: #3f5f7d;
  font-size: 10px;
}

@media (max-height: 900px) {
  .dashboard-grid {
    grid-template-rows: 250px 250px 220px;
  }
  .metric-card {
    min-height: 76px;
    padding-top: 9px;
  }
  .metric-card strong {
    font-size: 19px;
  }
}
</style>
