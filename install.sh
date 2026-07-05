#!/bin/bash
#
# Pi Dashboard — One-command installer for DietPi / Debian
# Usage: sudo bash install.sh
#

set -euo pipefail

APP_DIR="/opt/pi-dashboard"
SERVICE_NAME="pi-dashboard"

log()  { echo -e "\e[32m[OK]\e[0m $1"; }
warn() { echo -e "\e[33m[!!]\e[0m $1"; }
err()  { echo -e "\e[31m[ERR]\e[0m $1" >&2; exit 1; }

check_root() {
    [[ $EUID -eq 0 ]] || err "Запустите: sudo bash install.sh"
}

# ── Step 1: System packages ──────────────────────────────────────────
install_deps() {
    log "Установка системных пакетов..."
    apt-get update -qq

    apt-get install -y -qq \
        python3 python3-venv python3-pip python3-dev \
        samba samba-common-bin \
        transmission-daemon \
        udisks2 \
        2>/dev/null

    log "Системные пакеты установлены"
}

# ── Step 2: App directory + venv ──────────────────────────────────────
setup_venv() {
    log "Создание venv в ${APP_DIR}..."
    mkdir -p "${APP_DIR}"
    python3 -m venv "${APP_DIR}/venv"
    "${APP_DIR}/venv/bin/pip" install --upgrade pip -q
    log "Python venv готов"
}

# ── Step 3: Copy project files ────────────────────────────────────────
copy_files() {
    local SRC
    SRC="$(cd "$(dirname "$0")" && pwd)"

    log "Копирование файлов проекта..."
    for f in app.py usb.py samba.py transmission.py config.json requirements.txt; do
        [[ -f "${SRC}/${f}" ]] && cp "${SRC}/${f}" "${APP_DIR}/"
    done

    mkdir -p "${APP_DIR}/static"
    [[ -f "${SRC}/static/index.html" ]] && cp "${SRC}/static/index.html" "${APP_DIR}/static/"

    log "Файлы скопированы в ${APP_DIR}"
}

# ── Step 4: Install Python packages ───────────────────────────────────
install_python() {
    log "Установка Python-зависимостей..."
    "${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/requirements.txt" -q
    log "Python-пакеты установлены"
}

# ── Step 5: Systemd service ───────────────────────────────────────────
install_service() {
    log "Создание systemd-сервиса..."

    cat > "/etc/systemd/system/${SERVICE_NAME}.service" << 'UNIT'
[Unit]
Description=Pi Dashboard - System Monitoring Panel
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/pi-dashboard
ExecStart=/opt/pi-dashboard/venv/bin/gunicorn --workers 2 --bind 0.0.0.0:5000 app:app
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
Environment=FLASK_ENV=production

[Install]
WantedBy=multi-user.target
UNIT

    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}" -q 2>/dev/null
    systemctl restart "${SERVICE_NAME}"

    sleep 2

    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        log "Сервис запущен и включён в автозагрузку"
    else
        warn "Сервис мог не запуститься. Проверьте: journalctl -u ${SERVICE_NAME} -e"
    fi
}

# ── Step 6: DietPi tweaks ─────────────────────────────────────────────
dietpi_fixes() {
    if [[ -f /boot/dietpi.txt ]]; then
        log "DietPi обнаружен"

        if systemctl is-enabled systemd-logind.service &>/dev/null 2>&1; then
            true
        else
            warn "Размаскирую systemd-logind для udisks2..."
            systemctl unmask systemd-logind.service 2>/dev/null || true
            systemctl enable systemd-logind.service 2>/dev/null || true
            systemctl start systemd-logind.service 2>/dev/null || true
        fi
    fi
}

# ── Step 7: Summary ───────────────────────────────────────────────────
print_summary() {
    local IP
    IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

    echo ""
    echo "============================================"
    log "Установка завершена!"
    echo "============================================"
    echo ""
    echo "  URL:    http://${IP}:5000"
    echo "  Logs:   journalctl -u ${SERVICE_NAME} -f"
    echo "  Status: systemctl status ${SERVICE_NAME}"
    echo ""
}

# ── Main ──────────────────────────────────────────────────────────────
main() {
    echo ""
    log "=== Pi Dashboard Installer ==="
    echo ""

    check_root
    install_deps
    setup_venv
    copy_files
    install_python
    install_service
    dietpi_fixes
    print_summary
}

main "$@"
