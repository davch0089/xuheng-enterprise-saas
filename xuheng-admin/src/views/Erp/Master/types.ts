export interface MasterOption {
  label: string
  value: string | number
  children?: MasterOption[]
}

export interface MasterColumn {
  field: string
  label: string
  width?: number
  type?: 'boolean' | 'money'
  optionResource?: string
}

export interface MasterField {
  field: string
  label: string
  component?: 'input' | 'textarea' | 'number' | 'select' | 'switch' | 'tree-select'
  required?: boolean
  default?: any
  min?: number
  max?: number
  precision?: number
  span?: number
  optionResource?: string
  options?: MasterOption[]
  showWhen?: {
    field: string
    value: any
  }
}

export interface MasterPageConfig {
  resource: string
  title: string
  columns: MasterColumn[]
  fields: MasterField[]
}
