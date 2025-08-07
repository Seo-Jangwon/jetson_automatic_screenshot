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
        self.root.geometry("850x800")
        self.root.resizable(True, True)
        self.root.minsize(800, 800)

        # 기본값 설정
        self.start_delay = 0.0
        self.cap_time = [
            {'end_point': 10.0, 'interval': 1.0},
            {'end_point': 20.0, 'interval': 1.0}
        ]
        self.crop = {'xmin': 240, 'ymin': 100, 'width': 260, 'height': 800}
        self.target = 'target'
        self.titer = 'titer'
        self.base_path = './sample'

        self.roi_selecting = False
        self.roi_start = None
        self.roi_widgets = []
        self.preview_frame = None
        self.video_capture = None
        self.preview_running = True
        self.is_capturing = False
        self.capture_thread = None
        self.preview_thread = None
        self.timing_vars = []
        self.timing_frame_container = None
        self.add_button = None
        self.remove_button = None

        self.setup_ui()
        self.start_preview()

        self.root.bind("<Up>", self._on_key_press)
        self.root.bind("<Down>", self._on_key_press)
        self.root.bind("<Left>", self._on_key_press)
        self.root.bind("<Right>", self._on_key_press)

    def _on_key_press(self, event):
        if self.is_capturing:
            return
        try:
            xmin = int(self.xmin_var.get())
            ymin = int(self.ymin_var.get())
            width = int(self.width_var.get())
            height = int(self.height_var.get())
        except (ValueError, tk.TclError):
            return
        step = 10 if (event.state & 0x0001) else 1
        if event.keysym == 'Up': ymin -= step
        elif event.keysym == 'Down': ymin += step
        elif event.keysym == 'Left': xmin -= step
        elif event.keysym == 'Right': xmin += step
        if self.preview_frame is not None:
            frame_h, frame_w = self.preview_frame.shape[:2]
            xmin = max(0, min(xmin, frame_w - width))
            ymin = max(0, min(ymin, frame_h - height))
        self.xmin_var.set(str(xmin))
        self.ymin_var.set(str(ymin))

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

    def setup_timing_settings(self, parent):
        timing_frame = ttk.LabelFrame(parent, text="Capture Timing (seconds)", padding="10")
        timing_frame.pack(fill=tk.X, pady=(0, 10))

        button_frame = ttk.Frame(timing_frame)
        button_frame.pack(fill=tk.X, pady=(0, 5))
        self.add_button = ttk.Button(button_frame, text="+", width=3, command=self._add_interval)
        self.add_button.pack(side=tk.LEFT)
        self.remove_button = ttk.Button(button_frame, text="-", width=3, command=self._remove_interval)
        self.remove_button.pack(side=tk.LEFT, padx=5)

        info_label = ttk.Label(timing_frame, text="Info: Middle/End 값은 '누적 종료 시점'입니다.", font=("Arial", 8), foreground="gray")
        info_label.pack(anchor=tk.W, pady=(0, 10))
        
        self.timing_frame_container = ttk.Frame(timing_frame)
        self.timing_frame_container.pack(fill=tk.X)
        
        self._redraw_timing_widgets()

    def _redraw_timing_widgets(self):
        for widget in self.timing_frame_container.winfo_children():
            widget.destroy()
        
        self.timing_vars.clear()

        start_frame = ttk.Frame(self.timing_frame_container)
        start_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(start_frame, text="Start Delay:", width=10).grid(row=0, column=0, sticky=tk.W)
        start_var = tk.StringVar(value=str(self.start_delay))
        ttk.Entry(start_frame, textvariable=start_var, width=8).grid(row=0, column=1, padx=5)
        self.timing_vars.append({'type': 'start', 'var': start_var})

        ttk.Separator(self.timing_frame_container, orient='horizontal').pack(fill='x', pady=5)

        num_phases = len(self.cap_time)
        for i, phase_data in enumerate(self.cap_time):
            phase_frame = ttk.Frame(self.timing_frame_container)
            phase_frame.pack(fill=tk.X, pady=(0, 5))
            
            is_last_phase = (i == num_phases - 1)
            label_text = f"End Point:" if is_last_phase else f"Middle {i+1} at:"
            
            ttk.Label(phase_frame, text=f"Interval {i+1}:", width=10).grid(row=0, column=0, sticky=tk.W)
            interval_var = tk.StringVar(value=str(phase_data['interval']))
            ttk.Entry(phase_frame, textvariable=interval_var, width=8).grid(row=0, column=1, padx=5)
            
            ttk.Label(phase_frame, text=label_text).grid(row=0, column=2, sticky=tk.W, padx=(10, 0))
            endpoint_var = tk.StringVar(value=str(phase_data['end_point']))
            ttk.Entry(phase_frame, textvariable=endpoint_var, width=8).grid(row=0, column=3, padx=5)

            self.timing_vars.append({'type': 'phase', 'endpoint_var': endpoint_var, 'interval_var': interval_var})
        
        self._update_timing_buttons_state()

    def _update_timing_buttons_state(self):
        num_phases = len(self.cap_time)
        self.add_button.config(state=tk.NORMAL if num_phases < 3 else tk.DISABLED)
        self.remove_button.config(state=tk.NORMAL if num_phases > 1 else tk.DISABLED)
        
    def _add_interval(self):
        if len(self.cap_time) < 3:
            last_endpoint = self.cap_time[-1]['end_point'] if self.cap_time else 0
            self.cap_time.append({'end_point': last_endpoint + 10.0, 'interval': 1.0})
            self._redraw_timing_widgets()
    
    def _remove_interval(self):
        if len(self.cap_time) > 1:
            self.cap_time.pop()
            self._redraw_timing_widgets()

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
            if self.preview_frame is None: raise ValueError("Preview not available.")
            frame_h, frame_w = self.preview_frame.shape[:2]
            xmin, ymin, width, height = int(self.xmin_var.get()), int(self.ymin_var.get()), int(self.width_var.get()), int(self.height_var.get())
            if (xmin + width) > frame_w or (ymin + height) > frame_h: raise ValueError(f"ROI exceeds image bounds ({frame_w}x{frame_h})")
            
            last_endpoint = float(self.timing_vars[0]['var'].get())
            if last_endpoint < 0: raise ValueError("Start Delay must be non-negative")

            for var_dict in self.timing_vars:
                if var_dict['type'] == 'phase':
                    endpoint = float(var_dict['endpoint_var'].get())
                    interval = float(var_dict['interval_var'].get())
                    if interval <= 0:
                        raise ValueError("Intervals must be positive (e.g. > 0)")
                    if endpoint <= last_endpoint:
                        raise ValueError("Each end point must be greater than the previous time point.")
                    last_endpoint = endpoint

            if not self.target_var.get().strip() or not self.titer_var.get().strip(): raise ValueError("Target and Titer names cannot be empty")
            return True
        except (ValueError, tk.TclError) as e:
            messagebox.showerror("Input Error", str(e))
            return False

    def update_variables(self):
        self.crop = {'xmin': int(self.xmin_var.get()), 'ymin': int(self.ymin_var.get()), 'width': int(self.width_var.get()), 'height': int(self.height_var.get())}
        
        self.cap_time.clear()
        for var_dict in self.timing_vars:
            if var_dict['type'] == 'start':
                self.start_delay = float(var_dict['var'].get())
            elif var_dict['type'] == 'phase':
                self.cap_time.append({
                    'end_point': float(var_dict['endpoint_var'].get()),
                    'interval': float(var_dict['interval_var'].get())
                })

        self.target = self.target_var.get().strip()
        self.titer = self.titer_var.get().strip()
        self.base_path = self.base_path_var.get().strip()

    def gstreamer_pipeline(self, sensor_id=0, capture_width=3280, capture_height=2464, display_width=720, display_height=958, framerate=21, flip_method=3):
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
        
        for widget in self.roi_widgets:
            widget.config(state=tk.DISABLED)
        
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

            phases = []
            last_end_point = self.start_delay
            for phase_data in self.cap_time:
                start_point = last_end_point
                phases.append({
                    'start': start_point,
                    'end': phase_data['end_point'],
                    'interval': phase_data['interval'],
                    'next_scheduled_cap': start_point
                })
                last_end_point = phase_data['end_point']
            
            total_duration = last_end_point
            capture_start_time = time.time()
            
            num_phases = len(phases)
            while self.is_capturing:
                current_loop_time = time.time()
                elapsed_time = current_loop_time - capture_start_time

                if elapsed_time > total_duration + 0.01:
                    break
                
                if self.preview_frame is None:
                    time.sleep(0.01)
                    continue
                
                for i, phase in enumerate(phases):
                    is_last_phase = (i == num_phases - 1)
                    
                    in_phase = False
                    if is_last_phase:
                        if phase['start'] <= elapsed_time <= phase['end'] + 0.01:
                            in_phase = True
                    else:
                        if phase['start'] <= elapsed_time < phase['end']:
                            in_phase = True

                    if in_phase:
                        if elapsed_time >= phase['next_scheduled_cap']:
                            filename = os.path.join(version_path, f"{elapsed_time:.2f}.png")
                            
                            frame_to_save = self.preview_frame.copy()
                            xmin, ymin, w, h = self.crop.values()
                            save_frame = frame_to_save[ymin:ymin+h, xmin:xmin+w]
                            cv2.imwrite(filename, save_frame)
                            print(f"Captured {filename} (Scheduled: {phase['next_scheduled_cap']:.2f}s) in Phase {i+1}")

                            if phase['interval'] > 0:
                                phase['next_scheduled_cap'] += phase['interval']
                            else:
                                phase['next_scheduled_cap'] = float('inf')
                        break

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
        for widget in self.roi_widgets:
            widget.config(state=tk.NORMAL)

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
        if self.is_capturing: return
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
        if self.is_capturing: return
        if self.roi_selecting and self.roi_start:
            self.preview_canvas.delete("temp_roi")
            self.preview_canvas.create_rectangle(self.roi_start[0], self.roi_start[1], event.x, event.y, outline="red", width=2, tags="temp_roi")

    def on_mouse_release(self, event):
        if self.is_capturing: return
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
