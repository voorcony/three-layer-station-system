# Three-Layer Station System (三层站群支付系统)

A complete three-layer payment processing system built with FastAPI and Shopify Storefront API.

## Architecture

- **Layer 1: A站 (Landing Page Station)** - Mobile-first product landing pages with Jinja2 templates
- **Layer 2: 普货站 API (Bridge API)** - Creates Shopify carts with cover products
- **Layer 3: Shopify Checkout** - Secure payment processing via Shopify

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/orders` | Create a new order |
| GET | `/order/{id}` | Render mobile-first landing page |
| POST | `/api/checkout/{id}` | Create Shopify checkout |
| POST | `/api/webhook/shopify` | Receive Shopify webhooks |
| GET | `/api/orders` | List all orders |
| GET | `/api/orders/{id}` | Get order details |
| GET | `/health` | Health check |

## Cover Products

| Tier | Cover Product | Price |
|------|--------------|-------|
| Premium | Luxury Gift Box - Premium | $300 |
| Elite | Luxury Gift Box - Elite | $550 |
| Executive | Luxury Gift Box - Executive | $800 |
| Royal | Luxury Gift Box - Royal | $1200 |
| Imperial | Luxury Gift Box - Imperial | $1500 |

## Deployment

```bash
# Deploy via script
bash deploy.sh

# Or manually:
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up .env
cp .env.example .env

# 3. Run with uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```
