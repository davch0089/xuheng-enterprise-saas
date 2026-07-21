export interface SkuDisplayProduct {
  code?: string
  name?: string
  spu_name?: string
  barcode?: string
  variant_name?: string
  specification?: string
}

/** 组合 SKU 的规格维度与规格型号，避免重复展示。 */
export const skuSpec = (product?: SkuDisplayProduct | null): string => {
  if (!product) return '-'
  const values = [product.variant_name, product.specification]
    .map((value) => String(value || '').trim())
    .filter((value) => value && value !== '默认规格')
  return [...new Set(values)].join(' / ') || '默认规格'
}

/** 生成所有业务选择器统一使用的 SKU 标签。 */
export const skuLabel = (
  product?: SkuDisplayProduct | null,
  options: { barcode?: boolean } = {}
): string => {
  if (!product) return '未识别SKU'
  const name = product.spu_name || product.name || ''
  const barcode = options.barcode && product.barcode ? ` / ${product.barcode}` : ''
  return `${product.code || '-'} ${name} / ${skuSpec(product)}${barcode}`
}
