#!/bin/bash
# Install Git LFS
git lfs install
# Pull LFS files
git lfs pull
# Install Python dependencies
pip install -r requirements.txt