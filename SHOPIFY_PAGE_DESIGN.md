# Luxury Gift Collection — Shopify Product Page Design Guide

## Overview

The product page for "Luxury Gift Collection" should convey **premium luxury, trust, and simplicity**. Below are design recommendations for the Shopify Admin theme editor.

---

## 1. Hero Image

| Element | Recommendation |
|---------|---------------|
| **Main Image** | High-res photo of a luxury gift box on a dark (black/charcoal) background with gold/rose gold accents |
| **Second Image** | Open gift box revealing elegant velvet interior |
| **Third Image** | Gift box with ribbon, lifestyle setting (hands holding the box) |
| **Style** | Dark, moody, sophisticated — not bright/sterile |

**Source suggestions**: Unsplash "luxury gift box" or professional product photography

---

## 2. Product Title & Pricing

```
LUXURY GIFT COLLECTION
From $100 to $2,000
```

- Use a **serif font** for the title (e.g., Playfair Display, Cormorant Garamond) to convey luxury
- Price display: Show "From $100" with the option selector below
- Font color: White on dark background (if using a dark theme)

---

## 3. Variant Selector

**DON'T use a dropdown** for 20 options — it's poor UX.

**DO use one of these approaches:**

### Option A: Grid of Price Buttons (Recommended)

Display as a clean grid of buttons:
```
$100  $200  $300  $400  $500
$600  $700  $800  $900  $1,000
$1,100 ... etc
```

Each button highlights on hover and shows a checkmark when selected.

**Implementation**: In Shopify theme, add a custom option swatch variant selector, or use a metafield-driven grid.

### Option B: Stepped Slider

A horizontal slider with tick marks at each $100 increment. The selected price shows large and centered.

### Option C: Tiered Cards

Group into 4 tiers of 5 variants each:
- **Essential** ($100-$500): Certificate of authenticity, gift box
- **Premium** ($600-$1000): + velvet lining, magnetic closure  
- **Elite** ($1100-$1500): + gold accents, engraved plaque
- **Imperial** ($1600-$2000): + LED lighting, limited edition

---

## 4. Product Description

Use a three-column layout below the fold:

**Column 1: Features**
- ✅ Handcrafted premium gift box
- ✅ Piano-finished lacquer exterior
- ✅ Velvet/microsuede interior
- ✅ Magnetic closure with satin ribbon
- ✅ Personalized message card included

**Column 2: Specifications**
- Material: Premium wood/MDF with leather wrapping
- Dimensions: 12" × 8" × 4" (varies by tier)
- Weight: 2-5 lbs depending on tier
- Color: Piano Black / Walnut / Rose Gold

**Column 3: Guarantees**
- 🔒 SSL Secure Checkout
- 🚚 Express Worldwide Shipping (3-7 days)
- 💎 30-Day Satisfaction Guarantee
- 🛡️ Insured Delivery

---

## 5. Trust Badges

Display prominently below the "Add to Cart" button:

```
[🔒 Secure Checkout]  [🚚 Free Express Shipping]  [💎 30-Day Guarantee]
```

Use small icon + text badges in a row.

---

## 6. Theme Settings

| Setting | Value |
|---------|-------|
| **Theme** | Use a dark/luxury theme (e.g., "Sense" or "Dawn" customized) |
| **Background** | #0a0a0a or #1a1a2e (dark) |
| **Text** | #ffffff or #f5f5f5 |
| **Accent** | #d4af37 (gold) or #c9a84c |
| **Buttons** | Gold gradient (#d4af37 → #b8962f) |
| **Typography** | Playfair Display (headings), Inter (body) |

---

## 7. Mobile Optimization

- Ensure variant selector is easily tappable (min 44px touch targets)
- Use a vertical stack of price buttons on mobile
- Images should be optimized for mobile (max 800px wide)
- Sticky "Add to Cart" button on mobile scroll

---

## 8. Recommended Apps/Plugins

1. **Glood Product Options** — For custom variant grid/button selector
2. **Zoorix** — For bundle upsells after variant selection
3. **Loox** — Photo reviews (with gift box photos)
4. **PageFly Landing Page Builder** — For custom luxury landing pages

---

## 9. SEO Meta

- **Title**: Luxury Gift Collection | From $100 - Premium Gifts & Gift Boxes
- **Description**: Discover our curated Luxury Gift Collection. Choose from 20 tiers ($100-$2,000). Each gift arrives in a handcrafted piano-finished luxury box with velvet interior. Free express shipping worldwide.
- **URL Handle**: `/collections/luxury-gift-collection` or `/products/luxury-gift-collection`

---

## 10. Sample Product Page Layout

```
┌─────────────────────────────────────────────┐
│  [HERO IMAGE: Luxury Gift Box on Dark BG]   │
│                                             │
│       LUXURY GIFT COLLECTION                │
│       From $100 — Express Shipping          │
│                                             │
│    ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐          │
│    │100│ │200│ │300│ │400│ │500│          │
│    └───┘ └───┘ └───┘ └───┘ └───┘          │
│    ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐          │
│    │600│ │700│ │800│ │900│ │1k │          │
│    └───┘ └───┘ └───┘ └───┘ └───┘          │
│    ... (20 variants)                        │
│                                             │
│  [🛒 Add to Cart — $XXX]                     │
│  [🔒 Secure] [🚚 Free Ship] [💎 Guarantee]  │
│                                             │
├─────────────────────────────────────────────┤
│  | Features  | Specs     | Guarantees     │
│  | ✅ Crafted | Material  | 🔒 SSL Secure  │
│  | ✅ Lacquer | 12×8×4    | 🚚 Express     │
│  | ✅ Velvet  | 2-5 lbs   | 💎 30-Day      │
├─────────────────────────────────────────────┤
│  [Customer Reviews / Trust Badges]          │
└─────────────────────────────────────────────┘
```
