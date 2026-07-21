<script setup lang="ts">
import { computed } from 'vue'

defineOptions({ name: 'ErpDocumentPayment' })

interface Option {
  value: number
  label: string
  balance?: number
}

const props = withDefaults(
  defineProps<{
    modelValue: Record<string, any>
    total: number
    direction: 'receipt' | 'payment'
    accounts: Option[]
    settlementMethods: Option[]
    disabled?: boolean
  }>(),
  { disabled: false }
)
const emit = defineEmits<{ 'update:modelValue': [value: Record<string, any>] }>()

const discountRate = computed(() => Number(props.modelValue.settlement_discount_rate ?? 100))
const discountAmount = computed(() =>
  Number(((Number(props.total || 0) * (100 - discountRate.value)) / 100).toFixed(2))
)
const settlementAmount = computed(() =>
  Math.max(
    0,
    Number(
      (
        Number(props.total || 0) -
        discountAmount.value -
        Number(props.modelValue.rounding_amount || 0)
      ).toFixed(2)
    )
  )
)
const paymentLabel = computed(() => (props.direction === 'receipt' ? '本次收款' : '本次付款'))
const accountLabel = computed(() => (props.direction === 'receipt' ? '收款账号' : '付款账号'))
const title = computed(() => (props.direction === 'receipt' ? '收款信息' : '付款信息'))
const linkedDocumentNo = computed(() =>
  props.direction === 'receipt'
    ? props.modelValue.linked_receipt_no
    : props.modelValue.linked_payment_no
)

/** 更新付款信息中的单个字段。 */
const update = (field: string, value: unknown) => {
  emit('update:modelValue', { ...props.modelValue, [field]: value })
}
</script>

<template>
  <section class="document-payment">
    <div class="payment-title">
      <strong>{{ title }}</strong>
      <span
        >审核后自动生成{{ direction === 'receipt' ? '收款单并核销应收' : '付款单并核销应付' }}</span
      >
      <el-tag v-if="linkedDocumentNo" size="small" type="success">
        已联动 {{ linkedDocumentNo }}
      </el-tag>
    </div>
    <div class="payment-grid">
      <label>单据总额</label><span class="money-value">¥ {{ total.toFixed(2) }}</span>
      <label>整单折扣</label>
      <el-input-number
        :model-value="discountRate"
        :min="0"
        :max="100"
        :precision="2"
        :controls="false"
        :disabled="disabled"
        @update:model-value="update('settlement_discount_rate', $event)"
      />
      <label>优惠金额</label><span class="money-value">¥ {{ discountAmount.toFixed(2) }}</span>
      <label>抹零金额</label>
      <el-input-number
        :model-value="Number(modelValue.rounding_amount || 0)"
        :min="0"
        :max="Math.max(0, total - discountAmount)"
        :precision="2"
        :controls="false"
        :disabled="disabled"
        @update:model-value="update('rounding_amount', $event)"
      />
      <label>折后应结</label
      ><span class="money-value important">¥ {{ settlementAmount.toFixed(2) }}</span>
      <label>{{ paymentLabel }}</label>
      <el-input-number
        :model-value="Number(modelValue.current_payment_amount || 0)"
        :min="0"
        :max="settlementAmount"
        :precision="2"
        :controls="false"
        :disabled="disabled"
        @update:model-value="update('current_payment_amount', $event)"
      />
      <label>结算方式</label>
      <el-select
        :model-value="modelValue.settlement_method_id"
        clearable
        :disabled="disabled"
        @update:model-value="update('settlement_method_id', $event)"
      >
        <el-option v-for="item in settlementMethods" :key="item.value" v-bind="item" />
      </el-select>
      <label>{{ accountLabel }}</label>
      <el-select
        :model-value="modelValue.fund_account_id"
        clearable
        filterable
        :disabled="disabled"
        :placeholder="Number(modelValue.current_payment_amount || 0) ? '必选' : '未收付款可不选'"
        @update:model-value="update('fund_account_id', $event)"
      >
        <el-option
          v-for="item in accounts"
          :key="item.value"
          :value="item.value"
          :label="
            item.balance === undefined
              ? item.label
              : `${item.label}（余额 ¥${Number(item.balance).toFixed(2)}）`
          "
        />
      </el-select>
    </div>
  </section>
</template>

<style scoped>
.document-payment {
  margin-top: 10px;
  border: 1px solid #aeb6c0;
  background: #fff;
}
.payment-title {
  display: flex;
  align-items: center;
  gap: 14px;
  height: 32px;
  padding: 0 10px;
  background: #e9edf2;
  border-bottom: 1px solid #aeb6c0;
}
.payment-title span {
  color: #737d88;
  font-size: 12px;
}
.payment-grid {
  display: grid;
  grid-template-columns: 82px minmax(110px, 1fr) 82px minmax(110px, 1fr) 82px minmax(110px, 1fr) 82px minmax(
      180px,
      1.4fr
    );
  align-items: center;
  min-height: 38px;
}
.payment-grid > label {
  align-self: stretch;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 0 8px;
  color: #4e5965;
  font-size: 12px;
  background: #f7f8fa;
  border-right: 1px solid #d3d8df;
}
.payment-grid > :not(label) {
  margin: 4px 8px;
}
.payment-grid :deep(.el-input-number),
.payment-grid :deep(.el-select) {
  width: calc(100% - 16px);
}
.money-value {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.money-value.important {
  color: #c0392b;
  font-weight: 700;
}
@media (max-width: 1200px) {
  .payment-grid {
    grid-template-columns: 82px 1fr 82px 1fr;
  }
}
</style>
