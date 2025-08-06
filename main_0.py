import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
from simple_camera import capture_time_series_image

class CameraUI:
    def __init__(self, camera_id=0):
        self.camera_id = camera_id
        self.root = tk.Tk()
        self.root.title(f"Camera {camera_id} Control Panel")
        self.root.geometry("450x650")
        self.root.resizable(True, True)
        self.root.minsize(400, 600)
        
        # 기본값 설정
        self.crop = {'xmin': 240, 'ymin': 100, 'width': 260, 'height': 1040}
        self.cap_time = {'start': 0, 'interval_1': 1, 'middle': 900, 'interval_2': 1, 'end': 900}
        self.target = 'TRP'
        self.titer = 'Test_5.01'
        self.base_path = './sample'  # 기본 베이스 경로
        
        self.setup_ui()
        
    def setup_ui(self):
        # 스크롤 가능한 메인 컨테이너 생성
        main_canvas = tk.Canvas(self.root)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=main_canvas.yview)
        scrollable_frame = ttk.Frame(main_canvas)
        
        # 스크롤 영역 설정
        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )
        
        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)
        
        # 메인 프레임
        main_frame = ttk.Frame(scrollable_frame, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 제목
        title_label = ttk.Label(main_frame, text=f"Camera {self.camera_id} Settings", 
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 20))
        
        # 저장 경로 설정 섹션
        path_frame = ttk.LabelFrame(main_frame, text="Save Path Settings", padding="10")
        path_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 베이스 경로 선택
        base_path_frame = ttk.Frame(path_frame)
        base_path_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(base_path_frame, text="Base Path:").pack(side=tk.LEFT)
        self.base_path_var = tk.StringVar(value=self.base_path)
        base_path_entry = ttk.Entry(base_path_frame, textvariable=self.base_path_var, width=25)
        base_path_entry.pack(side=tk.LEFT, padx=(5, 5), fill=tk.X, expand=True)
        
        browse_button = ttk.Button(base_path_frame, text="Browse", command=self.browse_base_path)
        browse_button.pack(side=tk.RIGHT)
        
        # Target과 Titer 입력
        target_frame = ttk.Frame(path_frame)
        target_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(target_frame, text="Target:").grid(row=0, column=0, sticky=tk.W)
        self.target_var = tk.StringVar(value=self.target)
        ttk.Entry(target_frame, textvariable=self.target_var, width=15).grid(row=0, column=1, padx=(5, 15), sticky=(tk.W, tk.E))
        
        ttk.Label(target_frame, text="Titer:").grid(row=0, column=2, sticky=tk.W)
        self.titer_var = tk.StringVar(value=self.titer)
        ttk.Entry(target_frame, textvariable=self.titer_var, width=15).grid(row=0, column=3, padx=5, sticky=(tk.W, tk.E))
        
        target_frame.columnconfigure(1, weight=1)
        target_frame.columnconfigure(3, weight=1)
        
        # 경로 미리보기
        self.path_preview = tk.StringVar(value=f"{self.base_path}/{self.target}/{self.titer}/")
        ttk.Label(path_frame, text="Full Save Path:").pack(anchor=tk.W, pady=(10, 0))
        path_preview_label = ttk.Label(path_frame, textvariable=self.path_preview, 
                                      foreground="blue", font=("Arial", 9), relief="sunken", padding="5")
        path_preview_label.pack(fill=tk.X, pady=(5, 0))
        
        # ROI 설정 섹션
        roi_frame = ttk.LabelFrame(main_frame, text="ROI Settings", padding="10")
        roi_frame.pack(fill=tk.X, pady=(0, 10))
        
        # ROI 입력 필드들
        roi_grid = ttk.Frame(roi_frame)
        roi_grid.pack(fill=tk.X)
        
        ttk.Label(roi_grid, text="X Min:").grid(row=0, column=0, sticky=tk.W)
        self.xmin_var = tk.StringVar(value=str(self.crop['xmin']))
        ttk.Entry(roi_grid, textvariable=self.xmin_var, width=10).grid(row=0, column=1, padx=(5, 15))
        
        ttk.Label(roi_grid, text="Y Min:").grid(row=0, column=2, sticky=tk.W)
        self.ymin_var = tk.StringVar(value=str(self.crop['ymin']))
        ttk.Entry(roi_grid, textvariable=self.ymin_var, width=10).grid(row=0, column=3, padx=5)
        
        ttk.Label(roi_grid, text="Width:").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        self.width_var = tk.StringVar(value=str(self.crop['width']))
        ttk.Entry(roi_grid, textvariable=self.width_var, width=10).grid(row=1, column=1, padx=(5, 15), pady=(10, 0))
        
        ttk.Label(roi_grid, text="Height:").grid(row=1, column=2, sticky=tk.W, pady=(10, 0))
        self.height_var = tk.StringVar(value=str(self.crop['height']))
        ttk.Entry(roi_grid, textvariable=self.height_var, width=10).grid(row=1, column=3, padx=5, pady=(10, 0))
        
        # 타이밍 설정 섹션
        timing_frame = ttk.LabelFrame(main_frame, text="Capture Timing (seconds)", padding="10")
        timing_frame.pack(fill=tk.X, pady=(0, 10))
        
        timing_grid = ttk.Frame(timing_frame)
        timing_grid.pack(fill=tk.X)
        
        ttk.Label(timing_grid, text="Start Time:").grid(row=0, column=0, sticky=tk.W)
        self.start_var = tk.StringVar(value=str(self.cap_time['start']))
        ttk.Entry(timing_grid, textvariable=self.start_var, width=8).grid(row=0, column=1, padx=5)
        
        ttk.Label(timing_grid, text="Interval 1:").grid(row=0, column=2, sticky=tk.W, padx=(15, 0))
        self.interval1_var = tk.StringVar(value=str(self.cap_time['interval_1']))
        ttk.Entry(timing_grid, textvariable=self.interval1_var, width=8).grid(row=0, column=3, padx=5)
        
        ttk.Label(timing_grid, text="Middle Time:").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        self.middle_var = tk.StringVar(value=str(self.cap_time['middle']))
        ttk.Entry(timing_grid, textvariable=self.middle_var, width=8).grid(row=1, column=1, padx=5, pady=(10, 0))
        
        ttk.Label(timing_grid, text="Interval 2:").grid(row=1, column=2, sticky=tk.W, padx=(15, 0), pady=(10, 0))
        self.interval2_var = tk.StringVar(value=str(self.cap_time['interval_2']))
        ttk.Entry(timing_grid, textvariable=self.interval2_var, width=8).grid(row=1, column=3, padx=5, pady=(10, 0))
        
        ttk.Label(timing_grid, text="End Time:").grid(row=2, column=0, sticky=tk.W, pady=(10, 0))
        self.end_var = tk.StringVar(value=str(self.cap_time['end']))
        ttk.Entry(timing_grid, textvariable=self.end_var, width=8).grid(row=2, column=1, padx=5, pady=(10, 0))
        
        # 상태 표시
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, foreground="green")
        status_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # 시작 버튼
        start_button = ttk.Button(main_frame, text="Start Camera", command=self.start_camera)
        start_button.pack(pady=20, fill=tk.X)
        
        # 스크롤바와 캔버스 배치
        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 마우스 휠 스크롤 지원
        def _on_mousewheel(event):
            main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _bind_to_mousewheel(event):
            main_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _unbind_from_mousewheel(event):
            main_canvas.unbind_all("<MouseWheel>")
        
        main_canvas.bind('<Enter>', _bind_to_mousewheel)
        main_canvas.bind('<Leave>', _unbind_from_mousewheel)
        
        # 변수 바인딩 (경로 미리보기 업데이트용)
        self.base_path_var.trace('w', self.update_path_preview)
        self.target_var.trace('w', self.update_path_preview)
        self.titer_var.trace('w', self.update_path_preview)
        
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
        
    def start_camera(self):
        if not self.validate_inputs():
            return
            
        self.update_variables()
        
        # 베이스 경로를 포함한 전체 경로로 저장
        full_save_path = os.path.join(self.base_path_var.get(), self.target, self.titer)
        self.status_var.set("Starting camera...")
        
        # 별도 스레드에서 카메라 실행
        def run_camera():
            try:
                self.root.after(0, lambda: self.status_var.set("Camera running..."))
                capture_time_series_image(self.camera_id, self.crop, self.cap_time, self.target, self.titer)
                self.root.after(0, lambda: self.status_var.set("Camera stopped"))
            except Exception as e:
                self.root.after(0, lambda: self.status_var.set(f"Error: {str(e)}"))
                self.root.after(0, lambda: messagebox.showerror("Camera Error", str(e)))
        
        camera_thread = threading.Thread(target=run_camera, daemon=True)
        camera_thread.start()
        
    def run(self):
        self.root.mainloop()

if __name__ == '__main__':
    app = CameraUI(camera_id=0)
    app.run()
