<?php
/**
 * B站 Order API - WordPress内部的简易订单接口
 * FastAPI通过curl localhost调用此接口
 * 
 * 使用方式:
 *   POST /wp-content/orders-api.php?action=create
 *     Headers: X-API-Key: apk_b9a7c3d1e5f8
 *     Body: {
 *       "session_id": "ORD_xxx",
 *       "phone": "13800138000",
 *       "items": [{"product_name":"手表","variant":"钻石款","price":850}],
 *       "total_price": 850,
 *       "customer_name": "用户"
 *     }
 *
 *   GET /wp-content/orders-api.php?action=get&session_id=ORD_xxx
 *
 *   POST /wp-content/orders-api.php?action=update
 *     Body: {"session_id": "ORD_xxx", "shopify_order_id": "12345", "status": "paid"}
 */

require_once('/var/www/html/wp-load.php');

define('API_KEY', 'apk_b9a7c3d1e5f8024679b1a3c5d7e9f0b1');

header('Content-Type: application/json; charset=utf-8');

// Validate API key
$auth_header = '';
if (function_exists('getallheaders')) {
    $headers = getallheaders();
    $auth_header = $headers['X-API-Key'] ?? $headers['x-api-key'] ?? '';
}
if (!$auth_header && isset($_SERVER['HTTP_X_API_KEY'])) {
    $auth_header = $_SERVER['HTTP_X_API_KEY'];
}
if ($auth_header !== API_KEY) {
    http_response_code(401);
    echo json_encode(['error' => 'Invalid API key']);
    exit;
}

$action = $_GET['action'] ?? '';

switch ($action) {
    case 'create':
        handle_create();
        break;
    case 'get':
        handle_get();
        break;
    case 'update':
        handle_update();
        break;
    case 'list':
        handle_list();
        break;
    default:
        http_response_code(400);
        echo json_encode(['error' => 'Unknown action']);
}

function handle_create() {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input || empty($input['session_id'])) {
        http_response_code(400);
        echo json_encode(['error' => 'Missing session_id']);
        return;
    }

    $session_id = sanitize_text_field($input['session_id']);
    $phone = sanitize_text_field($input['phone'] ?? '');
    $customer_name = sanitize_text_field($input['customer_name'] ?? '');
    $total_price = floatval($input['total_price'] ?? 0);
    $items = $input['items'] ?? [];

    // Create order in WooCommerce
    $order = wc_create_order();
    
    // Add line items
    foreach ($items as $item) {
        $item_name = sanitize_text_field($item['product_name'] ?? $item['variant_summary'] ?? 'Product');
        $item_price = floatval($item['price'] ?? 0);
        $item_sku = sanitize_text_field($item['sku'] ?? '');
        
        $order->add_product(wc_get_product(), 1, [
            'name' => $item_name,
            'price' => $item_price,
            'subtotal' => $item_price,
            'total' => $item_price,
        ]);
    }

    // Set billing
    $order->set_billing([
        'first_name' => $customer_name ?: 'Customer',
        'phone' => $phone,
    ]);

    // Set payment
    $order->set_payment_method('shopify');
    $order->set_payment_method_title('Shopify Checkout');
    
    // Calculate totals
    $order->set_total($total_price);
    
    // Set status
    $order->set_status('pending');

    // Add meta data for our system
    $order->update_meta_data('_session_id', $session_id);
    $order->update_meta_data('_shopify_order_id', '');
    $order->update_meta_data('_customer_phone', $phone);
    $order->update_meta_data('_items_json', json_encode($items, JSON_UNESCAPED_UNICODE));
    $order->update_meta_data('_source', 'b-site-api');

    $order->save();

    echo json_encode([
        'success' => true,
        'order_id' => $order->get_id(),
        'session_id' => $session_id,
        'status' => $order->get_status(),
        'total' => $order->get_total(),
    ]);
}

function handle_get() {
    $session_id = sanitize_text_field($_GET['session_id'] ?? '');
    if (!$session_id) {
        http_response_code(400);
        echo json_encode(['error' => 'Missing session_id']);
        return;
    }

    $orders = wc_get_orders([
        'limit' => 1,
        'meta_key' => '_session_id',
        'meta_value' => $session_id,
    ]);

    if (empty($orders)) {
        http_response_code(404);
        echo json_encode(['error' => 'Order not found', 'session_id' => $session_id]);
        return;
    }

    $order = $orders[0];
    echo json_encode([
        'success' => true,
        'wc_order_id' => $order->get_id(),
        'session_id' => $order->get_meta('_session_id'),
        'status' => $order->get_status(),
        'total' => $order->get_total(),
        'phone' => $order->get_meta('_customer_phone'),
        'shopify_order_id' => $order->get_meta('_shopify_order_id'),
        'items' => json_decode($order->get_meta('_items_json') ?: '[]', true),
        'date_created' => $order->get_date_created()->format('Y-m-d H:i:s'),
        'feishu_record_id' => $order->get_meta('_feishu_record_id'),
    ]);
}

function handle_update() {
    $input = json_decode(file_get_contents('php://input'), true);
    if (!$input || empty($input['session_id'])) {
        http_response_code(400);
        echo json_encode(['error' => 'Missing session_id']);
        return;
    }

    $session_id = sanitize_text_field($input['session_id']);
    
    $orders = wc_get_orders([
        'limit' => 1,
        'meta_key' => '_session_id',
        'meta_value' => $session_id,
    ]);

    if (empty($orders)) {
        http_response_code(404);
        echo json_encode(['error' => 'Order not found']);
        return;
    }

    $order = $orders[0];

    if (!empty($input['shopify_order_id'])) {
        $order->update_meta_data('_shopify_order_id', sanitize_text_field($input['shopify_order_id']));
    }
    if (!empty($input['status'])) {
        $order->set_status(sanitize_text_field($input['status']));
    }
    if (!empty($input['checkout_url'])) {
        $order->update_meta_data('_shopify_checkout_url', esc_url_raw($input['checkout_url']));
    }
    if (!empty($input['cart_id'])) {
        $order->update_meta_data('_shopify_cart_id', sanitize_text_field($input['cart_id']));
    }
    if (!empty($input['feishu_record_id'])) {
        $order->update_meta_data('_feishu_record_id', sanitize_text_field($input['feishu_record_id']));
    }

    $order->save();

    echo json_encode([
        'success' => true,
        'wc_order_id' => $order->get_id(),
        'session_id' => $session_id,
        'status' => $order->get_status(),
    ]);
}

function handle_list() {
    $status = sanitize_text_field($_GET['status'] ?? '');
    $limit = intval($_GET['limit'] ?? 20);

    $args = ['limit' => $limit, 'orderby' => 'date', 'order' => 'DESC'];
    if ($status) {
        $args['status'] = $status;
    }

    $orders = wc_get_orders($args);
    $result = [];
    foreach ($orders as $order) {
        $result[] = [
            'wc_order_id' => $order->get_id(),
            'session_id' => $order->get_meta('_session_id'),
            'status' => $order->get_status(),
            'total' => $order->get_total(),
            'phone' => $order->get_meta('_customer_phone'),
            'shopify_order_id' => $order->get_meta('_shopify_order_id'),
            'date_created' => $order->get_date_created()->format('Y-m-d H:i:s'),
        'feishu_record_id' => $order->get_meta('_feishu_record_id'),
        ];
    }

    echo json_encode(['success' => true, 'orders' => $result, 'total' => count($result)]);
}