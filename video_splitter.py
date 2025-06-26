import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import subprocess
import os
import sys
import logging
from datetime import datetime

# Configure logging
logger = logging.getLogger('VideoSplitter')
logger.setLevel(logging.DEBUG)
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler = logging.FileHandler('video_splitter.log')
file_handler.setFormatter(log_formatter)
logger.addHandler(file_handler)

class TextHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.configure(state='disabled')
            self.text_widget.see(tk.END)
        self.text_widget.after(0, append)

class SegmentRow:
    def __init__(self, parent, row, remove_callback):
        self.start_var = tk.StringVar()
        self.end_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.audio_var = tk.BooleanVar(value=True)
        self.row = row
        self.remove_callback = remove_callback

        self.start_entry = ttk.Entry(parent, textvariable=self.start_var, width=10)
        self.end_entry = ttk.Entry(parent, textvariable=self.end_var, width=10)
        self.output_entry = ttk.Entry(parent, textvariable=self.output_var, width=30)
        self.audio_check = ttk.Checkbutton(parent, variable=self.audio_var)
        self.browse_btn = ttk.Button(parent, text='Browse', command=self.browse_output)
        self.remove_btn = ttk.Button(parent, text='Remove', command=self.remove)

    def grid(self, parent):
        self.start_entry.grid(row=self.row, column=0, padx=2, pady=2)
        self.end_entry.grid(row=self.row, column=1, padx=2, pady=2)
        self.output_entry.grid(row=self.row, column=2, padx=2, pady=2)
        self.browse_btn.grid(row=self.row, column=3, padx=2, pady=2)
        self.audio_check.grid(row=self.row, column=4, padx=2, pady=2)
        self.remove_btn.grid(row=self.row, column=5, padx=2, pady=2)

    def remove(self):
        self.start_entry.grid_remove()
        self.end_entry.grid_remove()
        self.output_entry.grid_remove()
        self.browse_btn.grid_remove()
        self.audio_check.grid_remove()
        self.remove_btn.grid_remove()
        self.remove_callback(self)

    def browse_output(self):
        file = filedialog.asksaveasfilename(defaultextension='.mp4', filetypes=[('MP4', '*.mp4'), ('MKV', '*.mkv'), ('AVI', '*.avi')])
        if file:
            self.output_var.set(file)

    def get_data(self):
        return {
            'start': self.start_var.get(),
            'end': self.end_var.get(),
            'output': self.output_var.get(),
            'audio': self.audio_var.get()
        }

class VideoSplitterApp:
    def __init__(self, root):
        self.root = root
        self.root.title('Video Splitter')
        self.input_file = tk.StringVar()
        self.segments = []
        self.process_thread = None
        self.stop_event = threading.Event()
        self.ffmpeg_procs = []

        self.build_gui()

    def build_gui(self):
        frm = ttk.Frame(self.root, padding=10)
        frm.pack(fill='both', expand=True)

        # --- Chế độ cắt ---
        self.mode_var = tk.StringVar(value='split_video')
        mode_frame = ttk.LabelFrame(frm, text='Chế độ')
        mode_frame.pack(fill='x', pady=5)
        ttk.Radiobutton(mode_frame, text='Cắt video thành nhiều đoạn nhỏ', variable=self.mode_var, value='split_video', command=self.update_mode).pack(side='left', padx=5)
        ttk.Radiobutton(mode_frame, text='Cắt video thành nhiều ảnh', variable=self.mode_var, value='split_image', command=self.update_mode).pack(side='left', padx=5)
        ttk.Radiobutton(mode_frame, text='Tách audio', variable=self.mode_var, value='extract_audio', command=self.update_mode).pack(side='left', padx=5)

        # Input file selector
        file_row = ttk.Frame(frm)
        file_row.pack(fill='x', pady=5)
        ttk.Label(file_row, text='Input Video:').pack(side='left')
        self.input_entry = ttk.Entry(file_row, textvariable=self.input_file, width=50)
        self.input_entry.pack(side='left', padx=5)
        ttk.Button(file_row, text='Browse', command=self.browse_input).pack(side='left')

        # --- Tuỳ chọn cho split_video ---
        self.split_video_frame = ttk.Frame(frm)
        ttk.Label(self.split_video_frame, text='Số giây mỗi đoạn:').pack(side='left')
        self.split_video_seconds = tk.IntVar(value=10)
        ttk.Entry(self.split_video_frame, textvariable=self.split_video_seconds, width=5).pack(side='left', padx=2)
        ttk.Label(self.split_video_frame, text='Thư mục lưu:').pack(side='left', padx=5)
        self.split_video_dir = tk.StringVar()
        ttk.Entry(self.split_video_frame, textvariable=self.split_video_dir, width=30).pack(side='left', padx=2)
        ttk.Button(self.split_video_frame, text='Chọn...', command=self.browse_split_video_dir).pack(side='left')

        # --- Tuỳ chọn cho split_image ---
        self.split_image_frame = ttk.Frame(frm)
        ttk.Label(self.split_image_frame, text='Số giây mỗi ảnh:').pack(side='left')
        self.split_image_seconds = tk.IntVar(value=5)
        ttk.Entry(self.split_image_frame, textvariable=self.split_image_seconds, width=5).pack(side='left', padx=2)
        ttk.Label(self.split_image_frame, text='Thư mục lưu:').pack(side='left', padx=5)
        self.split_image_dir = tk.StringVar()
        ttk.Entry(self.split_image_frame, textvariable=self.split_image_dir, width=30).pack(side='left', padx=2)
        ttk.Button(self.split_image_frame, text='Chọn...', command=self.browse_split_image_dir).pack(side='left')

        # Start/Stop buttons
        btn_row = ttk.Frame(frm)
        btn_row.pack(fill='x', pady=5)
        self.start_btn = ttk.Button(btn_row, text='Start', command=self.start_processing)
        self.start_btn.pack(side='left', padx=5)
        self.stop_btn = ttk.Button(btn_row, text='Stop', command=self.stop_processing, state='disabled')
        self.stop_btn.pack(side='left', padx=5)

        # Progress bar
        self.progress = ttk.Progressbar(frm, orient='horizontal', length=400, mode='determinate')
        self.progress.pack(fill='x', pady=5)

        # Log area
        log_frame = ttk.LabelFrame(frm, text='Logs')
        log_frame.pack(fill='both', expand=True, pady=5)
        self.log_text = tk.Text(log_frame, height=10, state='disabled', wrap='word')
        self.log_text.pack(fill='both', expand=True)
        text_handler = TextHandler(self.log_text)
        text_handler.setFormatter(log_formatter)
        logger.addHandler(text_handler)

        self.update_mode()

    def update_mode(self):
        mode = self.mode_var.get()
        self.split_video_frame.pack_forget()
        self.split_image_frame.pack_forget()
        if mode == 'split_video':
            self.split_video_frame.pack(fill='x', pady=2, before=self.start_btn.master)
        elif mode == 'split_image':
            self.split_image_frame.pack(fill='x', pady=2, before=self.start_btn.master)

    def browse_split_video_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.split_video_dir.set(d)

    def browse_split_image_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.split_image_dir.set(d)

    def browse_input(self):
        video_types = [
            ('All Video Files', '*.mp4 *.mkv *.avi *.mov *.flv *.wmv *.m4v *.webm *.mpg *.mpeg *.3gp *.ts *.ogv *.vob *.m2ts *.mts *.divx *.xvid *.f4v *.rmvb *.asf *.mxf *.m2v *.m1v *.m2p *.m2t *.m2ts *.m4p *.m4b *.m4r *.m4v *.3g2 *.3gp2 *.3gpp *.3gpp2 *.amv *.dpg *.ogg *.qt *.tod *.mod *.trp *.ts *.vob *.vro *.yuv *.rm *.rmvb *.mk3d *.mts *.m2ts *.mxf *.nsv *.ogm *.ogv *.ps *.rec *.rm *.swf *.tp *.tpr *.ts *.vdr *.vid *.vp6 *.webm *.wtv *.xesc'),
            ('MP4', '*.mp4'),
            ('MKV', '*.mkv'),
            ('AVI', '*.avi'),
            ('MOV', '*.mov'),
            ('FLV', '*.flv'),
            ('WMV', '*.wmv'),
            ('M4V', '*.m4v'),
            ('WEBM', '*.webm'),
            ('MPG', '*.mpg'),
            ('MPEG', '*.mpeg'),
            ('3GP', '*.3gp'),
            ('TS', '*.ts'),
            ('OGV', '*.ogv'),
            ('VOB', '*.vob'),
            ('M2TS', '*.m2ts'),
            ('MTS', '*.mts'),
            ('DIVX', '*.divx'),
            ('XVID', '*.xvid'),
            ('F4V', '*.f4v'),
            ('RMVB', '*.rmvb'),
            ('ASF', '*.asf'),
            ('MXF', '*.mxf'),
            ('All Files', '*.*'),
        ]
        file = filedialog.askopenfilename(filetypes=video_types)
        if file:
            self.input_file.set(file)

    def start_processing(self):
        mode = self.mode_var.get()
        if mode == 'split_video':
            if not self.input_file.get() or not os.path.isfile(self.input_file.get()):
                messagebox.showerror('Error', 'Vui lòng chọn file video đầu vào hợp lệ.')
                return
            if not self.split_video_dir.get():
                messagebox.showerror('Error', 'Vui lòng chọn thư mục lưu kết quả.')
                return
            seconds = self.split_video_seconds.get()
            if seconds <= 0:
                messagebox.showerror('Error', 'Số giây mỗi đoạn phải lớn hơn 0.')
                return
            self.progress['value'] = 0
            self.start_btn['state'] = 'disabled'
            self.stop_btn['state'] = 'normal'
            self.stop_event.clear()
            self.ffmpeg_procs = []
            logger.info('Bắt đầu cắt video thành nhiều đoạn nhỏ.')
            self.process_thread = threading.Thread(target=self.process_split_video, args=(seconds,), daemon=True)
            self.process_thread.start()
            return
        elif mode == 'split_image':
            if not self.input_file.get() or not os.path.isfile(self.input_file.get()):
                messagebox.showerror('Error', 'Vui lòng chọn file video đầu vào hợp lệ.')
                return
            if not self.split_image_dir.get():
                messagebox.showerror('Error', 'Vui lòng chọn thư mục lưu kết quả.')
                return
            seconds = self.split_image_seconds.get()
            if seconds <= 0:
                messagebox.showerror('Error', 'Số giây mỗi ảnh phải lớn hơn 0.')
                return
            self.progress['value'] = 0
            self.start_btn['state'] = 'disabled'
            self.stop_btn['state'] = 'normal'
            self.stop_event.clear()
            self.ffmpeg_procs = []
            logger.info('Bắt đầu cắt video thành nhiều ảnh.')
            self.process_thread = threading.Thread(target=self.process_split_image, args=(seconds,), daemon=True)
            self.process_thread.start()
            return
        elif mode == 'extract_audio':
            input_file = self.input_file.get()
            if not input_file or not os.path.isfile(input_file):
                messagebox.showerror('Error', 'Vui lòng chọn file video đầu vào hợp lệ.')
                return
            out_dir = filedialog.askdirectory(title='Chọn thư mục lưu audio')
            if not out_dir:
                return
            base = os.path.splitext(os.path.basename(input_file))[0]
            output = os.path.join(out_dir, base + '.mp3')
            self.progress['value'] = 0
            self.start_btn['state'] = 'disabled'
            self.stop_btn['state'] = 'disabled'
            self.stop_event.clear()
            self.ffmpeg_procs = []
            logger.info(f'Bắt đầu tách audio: {input_file} -> {output}')
            threading.Thread(target=self.process_extract_audio, args=(input_file, output), daemon=True).start()
            return

    def stop_processing(self):
        logger.info('Stopping process...')
        self.stop_event.set()
        for proc in self.ffmpeg_procs:
            if proc.poll() is None:
                try:
                    proc.terminate()
                    logger.info('Terminated ffmpeg process.')
                except Exception as e:
                    logger.error(f'Error terminating ffmpeg: {e}')
        self.stop_btn['state'] = 'disabled'

    def process_split_video(self, seconds):
        try:
            import math
            import ffmpeg
            input_file = self.input_file.get()
            out_dir = self.split_video_dir.get()
            # Lấy độ dài video
            try:
                import ffmpeg
                probe = ffmpeg.probe(input_file)
                duration = float(probe['format']['duration'])
            except Exception as e:
                logger.error(f'Không lấy được độ dài video: {e}')
                self.root.after(0, self.processing_done)
                return
            total_segments = math.ceil(duration / seconds)
            self.root.after(0, self.progress.config, {'maximum': total_segments})
            for i in range(total_segments):
                if self.stop_event.is_set():
                    logger.info('Process stopped by user.')
                    break
                start = i * seconds
                end = min((i+1)*seconds, duration)
                output = os.path.join(out_dir, f'segment_{i+1}.mp4')
                cmd = [
                    'ffmpeg', '-y',
                    '-i', input_file,
                    '-ss', str(int(start)),
                    '-to', str(int(end)),
                    '-c:v', 'copy',
                    '-c:a', 'copy',
                    output
                ]
                logger.info(f'Cắt đoạn {i+1}: {start}s đến {end}s -> {output}')
                try:
                    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    self.ffmpeg_procs.append(proc)
                    for line in proc.stdout:
                        logger.info(line.strip())
                        if self.stop_event.is_set():
                            proc.terminate()
                            logger.info('Terminated ffmpeg process during segment.')
                            break
                    proc.wait()
                except Exception as e:
                    logger.error(f'Lỗi khi cắt đoạn {i+1}: {e}')
                self.root.after(0, self.progress.step, 1)
            logger.info('Hoàn thành cắt video thành nhiều đoạn nhỏ.')
        except Exception as e:
            logger.error(f'Unexpected error: {e}')
        finally:
            self.root.after(0, self.processing_done)

    def process_split_image(self, seconds):
        try:
            import math
            import ffmpeg
            input_file = self.input_file.get()
            out_dir = self.split_image_dir.get()
            # Lấy độ dài video
            try:
                import ffmpeg
                probe = ffmpeg.probe(input_file)
                duration = float(probe['format']['duration'])
            except Exception as e:
                logger.error(f'Không lấy được độ dài video: {e}')
                self.root.after(0, self.processing_done)
                return
            total_frames = math.floor(duration / seconds)
            self.root.after(0, self.progress.config, {'maximum': total_frames})
            for i in range(total_frames):
                if self.stop_event.is_set():
                    logger.info('Process stopped by user.')
                    break
                timestamp = i * seconds
                output = os.path.join(out_dir, f'frame_{i+1}.jpg')
                cmd = [
                    'ffmpeg', '-y',
                    '-ss', str(int(timestamp)),
                    '-i', input_file,
                    '-frames:v', '1',
                    output
                ]
                logger.info(f'Xuất ảnh {i+1}: {timestamp}s -> {output}')
                try:
                    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    self.ffmpeg_procs.append(proc)
                    for line in proc.stdout:
                        logger.info(line.strip())
                        if self.stop_event.is_set():
                            proc.terminate()
                            logger.info('Terminated ffmpeg process during frame.')
                            break
                    proc.wait()
                except Exception as e:
                    logger.error(f'Lỗi khi xuất ảnh {i+1}: {e}')
                self.root.after(0, self.progress.step, 1)
            logger.info('Hoàn thành cắt video thành nhiều ảnh.')
        except Exception as e:
            logger.error(f'Unexpected error: {e}')
        finally:
            self.root.after(0, self.processing_done)

    def process_extract_audio(self, input_file, output):
        try:
            cmd = [
                'ffmpeg', '-y',
                '-i', input_file,
                '-vn',
                '-acodec', 'mp3',
                output
            ]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            self.ffmpeg_procs.append(proc)
            for line in proc.stdout:
                logger.info(line.strip())
                if self.stop_event.is_set():
                    proc.terminate()
                    logger.info('Terminated ffmpeg process during audio extraction.')
                    break
            proc.wait()
            if proc.returncode == 0:
                logger.info(f'Tách audio thành công: {output}')
            else:
                logger.error(f'Tách audio thất bại với mã lỗi {proc.returncode}.')
        except Exception as e:
            logger.error(f'Lỗi khi tách audio: {e}')
        finally:
            self.root.after(0, self.processing_done)

    def processing_done(self):
        self.start_btn['state'] = 'normal'
        self.stop_btn['state'] = 'disabled'
        self.progress['value'] = 0

if __name__ == '__main__':
    root = tk.Tk()
    app = VideoSplitterApp(root)
    root.mainloop() 