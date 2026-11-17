#!/usr/bin/env bash
set -euo pipefail
archive=/home/yuewei/product_bom_fix_20261102.tar.gz
app=/srv/aki-erp/deploy-20260930/aki-erp-full-20260929-182611/frappe_docker/development/frappe-bench/apps/client_akivision
container=aki_full_20260930_frappe_1
bench_dir=/workspace/development/frappe-bench
test -f "$archive"
test -d "$app/client_akivision"
sudo -v
backup=$(mktemp -d /home/yuewei/product-bom-before-20261102-XXXXXX)
echo "旧文件备份目录：$backup"
while IFS= read -r rel; do
  case "$rel" in
    client_akivision/utils/master_data_sidebar.py|client_akivision/utils/stock_sidebar.py|client_akivision/utils/engineering_drawing.py|client_akivision/public/js/bom.js|client_akivision/client_akivision/api/data_import.py) ;;
    *) echo "未知补丁路径：$rel"; exit 1 ;;
  esac
  if sudo test -f "$app/$rel"; then
    sudo mkdir -p "$backup/$(dirname "$rel")"
    sudo cp -a "$app/$rel" "$backup/$rel"
  else
    printf '%s\n' "$rel" >> "$backup/new-files.txt"
  fi
done < <(tar -tzf "$archive")
sudo tar -xzf "$archive" -C "$app" --no-same-owner
sudo docker exec -w "$bench_dir" "$container" node --check apps/client_akivision/client_akivision/public/js/bom.js
sudo docker exec -w "$bench_dir" "$container" bench --site aki_test.localhost execute client_akivision.utils.master_data_sidebar.sync_master_data_sidebar
sudo docker exec -w "$bench_dir" "$container" bench --site aki_test.localhost execute client_akivision.utils.stock_sidebar.sync_stock_sidebar_entries
sudo docker exec -w "$bench_dir" "$container" bench build --app client_akivision
sudo docker exec -w "$bench_dir" "$container" bench --site aki_test.localhost clear-cache
sudo docker restart "$container"
echo "部署命令执行完成。旧文件备份：$backup"
echo "请等待服务启动后执行：curl --max-time 20 -s -o /dev/null -w 'HTTP状态码：%{http_code}\\n' http://127.0.0.1:8300/login"
