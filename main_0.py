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
    def __init__(self, camera_id=0):
        self.camera_id = camera_id
        self.root = tk.Tk()
        self.root.title(f"Camera {camera_id} Control Panel")
        self.root.geometry("800x700")
        self.root.resizable(True, True)
        self.root.minsize(750, 650)

        # 기본값 설정
        self.crop = {'xmin': 240, 'ymin': 100, 'width': 260, 'height': 1040}
        self.cap_time = {'start': 0, 'interval_1': 1, 'middle': 900, 'interval_2': 1, 'end': 900}
        self.target = 'target'
        self.titer = 'titer'
        self.base_path = './sample'

        # ROI 선택 관련 변수
        self.roi_selecting = False
        self.roi_start = None

        # 스레드 및 상태 관리 변수
        self.preview_frame = None
        self.video_capture = None
        self.preview_running = True
        self.is_capturing = False
        self.capture_thread = None
        self.preview_thread = None

        self.setup_ui()
        self.start_preview()

    def setup_ui(self):
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)
        self.setup_controls(left_frame)
        self.setup_preview(right_frame)

    def setup_controls(self, parent):
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
        target_frame.columnconfigure(1, weight=1)
        target_frame.columnconfigure(3, weight=1)
        self.path_preview = tk.StringVar(value=f"{self.base_path}/{self.target}/{self.titer}/")
        ttk.Label(path_frame, text="Full Save Path:").pack(anchor=tk.W, pady=(10, 0))
        path_preview_label = ttk.Label(path_frame, textvariable=self.path_preview, foreground="blue", font=("Arial", 8), relief="sunken", padding="3")
        path_preview_label.pack(fill=tk.X, pady=(5, 0))
        self.base_path_var.trace('w', self.update_path_preview)
        self.target_var.trace('w', self.update_path_preview)
        self.titer_var.trace('w', self.update_path_preview)

    def setup_roi_settings(self, parent):
        roi_frame = ttk.LabelFrame(parent, text="ROI Settings", padding="10")
        roi_frame.pack(fill=tk.X, pady=(0, 10))
        roi_grid = ttk.Frame(roi_frame)
        roi_grid.pack(fill=tk.X)
        ttk.Label(roi_grid, text="X Min:").grid(row=0, column=0, sticky=tk.W)
        self.xmin_var = tk.StringVar(value=str(self.crop['xmin']))
        ttk.Entry(roi_grid, textvariable=self.xmin_var, width=8).grid(row=0, column=1, padx=(5, 10))
        ttk.Label(roi_grid, text="Y Min:").grid(row=0, column=2, sticky=tk.W)
        self.ymin_var = tk.StringVar(value=str(self.crop['ymin']))
        ttk.Entry(roi_grid, textvariable=self.ymin_var, width=8).grid(row=0, column=3, padx=5)
        ttk.Label(roi_grid, text="Width:").grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        self.width_var = tk.StringVar(value=str(self.crop['width']))
        ttk.Entry(roi_grid, textvariable=self.width_var, width=8).grid(row=1, column=1, padx=(5, 10), pady=(8, 0))
        ttk.Label(roi_grid, text="Height:").grid(row=1, column=2, sticky=tk.W, pady=(8, 0))
        self.height_var = tk.StringVar(value=str(self.crop['height']))
        ttk.Entry(roi_grid, textvariable=self.height_var, width=8).grid(row=1, column=3, padx=5, pady=(8, 0))
        button_frame = ttk.Frame(roi_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(button_frame, text="Reset ROI", command=self.reset_roi).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="Full Size", command=self.set_full_roi).pack(side=tk.LEFT, padx=(5, 0))
        help_label = ttk.Label(roi_frame, text="Tip: 오른쪽 미리보기에서 마우스로 드래그하여 ROI 선택 가능", font=("Arial", 8), foreground="gray")
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
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, foreground="green")
        status_label.pack(side=tk.LEFT, padx=(10, 0))
        self.start_button = ttk.Button(parent, text="Start Capture", command=self.start_camera)
        self.start_button.pack(pady=15, fill=tk.X)
        self.stop_button = ttk.Button(parent, text="Stop Capture", command=self.stop_camera, state=tk.DISABLED)
        self.stop_button.pack(pady=(5, 0), fill=tk.X)

    def setup_preview(self, parent):
        preview_frame = ttk.LabelFrame(parent, text="Camera Preview & ROI Selection", padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True)
        self.preview_canvas = tk.Canvas(preview_frame, bg='black', width=400, height=350)
        self.preview_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.preview_canvas.bind("<Button-1>", self.on_mouse_press)
        self.preview_canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.preview_canvas.bind("<ButtonRelease-1>", self.on_mouse_release)
        info_frame = ttk.Frame(preview_frame)
        info_frame.pack(fill=tk.X, pady=(5, 0))
        self.preview_info = tk.StringVar(value="미리보기 로딩중...")
        ttk.Label(info_frame, textvariable=self.preview_info, font=("Arial", 9)).pack()
    
    def reset_roi(self):
        self.xmin_var.set("240")
        self.ymin_var.set("100")
        self.width_var.set("260")
        self.height_var.set("1040")

    def set_full_roi(self):
        if self.preview_frame is not None:
            height, width = self.preview_frame.shape[:2]
            self.xmin_var.set("0")
            self.ymin_var.set("0")
            self.width_var.set(str(width))
            self.height_var.set(str(height))

    def browse_base_path(self):
        selected_path = filedialog.askdirectory(initialdir=self.base_path_var.get() or os.path.expanduser("~"))
        if selected_path:
            self.base_path_var.set(selected_path)

    def update_path_preview(self, *args):
        path = f"{self.base_path_var.get()}/{self.target_var.get()}/{self.titer_var.get()}/"
        self.path_preview.set(path)

    def validate_inputs(self):
        try:
            if self.preview_frame is None:
                raise ValueError("Preview not available.")
            frame_h, frame_w = self.preview_frame.shape[:2]
            xmin, ymin, width, height = int(self.xmin_var.get()), int(self.ymin_var.get()), int(self.width_var.get()), int(self.height_var.get())
            if (xmin + width) > frame_w or (ymin + height) > frame_h:
                raise ValueError(f"ROI exceeds image bounds ({frame_w}x{frame_h})")
            if not all(v >= 0 for v in [float(self.start_var.get()), float(self.interval1_var.get()), float(self.middle_var.get()), float(self.interval2_var.get()), float(self.end_var.get())]):
                raise ValueError("Timing values must be non-negative")
            if not self.target_var.get().strip() or not self.titer_var.get().strip():
                raise ValueError("Target and Titer names cannot be empty")
            return True
        except Exception as e:
            messagebox.showerror("Input Error", str(e))
            return False

    def update_variables(self):
        self.crop = {'xmin': int(self.xmin_var.get()), 'ymin': int(self.ymin_var.get()), 'width': int(self.width_var.get()), 'height': int(self.height_var.get())}
        self.cap_time = {'start': float(self.start_var.get()), 'interval_1': float(self.interval1_var.get()), 'middle': float(self.middle_var.get()), 'interval_2': float(self.interval2_var.get()), 'end': float(self.end_var.get())}
        self.target = self.target_var.get().strip()
        self.titer = self.titer_var.get().strip()
        self.base_path = self.base_path_var.get().strip()

    def gstreamer_pipeline(self, sensor_id=0, capture_width=1280, capture_height=720, display_width=720, display_height=1280, framerate=30, flip_method=3):
        return (f"nvarguscamerasrc sensor-id={sensor_id} ! video/x-raw(memory:NVMM), width=(int){capture_width}, height=(int){capture_height}, framerate=(fraction){framerate}/1 ! nvvidconv flip-method={flip_method} ! video/x-raw, width=(int){display_width}, height=(int){display_height}, format=(string)BGRx ! videoconvert ! video/x-raw, format=(string)BGR ! appsink")

    def start_preview(self):
        self.preview_thread = threading.Thread(target=self._preview_worker, daemon=True)
        self.preview_thread.start()

    def _preview_worker(self):
        try:
            self.video_capture = cv2.VideoCapture(self.gstreamer_pipeline(sensor_id=self.camera_id), cv2.CAP_GSTREAMER)
            time.sleep(2)
            if not self.video_capture.isOpened():
                self.root.after(0, lambda: self.preview_info.set("카메라 연결 실패"))
                return

            while self.preview_running:
                ret, frame = self.video_capture.read()
                if ret:
                    self.preview_frame = frame
                    self.root.after_idle(self.update_preview_display)
                    self.root.after_idle(lambda: self.preview_info.set(f"Live Preview - {frame.shape[1]}x{frame.shape[0]}"))
                else:
                    self.root.after_idle(lambda: self.preview_info.set("프레임 읽기 실패"))
                time.sleep(1/60)
        finally:
            if self.video_capture: self.video_capture.release()
            print("Preview thread finished.")

    def start_camera(self):
        if self.is_capturing: return
        if not self.validate_inputs(): return
        self.update_variables()
        self.is_capturing = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_var.set("Capturing... (Live)")
        self.capture_thread = threading.Thread(target=self._capture_worker, daemon=True)
        self.capture_thread.start()

    def _capture_worker(self):
        try:
            save_path = os.path.join(self.base_path, self.target, self.titer)
            os.makedirs(save_path, exist_ok=True)
            existing_folders = [d for d in os.listdir(save_path) if os.path.isdir(os.path.join(save_path, d)) and d.isdigit()]
            new_folder_num = max(map(int, existing_folders)) + 1 if existing_folders else 0
            version_path = os.path.join(save_path, str(new_folder_num))
            os.makedirs(version_path, exist_ok=True)
            print(f"--------- Capture Start: Saving to {version_path} ---------")

            start_delay, interval_1, middle_time, interval_2, end_time = self.cap_time['start'], self.cap_time['interval_1'], self.cap_time['middle'], self.cap_time['interval_2'], self.cap_time['end']
            capture_start_time = time.time()
            next_cap_time_1 = capture_start_time + start_delay
            next_cap_time_2 = capture_start_time + middle_time
            
            while self.is_capturing:
                current_time = time.time()
                elapsed_time = current_time - capture_start_time
                if elapsed_time > end_time: break
                
                if self.preview_frame is None:
                    time.sleep(0.01)
                    continue
                
                saved = False
                if start_delay <= elapsed_time < middle_time and current_time >= next_cap_time_1:
                    filename = os.path.join(version_path, f"{elapsed_time:.2f}.png")
                    saved = True
                    next_cap_time_1 += interval_1
                elif middle_time <= elapsed_time < end_time and current_time >= next_cap_time_2:
                    filename = os.path.join(version_path, f"{elapsed_time:.2f}.png")
                    saved = True
                    next_cap_time_2 += interval_2
                
                if saved:
                    frame_to_save = self.preview_frame.copy()
                    xmin, ymin, w, h = self.crop['xmin'], self.crop['ymin'], self.crop['width'], self.crop['height']
                    save_frame = frame_to_save[ymin:ymin+h, xmin:xmin+w]
                    cv2.imwrite(filename, save_frame)
                    print(f"Captured {filename}")

                time.sleep(0.005)
        except Exception as e:
            print(f"An error occurred during capture: {e}")
        finally:
            print("---------- Capture End ----------")
            self.root.after(0, self.stop_camera)

    def stop_camera(self):
        if not self.is_capturing: return
        self.is_capturing = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set("Ready")

    def update_preview_display(self):
        if self.preview_frame is None or not self.preview_running: return
        canvas_width = self.preview_canvas.winfo_width()
        canvas_height = self.preview_canvas.winfo_height()
        if canvas_width <= 1 or canvas_height <= 1: return

        frame = self.preview_frame
        height, width = frame.shape[:2]
        scale = min(canvas_width / width, canvas_height / height)
        new_width, new_height = int(width * scale), int(height * scale)
        resized = cv2.resize(frame, (new_width, new_height))

        try:
            xmin, ymin, roi_width, roi_height = int(self.xmin_var.get()), int(self.ymin_var.get()), int(self.width_var.get()), int(self.height_var.get())
            scaled_xmin, scaled_ymin, scaled_width, scaled_height = int(xmin * scale), int(ymin * scale), int(roi_width * scale), int(roi_height * scale)
            cv2.rectangle(resized, (scaled_xmin, scaled_ymin), (scaled_xmin + scaled_width, scaled_ymin + scaled_height), (0, 255, 0), 2)
        except (ValueError, tk.TclError): pass

        rgb_frame = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_frame)
        self.photo = ImageTk.PhotoImage(image=pil_image)
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(canvas_width / 2, canvas_height / 2, anchor=tk.CENTER, image=self.photo)

    def on_mouse_press(self, event):
        if not self.preview_running or self.preview_frame is None: return
        self.roi_selecting = True
        canvas_width, canvas_height = self.preview_canvas.winfo_width(), self.preview_canvas.winfo_height()
        height, width = self.preview_frame.shape[:2]
        scale = min(canvas_width / width, canvas_height / height)
        new_width, new_height = int(width * scale), int(height * scale)
        self.x_offset = (canvas_width - new_width) / 2
        self.y_offset = (canvas_height - new_height) / 2
        self.roi_start = (event.x, event.y)

    def on_mouse_drag(self, event):
        if self.roi_selecting and self.roi_start:
            self.preview_canvas.delete("temp_roi")
            self.preview_canvas.create_rectangle(self.roi_start[0], self.roi_start[1], event.x, event.y, outline="red", width=2, tags="temp_roi")

    def on_mouse_release(self, event):
        if not (self.roi_selecting and self.roi_start and self.preview_frame is not None): return
        canvas_width, canvas_height = self.preview_canvas.winfo_width(), self.preview_canvas.winfo_height()
        height, width = self.preview_frame.shape[:2]
        scale = min(canvas_width / width, canvas_height / height)
        start_x_canvas, start_y_canvas = min(self.roi_start[0], event.x), min(self.roi_start[1], event.y)
        end_x_canvas, end_y_canvas = max(self.roi_start[0], event.x), max(self.roi_start[1], event.y)
        start_x_orig, start_y_orig = int((start_x_canvas - self.x_offset) / scale), int((start_y_canvas - self.y_offset) / scale)
        end_x_orig, end_y_orig = int((end_x_canvas - self.x_offset) / scale), int((end_y_canvas - self.y_offset) / scale)
        xmin, ymin, xmax, ymax = max(0, start_x_orig), max(0, start_y_orig), min(width, end_x_orig), min(height, end_y_orig)
        self.xmin_var.set(str(xmin))
        self.ymin_var.set(str(ymin))
        self.width_var.set(str(xmax - xmin))
        self.height_var.set(str(ymax - ymin))
        self.preview_canvas.delete("temp_roi")
        self.roi_selecting = False

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

    def on_closing(self):
        print("Closing application...")
        self.preview_running = False
        self.is_capturing = False
        if self.preview_thread and self.preview_thread.is_alive(): self.preview_thread.join(timeout=2)
        if self.capture_thread and self.capture_thread.is_alive(): self.capture_thread.join(timeout=2)
        self.root.destroy()

if __name__ == '__main__':
    app = CameraUI(camera_id=0)
    app.run()
