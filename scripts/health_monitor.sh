#!/bin/bash
# health_monitor.sh — 系统健康监控
# 每5分钟检查 B站 FastAPI + WooCommerce 状态
# 连续失败阈值后发送飞书告警
# 安装: sudo ln -sf /opt/three-layer-stations/scripts/health_monitor.sh /etc/cron.d/health-monitor
# 或在 crontab 中添加: */5 * * * * /opt/three-layer-stations/scripts/health_monitor.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STATE_FILE="/tmp/hermes_health_state"
LOG_FILE="/var/log/hermes-health.log"
HEALTH_URL="http://127.0.0.1:8000/health"
FEISHU_WEBHOOK="${FEISHU_MONITOR_WEBHOOK:-}"

# 连续失败计数
MAX_FAILURES=3
CURRENT_FAILURES=0
if [ -f "$STATE_FILE" ]; then
    CURRENT_FAILURES=$(cat "$STATE_FILE")
fi

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

send_feishu_alert() {
    local msg="$1"
    log "发送飞书告警: $msg"
    if [ -n "$FEISHU_WEBHOOK" ]; then
        curl -s -X POST "$FEISHU_WEBHOOK" \
            -H "Content-Type: application/json" \
            -d "{\"msg_type\":\"text\",\"content\":{\"text\":\"⚠️ 系统告警: $msg\"}}" \
            -o /dev/null -w "%{http_code}" >> "$LOG_FILE" 2>&1
        log "飞书告警发送完成"
    else
        log "FEISHU_MONITOR_WEBHOOK 未设置，跳过飞书通知"
    fi
}

# 1. 检查 B站 FastAPI
HTTP_CODE=$(curl -s -o /tmp/hermes_health_resp.json -w "%{http_code}" "$HEALTH_URL" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    WC_STATUS=$(python3 -c "import json; d=json.load(open('/tmp/hermes_health_resp.json')); print(d.get('wc','unknown'))" 2>/dev/null || echo "parse_error")
    log "健康检查 OK (HTTP=$HTTP_CODE, wc=$WC_STATUS)"
    echo 0 > "$STATE_FILE"
else
    CURRENT_FAILURES=$((CURRENT_FAILURES + 1))
    echo "$CURRENT_FAILURES" > "$STATE_FILE"
    log "健康检查失败 (HTTP=$HTTP_CODE, 连续失败=$CURRENT_FAILURES/$MAX_FAILURES)"
    
    if [ "$CURRENT_FAILURES" -ge "$MAX_FAILURES" ]; then
        send_feishu_alert "B站系统不可用 (连续${MAX_FAILURES}次健康检查失败，HTTP=$HTTP_CODE)"
        # 重置计数器，避免重复告警
        echo 0 > "$STATE_FILE"
        # 尝试重启服务
        log "尝试重启 three-layer-stations 服务..."
        sudo systemctl restart three-layer-stations 2>> "$LOG_FILE" || log "重启失败"
    fi
fi

# 2. 检查磁盘
DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 85 ]; then
    log "磁盘使用率告警: ${DISK_USAGE}%"
    send_feishu_alert "磁盘使用率 ${DISK_USAGE}%，请及时清理"
elif [ "$DISK_USAGE" -gt 70 ]; then
    log "磁盘使用率注意: ${DISK_USAGE}%"
fi

# 3. 清理临时文件
rm -f /tmp/hermes_health_resp.json
