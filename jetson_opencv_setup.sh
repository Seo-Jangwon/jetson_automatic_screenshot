#!/bin/bash

echo "기존 OpenCV 제거 중..."
sudo apt remove -y python3-opencv libopencv-dev opencv-data
pip3 uninstall -y opencv-python opencv-contrib-python opencv-python-headless 2>/dev/null || true

echo "   - 기존 OpenCV 제거 완료"

echo "시스템 패키지 업데이트 중..."
sudo apt update
sudo apt upgrade -y

echo "GStreamer 패키지 설치 중..."
sudo apt install -y gstreamer1.0-tools gstreamer1.0-alsa 
sudo apt install -y gstreamer1.0-plugins-base gstreamer1.0-plugins-good 
sudo apt install -y gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly 
sudo apt install -y gstreamer1.0-libav
sudo apt install -y libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev

echo "   - GStreamer 패키지 설치 완료"

echo "기본 패키지 설치 중..."
sudo apt install -y python3-numpy
sudo apt install -y python3-dev python3-pip

echo "GUI 및 이미지 처리를 위한 패키지 설치 중..."
sudo apt install -y python3-tk
pip3 install Pillow

echo "NVIDIA OpenCV 설치 중..."
sudo apt install -y nvidia-opencv

echo "   - NVIDIA OpenCV 설치 완료"

echo "카메라 권한 설정 중..."
sudo usermod -a -G video $USER
sudo chmod 666 /dev/video* 2>/dev/null || true
echo "   - 카메라 권한 설정 완료"

echo "프로젝트 폴더 생성 중..."
mkdir -p sample

echo "   - 프로젝트 폴더 생성 완료"

echo "설치 검증 중..."
echo "   OpenCV 버전 확인:"
python3 -c "import cv2; print('OpenCV Version:', cv2.__version__)"

echo "GStreamer 지원 확인:"
GSTREAMER_CHECK=$(python3 -c "import cv2; print(cv2.getBuildInformation())" | grep -i gstreamer)
if [[ $GSTREAMER_CHECK == *"YES"* ]]; then
    echo "   GStreamer 지원: YES"
else
    echo "   GStreamer 지원: NO"
fi

echo "   NumPy 확인:"
python3 -c "import numpy; print('NumPy Version:', numpy.__version__)"

echo "9. 카메라 연결 상태 확인:"
if ls /dev/video* 1> /dev/null 2>&1; then
    echo "   카메라 장치 발견:"
    ls -l /dev/video*
else
    echo "  카메라 장치를 찾을 수 없습니다."
fi

echo "=========================================="
echo "설치 완료!"
echo "=========================================="
echo "주의사항:"
echo "1. 터미널을 재시작하거나 재로그인 해주세요."
echo "2. 카메라 테스트: gst-launch-1.0 nvarguscamerasrc sensor-id=0 ! nvvidconv ! xvimagesink"
echo "3. Python 테스트 코드:"
echo "   python3 -c \"import cv2; cap=cv2.VideoCapture(0); print('카메라 상태:', cap.isOpened()); cap.release()\""
echo "=========================================="

echo "변경사항 적용을 위해 재부팅을 권장"
echo "   sudo reboot"
echo ""
