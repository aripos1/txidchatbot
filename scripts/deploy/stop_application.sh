#!/bin/bash

# 애플리케이션 중지
if systemctl is-active --quiet multi_chain_tx_lookup; then
    sudo systemctl stop multi_chain_tx_lookup
    echo "Application stopped successfully"
else
    echo "Application was not running"
fi 