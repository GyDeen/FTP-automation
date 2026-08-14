#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

TEST_ROOT=$(mktemp -d /tmp/ftp-automation-test.XXXXXX)
DATA_DIR="$TEST_ROOT/data"
DOWNLOAD_DIR="$TEST_ROOT/downloads"
FTP_ROOT="$TEST_ROOT/ftp-root"
CONFIG_PATH="$TEST_ROOT/config.yaml"
SERVER_LOG="$TEST_ROOT/server.log"
SERVER_PID=""

cleanup() {
  status=$?
  trap - EXIT INT TERM
  if [[ -n "$SERVER_PID" ]]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  if [[ $status -ne 0 && -f "$SERVER_LOG" ]]; then
    echo "=== FTP server log ==="
    sed -n '1,200p' "$SERVER_LOG"
  fi
  rm -rf "$TEST_ROOT"
  exit "$status"
}
trap cleanup EXIT INT TERM

echo "=== 1. Prepare isolated test data ==="
mkdir -p "$DATA_DIR" "$DOWNLOAD_DIR" "$FTP_ROOT/uploads"

cat > "$DATA_DIR/users.csv" <<'EOF'
name,age,city
Alice,30,Beijing
Bob,25,Shanghai
Charlie,35,Shenzhen
EOF

cat > "$DATA_DIR/quarterly report.json" <<'EOF'
{"version": "1.0", "enabled": true, "retries": 3}
EOF

cat > "$CONFIG_PATH" <<EOF
ftp:
  host: "127.0.0.1"
  port: 2121
  user: "test"
  password: "test"
  timeout: 10
  max_retries: 2
  retry_delay: 0.1
  passive: true
  encoding: "utf-8"
  tls: false

tasks:
  - name: "Data upload"
    action: "upload"
    local_dir: "$DATA_DIR"
    remote_dir: "/created/nested"
    pattern: "*"
  - name: "Download test"
    action: "download"
    remote_dir: "/uploads"
    local_dir: "$DOWNLOAD_DIR"
    pattern: "*"
EOF

echo "=== 2. Start local FTP test server ==="
python3 test_ftp_server.py --port 2121 --root "$FTP_ROOT" > "$SERVER_LOG" 2>&1 &
SERVER_PID=$!
sleep 1

echo "=== 3. Upload and verify files ==="
python3 ftp_automation.py -c "$CONFIG_PATH" upload
cmp "$DATA_DIR/users.csv" "$FTP_ROOT/created/nested/users.csv"
cmp "$DATA_DIR/quarterly report.json" "$FTP_ROOT/created/nested/quarterly report.json"

echo "=== 4. Download and verify a filename containing spaces ==="
printf '%s\n' "hello from ftp" > "$FTP_ROOT/uploads/report final.txt"
python3 ftp_automation.py -c "$CONFIG_PATH" download
cmp "$FTP_ROOT/uploads/report final.txt" "$DOWNLOAD_DIR/report final.txt"

echo "=== Local FTP integration test passed ==="
