#!/bin/bash
set -e

echo "Starting installation script for Debian/Ubuntu..."

# Check if script is run as root
if [ "$(id -u)" != "0" ]; then
    echo "This script needs to be run as root. Please switch to root (e.g. 'su -') or run with sudo."
    exit 1
fi

echo "Updating package list..."
apt-get update -y

echo "Installing essential dependencies (sudo, curl, wget, git, python3, pip, venv)..."
apt-get install -y sudo curl wget git python3 python3-pip python3-venv

if ! command -v docker &> /dev/null; then
    echo "Docker not found. Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    
    echo "Installing Docker Compose plugin..."
    apt-get install -y docker-compose-plugin
else
    echo "Docker is already installed."
fi

echo "Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

echo "Installing Python dependencies..."
.venv/bin/pip install -r requirements.txt

if [ ! -f ".env" ] && [ -f ".env.template" ]; then
    echo "Copying .env.template to .env..."
    cp .env.template .env
    echo "NOTE: Please fill out the .env file with your specific credentials."
fi

echo "Installation complete!"
