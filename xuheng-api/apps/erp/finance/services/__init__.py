"""财务领域服务的延迟导出，避免库存、采购与核销服务形成循环导入。"""

from importlib import import_module

__all__ = ["FundDocumentService", "FundPostingEngine", "AccountingPeriodService", "ProfitQueryService", "SettlementService"]

_EXPORTS = {
    "FundDocumentService": ".fund",
    "FundPostingEngine": ".fund",
    "AccountingPeriodService": ".period",
    "ProfitQueryService": ".profit",
    "SettlementService": ".settlement",
}


def __getattr__(name: str):
    """首次访问服务类时再导入其模块，保持原有公共导入路径不变。"""

    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value
    return value
