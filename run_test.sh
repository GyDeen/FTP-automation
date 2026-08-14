#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "=== 1. Prepare test data ==="
mkdir -p data downloads ftp_root/backup/data ftp_root/uploads

# Generate test files
cat > data/users.csv << 'EOF'
name,age,city
Alice,30,Beijing
Bob,25,Shanghai
Charlie,35,Shenzhen
EOF

cat > data/config.json << 'EOF'
{"version": "1.0", "enabled": true, "retries": 3}
EOF

cat > data/notes.xml << 'EOF'
<?xml version="1.0"?>
<notes><note id="1"><title>Test</title><body>Hello FTP</body></note></notes>
EOF

echo "    CSV: $(wc -l < data/users.csv) rows, JSON: $(wc -c < data/config.json) B, XML: $(wc -c < data/notes.xml) B"

echo ""
echo "=== 2. Update configuration for the local test server ==="
cat > config.yaml << 'YAML'
ftp:
  host: "127.0.0.1"
  port: 2121
  user: "test"
  password: "test"
  timeout: 10
  max_retries: 2
  retry_delay: 1.0
  passive: true
  encoding: "utf-8"

tasks:
  - name: "Data file upload"
    action: "upload"
    local_dir: "./data"
    remote_dir: "/backup/data"
    pattern: "*"
  - name: "Download test"
    action: "download"
    remote_dir: "/uploads"
    local_dir: "./downloads"
    pattern: "*"

watch:
  enabled: false
  local_dir: "./watch"
  remote_dir: "/uploads"
  interval: 5
  pattern: "*"

scheduler:
  interval: 0
  cron: []
YAML
echo "    config.yaml updated"

echo ""
echo "=== 3. Start the local FTP test server ==="
echo "    (Running in the background on port 2121)"
python3 test_ftp_server.py --port 2121 --root ./ftp_root &
SRV_PID=$!
echo "    PID: $SRV_PID"
sleep 1

echo ""
echo "=== 4. Run upload ==="
python3 ftp_automation.py upload

echo ""
echo "=== 5. Verify remote files ==="
echo "    Remote directory contents:"
ls -la ftp_root/backup/data/

echo ""
echo "=== 6. Test download (first place a file in the remote uploads directory) ==="
echo "hello from ftp" > downloads/test.txt
cp downloads/test.txt ftp_root/uploads/
python3 ftp_automation.py download

echo ""
echo "=== 7. Verify download results ==="
ls -la downloads/

echo ""
echo "=== 8. Clean up ==="
kill $SRV_PID 2>/dev/null || true
echo "    Test server stopped"
echo ""
echo "=== Complete! ==="
