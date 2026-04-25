#!/bin/bash
# Script to start streaming the Raspberry Pi Camera Module 3 over TCP (MJPEG)
# This uses the --mode 4608:2592:12 flag to force the camera to read the entire 
# 16:9 12MP sensor so we get the full Wide Field of View (FOV) and prevent center-cropping.
# The stream is then downsampled to 640x360 for low latency transmission.

echo "Starting Raspberry Pi Camera Module 3 stream on tcp://0.0.0.0:8888"
echo "Remember to set PI_CAMERA_URL=\"tcp://<PI_IP>:8888\" in your laptop's .env file"
echo ""

sudo rpicam-vid -n -t 0 --mode 4608:2592:12 --width 640 --height 360 --framerate 30 --codec mjpeg --listen -o tcp://0.0.0.0:8888
