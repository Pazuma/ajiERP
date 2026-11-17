#!/usr/bin/env bash
set -euo pipefail
aki_app=/srv/aki-erp/deploy-20260930/aki-erp-full-20260929-182611/frappe_docker/development/frappe-bench/apps/client_akivision
aki_archive=/home/yuewei/item_code_display_fix_20261104.tar.gz
aki_rel=client_akivision/public/js/item_form_layout.js
aki_container=aki_full_20260930_frappe_1
aki_bench=/workspace/development/frappe-bench
test -d "$aki_app"
test -f "$aki_archive"
test "$(tar -tzf "$aki_archive")" = "$aki_rel"
sudo -v
sudo grep -q 'public/js/item_form_layout.js' "$aki_app/client_akivision/hooks.py" || {
  echo '服务器缺少物料排版脚本接入配置，已停止，请反馈此输出。'
  exit 1
}
aki_backup=$(mktemp -d /home/yuewei/item-code-display-before-XXXXXX)
sudo cp -a "$aki_app/$aki_rel" "$aki_backup/item_form_layout.js"
echo "旧文件备份：$aki_backup"
sudo tar -xzf "$aki_archive" -C "$aki_app" --no-same-owner
sudo docker exec -w "$aki_bench" "$aki_container" node --check "apps/client_akivision/$aki_rel"
sudo docker exec -w "$aki_bench" "$aki_container" bench build --app client_akivision
sudo docker exec -w "$aki_bench" "$aki_container" bench --site aki_test.localhost clear-cache
sudo docker restart "$aki_container"
echo '部署命令执行完成，请稍后检查登录页并按 Ctrl+Shift+R 刷新物料详情页。'
echo "旧文件备份：$aki_backup"
