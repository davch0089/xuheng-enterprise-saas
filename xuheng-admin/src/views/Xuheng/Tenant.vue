<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { addTenantApi, getTenantsApi } from '@/api/xuheng'

defineOptions({ name: 'XuhengTenant' })

const rows = ref<any[]>([])
const form = reactive({ code: '', name: '' })

const load = async () => {
  const res = await getTenantsApi()
  rows.value = res?.data || []
}

const create = async () => {
  if (!form.code || !form.name) {
    ElMessage.warning('请填写企业编码和名称')
    return
  }
  const res = await addTenantApi({ code: form.code, name: form.name })
  if (res) {
    ElMessage.success('企业已创建，当前账号已加入该企业')
    form.code = ''
    form.name = ''
    await load()
  }
}

onMounted(load)
</script>

<template>
  <div class="p-20px">
    <el-alert
      title="序衡按企业隔离商品、订单和库存。这里新建的企业只属于当前账号，和其他企业的数据不混在一起。"
      type="info"
      :closable="false"
      class="mb-16px"
    />
    <el-form inline>
      <el-form-item label="企业编码"><el-input v-model="form.code" /></el-form-item>
      <el-form-item label="企业名称"><el-input v-model="form.name" /></el-form-item>
      <el-form-item><el-button type="primary" @click="create">创建企业</el-button></el-form-item>
    </el-form>
    <el-table :data="rows" border>
      <el-table-column prop="code" label="编码" />
      <el-table-column prop="name" label="名称" />
    </el-table>
  </div>
</template>
