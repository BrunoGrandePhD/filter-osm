FROM ubuntu:22.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Update and install basic tools
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3.10-venv \
    git \
    curl \
    wget \
	build-essential cmake libboost-dev libexpat1-dev zlib1g-dev libbz2-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a symbolic link for python3 to python
RUN ln -s /usr/bin/python3 /usr/bin/python

# Install common Python packages
RUN pip3 install --no-cache-dir \
    pytest \
    pylint \
    black \
    ipython \
    requests

# Set the default shell to bash
ENV SHELL /bin/bash
