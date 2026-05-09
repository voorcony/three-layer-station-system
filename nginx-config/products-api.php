<?php
/**
 * products-api.php — B站 WooCommerce 产品数据接口
 * 
 * 用法: 挂载到 WordPress 容器内，访问 http://127.0.0.1:8080/wp-content/products-api.php
 * 无需 WC REST API key，直接读取 WooCommerce 产品数据
 * 
 * 认证: 与 orders-api.php 共用 API_KEY
 */

require_once dirname(__FILE__) . '/../wp-load.php';

// === Auth ===
define('API_KEY', 'apk_b9a7c3d1e5f8024679b1a3c5d7e9f0b1');
$auth_header = '';
if (isset($_SERVER['HTTP_X_API_KEY'])) {
    $auth_header = $_SERVER['HTTP_X_API_KEY'];
}
if ($auth_header !== API_KEY) {
    http_response_code(401);
    echo json_encode(['error' => 'Invalid API key']);
    exit;
}

header('Content-Type: application/json');

// 只支持 products action
$action = $_GET['action'] ?? 'list';
if ($action !== 'list') {
    http_response_code(400);
    echo json_encode(['error' => 'Unknown action: ' . $action]);
    exit;
}

try {
    $products = wc_get_products(['limit' => 100, 'status' => 'publish']);
    $result = [];

    foreach ($products as $product) {
        $item = [
            'id' => $product->get_id(),
            'name' => $product->get_name(),
            'slug' => $product->get_slug(),
            'type' => $product->get_type(),
            'description' => $product->get_short_description(),
            'images' => [],
            'categories' => [],
        ];

        // Images
        foreach ($product->get_gallery_image_ids() as $img_id) {
            $src = wp_get_attachment_url($img_id);
            if ($src) $item['images'][] = $src;
        }
        if ($product->get_image_id()) {
            $src = wp_get_attachment_url($product->get_image_id());
            if ($src) array_unshift($item['images'], $src);
        }

        // Categories
        $terms = wp_get_post_terms($product->get_id(), 'product_cat');
        foreach ($terms as $term) {
            $item['categories'][] = $term->name;
        }

        if ($product->get_type() === 'variable') {
            // Variable product
            $attrs = $product->get_attributes();
            $item['attributes'] = [];
            foreach ($attrs as $attr) {
                $item['attributes'][] = [
                    'name' => $attr->get_name(),
                    'options' => $attr->get_options(),
                    'variation' => $attr->get_variation(),
                ];
            }

            $item['variants'] = [];
            foreach ($product->get_children() as $vid) {
                $v = wc_get_product($vid);
                if (!$v) continue;
                $vattrs = [];
                foreach ($v->get_attributes() as $an => $av) {
                    $vattrs[$an] = is_string($av) ? $av : ($av ?? '');
                }
                $item['variants'][] = [
                    'id' => $v->get_id(),
                    'sku' => $v->get_sku(),
                    'price' => (float)$v->get_price(),
                    'regular_price' => (float)$v->get_regular_price(),
                    'sale_price' => $v->get_sale_price() ? (float)$v->get_sale_price() : null,
                    'stock_status' => $v->get_stock_status(),
                    'attributes' => $vattrs,
                    'image' => $v->get_image_id() ? wp_get_attachment_url($v->get_image_id()) : '',
                ];
            }
        } else {
            // Simple product
            $item['price'] = (float)$product->get_price();
            $item['regular_price'] = (float)$product->get_regular_price();
            $item['sale_price'] = $product->get_sale_price() ? (float)$product->get_sale_price() : null;
            $item['stock_status'] = $product->get_stock_status();
            $item['sku'] = $product->get_sku();
        }

        $result[] = $item;
    }

    echo json_encode(['success' => true, 'products' => $result, 'total' => count($result)]);

} catch (Exception $e) {
    http_response_code(500);
    echo json_encode(['error' => $e->getMessage()]);
}
