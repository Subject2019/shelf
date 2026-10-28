#!/usr/bin/env bash
# EchoShelf 部署诊断脚本
# 用法：./healthcheck.sh [http://127.0.0.1:8080]
set -uo pipefail

BASE="${1:-http://127.0.0.1:8080}"
CONTAINER="${SHELF_CONTAINER:-${ECHOSHELF_CONTAINER:-shelf}}"
FAIL=0

say() { printf '\n=== %s ===\n' "$1"; }
ok()  { printf '  [OK]   %s\n' "$1"; }
bad() { printf '  [FAIL] %s\n' "$1"; FAIL=1; }

say "1. 容器状态"
if docker ps --format '{{.Names}}\t{{.Status}}' 2>/dev/null | grep -q "^$CONTAINER"; then
  docker ps --format '  {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep "^  $CONTAINER"
  ok "容器运行中"
else
  bad "容器 $CONTAINER 未运行（docker compose up -d）"
fi

say "2. 健康接口"
HTTP_CODE=$(curl -s -o /tmp/shelf-health.json -w '%{http_code}' --max-time 5 "$BASE/api/v1/health" 2>/dev/null || echo 000)
if [ "$HTTP_CODE" = "200" ]; then
  ok "GET /api/v1/health -> 200"
  command -v python3 >/dev/null && python3 -m json.tool /tmp/shelf-health.json 2>/dev/null | sed 's/^/  /'
else
  bad "GET /api/v1/health -> $HTTP_CODE"
fi

say "3. Range 支持（关键，影响拖动进度）"
RANGE_CODE=$(curl -s -o /dev/null -w '%{http_code}' -r 0-1023 --max-time 5 \
  "$BASE/api/v1/books/1/tracks/1/stream" 2>/dev/null || echo 000)
case "$RANGE_CODE" in
  206|401|403|404) ok "Range 请求有响应（$RANGE_CODE；401/403/404 属正常，说明路由存在）" ;;
  000) bad "无法连接" ;;
  *)   bad "Range 返回 $RANGE_CODE，反代可能改写了 Range 头" ;;
esac

say "4. 数据目录（容器内）"
if docker ps --format '{{.Names}}' | grep -q "^$CONTAINER$"; then
  docker exec "$CONTAINER" sh -c '
    test -w /data && echo "  /data 可写" || echo "  /data 不可写"
    test -r /audiobooks && echo "  /audiobooks 可读" || echo "  /audiobooks 不可读"
    command -v ffmpeg >/dev/null && echo "  ffmpeg 可用" || echo "  ffmpeg 缺失（转码不可用）"
    du -sh /data 2>/dev/null | sed "s/^/  data 占用: /"
  '
  ok "容器内检查完成"
else
  bad "跳过（容器未运行）"
fi

say "5. 宿主机磁盘"
df -h / /volume1 2>/dev/null | awk 'NR==1 || /[0-9]%$/ {print "  "$0}'

say "结果"
if [ "$FAIL" -eq 0 ]; then
  echo "  全部通过"
else
  echo "  存在异常，见上文 [FAIL]；日志：docker compose logs --tail=200 $CONTAINER"
  exit 1
fi
