import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import cv2
import numpy as np
from PIL import Image, ImageTk
import sys
import time

class CameraUI:
    """
    젯슨나노 스크린샷 자동화
    
    카메라 미리보기, ROI 설정, 
    시간 기반 자동 캡처 기능 제공
    """
    def __init__(self, camera_id=1):
        """
        CameraUI 인스턴스 초기화
        
        Args:
            camera_id (int): 사용할 카메라 ID (기본값: 0)
        """
        self.camera_id = camera_id # 카메라 식별자

        # 메인 윈도우 생성 및 설정
        self.root = tk.Tk()
        self.root.title(f"Camera {camera_id} Control Panel")
        self.root.geometry("850x800") # 초기 윈도우 크기
        self.root.resizable(True, True) # 크기 조절 가능
        self.root.minsize(800, 800) # 최소 크기 제한

        # 캡처 관련 기본값 설정 Variables
        self.start_delay = 0.0 # 캡처 시작 전 대기 시간 (초)

        # 캡처 타이밍 설정 List 및 default value
        self.cap_time = [
            {'end_point': 10.0, 'interval': 1.0}, # end_point: 해당 구간의 종료 시점 (누적 시간), interval: 해당 구간에서의 캡처 간격
            {'end_point': 20.0, 'interval': 1.0}
        ]
        self.crop = {'xmin': 240, 'ymin': 100, 'width': 260, 'height': 800} # ROI default value
        
        # folder default name
        self.target = 'target' 
        self.titer = 'titer'
        self.base_path = './sample'

        # ROI 선택 관련 상태 변수
        self.roi_selecting = False  # ROI 선택 중인지
        self.roi_start = None  # ROI 선택 시작점
        self.roi_widgets = []  # ROI 관련 위젯들 (활성화/비활성화 제어용)
        
        # 카메라 및 미리보기 관련 변수
        self.preview_frame = None  # 현재 미리보기 프레임
        self.video_capture = None  # OpenCV VideoCapture 객체
        self.preview_running = True  # 미리보기 실행 상태
        
        # 캡처 프로세스 관련 변수
        self.is_capturing = False  # 캡처 진행 중 여부
        self.capture_thread = None  # 캡처 스레드
        self.preview_thread = None  # 미리보기 스레드
        
        # UI 관련 변수
        self.timing_vars = []  # 캡쳐 타이밍 설정 UI 변수들
        self.timing_frame_container = None  # 캡쳐 타이밍 위젯 컨테이너
        self.add_button = None  # 캡쳐 구간 추가 버튼
        self.remove_button = None  # 캡쳐 구간 제거 버튼

        # UI 구성 및 미리보기 시작
        self.setup_ui()
        self.start_preview()

        # 키보드 이벤트 바인딩 (ROI 위치 미세조정용)
        self.root.bind("<Up>", self._on_key_press)     # ↑: y 감소
        self.root.bind("<Down>", self._on_key_press)   # ↓: y 증가
        self.root.bind("<Left>", self._on_key_press)   # ←: x 감소
        self.root.bind("<Right>", self._on_key_press)  # →: x 증가

    def _on_key_press(self, event):
        """
        방향키로 ROI 위치 조정 핸들러
        
        방향키로 ROI 위치를 1픽셀씩 이동
        Shift + 방향키로 10픽셀씩 이동
        
        Args:
            event: 키보드 이벤트 객체
        """

        # 캡쳐 중 방향키 반영 X
        if self.is_capturing:
            return
        
        # 현재 ROI values 가져옴
        try:
            xmin = int(self.xmin_var.get())
            ymin = int(self.ymin_var.get())
            width = int(self.width_var.get())
            height = int(self.height_var.get())
        except (ValueError, tk.TclError):
            return # 유효하지 않은 값이면 return
        
        # Shift 키 눌려있으면 10픽셀 이동, 아님 1픽셀 이동
        step = 10 if (event.state & 0x0001) else 1

        # 방향키에 따라 ROI 위치 이동
        if event.keysym == 'Up': ymin -= step
        elif event.keysym == 'Down': ymin += step
        elif event.keysym == 'Left': xmin -= step
        elif event.keysym == 'Right': xmin += step

        # 프레임 경계 안벗어나도록
        if self.preview_frame is not None:
            frame_h, frame_w = self.preview_frame.shape[:2]
            xmin = max(0, min(xmin, frame_w - width))
            ymin = max(0, min(ymin, frame_h - height))

        # UI 업데이트
        self.xmin_var.set(str(xmin))
        self.ymin_var.set(str(ymin))

    def setup_ui(self):
        """
        전체 UI 레이아웃 구성
    
        좌측: 설정 컨트롤 패널
        우측: 카메라 미리보기 화면
        PanedWindow 사용해 크기 조절 가능한 2열 레이아웃 생성
        """

        # 수평 분할 윈도우(좌우 나누기)
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 좌측 프레임: 설정 컨트롤들
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)
        
        # 우측 프레임: 미리보기 화면
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)
        
        # 각 프레임에 내용 추가
        self.setup_controls(left_frame) # 좌측엔 컨트롤 패널
        self.setup_preview(right_frame) # 우측엔 미리보기 화면

    def setup_controls(self, parent):
        """
        좌측 컨트롤 패널 구성
        스크롤 가능한 영역에 모든 설정 위젯들 배치
    
        Args:
            parent: 컨트롤들 배치될 부모 프레임
        """
        
        canvas = tk.Canvas(parent, width=350)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        main_frame = ttk.Frame(scrollable_frame, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        title_label = ttk.Label(main_frame, text=f"Camera {self.camera_id} Settings", font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 20))
        self.setup_path_settings(main_frame)
        self.setup_roi_settings(main_frame)
        self.setup_timing_settings(main_frame)
        self.setup_status_and_button(main_frame)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def setup_path_settings(self, parent):
        """
        파일 저장 경로 설정 UI구성
   
        구성 요소:
        - 기본 경로 입력 및 탐색 버튼
        - Target과 Titer 이름 입력 필드
        - 최종 저장 경로 미리보기
   
        Args:
            parent: 위젯들이 배치될 부모 프레임
        """
        path_frame = ttk.LabelFrame(parent, text="Save Path Settings", padding="10")
        path_frame.pack(fill=tk.X, pady=(0, 10))
        base_path_frame = ttk.Frame(path_frame)
        base_path_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(base_path_frame, text="Base Path:").pack(side=tk.LEFT)
        self.base_path_var = tk.StringVar(value=self.base_path)
        base_path_entry = ttk.Entry(base_path_frame, textvariable=self.base_path_var, width=20)
        base_path_entry.pack(side=tk.LEFT, padx=(5, 5), fill=tk.X, expand=True)
        browse_button = ttk.Button(base_path_frame, text="Browse", command=self.browse_base_path)
        browse_button.pack(side=tk.RIGHT)
        target_frame = ttk.Frame(path_frame)
        target_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Label(target_frame, text="Target:").grid(row=0, column=0, sticky=tk.W)
        self.target_var = tk.StringVar(value=self.target)
        ttk.Entry(target_frame, textvariable=self.target_var, width=12).grid(row=0, column=1, padx=(5, 10), sticky=(tk.W, tk.E))
        ttk.Label(target_frame, text="Titer:").grid(row=0, column=2, sticky=tk.W)
        self.titer_var = tk.StringVar(value=self.titer)
        ttk.Entry(target_frame, textvariable=self.titer_var, width=12).grid(row=0, column=3, padx=5, sticky=(tk.W, tk.E))
        # 컬럼 크기 조정 (입력 필드가 늘어나도록)
        target_frame.columnconfigure(1, weight=1)
        target_frame.columnconfigure(3, weight=1)
        self.path_preview = tk.StringVar(value=f"{self.base_path}/{self.target}/{self.titer}/")
        ttk.Label(path_frame, text="Full Save Path:").pack(anchor=tk.W, pady=(10, 0))
        path_preview_label = ttk.Label(path_frame, textvariable=self.path_preview, foreground="blue", font=("Arial", 8), relief="sunken", padding="3")
        path_preview_label.pack(fill=tk.X, pady=(5, 0))
        self.base_path_var.trace('w', self.update_path_preview)
        self.target_var.trace('w', self.update_path_preview)
        self.titer_var.trace('w', self.update_path_preview)

    def browse_base_path(self):
        """
        폴더 선택 다이얼로그 열어 기본 경로 선택
   
        현재 설정된 경로를 초기 위치로 사용, 없으면 사용자 홈 디렉토리 표시
        """
        selected_path = filedialog.askdirectory(initialdir=self.base_path_var.get() or os.path.expanduser("~"))
        if selected_path:
            self.base_path_var.set(selected_path)

    def update_path_preview(self, *args):
        """
        경로 미리보기를 업데이트
   
        base_path, target, titer를 조합하여 실제 저장될 전체 경로를 표시
   
        Args:
           *args: trace 콜백에서 전달되는 인자들 (사용하지 않음)
        """
        path = f"{self.base_path_var.get()}/{self.target_var.get()}/{self.titer_var.get()}/"
        self.path_preview.set(path)


    def setup_roi_settings(self, parent):
        """
        ROI 설정 UI 구성
   
        구성 요소:
        - X Min, Y Min: ROI 시작점 좌표
        - Width, Height: ROI 크기
        - Reset ROI: 기본값으로 초기화
        - Full Size: 전체 프레임 크기로 설정
        - 도움말 텍스트
   
        Args:
           parent: 위젯들이 배치될 부모 프레임
        """
        roi_frame = ttk.LabelFrame(parent, text="ROI Settings", padding="10")
        roi_frame.pack(fill=tk.X, pady=(0, 10))
        roi_grid = ttk.Frame(roi_frame)
        roi_grid.pack(fill=tk.X)
        
        ttk.Label(roi_grid, text="X Min:").grid(row=0, column=0, sticky=tk.W)
        self.xmin_var = tk.StringVar(value=str(self.crop['xmin']))
        xmin_entry = ttk.Entry(roi_grid, textvariable=self.xmin_var, width=8)
        xmin_entry.grid(row=0, column=1, padx=(5, 10))

        ttk.Label(roi_grid, text="Y Min:").grid(row=0, column=2, sticky=tk.W)
        self.ymin_var = tk.StringVar(value=str(self.crop['ymin']))
        ymin_entry = ttk.Entry(roi_grid, textvariable=self.ymin_var, width=8)
        ymin_entry.grid(row=0, column=3, padx=5)

        ttk.Label(roi_grid, text="Width:").grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        self.width_var = tk.StringVar(value=str(self.crop['width']))
        width_entry = ttk.Entry(roi_grid, textvariable=self.width_var, width=8)
        width_entry.grid(row=1, column=1, padx=(5, 10), pady=(8, 0))

        ttk.Label(roi_grid, text="Height:").grid(row=1, column=2, sticky=tk.W, pady=(8, 0))
        self.height_var = tk.StringVar(value=str(self.crop['height']))
        height_entry = ttk.Entry(roi_grid, textvariable=self.height_var, width=8)
        height_entry.grid(row=1, column=3, padx=5, pady=(8, 0))

        button_frame = ttk.Frame(roi_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        reset_button = ttk.Button(button_frame, text="Reset ROI", command=self.reset_roi)
        reset_button.pack(side=tk.LEFT)
        
        full_size_button = ttk.Button(button_frame, text="Full Size", command=self.set_full_roi)
        full_size_button.pack(side=tk.LEFT, padx=(5, 0))
        
        self.roi_widgets = [xmin_entry, ymin_entry, width_entry, height_entry, reset_button, full_size_button]
        help_text = "마우스 드래그로 ROI 선택, 방향키로 위치 이동 (Shift+방향키: 10px)"
        help_label = ttk.Label(roi_frame, text=help_text, font=("Arial", 8), foreground="gray")
        help_label.pack(pady=(5, 0))
    
    def reset_roi(self):
        """
        ROI 기본값으로 초기화
   
        기본값:
        - xmin: 240, ymin: 100
        - width: 260, height: 800
        """
        self.xmin_var.set("240")
        self.ymin_var.set("100")
        self.width_var.set("260")
        self.height_var.set("800")

    def set_full_roi(self):
        """
        ROI를 전체 프레임 크기로 설정
   
        현재 미리보기 프레임의 전체 크기를 ROI로 설정
        프레임이 없으면 아무 동작 안 함
        """
        if self.preview_frame is not None:
            height, width = self.preview_frame.shape[:2]
            self.xmin_var.set("0")
            self.ymin_var.set("0")
            self.width_var.set(str(width))
            self.height_var.set(str(height))

    def setup_timing_settings(self, parent):
        """
        캡처 타이밍 설정 UI 구성
   
        구성 요소:
        - 구간 추가/제거 버튼 (+, -)
        - Start Delay: 캡처 시작 전 대기 시간
        - 각 구간별 Interval과 End Point 설정
        - 최대 3개 구간까지 설정 가능
   
        Args:
            parent: 위젯들이 배치될 부모 프레임
        """
        timing_frame = ttk.LabelFrame(parent, text="Capture Timing (seconds)", padding="10")
        timing_frame.pack(fill=tk.X, pady=(0, 10))
        
        # ===== 구간 추가/제거 버튼 섹션 =====
        button_frame = ttk.Frame(timing_frame)
        button_frame.pack(fill=tk.X, pady=(0, 5))

        # + 버튼: 새로운 구간 추가 (최대 3개)
        self.add_button = ttk.Button(button_frame, text="+", width=3, command=self._add_interval)
        self.add_button.pack(side=tk.LEFT)

        # - 버튼: 마지막 구간 제거 (최소 1개 유지)
        self.remove_button = ttk.Button(button_frame, text="-", width=3, command=self._remove_interval)
        self.remove_button.pack(side=tk.LEFT, padx=5)

        info_label = ttk.Label(timing_frame, text="Info: Middle/End 값은 '누적 종료 시점'입니다.", font=("Arial", 8), foreground="gray")
        info_label.pack(anchor=tk.W, pady=(0, 10))
        
        # 타이밍 위젯들 동적으로 생성될 컨테이너
        self.timing_frame_container = ttk.Frame(timing_frame)
        self.timing_frame_container.pack(fill=tk.X)
        
        # 초기 타이밍 위젯들 생성
        self._redraw_timing_widgets()

    def _redraw_timing_widgets(self):
        """
        타이밍 설정 위젯들 다시 그림
   
        구간이 추가/제거될 때마다 호출되어
        현재 self.cap_time 데이터에 맞춰 UI를 재구성
        """

        # 기존 위젯들 모두 제거
        for widget in self.timing_frame_container.winfo_children():
            widget.destroy()
        
        # timing_vars 리스트 초기화
        self.timing_vars.clear()

        # ===== Start Delay 입력 필드 =====
        start_frame = ttk.Frame(self.timing_frame_container)
        start_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(start_frame, text="Start Delay:", width=10).grid(row=0, column=0, sticky=tk.W)
        
        # Start Delay 값 저장할 변수
        start_var = tk.StringVar(value=str(self.start_delay))
        ttk.Entry(start_frame, textvariable=start_var, width=8).grid(row=0, column=1, padx=5)
        
        # timing_vars에 추가 (나중에 값 읽기 위해)
        self.timing_vars.append({'type': 'start', 'var': start_var})
        
        # 구분선
        ttk.Separator(self.timing_frame_container, orient='horizontal').pack(fill='x', pady=5)

        # ===== 각 구간(Phase)별 설정 =====
        num_phases = len(self.cap_time)
        for i, phase_data in enumerate(self.cap_time):
            phase_frame = ttk.Frame(self.timing_frame_container)
            phase_frame.pack(fill=tk.X, pady=(0, 5))
            
            # 마지막 구간인지 확인 (마지막은 "End Point", 중간은 "Middle X at")
            is_last_phase = (i == num_phases - 1)
            label_text = f"End Point:" if is_last_phase else f"Middle {i+1} at:"
            
            # Interval 입력 필드 (캡처 간격)
            ttk.Label(phase_frame, text=f"Interval {i+1}:", width=10).grid(row=0, column=0, sticky=tk.W)
            interval_var = tk.StringVar(value=str(phase_data['interval']))
            ttk.Entry(phase_frame, textvariable=interval_var, width=8).grid(row=0, column=1, padx=5)
            
            # End Point 입력 필드 (구간 종료 시점 - 누적 시간)
            ttk.Label(phase_frame, text=label_text).grid(row=0, column=2, sticky=tk.W, padx=(10, 0))
            endpoint_var = tk.StringVar(value=str(phase_data['end_point']))
            ttk.Entry(phase_frame, textvariable=endpoint_var, width=8).grid(row=0, column=3, padx=5)

            # timing_vars에 추가
            self.timing_vars.append({'type': 'phase', 'endpoint_var': endpoint_var, 'interval_var': interval_var})
        
        # 버튼 상태 업데이트
        self._update_timing_buttons_state()

    def _update_timing_buttons_state(self):
        """
        구간 추가/제거 버튼 활성화 상태 업데이트
   
        - 구간이 3개면 추가 버튼 비활성화
        - 구간이 1개면 제거 버튼 비활성화
        """
        num_phases = len(self.cap_time)
        self.add_button.config(state=tk.NORMAL if num_phases < 3 else tk.DISABLED)
        self.remove_button.config(state=tk.NORMAL if num_phases > 1 else tk.DISABLED)
        
    def _add_interval(self):
        """
        새로운 캡처 구간 추가
   
        마지막 구간의 종료 시점 + 10초를 새 구간의 종료 시점으로 설정
        최대 3개까지만 추가 가능
        """
        if len(self.cap_time) < 3:
            last_endpoint = self.cap_time[-1]['end_point'] if self.cap_time else 0
            self.cap_time.append({'end_point': last_endpoint + 10.0, 'interval': 1.0})
            self._redraw_timing_widgets()
    
    def _remove_interval(self):
        """
        마지막 캡처 구간 제거
   
        최소 1개 구간은 유지되어야 함
        """
        if len(self.cap_time) > 1:
            self.cap_time.pop()
            self._redraw_timing_widgets()

    def setup_status_and_button(self, parent):
        """
        상태 표시 라벨과 캡처 시작/정지 버튼을 구성합니다.
   
        구성 요소:
        - Status 라벨: 현재 상태 표시 (Ready/Capturing...)
        - Start Capture 버튼: 캡처 시작
        - Stop Capture 버튼: 캡처 중지
   
        Args:
            parent: 위젯들이 배치될 부모 프레임
        """

        # ===== 상태 표시 =====
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT)
        
        # 상태 메시지를 저장
        self.status_var = tk.StringVar(value="Ready")

        # 상태 표시 라벨 (녹색 텍스트)
        status_label = ttk.Label(status_frame, textvariable=self.status_var, foreground="green")
        status_label.pack(side=tk.LEFT, padx=(10, 0))

        # ===== 캡처 시작 버튼 =====
        self.start_button = ttk.Button(parent, text="Start Capture", command=self.start_camera)
        self.start_button.pack(pady=15, fill=tk.X)

        # ===== 캡처 정지 버튼 (초기에는 비활성화) =====
        self.stop_button = ttk.Button(parent, text="Stop Capture", command=self.stop_camera, state=tk.DISABLED)
        self.stop_button.pack(pady=(5, 0), fill=tk.X)

    def setup_preview(self, parent):
        """
        카메라 미리보기 화면을 구성합니다.
   
        구성 요소:
        - 미리보기 캔버스: 실시간 카메라 영상과 ROI 표시
        - 정보 라벨: 해상도 등 미리보기 정보 표시
        - 마우스 이벤트 바인딩: ROI 선택 기능
   
        Args:
            parent: 미리보기가 배치될 부모 프레임
        """
        preview_frame = ttk.LabelFrame(parent, text="Camera Preview & ROI Selection", padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True)
        self.preview_canvas = tk.Canvas(preview_frame, bg='black', width=400, height=350)
        self.preview_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 마우스 이벤트 바인딩 (ROI 선택용)
        # Button-1: 마우스 왼쪽 버튼
        self.preview_canvas.bind("<Button-1>", self.on_mouse_press)
        self.preview_canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.preview_canvas.bind("<ButtonRelease-1>", self.on_mouse_release)
        
        # 미리보기 정보 표시
        info_frame = ttk.Frame(preview_frame)
        info_frame.pack(fill=tk.X, pady=(5, 0))
        
        # 미리보기 정보 텍스트 (해상도 등)
        self.preview_info = tk.StringVar(value="미리보기 로딩중...")
        ttk.Label(info_frame, textvariable=self.preview_info, font=("Arial", 9)).pack()

    def validate_inputs(self):
        """
        사용자 입력값들 유효성 검증
   
        검증 항목:
        - ROI가 프레임 경계 내에 있는지
        - 타이밍 값들이 유효한지 (양수, 순차적)
        - Target과 Titer 이름이 입력되었는지
   
        Returns:
            bool: 모든 입력이 유효하면 True, 아니면 False
        """
        
        try:
            # 미리보기 프레임이 없으면 검증 불가
            if self.preview_frame is None: raise ValueError("Preview not available.")
            
            # 현재 프레임 크기 가져오기
            frame_h, frame_w = self.preview_frame.shape[:2]
            
            # ROI 값들 가져오기
            xmin, ymin, width, height = int(self.xmin_var.get()), int(self.ymin_var.get()), int(self.width_var.get()), int(self.height_var.get())
            
            # ROI가 프레임 경계를 벗어나는지 확인
            if (xmin + width) > frame_w or (ymin + height) > frame_h: raise ValueError(f"ROI exceeds image bounds ({frame_w}x{frame_h})")
            
            # Start Delay 검증
            last_endpoint = float(self.timing_vars[0]['var'].get())
            if last_endpoint < 0: raise ValueError("Start Delay must be non-negative")

            # 각 구간 타이밍 값 검증
            for var_dict in self.timing_vars:
                if var_dict['type'] == 'phase':
                    endpoint = float(var_dict['endpoint_var'].get())
                    interval = float(var_dict['interval_var'].get())
                    
                    # 간격은 양수여야 함
                    if interval <= 0:
                        raise ValueError("Intervals must be positive (e.g. > 0)")
                    
                    # 종료 시점은 이전 시점보다 커야 함 (순차적)
                    if endpoint <= last_endpoint:
                        raise ValueError("Each end point must be greater than the previous time point.")
                    last_endpoint = endpoint
            # Target과 Titer 이름이 비어있지 않은지 확인
            if not self.target_var.get().strip() or not self.titer_var.get().strip(): raise ValueError("Target and Titer names cannot be empty")
            return True
        except (ValueError, tk.TclError) as e:
            # 아니면 오류 표시
            messagebox.showerror("Input Error", str(e))
            return False

    def update_variables(self):
        """
        UI의 현재 값들 인스턴스 변수에 저장
        캡처 시작 전에 호출, UI의 설정값들을 실제 캡처에 사용할 변수들로 복사
        """
        # ROI 설정 업데이트
        self.crop = {'xmin': int(self.xmin_var.get()), 'ymin': int(self.ymin_var.get()), 'width': int(self.width_var.get()), 'height': int(self.height_var.get())}
        
        # 캡쳐 타이밍 설정 업데이트
        self.cap_time.clear()
        for var_dict in self.timing_vars:
            if var_dict['type'] == 'start':
                # Start Delay 업데이트
                self.start_delay = float(var_dict['var'].get())
            elif var_dict['type'] == 'phase':
                # 각 구간 설정
                self.cap_time.append({
                    'end_point': float(var_dict['endpoint_var'].get()),
                    'interval': float(var_dict['interval_var'].get())
                })
        # 경로 설정 업데이트
        self.target = self.target_var.get().strip()
        self.titer = self.titer_var.get().strip()
        self.base_path = self.base_path_var.get().strip()

    def gstreamer_pipeline(self, sensor_id=0, capture_width=3280, capture_height=2464, display_width=720, display_height=958, framerate=21, flip_method=3):
        """
        GStreamer 파이프라인 생성
        CSI 카메라에서 영상을 캡처, OpenCV에서 사용할 수 있는 형식으로 변환
   
        Args:
            sensor_id (int): 카메라 센서 ID
            capture_width (int): 센서에서 캡처할 원본 너비
            capture_height (int): 센서에서 캡처할 원본 높이
            display_width (int): 출력 영상 너비
            display_height (int): 출력 영상 높이
            framerate (int): 프레임 속도 (fps)
            flip_method (int): 영상 회전 방법
                - 0: 회전 없음
                - 1: 90도 반시계 방향
                - 2: 180도
                - 3: 90도 시계 방향 + 상하 반전
                - 4: 수평 반전
                - 5: 수직 반전
                - 6: 90도 시계 방향
                - 7: 90도 반시계 방향 + 상하 반전
   
        Returns:
            str: GStreamer 파이프라인 문자열
        """
        return (f"nvarguscamerasrc sensor-id={sensor_id} ! video/x-raw(memory:NVMM), width=(int){capture_width}, height=(int){capture_height}, framerate=(fraction){framerate}/1 ! nvvidconv flip-method={flip_method} ! video/x-raw, width=(int){display_width}, height=(int){display_height}, format=(string)BGRx ! videoconvert ! video/x-raw, format=(string)BGR ! appsink")

    def start_preview(self):
        """
        미리보기 스레드 시작
   
        별도 스레드에서 카메라 영상을 지속적으로 읽어와 UI에 표시
        """
        # 데몬 스레드로 생성 (메인 프로그램 종료시 자동 종료)
        self.preview_thread = threading.Thread(target=self._preview_worker, daemon=True)
        self.preview_thread.start()

    def _preview_worker(self):
        """
        미리보기 스레드
   
        카메라에서 계속 프레임 읽어서 self.preview_frame에 저장, UI 업데이트 트리거
        """
        try:
            # GStreamer 파이프라인으로 카메라 열기
            self.video_capture = cv2.VideoCapture(self.gstreamer_pipeline(sensor_id=self.camera_id), cv2.CAP_GSTREAMER)
            
            # 카메라 초기화 대기
            time.sleep(2)
            
            # 카메라 연결 확인
            if not self.video_capture.isOpened():
                self.root.after(0, lambda: self.preview_info.set("카메라 연결 실패"))
                return
            
            # 미리보기 루프
            while self.preview_running:
                # 프레임 읽기
                ret, frame = self.video_capture.read()
                if ret:
                    
                    # 프레임 저장
                    self.preview_frame = frame
                    
                    # UI 업데이트 요청 (메인 스레드에서 실행), after_idle: 유휴 시간에 실행
                    self.root.after_idle(self.update_preview_display)
                    
                    # 프레임 정보 업데이트
                    self.root.after_idle(lambda: self.preview_info.set(f"Live Preview - {frame.shape[1]}x{frame.shape[0]}"))
                else:
                    self.root.after_idle(lambda: self.preview_info.set("프레임 읽기 실패"))
                
                # 60fps 목표
                time.sleep(1/60)
        finally:

            # 카메라 리소스 해제
            if self.video_capture: self.video_capture.release()
            print("Preview thread finished.")

    def update_preview_display(self):
        """
        미리보기 캔버스 업데이트
   
        현재 프레임을 캔버스 크기에 맞게 리사이즈, ROI 영역 녹색 사각형으로 표시
        """
        # 프레임이 없거나 미리보기가 중지되었으면 종료
        if self.preview_frame is None or not self.preview_running: return
        
        # 현재 캔버스 크기 가져오기
        canvas_width = self.preview_canvas.winfo_width()
        canvas_height = self.preview_canvas.winfo_height()
        
        # 캔버스가 아직 렌더링되지 않았으면 종료
        if canvas_width <= 1 or canvas_height <= 1: return

        frame = self.preview_frame
        height, width = frame.shape[:2]

        # 캔버스에 맞게 스케일 계산 (비율 유지)
        scale = min(canvas_width / width, canvas_height / height)
        new_width, new_height = int(width * scale), int(height * scale)
        
        # 프레임 리사이즈
        resized = cv2.resize(frame, (new_width, new_height))

        # ROI 사각형 그리기
        try:
            # ROI 값 가져오기
            xmin, ymin, roi_width, roi_height = int(self.xmin_var.get()), int(self.ymin_var.get()), int(self.width_var.get()), int(self.height_var.get())
            
            # ROI 좌표 변환(스케일에 맞게)
            scaled_xmin, scaled_ymin, scaled_width, scaled_height = int(xmin * scale), int(ymin * scale), int(roi_width * scale), int(roi_height * scale)
            
            # 사각형 그리기
            cv2.rectangle(resized, (scaled_xmin, scaled_ymin), (scaled_xmin + scaled_width, scaled_ymin + scaled_height), (0, 255, 0), 2)
        except (ValueError, tk.TclError): pass # ROI 값이 유효하지 않으면 무시

        # BGR을 RGB로 (OpenCV는 BGR, Tkinter는 RGB 사용)
        rgb_frame = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        
        # PIL Image로
        pil_image = Image.fromarray(rgb_frame)
        
        # PhotoImage로 변환
        self.photo = ImageTk.PhotoImage(image=pil_image)
        
        # 이미지 비우기
        self.preview_canvas.delete("all")
        
        # 이미지 표시
        self.preview_canvas.create_image(canvas_width / 2, canvas_height / 2, anchor=tk.CENTER, image=self.photo)

    def start_camera(self):
        """
        카메라 캡처 시작
   
        1. 입력값 유효성 검증
        2. UI 값들을 인스턴스 변수에 저장
        3. 캡처 스레드 시작
        4. UI 상태 업데이트 (버튼 비활성화 등)
        """
        # 이미 캡처 중이면 무시
        if self.is_capturing: return

        # 입력값 유효성 검증 실패시 종료
        if not self.validate_inputs(): return

        # UI의 현재 값들 인스턴스 변수에 저장
        self.update_variables()

        # 캡처 상태 플래그 설정
        self.is_capturing = True

        # 시작 버튼 비활성화, 정지 버튼 활성화
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)

        # 상태 메시지 최신화
        self.status_var.set("Capturing... (Live)")
        
        # ROI 관련 위젯들 비활성화(캡쳐 중 변경하는거 막을라고)
        for widget in self.roi_widgets:
            widget.config(state=tk.DISABLED)
        
        # 캡처 워커 스레드 시작
        self.capture_thread = threading.Thread(target=self._capture_worker, daemon=True)
        self.capture_thread.start()

    def _capture_worker(self):
        """
        실제 캡처 작업 수행
   
        타이밍에 따라 프레임 캡처, 파일로 저장
        각 구간(phase)별로 다른 간격으로 캡처 수행
        """
        try:
            # 전체 경로: base_path/target/titer/버전번호/
            save_path = os.path.join(self.base_path, self.target, self.titer)
            os.makedirs(save_path, exist_ok=True)
            
            # 기존 버전 폴더들 찾기 (숫자로 된 폴더들)
            existing_folders = [d for d in os.listdir(save_path) if os.path.isdir(os.path.join(save_path, d)) and d.isdigit()]
            
            # 새 버전 번호 결정 (기존 최대값 + 1, 없으면 0)
            new_folder_num = max(map(int, existing_folders)) + 1 if existing_folders else 0
            
            # 버전 폴더 생성
            version_path = os.path.join(save_path, str(new_folder_num))
            os.makedirs(version_path, exist_ok=True)
            print(f"--------- Capture Start: Saving to {version_path} ---------")

            # 캡처 구간(페이즈) 설정
            phases = []
            last_end_point = self.start_delay # 시작 지연 시간
           
            # 각 구간의 시작/종료 시점, 다음 캡처 예정 시간 계산
            for phase_data in self.cap_time:
                start_point = last_end_point # 이전 구간의 끝이 이번 구간의 시작
                phases.append({
                    'start': start_point, # 구간 시작 시점
                    'end': phase_data['end_point'], # 구간 종료 시점
                    'interval': phase_data['interval'], # 캡처 간격
                    'next_scheduled_cap': start_point # 다음 캡처 예정 시간 (처음엔 시작 시점)
                })
                last_end_point = phase_data['end_point']
            
            # 전체 캡처 시간
            total_duration = last_end_point 
            
            # 캡처 시작 시간 기록
            capture_start_time = time.time()
            
            num_phases = len(phases)

            # 캡처 반복문
            while self.is_capturing:
                current_loop_time = time.time()

                # elapsed_time은 시작 시점부터의 경과 시간
                elapsed_time = current_loop_time - capture_start_time

                # 전체 캡처 시간이 지났으면 종료, 0.01초 여유
                if elapsed_time > total_duration + 0.01:
                    break
                
                # 미리보기 프레임이 없으면 대기
                if self.preview_frame is None:
                    time.sleep(0.01)
                    continue
                
                # 현재 시간에 해당하는 구간 찾기 및 캡처
                for i, phase in enumerate(phases):
                    # 마지막 구간인지
                    is_last_phase = (i == num_phases - 1)
                    
                    # 현재 시간이 이 구간에 속하는지
                    in_phase = False
                    if is_last_phase: # 마지막 구간: 시작 <= 현재 <= 종료 (종료 시점 포함)
                        if phase['start'] <= elapsed_time <= phase['end'] + 0.01:
                            in_phase = True
                    else: # 중간 구간: 시작 <= 현재 < 종료 (종료 시점 미포함)
                        if phase['start'] <= elapsed_time < phase['end']:
                            in_phase = True

                    # 현재 시간이 이 구간에 속한다면
                    if in_phase: 

                        # 예정된 캡처 시간이 되었는지 확인
                        if elapsed_time >= phase['next_scheduled_cap']:
                            # 시간이 되었다면
                            # 파일명 생성 (경과시간.png)
                            filename = os.path.join(version_path, f"{elapsed_time:.2f}.png")
                            
                            # 현재 프레임 복사 (원본 보존)
                            frame_to_save = self.preview_frame.copy()

                            # ROI 영역만 잘라내기
                            xmin, ymin, w, h = self.crop.values()
                            save_frame = frame_to_save[ymin:ymin+h, xmin:xmin+w]

                            # PNG 파일로 저장
                            cv2.imwrite(filename, save_frame)
                            print(f"Captured {filename} (Scheduled: {phase['next_scheduled_cap']:.2f}s) in Phase {i+1}")

                            # 다음 캡처 시간 업데이트
                            if phase['interval'] > 0:
                                phase['next_scheduled_cap'] += phase['interval']
                            else:
                                # interval이 0이면 더 이상 캡처하지 않음
                                phase['next_scheduled_cap'] = float('inf')
                        # 루프 종료
                        break

                time.sleep(0.005)
        except Exception as e:
            print(f"An error occurred during capture: {e}")
        finally:
            # 캡처 종료
            print("---------- Capture End ----------")
            # stop_camera 호출
            self.root.after(0, self.stop_camera)

    def stop_camera(self):
        """
        카메라 캡처 중지
   
        1. 캡처 플래그 해제
        2. UI 상태를 원래대로 복원
        3. 비활성화했던 위젯들 재활성화
        """

        # 이미 정지 상태면 무시
        if not self.is_capturing: return

        # 캡처 중지 플래그 설정
        self.is_capturing = False

        # 시작 버튼 활성화, 정지 버튼 비활성화
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)

        # 상태 메시지 Ready로
        self.status_var.set("Ready")

        # ROI 관련 위젯들 재활성화
        for widget in self.roi_widgets:
            widget.config(state=tk.NORMAL)

    def on_mouse_press(self, event):
        """
        ROI 선택 시작, 클릭 위치를 저장
        캔버스 좌표를 실제 프레임 좌표로 변환 위한 오프셋 계산
   
        Args:
            event: 마우스 이벤트 객체 (x, y 좌표 포함)
        """

        # 캡처 중에는 ROI 변경 불가
        if self.is_capturing: return

        # 미리보기가 실행 중이고 프레임이 있을 때만 동작
        if not self.preview_running or self.preview_frame is None: return

        # ROI 선택 시작 플래그 설정
        self.roi_selecting = True

        # 캔버스, 실제 이미지 크기
        canvas_width, canvas_height = self.preview_canvas.winfo_width(), self.preview_canvas.winfo_height()
        height, width = self.preview_frame.shape[:2]
        
        # 이미지가 캔버스에 맞게 스케일링된 비율
        scale = min(canvas_width / width, canvas_height / height)
        new_width, new_height = int(width * scale), int(height * scale)

        # (캔버스 크기 - 스케일된 이미지 크기) / 2 (이미지가 캔버스 중앙에 위치하므로)
        self.x_offset = (canvas_width - new_width) / 2
        self.y_offset = (canvas_height - new_height) / 2

        # ROI 선택 시작점
        self.roi_start = (event.x, event.y)

    def on_mouse_drag(self, event):
        """
        마우스 드래그 중 호출
        드래그 중인 ROI 영역을 빨간색 사각형으로
   
        Args:
            event: 마우스 이벤트 객체 (현재 x, y 좌표 포함)
        """
        # 캡처 중에는 ROI 변경 불가
        if self.is_capturing: return
        # ROI 선택이 시작되었고 시작점이 있을 때
        if self.roi_selecting and self.roi_start:
            # 이전에 그린 임시 ROI 삭제
            # "temp_roi" 태그 달린 모든 도형 삭제
            self.preview_canvas.delete("temp_roi")

            # 새로운 임시 ROI 사각형
            # 시작점부터 현재 마우스 위치까지
            self.preview_canvas.create_rectangle(self.roi_start[0], self.roi_start[1], event.x, event.y, outline="red", width=2, tags="temp_roi")

    def on_mouse_release(self, event):
        """
        마우스 왼쪽 버튼 릴리즈 시 호출
   
        ROI 선택 완료, 캔버스 좌표를 실제 프레임 좌표로 변환, ROI 설정값 업데이트
   
        Args:
            event: 마우스 이벤트 객체 (릴리즈 위치 x, y 좌표 포함)
        """

        # 캡처 중에는 ROI 변경 불가
        if self.is_capturing: return

        # ROI 선택이 진행 중이고 필요한 정보가 없다면 리턴
        if not (self.roi_selecting and self.roi_start and self.preview_frame is not None): return
        
        # 좌표 변환 준비
        canvas_width, canvas_height = self.preview_canvas.winfo_width(), self.preview_canvas.winfo_height()
        height, width = self.preview_frame.shape[:2]
        
        # 캔버스에서 프레임으로의 스케일 계산
        scale = min(canvas_width / width, canvas_height / height)
        
        # 캔버스 좌표에서 ROI 영역 계산(시작점과 끝점 중 작은 값이 좌상단, 큰 값이 우하단)
        start_x_canvas, start_y_canvas = min(self.roi_start[0], event.x), min(self.roi_start[1], event.y)
        end_x_canvas, end_y_canvas = max(self.roi_start[0], event.x), max(self.roi_start[1], event.y)
        
        # 캔버스 좌표를 원본 프레임 좌표로(오프셋 제거 및 원본 크기로 역변환)
        start_x_orig, start_y_orig = int((start_x_canvas - self.x_offset) / scale), int((start_y_canvas - self.y_offset) / scale)
        end_x_orig, end_y_orig = int((end_x_canvas - self.x_offset) / scale), int((end_y_canvas - self.y_offset) / scale)
        
        # 프레임 경계 체크(좌표가 프레임 범위를 벗어나지 않도록)
        xmin, ymin, xmax, ymax = max(0, start_x_orig), max(0, start_y_orig), min(width, end_x_orig), min(height, end_y_orig)
        
        # UI 업데이트
        self.xmin_var.set(str(xmin))
        self.ymin_var.set(str(ymin))
        self.width_var.set(str(xmax - xmin))
        self.height_var.set(str(ymax - ymin))

        # temp_roi 태그 떼기
        self.preview_canvas.delete("temp_roi")

        # # ROI 선택 종료
        self.roi_selecting = False

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

    def on_closing(self):
        """
        윈도우 종료 시 호출

        1. 모든 스레드 종료
        2. 카메라 리소스 해제
        3. 윈도우 디스트로이
        """
        print("Closing application...")
        self.preview_running = False
        self.is_capturing = False

        if self.preview_thread and self.preview_thread.is_alive(): self.preview_thread.join(timeout=2)
        if self.capture_thread and self.capture_thread.is_alive(): self.capture_thread.join(timeout=2)
        self.root.destroy() 

if __name__ == '__main__':
    app = CameraUI(camera_id=1)
    app.run()
