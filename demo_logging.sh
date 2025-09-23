#!/bin/bash
# Demonstration script for the new logging service

echo "=== File Transfer Application - Logging Service Demo ==="
echo ""

cd src

echo "1. Testing VERBOSE mode (-v flag):"
echo "Command: python3 start-server.py -v -H 127.0.0.1 -p 5000"
echo "Expected output: INFO, DEBUG, and VERBOSE messages with timestamps"
echo ""

echo "2. Testing NORMAL mode (no flag):"
echo "Command: python3 start-server.py -H 127.0.0.1 -p 5000"
echo "Expected output: Only INFO messages with timestamps"
echo ""

echo "3. Testing QUIET mode (-q flag):"
echo "Command: python3 start-server.py -q -H 127.0.0.1 -p 5000"
echo "Expected output: Only ERROR and CRITICAL messages with timestamps"
echo ""

echo "4. Testing upload with verbose logging:"
echo "Command: python3 upload.py -v -H 127.0.0.1 -p 5000 -s file.txt -n test.txt"
echo "Expected output: Detailed handshake info, protocol details, file paths"
echo ""

echo "5. Testing download with verbose logging:"
echo "Command: python3 download.py -v -H 127.0.0.1 -p 5000 -n test.txt -d result.txt"
echo "Expected output: Detailed transfer information and debugging info"
echo ""

echo "All logging messages include timestamps in [HH:MM:SS.mmm] format"
echo "Log levels: CRITICAL, ERROR, INFO, DEBUG, VERBOSE"
echo "Errors go to stderr, other messages to stdout"