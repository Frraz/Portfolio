#!/usr/bin/env bash
set -euo pipefail

PROJECT_PATH="${PROJECT_PATH:-/home/ubuntu/Portfolio}"
SERVICE_NAME="${SERVICE_NAME:-portfolio}"

echo "[deploy] Iniciando deploy em ${PROJECT_PATH}"

# Carregar venv e instalar dependências
if [ ! -d "${PROJECT_PATH}/venv" ]; then
  echo "[deploy] Criando venv..."
  python3 -m venv "${PROJECT_PATH}/venv"
fi

source "${PROJECT_PATH}/venv/bin/activate"

echo "[deploy] Atualizando pip e instalando requirements..."
pip install --upgrade pip
pip install -r "${PROJECT_PATH}/requirements.txt"

# Permissões para nginx acessar socket
echo "[deploy] Ajustando permissões..."
sudo chown -R ubuntu:www-data "${PROJECT_PATH}"
sudo chmod 750 "${PROJECT_PATH}"

# Reiniciar serviço
echo "[deploy] Reiniciando serviço ${SERVICE_NAME}..."
sudo systemctl daemon-reload
sudo systemctl restart "${SERVICE_NAME}"
sudo systemctl status "${SERVICE_NAME}" --no-pager

echo "[deploy] Deploy concluído."