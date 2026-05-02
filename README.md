# Three-Layer Station System (三层站群支付系统)

A premium multi-layer payment processing system built with **FastAPI + Shopify Storefront API**. Features a luxury brand-inspired checkout landing page, dynamic variant-based product mapping, admin dashboard, and automated order fulfillment workflows.

> **Version**: 2.1.0
> **Design**: Rolex/Hermès/LV-inspired luxury checkout aesthetic

---

## Architecture

```
Layer 1: A站 (Landing Page)
├── FastAPI backend with Jinja2 templates
├── Luxury brand-themed checkout pages
├── Mobile-first responsive design
└── Per-order unique landing pages

Layer 2: 普货站 (Bridge API)
├── Shopify Storefront API integration
├── Dynamic variant selection (One Product, Many Variants)
├── Dual-mode: Luxury Gift Collection 20 tiers + Legacy 5 tiers fallback
└── Cart note + metafield order referencing

Layer 3: Shopify Checkout
├── Secure payment processing
├── Webhook order synchronization
└── Automatic order status tracking
```

## Design

The landing page template (`app/templates/order.html`) features a premium luxury aesthetic:

| Element | Description |
|---------|-------------|
| **Color Palette** | Deep black `#0c0c0c` + Rolex gold `#c5a55a` + warm off-white `#f5f0e8` |
| **Typography** | Cormorant Garamond (serif headings) + Inter (sans-serif body) |
| **Top Bar** | 3px gold gradient + "LUXE TIMEPIECES" brand + order number |
| **Trust Bar** | 4 SVG icon badges: Secure Checkout, 30-Day Guarantee, Express Shipping, Insured Delivery |
| **Checkout Explanation** | Professional "Secure Third-Party Processing" disclosure card |
| **CTA Button** | Gold gradient `#c5a55a → #a8853a` with hover glow effect |
| **Shipping Journey** | 3 hand-crafted SVG illustrations (400x300 each): Quality Inspection, Express Shipping, Joyful Unboxing |
| **Payment Methods** | Visa, Mastercard, Amex, PayPal, Apple Pay |

## Quick Start

### Prerequisites
- Python 3.10+
- A Shopify store with Storefront API access token
- Server with public IP (or local development)

### Installation

```bash
# Clone
git clone https://github.com/voorcony/three-layer-station-system.git
cd three-layer-station-system

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Shopify credentials:
#   SHOPIFY_STORE=your-store.myshopify.com
#   SHOPIFY_STOREFRONT_TOKEN=your_token_here

# Run
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

### Production Deployment

```bash
# One-command deploy
bash deploy.sh

# Or manually:
# 1. Set up systemd service
sudo cp three-layer.service /etc/systemd/system/
sudo systemctl enable three-layer.service
sudo systemctl start three-layer.service

# 2. Configure nginx reverse proxy
# See deploy.sh for nginx config example
```

## Shopify Product Setup

Create a single product "**Luxury Gift Collection**" in your Shopify admin with:

| Variant | Price | Tier |
|---------|-------|------|
| $100 Tier | $100 | Economy |
| $200 Tier | $200 | Budget |
| $300 Tier | $300 | Entry |
| $400 Tier | $400 | Standard |
| $500 Tier | $500 | Mid-Range |
| $600 Tier | $600 | Premium |
| $700 Tier | $700 | Superior |
| $800 Tier | $800 | Elite |
| $900 Tier | $900 | Luxury |
| $1000 Tier | $1000 | Executive |
| $1100 Tier | $1100 | Prestige |
| $1200 Tier | $1200 | Royal |
| $1300 Tier | $1300 | Sovereign |
| $1400 Tier | $1400 | Majestic |
| $1500 Tier | $1500 | Imperial |
| $1600 Tier | $1600 | Grand Imperial |
| $1700 Tier | $1700 | Crown |
| $1800 Tier | $1800 | Regal |
| $1900 Tier | $1900 | Supreme |
| $2000 Tier | $2000 | Ultimate |

The system automatically selects the closest variant >= order price.
If "Luxury Gift Collection" is not found, falls back to legacy 5-tier Body Pillow variants.

## Admin Dashboard

Access: `http://your-server/admin/login`
Default credentials: Set via `ADMIN_USERNAME` and `ADMIN_PASSWORD` in `.env`

Features:
- Full order management table
- Search/filter by order ID, product name, customer
- Color-coded status badges (pending → checkout_created → paid → fulfilled)
- One-click status updates (fulfill, reset)
- Copy checkout URL
- Refresh Shopify product cache
- Auto-refresh every 30 seconds

## License

MIT
