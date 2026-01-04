#!/bin/bash

# 로그 디렉토리 생성
sudo mkdir -p /var/log/multi_chain_tx_lookup
sudo chown ec2-user:ec2-user /var/log/multi_chain_tx_lookup

# 애플리케이션 디렉토리 생성
sudo mkdir -p /var/www/multi_chain_tx_lookup
sudo chown ec2-user:ec2-user /var/www/multi_chain_tx_lookup

# 기존 애플리케이션 중지
if systemctl is-active --quiet multi_chain_tx_lookup; then
    sudo systemctl stop multi_chain_tx_lookup
fi

echo "BeforeInstall completed successfully" 