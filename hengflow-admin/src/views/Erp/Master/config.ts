import type { MasterPageConfig } from './types'

const activeColumn = { field: 'is_active', label: '启用', width: 80, type: 'boolean' as const }
const baseFields = [
  { field: 'code', label: '编码', required: true },
  { field: 'name', label: '名称', required: true },
  { field: 'is_active', label: '启用', component: 'switch' as const, default: true },
  { field: 'remark', label: '备注', component: 'textarea' as const, span: 24 }
]

export const productConfig: MasterPageConfig = {
  resource: 'products',
  title: '商品',
  columns: [
    { field: 'code', label: '商品编码', width: 140 },
    { field: 'name', label: '商品名称', width: 180 },
    { field: 'barcode', label: '条码', width: 140 },
    { field: 'category_id', label: '分类', width: 150, optionResource: 'product-categories' },
    { field: 'base_unit_id', label: '基本单位', width: 130, optionResource: 'units' },
    { field: 'multi_unit_enabled', label: '多单位', width: 90, type: 'boolean' },
    { field: 'unit_group_id', label: '多单位方案', width: 170, optionResource: 'unit-conversions' },
    { field: 'specification', label: '规格型号', width: 150 },
    { field: 'default_purchase_price', label: '参考进价', width: 110, type: 'money' },
    { field: 'default_sale_price', label: '参考售价', width: 110, type: 'money' },
    activeColumn
  ],
  fields: [
    { field: 'code', label: '商品编码', required: true },
    { field: 'name', label: '商品名称', required: true },
    { field: 'barcode', label: '条码' },
    {
      field: 'category_id',
      label: '商品分类',
      component: 'select',
      optionResource: 'product-categories',
      required: true
    },
    {
      field: 'multi_unit_enabled',
      label: '启用多单位',
      component: 'switch',
      default: false
    },
    {
      field: 'base_unit_id',
      label: '基本单位',
      component: 'select',
      optionResource: 'units',
      required: true,
      showWhen: { field: 'multi_unit_enabled', value: false }
    },
    {
      field: 'unit_group_id',
      label: '多单位方案',
      component: 'select',
      optionResource: 'unit-conversions',
      required: true,
      showWhen: { field: 'multi_unit_enabled', value: true }
    },
    { field: 'specification', label: '规格型号' },
    { field: 'brand', label: '品牌' },
    {
      field: 'default_purchase_price',
      label: '参考进价',
      component: 'number',
      min: 0,
      precision: 4,
      default: 0
    },
    {
      field: 'default_sale_price',
      label: '参考售价',
      component: 'number',
      min: 0,
      precision: 4,
      default: 0
    },
    {
      field: 'tax_rate',
      label: '税率(%)',
      component: 'number',
      min: 0,
      max: 100,
      precision: 4,
      default: 0
    },
    {
      field: 'min_stock',
      label: '最低库存',
      component: 'number',
      min: 0,
      precision: 4,
      default: 0
    },
    { field: 'max_stock', label: '最高库存', component: 'number', min: 0, precision: 4 },
    {
      field: 'costing_method',
      label: '成本方法',
      component: 'select',
      required: true,
      default: 'moving_average',
      options: [{ label: '移动加权平均', value: 'moving_average' }]
    },
    { field: 'batch_enabled', label: '批次管理', component: 'switch', default: false },
    { field: 'serial_enabled', label: '序列号管理', component: 'switch', default: false },
    { field: 'shelf_life_days', label: '保质期(天)', component: 'number', min: 0 },
    { field: 'is_active', label: '启用', component: 'switch', default: true },
    { field: 'remark', label: '备注', component: 'textarea', span: 24 }
  ]
}

export const productCategoryConfig: MasterPageConfig = {
  resource: 'product-categories',
  title: '商品分类',
  columns: [
    { field: 'code', label: '分类编码' },
    { field: 'name', label: '分类名称' },
    { field: 'parent_id', label: '上级分类', optionResource: 'product-categories' },
    { field: 'order', label: '排序', width: 90 },
    activeColumn
  ],
  fields: [
    { field: 'code', label: '分类编码', required: true },
    { field: 'name', label: '分类名称', required: true },
    {
      field: 'parent_id',
      label: '上级分类',
      component: 'select',
      optionResource: 'product-categories'
    },
    { field: 'order', label: '排序', component: 'number', min: 0, default: 0 },
    { field: 'is_active', label: '启用', component: 'switch', default: true },
    { field: 'remark', label: '备注', component: 'textarea', span: 24 }
  ]
}

export const unitConfig: MasterPageConfig = {
  resource: 'units',
  title: '计量单位',
  columns: [
    { field: 'code', label: '单位编码' },
    { field: 'name', label: '单位名称' },
    { field: 'symbol', label: '符号', width: 100 },
    { field: 'decimal_places', label: '小数位', width: 100 },
    activeColumn
  ],
  fields: [
    { field: 'code', label: '单位编码', required: true },
    { field: 'name', label: '单位名称', required: true },
    { field: 'symbol', label: '单位符号' },
    {
      field: 'decimal_places',
      label: '数量小数位',
      component: 'number',
      min: 0,
      max: 8,
      default: 2,
      required: true
    },
    { field: 'is_active', label: '启用', component: 'switch', default: true },
    { field: 'remark', label: '备注', component: 'textarea', span: 24 }
  ]
}

const settlementField = {
  field: 'settlement_method_id',
  label: '结算方式',
  component: 'select' as const,
  optionResource: 'settlement-methods'
}
const partnerFields = [
  { field: 'code', label: '编码', required: true },
  { field: 'name', label: '全称', required: true },
  { field: 'short_name', label: '简称' },
  { field: 'category', label: '分类' },
  { field: 'contact_name', label: '联系人' },
  { field: 'phone', label: '联系电话' },
  { field: 'email', label: '邮箱' },
  { field: 'tax_no', label: '税号' },
  { field: 'bank_name', label: '开户行' },
  { field: 'bank_account', label: '银行账号' },
  { field: 'address', label: '地址', span: 24 },
  settlementField,
  { field: 'payment_days', label: '账期(天)', component: 'number' as const, min: 0, default: 0 },
  { field: 'is_active', label: '启用', component: 'switch' as const, default: true },
  { field: 'remark', label: '备注', component: 'textarea' as const, span: 24 }
]
const partnerColumns = [
  { field: 'code', label: '编码', width: 130 },
  { field: 'name', label: '名称', width: 190 },
  { field: 'category', label: '分类', width: 110 },
  { field: 'contact_name', label: '联系人', width: 100 },
  { field: 'phone', label: '联系电话', width: 140 },
  {
    field: 'settlement_method_id',
    label: '结算方式',
    width: 150,
    optionResource: 'settlement-methods'
  },
  activeColumn
]

export const customerConfig: MasterPageConfig = {
  resource: 'customers',
  title: '客户',
  columns: partnerColumns,
  fields: [
    ...partnerFields.slice(0, -2),
    {
      field: 'credit_limit',
      label: '信用额度',
      component: 'number',
      min: 0,
      precision: 2,
      default: 0
    },
    ...partnerFields.slice(-2)
  ]
}

export const supplierConfig: MasterPageConfig = {
  resource: 'suppliers',
  title: '供应商',
  columns: partnerColumns,
  fields: partnerFields
}

export const warehouseConfig: MasterPageConfig = {
  resource: 'warehouses',
  title: '仓库',
  columns: [
    { field: 'code', label: '仓库编码' },
    { field: 'name', label: '仓库名称' },
    { field: 'manager_name', label: '负责人' },
    { field: 'phone', label: '联系电话' },
    { field: 'allow_negative_stock', label: '允许负库存', width: 110, type: 'boolean' },
    activeColumn
  ],
  fields: [
    ...baseFields.slice(0, 2),
    { field: 'manager_name', label: '负责人' },
    { field: 'phone', label: '联系电话' },
    { field: 'address', label: '地址', span: 24 },
    { field: 'allow_negative_stock', label: '允许负库存', component: 'switch', default: false },
    ...baseFields.slice(2)
  ]
}

export const employeeConfig: MasterPageConfig = {
  resource: 'employees',
  title: '职员',
  columns: [
    { field: 'code', label: '职员编码' },
    { field: 'name', label: '姓名' },
    { field: 'department_id', label: '部门', optionResource: 'departments' },
    { field: 'position', label: '职位' },
    { field: 'phone', label: '联系电话' },
    activeColumn
  ],
  fields: [
    ...baseFields.slice(0, 2),
    { field: 'department_id', label: '部门', component: 'select', optionResource: 'departments' },
    { field: 'position', label: '职位' },
    { field: 'phone', label: '联系电话' },
    { field: 'email', label: '邮箱' },
    ...baseFields.slice(2)
  ]
}

export const settlementMethodConfig: MasterPageConfig = {
  resource: 'settlement-methods',
  title: '结算方式',
  columns: [
    { field: 'code', label: '结算编码' },
    { field: 'name', label: '结算名称' },
    { field: 'method_type', label: '结算类型' },
    { field: 'payment_days', label: '默认账期', width: 100 },
    activeColumn
  ],
  fields: [
    ...baseFields.slice(0, 2),
    {
      field: 'method_type',
      label: '结算类型',
      component: 'select',
      default: 'other',
      required: true,
      options: [
        { label: '现金', value: 'cash' },
        { label: '银行转账', value: 'bank' },
        { label: '赊销/赊购', value: 'credit' },
        { label: '其他', value: 'other' }
      ]
    },
    { field: 'payment_days', label: '默认账期(天)', component: 'number', min: 0, default: 0 },
    ...baseFields.slice(2)
  ]
}
