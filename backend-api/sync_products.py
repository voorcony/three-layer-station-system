#!/usr/bin/env python3
"""
sync_products.py — 从 WooCommerce REST API 同步产品到静态 JSON
用法: python3 sync_products.py
输出: /var/www/landing/data/products.json
"""
import json, os, sys, requests
from datetime import datetime

# ===== 配置（从环境变量读取，避免硬编码） =====
WC_URL = os.getenv("WC_URL", "http://127.0.0.1:8080")
WC_KEY = os.getenv("WC_CONSUMER_KEY", "")
WC_SECRET = os.getenv("WC_CONSUMER_SECRET", "")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/var/www/landing/data")
PAGE_TITLE = os.getenv("PAGE_TITLE", "奢华礼品精选")
PAGE_SUBTITLE = os.getenv("PAGE_SUBTITLE", "精选高端礼品，为您尊贵的客户")

# ===== 核心逻辑 =====

def fetch_all(endpoint, params=None):
    """分页拉取全部数据"""
    if params is None:
        params = {}
    params.setdefault("per_page", 100)
    all_items = []
    page = 1
    while True:
        params["page"] = page
        try:
            resp = requests.get(
                f"{WC_URL}/wp-json/wc/v3/{endpoint}",
                auth=(WC_KEY, WC_SECRET),
                params=params,
                timeout=15
            )
        except requests.RequestException as e:
            print(f"Error fetching page {page}: {e}", file=sys.stderr)
            break
        if resp.status_code != 200:
            print(f"HTTP {resp.status_code} on page {page}: {resp.text[:200]}", file=sys.stderr)
            break
        data = resp.json()
        if not data:
            break
        all_items.extend(data)
        page += 1
    return all_items

def fetch_variation(product_id, variation_id):
    """获取单个变体详情"""
    try:
        resp = requests.get(
            f"{WC_URL}/wp-json/wc/v3/products/{product_id}/variations/{variation_id}",
            auth=(WC_KEY, WC_SECRET),
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Error fetching variation {variation_id}: {e}", file=sys.stderr)
    return None

def transform_products(raw_products):
    """转成前端友好的格式"""
    products = []
    for p in raw_products:
        item = {
            "id": p["id"],
            "name": p["name"],
            "slug": p.get("slug", ""),
            "type": p.get("type", "simple"),
            "description": p.get("short_description", ""),
            "images": [img["src"] for img in p.get("images", []) if img.get("src")],
            "categories": [c["name"] for c in p.get("categories", [])],
        }

        if p.get("type") == "variable":
            # 可变产品：需要属性定义 + 变体列表
            attrs = []
            for a in p.get("attributes", []):
                attrs.append({
                    "name": a["name"],
                    "options": a.get("options", []),
                    "variation": a.get("variation", False),
                })
            item["attributes"] = attrs

            # 拉取变体
            variants = []
            for vid in p.get("variations", []):
                v = fetch_variation(p["id"], vid)
                if v:
                    variant_attrs = {}
                    for a in v.get("attributes", []):
                        variant_attrs[a["name"]] = a["option"]
                    variants.append({
                        "id": v["id"],
                        "sku": v.get("sku", ""),
                        "price": float(v.get("price", 0)),
                        "regular_price": float(v.get("regular_price", 0)),
                        "sale_price": float(v["sale_price"]) if v.get("sale_price") else None,
                        "stock_status": v.get("stock_status", "instock"),
                        "attributes": variant_attrs,
                        "image": v.get("image", {}).get("src", "") if v.get("image") else "",
                    })
            item["variants"] = variants

        elif p.get("type") == "simple":
            item.update({
                "price": float(p.get("price", 0)),
                "regular_price": float(p.get("regular_price", 0)),
                "sale_price": float(p["sale_price"]) if p.get("sale_price") else None,
                "stock_status": p.get("stock_status", "instock"),
                "sku": p.get("sku", ""),
            })

        products.append(item)
    return products

def write_json(path, data):
    """安全写入JSON，先写tmp再rename"""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not WC_KEY or not WC_SECRET:
        print("⚠️  WC_CONSUMER_KEY 或 WC_CONSUMER_SECRET 未设置，生成演示数据", file=sys.stderr)
        # 生成演示数据
        products = [
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
    else:
        print(f"Fetching products from {WC_URL}...")
        raw = fetch_all("products")
        products = transform_products(raw)
        print(f"Fetched {len(raw)} raw products → {len(products)} transformed")

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
