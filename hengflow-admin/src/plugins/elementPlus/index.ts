import type { App } from 'vue'

import ElementPlus from 'element-plus'

// 为了开发环境启动更快，一次性引入所有样式
if (import.meta.env.VITE_USE_ALL_ELEMENT_PLUS_STYLE === 'true') {
  import('element-plus/dist/index.css')
}

export const setupElementPlus = (app: App<Element>) => {
  app.use(ElementPlus)
}
