import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import cv2
import numpy as np
from PIL import Image, ImageTk
import subprocess
import sys
import time

class CameraUI:
    def __init__(self, camera_id=1):
        self.camera_id = camera_id
        self.root = tk.Tk()
        self.root.title(f"Camera {camera_id} Control Panel")
        self.root.geometry("800x700")
        self.root.resizable(True, True)
        self.root.minsize(750, 650)

        # 기본값 설정
        self.crop = {'xmin': 240, 'ymin': 100, 'width': 260, 'height': 1040}
        self.cap_time = {'start': 0, 'interval_1': 1, 'middle': 900, 'interval_2': 1, 'end': 900}
        self.target = 'TRP'
        self.titer = 'Test_5.01'
        self.base_path = './sample'

        # ROI 선택 관련 변수
        self.roi_selecting = False
        self.roi_start = None

        # --- Correctly placed code block ---
        self.preview_frame = None
        self.video_capture = None
        self.preview_running = True
        self.capture_process = None

        self.setup_ui()
        self.start_preview()
        # --- End of corrected block ---

    def setup_ui(self):
        # 메인 컨테이너를 좌우로 분할
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 왼쪽: 설정 패널
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)

        # 오른쪽: 카메라 미리보기
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)

        self.setup_controls(left_frame)
        self.setup_preview(right_frame)

    def setup_controls(self, parent):
        # 스크롤 가능한 설정 영역
        canvas = tk.Canvas(parent, width=350)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # 메인 설정 프레임
        main_frame = ttk.Frame(scrollable_frame, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 제목
        title_label = ttk.Label(main_frame, text=f"Camera {self.camera_id} Settings",
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 20))

        # 저장 경로 설정 섹션
        self.setup_path_settings(main_frame)

        # ROI 설정 섹션
        self.setup_roi_settings(main_frame)

        # 타이밍 설정 섹션
        self.setup_timing_settings(main_frame)

        # 상태 및 시작 버튼
        self.setup_status_and_button(main_frame)

        # 스크롤바와 캔버스 배치
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 마우스 휠 스크롤 지원
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def setup_path_settings(self, parent):
        path_frame = ttk.LabelFrame(parent, text="Save Path Settings", padding="10")
        path_frame.pack(fill=tk.X, pady=(0, 10))

        # 베이스 경로 선택
        base_path_frame = ttk.Frame(path_frame)
        base_path_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(base_path_frame, text="Base Path:").pack(side=tk.LEFT)
        self.base_path_var = tk.StringVar(value=self.base_path)
        base_path_entry = ttk.Entry(base_path_frame, textvariable=self.base_path_var, width=20)
        base_path_entry.pack(side=tk.LEFT, padx=(5, 5), fill=tk.X, expand=True)

        browse_button = ttk.Button(base_path_frame, text="Browse", command=self.browse_base_path)
        browse_button.pack(side=tk.RIGHT)

        # Target과 Titer 입력
        target_frame = ttk.Frame(path_frame)
        target_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Label(target_frame, text="Target:").grid(row=0, column=0, sticky=tk.W)
        self.target_var = tk.StringVar(value=self.target)
        ttk.Entry(target_frame, textvariable=self.target_var, width=12).grid(row=0, column=1, padx=(5, 10), sticky=(tk.W, tk.E))

        ttk.Label(target_frame, text="Titer:").grid(row=0, column=2, sticky=tk.W)
        self.titer_var = tk.StringVar(value=self.titer)
        ttk.Entry(target_frame, textvariable=self.titer_var, width=12).grid(row=0, column=3, padx=5, sticky=(tk.W, tk.E))

        target_frame.columnconfigure(1, weight=1)
        target_frame.columnconfigure(3, weight=1)

        # 경로 미리보기
        self.path_preview = tk.StringVar(value=f"{self.base_path}/{self.target}/{self.titer}/")
        ttk.Label(path_frame, text="Full Save Path:").pack(anchor=tk.W, pady=(10, 0))
        path_preview_label = ttk.Label(path_frame, textvariable=self.path_preview,
                                      foreground="blue", font=("Arial", 8), relief="sunken", padding="3")
        path_preview_label.pack(fill=tk.X, pady=(5, 0))

        # 변수 바인딩
        self.base_path_var.trace('w', self.update_path_preview)
        self.target_var.trace('w', self.update_path_preview)
        self.titer_var.trace('w', self.update_path_preview)

    def setup_roi_settings(self, parent):
        roi_frame = ttk.LabelFrame(parent, text="ROI Settings", padding="10")
        roi_frame.pack(fill=tk.X, pady=(0, 10))

        # ROI 입력 필드들
        roi_grid = ttk.Frame(roi_frame)
        roi_grid.pack(fill=tk.X)

        ttk.Label(roi_grid, text="X Min:").grid(row=0, column=0, sticky=tk.W)
        self.xmin_var = tk.StringVar(value=str(self.crop['xmin']))
        self.xmin_var.trace('w', self.update_roi_preview)
        ttk.Entry(roi_grid, textvariable=self.xmin_var, width=8).grid(row=0, column=1, padx=(5, 10))

        ttk.Label(roi_grid, text="Y Min:").grid(row=0, column=2, sticky=tk.W)
        self.ymin_var = tk.StringVar(value=str(self.crop['ymin']))
        self.ymin_var.trace('w', self.update_roi_preview)
        ttk.Entry(roi_grid, textvariable=self.ymin_var, width=8).grid(row=0, column=3, padx=5)

        ttk.Label(roi_grid, text="Width:").grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        self.width_var = tk.StringVar(value=str(self.crop['width']))
        self.width_var.trace('w', self.update_roi_preview)
        ttk.Entry(roi_grid, textvariable=self.width_var, width=8).grid(row=1, column=1, padx=(5, 10), pady=(8, 0))

        ttk.Label(roi_grid, text="Height:").grid(row=1, column=2, sticky=tk.W, pady=(8, 0))
        self.height_var = tk.StringVar(value=str(self.crop['height']))
        self.height_var.trace('w', self.update_roi_preview)
        ttk.Entry(roi_grid, textvariable=self.height_var, width=8).grid(row=1, column=3, padx=5, pady=(8, 0))

        # ROI 조작 버튼들
        button_frame = ttk.Frame(roi_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text="Reset ROI", command=self.reset_roi).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="Full Size", command=self.set_full_roi).pack(side=tk.LEFT, padx=(5, 0))

        # 사용법 안내
        help_label = ttk.Label(roi_frame, text="Tip: 오른쪽 미리보기에서 마우스로 드래그하여 ROI 선택 가능",
                              font=("Arial", 8), foreground="gray")
        help_label.pack(pady=(5, 0))

    def setup_timing_settings(self, parent):
        timing_frame = ttk.LabelFrame(parent, text="Capture Timing (seconds)", padding="10")
        timing_frame.pack(fill=tk.X, pady=(0, 10))

        timing_grid = ttk.Frame(timing_frame)
        timing_grid.pack(fill=tk.X)

        ttk.Label(timing_grid, text="Start:").grid(row=0, column=0, sticky=tk.W)
        self.start_var = tk.StringVar(value=str(self.cap_time['start']))
        ttk.Entry(timing_grid, textvariable=self.start_var, width=6).grid(row=0, column=1, padx=5)

        ttk.Label(timing_grid, text="Int1:").grid(row=0, column=2, sticky=tk.W, padx=(10, 0))
        self.interval1_var = tk.StringVar(value=str(self.cap_time['interval_1']))
        ttk.Entry(timing_grid, textvariable=self.interval1_var, width=6).grid(row=0, column=3, padx=5)

        ttk.Label(timing_grid, text="Middle:").grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        self.middle_var = tk.StringVar(value=str(self.cap_time['middle']))
        ttk.Entry(timing_grid, textvariable=self.middle_var, width=6).grid(row=1, column=1, padx=5, pady=(8, 0))

        ttk.Label(timing_grid, text="Int2:").grid(row=1, column=2, sticky=tk.W, padx=(10, 0), pady=(8, 0))
        self.interval2_var = tk.StringVar(value=str(self.cap_time['interval_2']))
        ttk.Entry(timing_grid, textvariable=self.interval2_var, width=6).grid(row=1, column=3, padx=5, pady=(8, 0))

        ttk.Label(timing_grid, text="End:").grid(row=2, column=0, sticky=tk.W, pady=(8, 0))
        self.end_var = tk.StringVar(value=str(self.cap_time['end']))
        ttk.Entry(timing_grid, textvariable=self.end_var, width=6).grid(row=2, column=1, padx=5, pady=(8, 0))

    def setup_status_and_button(self, parent):
        # 상태 표시
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, foreground="green")
        status_label.pack(side=tk.LEFT, padx=(10, 0))

        # 시작 버튼
        self.start_button = ttk.Button(parent, text="Start Camera", command=self.start_camera)
        self.start_button.pack(pady=15, fill=tk.X)

        # 중지 버튼 (처음에는 비활성화)
        self.stop_button = ttk.Button(parent, text="Stop Camera", command=self.stop_camera, state=tk.DISABLED)
        self.stop_button.pack(pady=(5, 0), fill=tk.X)

    def setup_preview(self, parent):
        preview_frame = ttk.LabelFrame(parent, text="Camera Preview & ROI Selection", padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True)

        # 미리보기 캔버스
        self.preview_canvas = tk.Canvas(preview_frame, bg='black', width=400, height=350)
        self.preview_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 마우스 이벤트 바인딩
        self.preview_canvas.bind("<Button-1>", self.on_mouse_press)
        self.preview_canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.preview_canvas.bind("<ButtonRelease-1>", self.on_mouse_release)

        # 상태 정보
        info_frame = ttk.Frame(preview_frame)
        info_frame.pack(fill=tk.X, pady=(5, 0))

        self.preview_info = tk.StringVar(value="미리보기 로딩중...")
        ttk.Label(info_frame, textvariable=self.preview_info, font=("Arial", 9)).pack()

    def update_roi_preview(self, *args):
        """ROI 값 변경시 미리보기 업데이트"""
        if self.preview_running:
            # 다음 프레임에서 업데이트하도록 예약
            self.root.after_idle(self.update_preview_display)

    def reset_roi(self):
        """ROI 초기값으로 리셋"""
        self.xmin_var.set("240")
        self.ymin_var.set("100")
        self.width_var.set("260")
        self.height_var.set("1040")

    def set_full_roi(self):
        """전체 화면으로 ROI 설정"""
        self.xmin_var.set("0")
        self.ymin_var.set("0")
        self.width_var.set("720")
        self.height_var.set("1280")

    def browse_base_path(self):
        """베이스 경로 선택"""
        selected_path = filedialog.askdirectory(
            title="Select Base Save Directory",
            initialdir=self.base_path_var.get() or os.path.expanduser("~")
        )

        if selected_path:
            self.base_path_var.set(selected_path)

    def update_path_preview(self, *args):
        base = self.base_path_var.get() or './sample'
        target = self.target_var.get() or 'TRP'
        titer = self.titer_var.get() or 'Test_5.01'
        path = f"{base}/{target}/{titer}/"
        self.path_preview.set(path)

    def validate_inputs(self):
        try:
            # ROI 검증
            xmin = int(self.xmin_var.get())
            ymin = int(self.ymin_var.get())
            width = int(self.width_var.get())
            height = int(self.height_var.get())

            if (xmin + width) > 720 or (ymin + height) > 1280:
                raise ValueError("ROI exceeds image bounds (720x1280)")

            if xmin < 0 or ymin < 0 or width <= 0 or height <= 0:
                raise ValueError("ROI values must be positive")

            # 타이밍 검증
            start = float(self.start_var.get())
            interval1 = float(self.interval1_var.get())
            middle = float(self.middle_var.get())
            interval2 = float(self.interval2_var.get())
            end = float(self.end_var.get())

            if interval1 < 0.25:
                raise ValueError("Interval 1 minimum value is 0.25 seconds")

            if not all(v >= 0 for v in [start, interval1, middle, interval2, end]):
                raise ValueError("All timing values must be non-negative")

            # 경로 검증
            if not self.target_var.get().strip():
                raise ValueError("Target name cannot be empty")
            if not self.titer_var.get().strip():
                raise ValueError("Titer name cannot be empty")

            return True

        except ValueError as e:
            messagebox.showerror("Input Error", str(e))
            return False

    def update_variables(self):
        # ROI 업데이트
        self.crop['xmin'] = int(self.xmin_var.get())
        self.crop['ymin'] = int(self.ymin_var.get())
        self.crop['width'] = int(self.width_var.get())
        self.crop['height'] = int(self.height_var.get())

        # 타이밍 업데이트
        self.cap_time['start'] = float(self.start_var.get())
        self.cap_time['interval_1'] = float(self.interval1_var.get())
        self.cap_time['middle'] = float(self.middle_var.get())
        self.cap_time['interval_2'] = float(self.interval2_var.get())
        self.cap_time['end'] = float(self.end_var.get())

        # 경로 업데이트
        self.target = self.target_var.get().strip()
        self.titer = self.titer_var.get().strip()
        self.base_path = self.base_path_var.get().strip() or './sample'

    def gstreamer_pipeline(self, sensor_id=0, capture_width=1280, capture_height=720,
                          display_width=720, display_height=1280, framerate=30, flip_method=3):
        return (
            "nvarguscamerasrc sensor-id=%d ! "
            "video/x-raw(memory:NVMM), width=(int)%d, height=(int)%d, framerate=(fraction)%d/1 ! "
            "nvvidconv flip-method=%d ! "
            "video/x-raw, width=(int)%d, height=(int)%d, format=(string)BGRx ! "
            "videoconvert ! "
            "video/x-raw, format=(string)BGR ! appsink"
            % (sensor_id, capture_width, capture_height, framerate, flip_method, display_width, display_height)
        )

    def start_preview(self):
        """카메라 미리보기 시작"""
        def update_preview():
            if not self.preview_running:
                return

            if self.video_capture is None:
                try:
                    self.video_capture = cv2.VideoCapture(
                        self.gstreamer_pipeline(sensor_id=self.camera_id), cv2.CAP_GSTREAMER
                    )
                    time.sleep(0.5)  # 카메라 초기화 대기
                except Exception:
                    self.preview_info.set("카메라 연결 실패")
                    if self.preview_running:
                        self.root.after(2000, update_preview)
                    return

            if self.video_capture and self.video_capture.isOpened():
                ret, frame = self.video_capture.read()
                if ret:
                    self.preview_frame = frame
                    self.update_preview_display()
                    self.preview_info.set(f"Live Preview - {frame.shape[1]}x{frame.shape[0]}")
                else:
                    self.preview_info.set("프레임 읽기 실패")
            else:
                self.preview_info.set("카메라 미연결")

            if self.preview_running:
                self.root.after(100, update_preview)

        self.preview_running = True
        threading.Thread(target=update_preview, daemon=True).start()

    def stop_preview(self):
        """미리보기 중지"""
        self.preview_running = False
        if self.video_capture:
            self.video_capture.release()
            self.video_capture = None
        self.preview_canvas.delete("all")
        self.preview_info.set("카메라 중지됨")

    def create_capture_script(self):
        """별도 캡처 스크립트 생성"""
        script_content = f"""
import sys
sys.path.append('.')
# Assuming simple_camera module and capture_time_series_image function exist
from simple_camera import capture_time_series_image

camera = {self.camera_id}
crop = {self.crop}
cap_time = {self.cap_time}
target = '{self.target}'
titer = '{self.titer}'

if __name__ == '__main__':
    capture_time_series_image(camera, crop, cap_time, target, titer)
"""
        script_name = f"capture_script_{self.camera_id}.py"
        with open(script_name, 'w') as f:
            f.write(script_content)
        return script_name

    def start_camera(self):
        if not self.validate_inputs():
            return

        self.update_variables()
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.stop_preview()

        script_name = self.create_capture_script()

        def run_capture():
            try:
                self.root.after(0, lambda: self.status_var.set("Camera running..."))
                self.capture_process = subprocess.Popen([sys.executable, script_name])
                self.capture_process.wait()
                self.root.after(0, lambda: self.status_var.set("Camera stopped"))
            except Exception as e:
                self.root.after(0, lambda: self.status_var.set(f"Error: {str(e)}"))
                self.root.after(0, lambda: messagebox.showerror("Camera Error", str(e)))
            finally:
                self.root.after(0, self.cleanup_after_capture)
                if os.path.exists(script_name):
                    os.remove(script_name)

        threading.Thread(target=run_capture, daemon=True).start()

    def stop_camera(self):
        """캡처 중지"""
        if self.capture_process:
            self.capture_process.terminate()
            self.capture_process = None
        self.cleanup_after_capture()

    def cleanup_after_capture(self):
        """캡처 종료 후 정리"""
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.root.after(1000, self.start_preview)

    def update_preview_display(self):
        """미리보기 디스플레이 업데이트"""
        if self.preview_frame is None or not self.preview_running:
            return

        canvas_width = self.preview_canvas.winfo_width()
        canvas_height = self.preview_canvas.winfo_height()
        if canvas_width <= 1 or canvas_height <= 1:
            self.root.after(100, self.update_preview_display)
            return

        height, width = self.preview_frame.shape[:2]
        scale = min((canvas_width - 20) / width, (canvas_height - 20) / height, 0.8)
        new_width = int(width * scale)
        new_height = int(height * scale)

        resized = cv2.resize(self.preview_frame, (new_width, new_height))

        try:
            xmin = int(self.xmin_var.get())
            ymin = int(self.ymin_var.get())
            roi_width = int(self.width_var.get())
            roi_height = int(self.height_var.get())

            scaled_xmin = int(xmin * scale)
            scaled_ymin = int(ymin * scale)
            scaled_width = int(roi_width * scale)
            scaled_height = int(roi_height * scale)

            cv2.rectangle(resized, (scaled_xmin, scaled_ymin), (scaled_xmin + scaled_width, scaled_ymin + scaled_height), (0, 255, 0), 2)
            overlay = resized.copy()
            cv2.rectangle(overlay, (scaled_xmin, scaled_ymin), (scaled_xmin + scaled_width, scaled_ymin + scaled_height), (0, 255, 0), -1)
            cv2.addWeighted(resized, 0.8, overlay, 0.2, 0, resized)
        except ValueError:
            pass

        rgb_frame = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_frame)
        photo = ImageTk.PhotoImage(image=pil_image)

        self.preview_canvas.delete("all")
        x_offset = (canvas_width - new_width) // 2
        y_offset = (canvas_height - new_height) // 2
        self.preview_canvas.create_image(x_offset, y_offset, anchor=tk.NW, image=photo)
        self.preview_canvas.image = photo

    def on_mouse_press(self, event):
        if not self.preview_running: return
        self.roi_selecting = True
        self.roi_start = (event.x, event.y)

    def on_mouse_drag(self, event):
        if self.roi_selecting and self.roi_start and self.preview_running:
            self.preview_canvas.delete("temp_roi")
            self.preview_canvas.create_rectangle(self.roi_start[0], self.roi_start[1], event.x, event.y, outline="red", width=2, tags="temp_roi")

    def on_mouse_release(self, event):
        if not (self.preview_running and self.roi_selecting and self.roi_start and self.preview_frame is not None):
            return

        canvas_width = self.preview_canvas.winfo_width()
        canvas_height = self.preview_canvas.winfo_height()
        height, width = self.preview_frame.shape[:2]
        scale = min((canvas_width - 20) / width, (canvas_height - 20) / height, 0.8)
        new_width = int(width * scale)
        new_height = int(height * scale)
        x_offset = (canvas_width - new_width) // 2
        y_offset = (canvas_height - new_height) // 2

        start_x = max(0, int((self.roi_start[0] - x_offset) / scale))
        start_y = max(0, int((self.roi_start[1] - y_offset) / scale))
        end_x = max(0, int((event.x - x_offset) / scale))
        end_y = max(0, int((event.y - y_offset) / scale))

        xmin, ymin = min(start_x, end_x), min(start_y, end_y)
        xmax, ymax = max(start_x, end_x), max(start_y, end_y)

        xmin = max(0, min(xmin, width - 10))
        ymin = max(0, min(ymin, height - 10))
        xmax = max(xmin + 10, min(xmax, width))
        ymax = max(ymin + 10, min(ymax, height))

        self.xmin_var.set(str(xmin))
        self.ymin_var.set(str(ymin))
        self.width_var.set(str(xmax - xmin))
        self.height_var.set(str(ymax - ymin))

        self.preview_canvas.delete("temp_roi")
        self.roi_selecting = False
        self.roi_start = None

    def __del__(self):
        self.preview_running = False
        if self.video_capture:
            self.video_capture.release()

    def run(self):
        try:
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            self.root.mainloop()
        finally:
            self.cleanup()

    def on_closing(self):
        self.cleanup()
        self.root.destroy()

    def cleanup(self):
        self.preview_running = False
        if self.video_capture:
            self.video_capture.release()
        if self.capture_process and self.capture_process.poll() is None:
            self.capture_process.terminate()

if __name__ == '__main__':
    app = CameraUI(camera_id=1)
    app.run()
