"""序衡库存、成本、应收、应付和资金流水的幂等键。"""


def stock_movement(source_type: str, source_id: int, posting_version: int, line_id: int, role: str) -> str:
    """库存过账幂等键。"""

    return f"XH-STK|{source_type}|{source_id}|{posting_version}|{line_id}|{role}"


def stock_reversal(ledger_id: int) -> str:
    """库存冲销幂等键。"""

    return f"XH-STK-R|{ledger_id}"


def cost_for_stock(stock_key: str) -> str:
    """由库存幂等键派生成本幂等键。"""

    return f"XH-COST|{stock_key}"


def cost_reversal(ledger_id: int) -> str:
    """成本冲销幂等键。"""

    return f"XH-COST-R|{ledger_id}"


def receivable(source_type: str, source_id: int, posting_version: int) -> str:
    """应收过账幂等键。"""

    return f"XH-AR|{source_type}|{source_id}|{posting_version}"


def receivable_reversal(ledger_id: int) -> str:
    """应收冲销幂等键。"""

    return f"XH-AR-R|{ledger_id}"


def payable(source_type: str, source_id: int, posting_version: int) -> str:
    """应付过账幂等键。"""

    return f"XH-AP|{source_type}|{source_id}|{posting_version}"


def payable_reversal(ledger_id: int) -> str:
    """应付冲销幂等键。"""

    return f"XH-AP-R|{ledger_id}"


def fund(source_type: str, source_id: int, entry_type: str, posting_version: int) -> str:
    """资金过账幂等键。"""

    return f"XH-FUND|{source_type}|{source_id}|{entry_type}|{posting_version}"


def fund_reversal(ledger_id: int) -> str:
    """资金冲销幂等键。"""

    return f"XH-FUND-R|{ledger_id}"
