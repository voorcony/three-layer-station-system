// js/checkout.js — Shopify Checkout Module
// Delegates all checkout logic to B站 API (43.154.181.44)

// B站 API endpoint — FastAPI on B站 server handles all Shopify logic
const B_STATION_API = 'http://43.154.181.44';

/**
 * Display a friendly maintenance overlay when the B站 API is unreachable
 * or returns an error. Avoids redirecting the user away from the page.
 */
function showMaintenanceModal() {
  if (document.getElementById('b-station-maintenance-modal')) return;

  const overlay = document.createElement('div');
  overlay.id = 'b-station-maintenance-modal';
  overlay.style.cssText = [
    'position:fixed', 'top:0', 'left:0', 'width:100%', 'height:100%',
    'background:rgba(0,0,0,0.5)', 'display:flex', 'align-items:center',
    'justify-content:center', 'z-index:99999'
  ].join(';');

  const box = document.createElement('div');
  box.style.cssText = [
    'background:#fff', 'padding:24px 32px', 'border-radius:8px',
    'min-width:280px', 'max-width:90%', 'text-align:center',
    'box-shadow:0 4px 16px rgba(0,0,0,0.2)', 'font-family:sans-serif'
  ].join(';');

  const msg = document.createElement('p');
  msg.textContent = '系统繁忙，请稍后再试';
  msg.style.cssText = 'margin:0 0 20px 0;font-size:16px;color:#333';

  const btn = document.createElement('button');
  btn.textContent = '关闭';
  btn.style.cssText = [
    'padding:8px 24px', 'background:#007bff', 'color:#fff',
    'border:none', 'border-radius:4px', 'cursor:pointer', 'font-size:14px'
  ].join(';');
  btn.onclick = () => overlay.remove();

  box.appendChild(msg);
  box.appendChild(btn);
  overlay.appendChild(box);
  document.body.appendChild(overlay);
}

/**
 * Submit an order to B站 for Shopify checkout processing.
 * B站 returns checkout_url directly from POST /api/create_checkout.
 */
async function submitOrderToBStation(sessionId, totalPrice, phone, items) {
  try {
    const resp = await fetch(`${B_STATION_API}/api/create_checkout`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Api-Key': 'apk_b9a7c3d1e5f80'
      },
      body: JSON.stringify({
        session_id: sessionId,
        total_price: parseFloat(totalPrice),
        phone: phone,
        items: items.map(i => ({
          product_name: i.productName,
          variant_summary: i.variantSummary || '',
          price: i.price,
          sku: i.sku || ''
        }))
      })
    });

    if (!resp.ok) throw new Error('Status ' + resp.status);

    const data = await resp.json();
    if (data.checkout_url) return data.checkout_url;
    throw new Error('No checkout_url');
  } catch (e) {
    console.warn('B站 API error:', e);
    showMaintenanceModal();
    return null;
  }
}

window.submitOrderToBStation = submitOrderToBStation;
