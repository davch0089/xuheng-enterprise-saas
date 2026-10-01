<script setup lang="ts">
import { computed } from 'vue'
import { useAppStore } from '@/store/modules/app'
import { ConfigGlobal } from '@/components/ConfigGlobal'
import { useDesign } from '@/hooks/web/useDesign'
import { getSystemBaseConfigApi } from '@/api/vadmin/system/settings'

const { getPrefixCls } = useDesign()

const prefixCls = getPrefixCls('app')

const appStore = useAppStore()

const currentSize = computed(() => appStore.getCurrentSize)

const greyMode = computed(() => appStore.getGreyMode)

// 添加mate标签
const addMeta = (name: string, content: string) => {
  const meta = document.createElement('meta')
  meta.content = content
  meta.name = name
  document.getElementsByTagName('head')[0].appendChild(meta)
}

// 获取并设置系统配置
const setSystemConfig = async () => {
  if (appStore.getLogoImage) {
    return
  }
  const res = await getSystemBaseConfigApi()
  if (res) {
    appStore.setTitle(res.data.web_title || import.meta.env.VITE_APP_TITLE)
    appStore.setLogoImage(res.data.web_logo || '/media/system/logo.png')
    appStore.setFooterContent(res.data.web_copyright || '序衡演示 · 基于 HengFlow ERP')
    appStore.setIcpNumber(res.data.web_icp_number || '')
    addMeta(
      'description',
      res.data.web_desc || '序衡，面向商品、订单、用户与运营后台的企业 SaaS 管理系统'
    )
  }
}

appStore.initTheme()
setSystemConfig()
</script>

<template>
  <ConfigGlobal :size="currentSize">
    <RouterView :class="greyMode ? `${prefixCls}-grey-mode` : ''" />
  </ConfigGlobal>
</template>

<style lang="less">
@prefix-cls: ~'@{namespace}-app';

.size {
  width: 100% !important;
  height: 100%;
}

html,
body {
  padding: 0 !important;
  margin: 0;
  overflow: hidden;
  .size;

  #app {
    .size;
  }
}

.@{prefix-cls}-grey-mode {
  filter: grayscale(100%);
}

ol {
  display: block;
  list-style-type: decimal;
  margin-block-start: 1em;
  margin-block-end: 1em;
  margin-inline-start: 0px;
  margin-inline-end: 0px;
  padding-inline-start: 40px;
}
</style>
