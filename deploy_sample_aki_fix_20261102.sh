#!/usr/bin/env bash
set -euo pipefail
aki_app=/srv/aki-erp/deploy-20260930/aki-erp-full-20260929-182611/frappe_docker/development/frappe-bench/apps/client_akivision
aki_archive=/home/yuewei/sample_aki_fix_20261102.tar.gz
aki_container=aki_full_20260930_frappe_1
aki_bench=/workspace/development/frappe-bench
test -d "$aki_app"
test -f "$aki_archive"
sudo -v
aki_backup=$(mktemp -d /home/yuewei/sample-aki-before-XXXXXX)
tar -tzf "$aki_archive" > "$aki_backup/package-files.txt"
while IFS= read -r aki_rel; do
  case "$aki_rel" in
    client_akivision/*) ;;
    *) echo "压缩包路径不合法：$aki_rel"; exit 1 ;;
  esac
  if [[ "$aki_rel" == *..* ]]; then exit 1; fi
  if sudo test -f "$aki_app/$aki_rel"; then
    sudo mkdir -p "$aki_backup/files/$(dirname "$aki_rel")"
    sudo cp -a "$aki_app/$aki_rel" "$aki_backup/files/$aki_rel"
  else
    printf '%s\n' "$aki_rel" >> "$aki_backup/new-files.txt"
  fi
done < "$aki_backup/package-files.txt"
echo "备份目录：$aki_backup"
sudo tar -xzf "$aki_archive" -C "$aki_app" --no-same-owner
sudo docker exec -w "$aki_bench" "$aki_container" bench --site aki_test.localhost execute client_akivision.utils.sample_loan_settings.ensure_schema
sudo docker exec -w "$aki_bench" "$aki_container" bench --site aki_test.localhost execute client_akivision.utils.selling_sidebar.sync_selling_sidebar_entries
sudo docker exec -w "$aki_bench" "$aki_container" bench --site aki_test.localhost clear-cache
sudo docker restart "$aki_container"
echo "部署命令已完成。请稍后检查登录页并强制刷新浏览器。"
echo "备份目录：$aki_backup"
