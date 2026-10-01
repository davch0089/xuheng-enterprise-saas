<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

defineOptions({ name: 'ErpDocumentSerialEditor' })

const props = defineProps<{ modelValue: string[]; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()
const visible = ref(false)
const text = ref('')
const generator = reactive({ prefix: '', start: '001', increment: 1, count: 1 })

/** 打开与入库单一致的序列号批量录入窗口。 */
const open = () => {
  if (props.disabled) return
  text.value = (props.modelValue || []).join('\n')
  visible.value = true
}

/** 按前缀、起始号和递增量生成连续序列号。 */
const generate = () => {
  const start = Number(generator.start)
  const width = generator.start.length
  const rows = Array.from({ length: Math.max(0, generator.count) }, (_, index) => {
    const value = start + index * generator.increment
    return `${generator.prefix}${String(value).padStart(width, '0')}`
  })
  text.value = [text.value, ...rows].filter(Boolean).join('\n')
}

/** 清理序列号、拒绝重复并回写当前商品行。 */
const apply = () => {
  const values = text.value
    .split(/[,，\s]+/)
    .map((item) => item.trim())
    .filter(Boolean)
  if (new Set(values).size !== values.length) return ElMessage.warning('序列号不能重复')
  emit('update:modelValue', values)
  visible.value = false
}
</script>

<template>
  <el-button v-if="!disabled" link type="primary" @click="open">
    录入（{{ modelValue?.length || 0 }}）
  </el-button>
  <span v-else class="serial-disabled">{{
    modelValue?.length ? `已录入 ${modelValue.length}` : '不管理'
  }}</span>
  <el-dialog v-model="visible" title="序列号录入" width="760px" append-to-body>
    <el-alert
      title="一行一个序列号，也可用逗号或空格分隔；确认后自动回填当前商品行。"
      type="info"
      :closable="false"
    />
    <div class="serial-generator">
      <el-input v-model="generator.prefix" placeholder="前缀（可空）" />
      <el-input v-model="generator.start" placeholder="起始号，如 001" />
      <el-input-number v-model="generator.increment" :min="1" placeholder="递增量" />
      <el-input-number v-model="generator.count" :min="1" placeholder="个数" />
      <el-button type="primary" @click="generate">批量生成</el-button>
    </div>
    <el-input v-model="text" type="textarea" :rows="14" placeholder="SN0001&#10;SN0002" />
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="apply">确认录入</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.serial-generator {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 14px 0;
}
.serial-generator .el-input {
  width: 150px;
}
.serial-generator .el-input-number {
  width: 120px;
}
.serial-disabled {
  color: var(--el-text-color-placeholder);
  font-size: 11px;
}
</style>
