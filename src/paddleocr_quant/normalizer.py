ALIAS_TO_CODE = {
    "营业收入": "REVENUE",
    "收入": "REVENUE",
    "revenue": "REVENUE",
    "net sales": "REVENUE",
    "归属于上市公司股东的净利润": "NP_PARENT",
    "归母净利润": "NP_PARENT",
    "net profit attributable to shareholders": "NP_PARENT",
    "净利润": "NET_PROFIT",
    "net income": "NET_PROFIT",
    "经营活动产生的现金流量净额": "OCF_NET",
    "经营现金流净额": "OCF_NET",
    "operating cash flow": "OCF_NET",
    "cash generated from operations": "OCF_NET",
    "毛利率": "GROSS_MARGIN",
    "gross margin": "GROSS_MARGIN",
    "资产负债率": "ASSET_LIAB_RATIO",
    "liability to asset ratio": "ASSET_LIAB_RATIO",
    "自由现金流": "FCF",
    "free cash flow": "FCF",
    "净资产收益率": "ROE",
    "roe": "ROE",
    "return on equity": "ROE",
    "revenue growth": "REVENUE_GROWTH",
    "收入增长率": "REVENUE_GROWTH"
}


def normalize_field_name(name: str) -> str:
    return ALIAS_TO_CODE.get(name.strip().lower(), ALIAS_TO_CODE.get(name.strip(), name.strip().upper().replace(" ", "_")))


def normalize_fields(fields: dict[str, float]) -> dict[str, float]:
    return {normalize_field_name(name): value for name, value in fields.items()}
