<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'
import { ContentWrap } from '@/components/ContentWrap'
import { getOperatingProfitApi } from '@/api/erp/finance'
import { skuSpec } from '@/utils/erp/product'
defineOptions({ name: 'ErpFinanceProfit' })
const loading = ref(false),
  data = ref<any>({ details: [] })
const query = reactive({
  date_start: dayjs().startOf('month').format('YYYY-MM-DD'),
  date_end: dayjs().endOf('month').format('YYYY-MM-DD')
})
const money = (v: any) => Number(v || 0).toFixed(2)
const load = async () => {
  loading.value = true
  try {
    const r = await getOperatingProfitApi(query)
    data.value = r.data || { details: [] }
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>
<template>
  <ContentWrap v-loading="loading"
    ><div class="toolbar"
      ><el-date-picker v-model="query.date_start" value-format="YYYY-MM-DD" /><span>至</span
      ><el-date-picker v-model="query.date_end" value-format="YYYY-MM-DD" /><el-button
        type="primary"
        @click="load"
        >查询</el-button
      ></div
    ><el-row :gutter="12" class="cards"
      ><el-col
        v-for="item in [
          { k: 'net_sales_revenue', l: '销售净收入' },
          { k: 'sales_cost', l: '销售成本' },
          { k: 'gross_profit', l: '毛利' },
          { k: 'variable_expense', l: '变动费用' },
          { k: 'contribution_profit', l: '贡献利润' },
          { k: 'sales_return_reversal', l: '销售退货冲回' }
        ]"
        :key="item.k"
        :span="4"
        ><el-card shadow="never"
          ><small>{{ item.l }}</small
          ><strong>¥ {{ money(data[item.k]) }}</strong></el-card
        ></el-col
      ></el-row
    ><el-descriptions :column="4" border class="summary"
      ><el-descriptions-item label="销售出库收入"
        >¥ {{ money(data.gross_sales) }}</el-descriptions-item
      ><el-descriptions-item label="退货收入冲回"
        >¥ {{ money(data.sales_return_reversal) }}</el-descriptions-item
      ><el-descriptions-item label="出库成本"
        >¥ {{ money(data.gross_sales_cost) }}</el-descriptions-item
      ><el-descriptions-item label="退货成本冲回"
        >¥ {{ money(data.return_cost_reversal) }}</el-descriptions-item
      ></el-descriptions
    ><el-table :data="data.details || []" border stripe
      ><el-table-column prop="product_code" label="SKU编码" width="150" /><el-table-column
        prop="product_name"
        label="商品名称"
        min-width="190"
      /><el-table-column label="SKU规格" min-width="160"
        ><template #default="s">{{ skuSpec(s.row) }}</template></el-table-column
      ><el-table-column prop="barcode" label="条码" min-width="140" /><el-table-column
        label="销售收入"
        align="right"
        ><template #default="s">{{ money(s.row.gross_sales) }}</template></el-table-column
      ><el-table-column label="退货冲回" align="right"
        ><template #default="s">{{ money(s.row.sales_returns) }}</template></el-table-column
      ><el-table-column label="净收入" align="right"
        ><template #default="s">{{ money(s.row.net_sales_revenue) }}</template></el-table-column
      ><el-table-column label="销售成本" align="right"
        ><template #default="s">{{ money(s.row.sales_cost) }}</template></el-table-column
      ><el-table-column label="毛利" align="right"
        ><template #default="s"
          ><b>{{ money(s.row.gross_profit) }}</b></template
        ></el-table-column
      ></el-table
    ></ContentWrap
  >
</template>
<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}
.cards {
  margin-bottom: 16px;
}
.cards small,
.cards strong {
  display: block;
}
.cards strong {
  font-size: 20px;
  margin-top: 8px;
}
.summary {
  margin-bottom: 16px;
}
</style>
