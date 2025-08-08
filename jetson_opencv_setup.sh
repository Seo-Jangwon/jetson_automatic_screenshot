#!/bin/bash

# 스크립트 실행 중 오류가 발생하면 즉시 중단
set -e

echo "기존 OpenCV 관련 패키지 제거 중..."
# 충돌을 방지하기 위해 시스템에 설치된 이전 버전의 OpenCV를 제거
sudo apt-get remove -y python3-opencv libopencv-dev opencv-data > /dev/null 2>&1 || true
pip3 uninstall -y opencv-python opencv-contrib-python opencv-python-headless > /dev/null 2>&1 || true
echo "   - 기존 OpenCV 제거 완료"
echo ""

echo "시스템 패키지 목록 업데이트 및 업그레이드 중..."
sudo apt-get update
sudo apt-get upgrade -y
echo "   - 시스템 업데이트 완료"
echo ""

echo "GStreamer 관련 패키지 설치 중..."
# Python 스크립트에서 nvarguscamerasrc 파이프라인을 사용하기 위해 GStreamer와 플러그인들을 설치
sudo apt-get install -y gstreamer1.0-tools gstreamer1.0-alsa \
                        gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
                        gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
                        gstreamer1.0-libav libgstreamer1.0-dev \
                        libgstreamer-plugins-base1.0-dev
echo "   - GStreamer 패키지 설치 완료"
echo ""

echo "Python 개발 및 기본 패키지 설치 중..."
sudo apt-get install -y python3-dev python3-pip python3-numpy
echo "   - Python 기본 패키지 설치 완료"
echo ""

echo "GUI 및 이미지 처리 라이브러리 설치 중..."
# Tkinter GUI 라이브러리를 설치
sudo apt-get install -y python3-tk

# Pillow 라이브러리 빌드에 필요한 의존성 패키지를 먼저 설치
echo "   - Pillow 의존성 라이브러리(libjpeg) 설치..."
sudo apt-get install -y libjpeg-dev

# Pillow 라이브러리를 pip을 통해 설치
pip3 install Pillow
echo "   - GUI 및 이미지 처리 라이브러리 설치 완료"
echo ""


echo "NVIDIA 최적화 OpenCV 설치 중..."
# Jetson에 최적화된 하드웨어 가속 지원 OpenCV 버전을 설치
sudo apt-get install -y nvidia-opencv
echo "   - NVIDIA OpenCV 설치 완료"
echo ""

echo "카메라 장치 권한 설정 중..."
# 현재 사용자가 비디오 장치에 접근할 수 있도록 'video' 그룹에 추가
sudo usermod -a -G video $USER
# /dev/video* 장치에 대한 읽기/쓰기 권한을 부여
sudo chmod 666 /dev/video* 2>/dev/null || true
echo "   - 카메라 권한 설정 완료"
echo ""

echo "프로젝트 폴더 생성 중..."
# Python 스크립트에서 사용할 샘플 폴더를 생성
mkdir -p sample
echo "   - 프로젝트 폴더 생성 완료"
echo ""

echo "=========================================="
echo "          설치 환경 검증"
echo "=========================================="

echo "1. OpenCV 버전 확인:"
python3 -c "import cv2; print(f'   - OpenCV Version: {cv2.__version__}')"

echo "2. GStreamer 지원 여부 확인:"
GSTREAMER_CHECK=$(python3 -c "import cv2; print(cv2.getBuildInformation())" | grep -i gstreamer)
if [[ $GSTREAMER_CHECK == *"YES"* ]]; then
    echo "   - GStreamer 지원: YES"
else
    echo "   - GStreamer 지원: NO (문제 발생 가능성 있음)"
fi

echo "3. Pillow (PIL) 라이브러리 확인:"
python3 -c "from PIL import Image; print(f'   - Pillow Version: {Image.__version__}')"

echo "4. NumPy 라이브러리 확인:"
python3 -c "import numpy; print(f'   - NumPy Version: {numpy.__version__}')"

echo "5. 카메라 장치 연결 상태 확인:"
if ls /dev/video* 1> /dev/null 2>&1; then
    echo "   - 카메라 장치 발견:"
    ls -l /dev/video*
else
    echo "   - 카메라 장치를 찾을 수 없습니다. 연결을 확인하세요."
fi

echo ""
echo "=========================================="
echo "          설치 완료!"
echo "=========================================="
echo ""
echo "!!! 중요 !!!"
echo "1. 변경사항(특히 사용자 그룹)을 완전히 적용하려면 터미널을 재시작하거나 재로그인해야 합니다."
echo "2. 가장 확실한 방법은 시스템을 재부팅하는 것입니다: sudo reboot"
echo ""