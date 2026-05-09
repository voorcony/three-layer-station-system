#!/usr/bin/env python3
"""
sync_products.py — 从 B站 FastAPI 同步产品到静态 JSON
用法: python3 sync_products.py
输出: /var/www/landing/data/products.json

从 B站 /api/products 接口获取产品数据（不再需要本地 WooCommerce）
"""
import json, os, sys, requests
from datetime import datetime

# ===== 配置（从环境变量读取） =====
B_API_URL = os.getenv("B_API_URL", "http://43.154.181.44")
B_API_KEY = os.getenv("B_API_KEY", "apk_b9a7c3d1e5f80")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/var/www/landing/data")
PAGE_TITLE = os.getenv("PAGE_TITLE", "奢华礼品精选")
PAGE_SUBTITLE = os.getenv("PAGE_SUBTITLE", "精选高端礼品，为您尊贵的客户")

# ===== 回退数据（当B站不可用时） =====
FALLBACK_PRODUCTS = [
    {"id": 1, "name": "奢华礼品套装", "type": "variable",
     "description": "精选高端礼品套装，多种档次可选",
     "images": [], "categories": ["礼品套装"],
     "attributes": [
         {"name": "档次", "options": ["标准", "豪华", "尊享"], "variation": True},
         {"name": "包装", "options": ["简约", "礼盒", "精装", "限定版"], "variation": True}
     ],
     "variants": [
         {"id": 101, "sku": "SET-A", "price": 99, "stock_status": "instock",
          "attributes": {"档次": "标准", "包装": "简约"}},
         {"id": 102, "sku": "SET-B", "price": 149, "stock_status": "instock",
          "attributes": {"档次": "标准", "包装": "礼盒"}},
         {"id": 103, "sku": "SET-C", "price": 199, "stock_status": "instock",
          "attributes": {"档次": "豪华", "包装": "礼盒"}},
         {"id": 104, "sku": "SET-D", "price": 299, "stock_status": "instock",
          "attributes": {"档次": "豪华", "包装": "精装"}},
         {"id": 105, "sku": "SET-E", "price": 499, "stock_status": "instock",
          "attributes": {"档次": "尊享", "包装": "精装"}},
         {"id": 106, "sku": "SET-F", "price": 999, "stock_status": "instock",
          "attributes": {"档次": "尊享", "包装": "限定版"}}
     ]},
    {"id": 2, "name": "精美手表", "type": "simple",
     "description": "经典设计，精工品质",
     "images": [], "categories": ["手表"],
     "price": 299, "stock_status": "instock", "sku": "WATCH-001"},
]


def fetch_products_from_b_station():
    """从 B站 /api/products 拉取产品数据"""
    url = f"{B_API_URL.rstrip('/')}/api/products"
    headers = {"X-API-Key": B_API_KEY}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success") and data.get("products"):
                return data["products"]
            else:
                print(f"⚠️  B站 returned success=false: {data}", file=sys.stderr)
        else:
            print(f"⚠️  B站 API returned HTTP {resp.status_code}", file=sys.stderr)
    except requests.RequestException as e:
        print(f"⚠️  B站 API不可用: {e}", file=sys.stderr)
    return None


def write_json(path, data):
    """安全写入JSON，先写tmp再rename"""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 尝试从B站拉取
    products = fetch_products_from_b_station()

    if products is None:
        print("⚠️  使用本地回退数据", file=sys.stderr)
        products = FALLBACK_PRODUCTS
    else:
        print(f"✅ 从B站拉取 {len(products)} 个产品")

    # 输出主文件
    output = {
        "page_title": PAGE_TITLE,
        "page_subtitle": PAGE_SUBTITLE,
        "last_updated": datetime.now().isoformat(),
        "total_products": len(products),
        "products": products,
    }
    write_json(f"{OUTPUT_DIR}/products.json", output)
    print(f"✅ Wrote products.json ({len(products)} products)")

    # 按分类拆分
    categories = {}
    for p in products:
        for cat in p.get("categories", ["全部"]):
            categories.setdefault(cat, []).append(p)

    for cat, items in categories.items():
        safe_name = cat.replace(" ", "_").lower()
        write_json(f"{OUTPUT_DIR}/category_{safe_name}.json", items)

    # 分类列表
    write_json(f"{OUTPUT_DIR}/categories.json", list(categories.keys()))
    print(f"✅ Wrote {len(categories)} categories")


if __name__ == "__main__":
    main()
