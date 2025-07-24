''' 기본코드
import tkinter as tk
from tkinter import messagebox
import pyvisa
import serial
import socket
import threading
import csv
import time
from datetime import datetime

class PowerAnalyzerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("통합 테스트 시스템")
        self.connection_type = {}
        self.instrument = {}
        self.csv_file = None
        self.csv_writer = None
        self.is_testing = False
        self.test_thread = None
        self.rm = pyvisa.ResourceManager()
        self.build_gui()

    def build_gui(self):
        labels = ["Power Supply", "Electronic Load", "온도 센서"]
        self.device_entries = {}
        for i, label in enumerate(labels):
            tk.Label(self.root, text=label).grid(row=i, column=0)
            entry = tk.Entry(self.root, width=40)
            entry.grid(row=i, column=1, columnspan=3)
            self.device_entries[label] = entry
        self.connect_btn = tk.Button(self.root, text="장비 연결", command=self.connect_all)
        self.connect_btn.grid(row=0, column=4, rowspan=3, sticky="ns")
        tk.Label(self.root, text="전압 시퀀스 설정 (V):").grid(row=3, column=0)
        self.voltage_entry = tk.Entry(self.root, width=30)
        self.voltage_entry.grid(row=3, column=1)
        self.voltage_entry.insert(0, "60,90")
        tk.Label(self.root, text="대기 시간 (s):").grid(row=4, column=0)
        self.wait_entry = tk.Entry(self.root, width=10)
        self.wait_entry.grid(row=4, column=1)
        self.wait_entry.insert(0, "300")
        tk.Label(self.root, text="샘플링 간격 (s):").grid(row=5, column=0)
        self.sampling_entry = tk.Entry(self.root, width=10)
        self.sampling_entry.grid(row=5, column=1)
        self.sampling_entry.insert(0, "5")
        self.start_test_btn = tk.Button(self.root, text="테스트 시작", command=self.start_test)
        self.start_test_btn.grid(row=6, column=0, columnspan=2)
        self.log_box = tk.Text(self.root, height=15, width=100)
        self.log_box.grid(row=7, column=0, columnspan=5)

    def log(self, text):
        def append_log():
            timestamp = time.strftime("%H:%M:%S")
            self.log_box.insert(tk.END, f"[{timestamp}] {text}\n")
            self.log_box.see(tk.END)
        self.root.after(0, append_log)

    def connect_all(self):
        for label, entry in self.device_entries.items():
            address = entry.get().strip()
            if not address:
                continue
            try:
                if address.upper().startswith("USB") or "::" in address:
                    inst = self.rm.open_resource(address)
                    inst.timeout = 3000
                    inst.query("*IDN?")
                    self.instrument[label] = inst
                    self.connection_type[label] = "VISA"
                    self.log(f"{label} 연결 성공 (VISA)")
                elif address.upper().startswith("COM"):
                    ser = serial.Serial(address, baudrate=9600, timeout=3)
                    self.instrument[label] = ser
                    self.connection_type[label] = "SERIAL"
                    self.log(f"{label} 연결 성공 (SERIAL)")
                elif ":" in address:
                    ip, port = address.split(":")
                    sock = socket.create_connection((ip, int(port)), timeout=3)
                    self.instrument[label] = sock
                    self.connection_type[label] = "LAN"
                    self.log(f"{label} 연결 성공 (LAN)")
                else:
                    raise ValueError("주소 형식을 인식할 수 없음.")
            except Exception as e:
                self.log(f"{label} 연결 실패: {e}")

    def write(self, label, command):
        try:
            if label not in self.connection_type or label not in self.instrument:
                return
            conn_type = self.connection_type[label]
            inst = self.instrument[label]
            if conn_type == "VISA":
                inst.write(command)
            elif conn_type == "SERIAL":
                inst.write((command + "\n").encode())
            elif conn_type == "LAN":
                inst.sendall((command + "\n").encode())
        except Exception as e:
            self.log(f"{label} 명령 전송 오류: {e}")

    def query(self, label, command):
        try:
            if label not in self.connection_type or label not in self.instrument:
                return None
            conn_type = self.connection_type[label]
            inst = self.instrument[label]
            if conn_type == "VISA":
                return inst.query(command).strip()
            elif conn_type == "SERIAL":
                inst.write((command + "\n").encode())
                time.sleep(0.3)
                return inst.readline().decode().strip()
            elif conn_type == "LAN":
                inst.sendall((command + "\n").encode())
                return inst.recv(1024).decode().strip()
        except Exception as e:
            self.log(f"{label} 쿼리 오류: {e}")
            return None

    def start_test(self):
    # 연결된 장치가 최소 1개 이상인지 체크
        if not self.instrument:
            self.log("연결된 장치가 없습니다.")
            messagebox.showerror("연결 오류", "연결된 장치가 없습니다.")
            return

        # 기존 입력값 체크와 저장
        try:
            voltages = [float(v.strip()) for v in self.voltage_entry.get().split(",") if v.strip()]
            if not voltages:
                raise ValueError("전압 시퀀스를 입력하세요.")
            wait_time = float(self.wait_entry.get())
            sampling_interval = float(self.sampling_entry.get())
            if wait_time <= 0 or sampling_interval <= 0:
                raise ValueError("대기 시간과 샘플링 간격은 0보다 커야 합니다.")
        except Exception as e:
            self.log(f"입력값 오류: {e}")
            messagebox.showerror("입력값 오류", str(e))
            return

        self.voltages = voltages
        self.wait_time = wait_time
        self.sampling_interval = sampling_interval

        self.open_log_file()
        self.is_testing = True
        self.test_thread = threading.Thread(target=self.run_test_sequence, daemon=True)
        self.test_thread.start()

    def open_log_file(self):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.csv_file = open(f"result_{timestamp}.csv", "w", newline="")
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(["Time", "Set_V", "Measured_V", "Current", "Power", "Temperature", "Supply_v"])
        self.log("CSV 파일 생성 완료")

    def run_test_sequence(self):
        try:
            supply_label = "Power Supply"
            load_label = "Electronic Load"
            temp_label = "온도 센서"
            for v in self.voltages:
                self.log(f"전압 {v}V 설정 및 테스트 시작")
                time.sleep(0.5)
                # Power Supply 명령
                if supply_label in self.instrument:
                    try:
                        self.write(supply_label, "*RST")
                        time.sleep(1)
                        self.write(supply_label, "AR 1")
                        time.sleep(1)
                        self.write(supply_label, f"VOLT {v}")
                        time.sleep(1)
                        self.write(supply_label, "TEST") # 필요시 OUTP ON 등으로 변경
                        time.sleep(1)
                    except Exception as e:
                        self.log(f"Power Supply 명령 오류: {e}")
                        #continue
                # Electronic Load 명령
                if load_label in self.instrument:
                    try:
                        self.write(load_label, ":MODE CC")
                        self.write(load_label, ":CURR 11.0")
                        self.write(load_label, ":LOAD ON")
                    except Exception as e:
                        self.log(f"Electronic Load 명령 오류: {e}")
                        #continue

                start_time = time.time()
                while time.time() - start_time < self.wait_time:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    # 초기값
                    supply_v = temperature = voltage_meas = current_meas = power_meas = "N/A"
                    # 연결된 장비만 쿼리
                    try:
                        if supply_label in self.instrument:
                            val = self.query(supply_label, "TDVOLT?")
                            if val is not None:
                                supply_v = float(val)
                        if temp_label in self.instrument:
                            val = self.query(temp_label, ":VAL1:VAL?")
                            if val is not None:
                                temperature = float(val)
                        if load_label in self.instrument:
                            val_v = self.query(load_label, ":MEAS:VOLT?")
                            val_c = self.query(load_label, ":MEAS:CURR?")
                            val_p = self.query(load_label, ":MEAS:POW?")
                            if val_v is not None:
                                voltage_meas = float(val_v)
                            if val_c is not None:
                                current_meas = float(val_c)
                            if val_p is not None:
                                power_meas = float(val_p)
                    except Exception as e:
                        self.log(f"측정 오류: {e}")

                    self.csv_writer.writerow([timestamp, v, voltage_meas, current_meas, power_meas, temperature])
                    self.csv_file.flush()
                    self.log(f"[{timestamp}] V={voltage_meas}, I={current_meas}, P={power_meas}, T={temperature}")

                # 종료 명령 (연결된 장비만)
                if load_label in self.instrument:
                    try:
                        self.write(load_label, ":LOAD OFF")
                    except Exception as e:
                        self.log(f"Electronic Load 종료 명령 오류: {e}")
                if supply_label in self.instrument:
                    try:
                        self.write(supply_label, "*RST")
                    except Exception as e:
                        self.log(f"Power Supply 종료 명령 오류: {e}")
                time.sleep(2)
            self.log("모든 테스트 완료")
        except Exception as e:
            self.log(f"시퀀스 실행 중 오류: {e}")
        finally:
            self.is_testing = False
            if self.csv_file:
                self.csv_file.close()
                self.log("CSV 저장 완료")
            for label, inst in self.instrument.items():
                try:
                    if self.connection_type[label] == "VISA":
                        inst.close()
                    elif self.connection_type[label] == "SERIAL":
                        inst.close()
                    elif self.connection_type[label] == "LAN":
                        inst.close()
                except Exception:
                    pass

if __name__ == "__main__":
    root = tk.Tk()
    app = PowerAnalyzerGUI(root)
    root.mainloop()

'''
import tkinter as tk
from tkinter import messagebox, ttk
import pyvisa
import serial
import socket
import threading
import csv
import time
import atexit
from datetime import datetime

class PowerAnalyzerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("통합 테스트 시스템")
        self.connection_type = {}
        self.instrument = {}
        self.csv_file = None
        self.csv_writer = None
        self.is_testing = False
        self.test_thread = None
        self.rm = pyvisa.ResourceManager()
        
        # 상태 변수들
        self.current_voltage = 0
        self.test_progress = 0
        
        # 프로그램 종료 시 정리 작업 등록
        atexit.register(self.cleanup_resources)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.build_gui()

    def build_gui(self):
        # 메인 프레임
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 장비 연결 섹션
        connection_frame = ttk.LabelFrame(main_frame, text="장비 연결", padding="5")
        connection_frame.grid(row=0, column=0, columnspan=5, sticky=(tk.W, tk.E), pady=5)
        
        labels = ["Power Supply", "Electronic Load", "온도 센서"]
        self.device_entries = {}
        self.connection_status = {}
        
        for i, label in enumerate(labels):
            ttk.Label(connection_frame, text=label).grid(row=i, column=0, sticky=tk.W, padx=5)
            entry = ttk.Entry(connection_frame, width=40)
            entry.grid(row=i, column=1, columnspan=2, sticky=(tk.W, tk.E), padx=5)
            self.device_entries[label] = entry
            
            # 연결 상태 표시
            status_label = ttk.Label(connection_frame, text="미연결", foreground="red")
            status_label.grid(row=i, column=3, padx=5)
            self.connection_status[label] = status_label

        self.connect_btn = ttk.Button(connection_frame, text="장비 연결", command=self.connect_all)
        self.connect_btn.grid(row=0, column=4, rowspan=3, padx=5)

        # 테스트 설정 섹션
        settings_frame = ttk.LabelFrame(main_frame, text="테스트 설정", padding="5")
        settings_frame.grid(row=1, column=0, columnspan=5, sticky=(tk.W, tk.E), pady=5)

        # 첫 번째 행
        ttk.Label(settings_frame, text="전압 시퀀스 (V):").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.voltage_entry = ttk.Entry(settings_frame, width=20)
        self.voltage_entry.grid(row=0, column=1, padx=5)
        self.voltage_entry.insert(0, "60,90")

        ttk.Label(settings_frame, text="부하 전류 (A):").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.current_entry = ttk.Entry(settings_frame, width=10)
        self.current_entry.grid(row=0, column=3, padx=5)
        self.current_entry.insert(0, "11.0")

        # 두 번째 행
        ttk.Label(settings_frame, text="대기 시간 (s):").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.wait_entry = ttk.Entry(settings_frame, width=10)
        self.wait_entry.grid(row=1, column=1, padx=5)
        self.wait_entry.insert(0, "300")

        ttk.Label(settings_frame, text="샘플링 간격 (s):").grid(row=1, column=2, sticky=tk.W, padx=5)
        self.sampling_entry = ttk.Entry(settings_frame, width=10)
        self.sampling_entry.grid(row=1, column=3, padx=5)
        self.sampling_entry.insert(0, "5")

        # 컨트롤 섹션
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=2, column=0, columnspan=5, pady=10)

        self.start_test_btn = ttk.Button(control_frame, text="테스트 시작", command=self.start_test)
        self.start_test_btn.grid(row=0, column=0, padx=5)

        self.stop_test_btn = ttk.Button(control_frame, text="테스트 정지", command=self.stop_test, state="disabled")
        self.stop_test_btn.grid(row=0, column=1, padx=5)

        # 진행률 바
        self.progress_var = tk.StringVar(value="대기 중")
        ttk.Label(control_frame, textvariable=self.progress_var).grid(row=0, column=2, padx=10)
        
        self.progress_bar = ttk.Progressbar(control_frame, mode='indeterminate')
        self.progress_bar.grid(row=0, column=3, padx=5)

        # 실시간 측정값 표시
        status_frame = ttk.LabelFrame(main_frame, text="실시간 측정값", padding="5")
        status_frame.grid(row=3, column=0, columnspan=5, sticky=(tk.W, tk.E), pady=5)

        self.measurement_vars = {
            "전압": tk.StringVar(value="N/A"),
            "전류": tk.StringVar(value="N/A"),
            "전력": tk.StringVar(value="N/A"),
            "온도": tk.StringVar(value="N/A")
        }

        col = 0
        for label, var in self.measurement_vars.items():
            ttk.Label(status_frame, text=f"{label}:").grid(row=0, column=col*2, sticky=tk.W, padx=5)
            ttk.Label(status_frame, textvariable=var, font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=col*2+1, sticky=tk.W, padx=5)
            col += 1

        # 로그 섹션
        log_frame = ttk.LabelFrame(main_frame, text="로그", padding="5")
        log_frame.grid(row=4, column=0, columnspan=5, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        # 스크롤바가 있는 텍스트 위젯
        self.log_box = tk.Text(log_frame, height=15, width=100)
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_box.yview)
        self.log_box.configure(yscrollcommand=scrollbar.set)
        
        self.log_box.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # 그리드 가중치 설정
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(4, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

    def log(self, text, level="INFO"):
        """로그 메시지 추가 (레벨별 색상 구분)"""
        def append_log():
            timestamp = time.strftime("%H:%M:%S")
            message = f"[{timestamp}] {text}\n"
            
            # 로그 레벨에 따른 색상 설정
            if level == "ERROR":
                self.log_box.insert(tk.END, message, "error")
                self.log_box.tag_config("error", foreground="red")
            elif level == "WARNING":
                self.log_box.insert(tk.END, message, "warning")
                self.log_box.tag_config("warning", foreground="orange")
            elif level == "SUCCESS":
                self.log_box.insert(tk.END, message, "success")
                self.log_box.tag_config("success", foreground="green")
            else:
                self.log_box.insert(tk.END, message)
            
            self.log_box.see(tk.END)
        self.root.after(0, append_log)

    def update_connection_status(self, label, connected):
        """연결 상태 업데이트"""
        if connected:
            self.connection_status[label].config(text="연결됨", foreground="green")
        else:
            self.connection_status[label].config(text="미연결", foreground="red")

    def connect_all(self):
        """모든 장비 연결"""
        self.connect_btn.config(state="disabled")
        
        # 기존 연결 해제
        self.disconnect_all()
        
        for label, entry in self.device_entries.items():
            address = entry.get().strip()
            if not address:
                continue
                
            try:
                success = False
                if address.upper().startswith("USB") or "::" in address:
                    inst = self.rm.open_resource(address)
                    inst.timeout = 3000
                    response = inst.query("*IDN?")
                    self.instrument[label] = inst
                    self.connection_type[label] = "VISA"
                    self.log(f"{label} 연결 성공 (VISA): {response.strip()}", "SUCCESS")
                    success = True
                    
                elif address.upper().startswith("COM"):
                    ser = serial.Serial(address, baudrate=9600, timeout=3)
                    self.instrument[label] = ser
                    self.connection_type[label] = "SERIAL"
                    self.log(f"{label} 연결 성공 (SERIAL)", "SUCCESS")
                    success = True
                    
                elif ":" in address and not "::" in address:
                    ip, port = address.split(":")
                    sock = socket.create_connection((ip, int(port)), timeout=3)
                    self.instrument[label] = sock
                    self.connection_type[label] = "LAN"
                    self.log(f"{label} 연결 성공 (LAN)", "SUCCESS")
                    success = True
                    
                else:
                    raise ValueError("지원되지 않는 주소 형식입니다.")
                
                self.update_connection_status(label, success)
                    
            except Exception as e:
                self.log(f"{label} 연결 실패: {e}", "ERROR")
                self.update_connection_status(label, False)
        
        self.connect_btn.config(state="normal")

    def disconnect_all(self):
        """모든 장비 연결 해제"""
        for label in list(self.instrument.keys()):
            try:
                inst = self.instrument[label]
                conn_type = self.connection_type[label]
                
                if conn_type == "VISA":
                    inst.close()
                elif conn_type == "SERIAL":
                    inst.close()
                elif conn_type == "LAN":
                    inst.close()
                    
                del self.instrument[label]
                del self.connection_type[label]
                self.update_connection_status(label, False)
                
            except Exception as e:
                self.log(f"{label} 연결 해제 중 오류: {e}", "WARNING")

    def safe_write(self, label, command):
        """안전한 명령 전송"""
        try:
            if label not in self.connection_type or label not in self.instrument:
                return False
                
            conn_type = self.connection_type[label]
            inst = self.instrument[label]
            
            if conn_type == "VISA":
                inst.write(command)
            elif conn_type == "SERIAL":
                inst.write((command + "\n").encode())
            elif conn_type == "LAN":
                inst.sendall((command + "\n").encode())
            return True
            
        except Exception as e:
            self.log(f"{label} 명령 전송 오류: {e}", "ERROR")
            self.update_connection_status(label, False)
            return False

    def safe_query(self, label, command, timeout_retry=1):
        """안전한 쿼리 (재시도 포함)"""
        for attempt in range(timeout_retry + 1):
            try:
                if label not in self.connection_type or label not in self.instrument:
                    return None
                    
                conn_type = self.connection_type[label]
                inst = self.instrument[label]
                
                if conn_type == "VISA":
                    result = inst.query(command).strip()
                elif conn_type == "SERIAL":
                    inst.write((command + "\n").encode())
                    time.sleep(0.3)
                    result = inst.readline().decode().strip()
                elif conn_type == "LAN":
                    inst.sendall((command + "\n").encode())
                    result = inst.recv(1024).decode().strip()
                
                # 결과 검증
                if result and result != "":
                    return result
                    
            except Exception as e:
                if attempt == timeout_retry:
                    self.log(f"{label} 쿼리 오류 (최종 실패): {e}", "ERROR")
                    self.update_connection_status(label, False)
                else:
                    time.sleep(0.5)  # 재시도 전 잠시 대기
                    
        return None

    def validate_measurement(self, value, min_val=None, max_val=None):
        """측정값 유효성 검증"""
        try:
            float_val = float(value)
            if min_val is not None and float_val < min_val:
                return False
            if max_val is not None and float_val > max_val:
                return False
            return True
        except:
            return False

    def update_measurements(self, voltage, current, power, temperature):
        """실시간 측정값 업데이트"""
        def update():
            self.measurement_vars["전압"].set(f"{voltage} V" if voltage != "N/A" else "N/A")
            self.measurement_vars["전류"].set(f"{current} A" if current != "N/A" else "N/A")
            self.measurement_vars["전력"].set(f"{power} W" if power != "N/A" else "N/A")
            self.measurement_vars["온도"].set(f"{temperature} °C" if temperature != "N/A" else "N/A")
        self.root.after(0, update)

    def start_test(self):
        """테스트 시작"""
        if not self.instrument:
            self.log("연결된 장치가 없습니다.", "ERROR")
            messagebox.showerror("연결 오류", "연결된 장치가 없습니다.")
            return

        try:
            # 입력값 검증
            voltages = [float(v.strip()) for v in self.voltage_entry.get().split(",") if v.strip()]
            if not voltages:
                raise ValueError("전압 시퀀스를 입력하세요.")
            
            wait_time = float(self.wait_entry.get())
            sampling_interval = float(self.sampling_entry.get())
            load_current = float(self.current_entry.get())
            
            # 범위 검증
            if wait_time <= 0 or sampling_interval <= 0:
                raise ValueError("대기 시간과 샘플링 간격은 0보다 커야 합니다.")
            if load_current <= 0:
                raise ValueError("부하 전류는 0보다 커야 합니다.")
            if any(v <= 0 for v in voltages):
                raise ValueError("전압값은 0보다 커야 합니다.")
                
        except Exception as e:
            self.log(f"입력값 오류: {e}", "ERROR")
            messagebox.showerror("입력값 오류", str(e))
            return

        # 테스트 매개변수 저장
        self.voltages = voltages
        self.wait_time = wait_time
        self.sampling_interval = sampling_interval
        self.load_current = load_current

        # UI 상태 변경
        self.start_test_btn.config(state="disabled")
        self.stop_test_btn.config(state="normal")
        self.progress_bar.start()
        self.progress_var.set("테스트 준비 중...")

        # CSV 파일 생성
        if not self.open_log_file():
            return

        # 테스트 시작
        self.is_testing = True
        self.test_thread = threading.Thread(target=self.run_test_sequence, daemon=True)
        self.test_thread.start()

    def stop_test(self):
        """테스트 중지"""
        self.is_testing = False
        self.log("테스트 중지 요청됨...", "WARNING")
        self.progress_var.set("테스트 중지 중...")

    def open_log_file(self):
        """CSV 로그 파일 생성"""
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            self.csv_file = open(f"result_{timestamp}.csv", "w", newline="", encoding='utf-8-sig')
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow([
                "Time", "Set_Voltage_V", "Measured_Voltage_V", "Current_A", 
                "Power_W", "Temperature_C", "Supply_Voltage_V"
            ])
            self.csv_file.flush()
            self.log("CSV 파일 생성 완료", "SUCCESS")
            return True
        except Exception as e:
            self.log(f"CSV 파일 생성 실패: {e}", "ERROR")
            messagebox.showerror("파일 오류", f"CSV 파일을 생성할 수 없습니다: {e}")
            return False

    def run_test_sequence(self):
        """테스트 시퀀스 실행"""
        try:
            supply_label = "Power Supply"
            load_label = "Electronic Load"
            temp_label = "온도 센서"
            
            total_steps = len(self.voltages)
            
            for step, voltage in enumerate(self.voltages):
                if not self.is_testing:
                    break
                
                self.current_voltage = voltage
                self.progress_var.set(f"전압 {voltage}V 테스트 ({step+1}/{total_steps})")
                self.log(f"=== 전압 {voltage}V 설정 및 테스트 시작 ===")
                
                # Power Supply 설정
                if supply_label in self.instrument:
                    self.setup_power_supply(supply_label, voltage)
                
                # Electronic Load 설정
                if load_label in self.instrument:
                    self.setup_electronic_load(load_label)
                
                # 측정 루프
                self.measurement_loop(step+1, total_steps, supply_label, load_label, temp_label)
                
                # 장비 종료
                self.shutdown_equipment(supply_label, load_label)
                
                if self.is_testing and step < total_steps - 1:
                    self.log("다음 전압 설정 전 대기...")
                    time.sleep(2)
            
            if self.is_testing:
                self.log("=== 모든 테스트 완료 ===", "SUCCESS")
            else:
                self.log("=== 테스트가 사용자에 의해 중지됨 ===", "WARNING")
                
        except Exception as e:
            self.log(f"시퀀스 실행 중 치명적 오류: {e}", "ERROR")
        finally:
            self.cleanup_test()

    def setup_power_supply(self, label, voltage):
        """Power Supply 설정"""
        try:
            commands = [
                ("*RST", 1),
                ("AR 1", 1),
                (f"VOLT {voltage}", 1),
                ("TEST", 1)
            ]
            
            for cmd, delay in commands:
                if not self.is_testing:
                    break
                if not self.safe_write(label, cmd):
                    raise Exception(f"명령 전송 실패: {cmd}")
                time.sleep(delay)
                
            self.log(f"Power Supply 설정 완료: {voltage}V", "SUCCESS")
            
        except Exception as e:
            self.log(f"Power Supply 설정 오류: {e}", "ERROR")
            raise

    def setup_electronic_load(self, label):
        """Electronic Load 설정"""
        try:
            commands = [
                ":MODE CC",
                f":CURR {self.load_current}",
                ":LOAD ON"
            ]
            
            for cmd in commands:
                if not self.is_testing:
                    break
                if not self.safe_write(label, cmd):
                    raise Exception(f"명령 전송 실패: {cmd}")
                time.sleep(0.5)
                
            self.log(f"Electronic Load 설정 완료: {self.load_current}A", "SUCCESS")
            
        except Exception as e:
            self.log(f"Electronic Load 설정 오류: {e}", "ERROR")
            raise

    def measurement_loop(self, current_step, total_steps, supply_label, load_label, temp_label):
        """측정 루프"""
        start_time = time.time()
        measurement_count = 0
        
        while time.time() - start_time < self.wait_time and self.is_testing:
            elapsed_time = time.time() - start_time
            remaining_time = self.wait_time - elapsed_time
            
            self.progress_var.set(f"측정 중... ({current_step}/{total_steps}) - 남은시간: {int(remaining_time)}s")
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 측정값 초기화
            measurements = {
                'supply_v': "N/A",
                'temperature': "N/A",
                'voltage_meas': "N/A",
                'current_meas': "N/A",
                'power_meas': "N/A"
            }
            
            # 각 장비에서 측정
            self.measure_from_supply(supply_label, measurements)
            self.measure_from_load(load_label, measurements)
            self.measure_from_temp_sensor(temp_label, measurements)
            
            # CSV에 기록
            if self.csv_writer:
                self.csv_writer.writerow([
                    timestamp, self.current_voltage,
                    measurements['voltage_meas'], measurements['current_meas'],
                    measurements['power_meas'], measurements['temperature'],
                    measurements['supply_v']
                ])
                self.csv_file.flush()
            
            # 실시간 표시 업데이트
            self.update_measurements(
                measurements['voltage_meas'], measurements['current_meas'],
                measurements['power_meas'], measurements['temperature']
            )
            
            # 로그 출력
            measurement_count += 1
            self.log(f"측정#{measurement_count}: V={measurements['voltage_meas']}, "
                    f"I={measurements['current_meas']}, P={measurements['power_meas']}, "
                    f"T={measurements['temperature']}")
            
            time.sleep(self.sampling_interval)

    def measure_from_supply(self, label, measurements):
        """Power Supply에서 측정"""
        if label in self.instrument:
            try:
                val = self.safe_query(label, "TDVOLT?")
                if val and self.validate_measurement(val, 0, 1000):
                    measurements['supply_v'] = float(val)
            except Exception as e:
                self.log(f"Power Supply 측정 오류: {e}", "WARNING")

    def measure_from_load(self, label, measurements):
        """Electronic Load에서 측정"""
        if label in self.instrument:
            try:
                voltage = self.safe_query(label, ":MEAS:VOLT?")
                current = self.safe_query(label, ":MEAS:CURR?")
                power = self.safe_query(label, ":MEAS:POW?")
                
                if voltage and self.validate_measurement(voltage, 0, 1000):
                    measurements['voltage_meas'] = float(voltage)
                if current and self.validate_measurement(current, 0, 100):
                    measurements['current_meas'] = float(current)
                if power and self.validate_measurement(power, 0, 10000):
                    measurements['power_meas'] = float(power)
                    
            except Exception as e:
                self.log(f"Electronic Load 측정 오류: {e}", "WARNING")

    def measure_from_temp_sensor(self, label, measurements):
        """온도 센서에서 측정"""
        if label in self.instrument:
            try:
                val = self.safe_query(label, ":VAL1:VAL?")
                if val and self.validate_measurement(val, -50, 200):
                    measurements['temperature'] = float(val)
            except Exception as e:
                self.log(f"온도 센서 측정 오류: {e}", "WARNING")

    def shutdown_equipment(self, supply_label, load_label):
        """장비 종료"""
        # Electronic Load 먼저 끄기
        if load_label in self.instrument:
            try:
                self.safe_write(load_label, ":LOAD OFF")
                self.log("Electronic Load 종료 완료")
            except Exception as e:
                self.log(f"Electronic Load 종료 오류: {e}", "WARNING")
        
        # Power Supply 리셋
        if supply_label in self.instrument:
            try:
                self.safe_write(supply_label, "*RST")
                self.log("Power Supply 리셋 완료")
            except Exception as e:
                self.log(f"Power Supply 리셋 오류: {e}", "WARNING")

    def cleanup_test(self):
        """테스트 종료 후 정리"""
        def cleanup_ui():
            self.is_testing = False
            self.start_test_btn.config(state="normal")
            self.stop_test_btn.config(state="disabled")
            self.progress_bar.stop()
            self.progress_var.set("테스트 완료")
            
            # 측정값 초기화
            for var in self.measurement_vars.values():
                var.set("N/A")
        
        self.root.after(0, cleanup_ui)
        
        # CSV 파일 닫기
        if self.csv_file:
            try:
                self.csv_file.close()
                self.csv_file = None
                self.log("CSV 파일 저장 완료", "SUCCESS")
            except Exception as e:
                self.log(f"CSV 파일 저장 오류: {e}", "ERROR")

    def cleanup_resources(self):
        """리소스 정리"""
        self.is_testing = False
        
        if self.csv_file:
            try:
                self.csv_file.close()
            except:
                pass
        
        self.disconnect_all()
        
        try:
            self.rm.close()
        except:
            pass

    def on_closing(self):
        """프로그램 종료 시 처리"""
        if self.is_testing:
            result = messagebox.askyesno("종료 확인", "테스트가 진행 중입니다. 정말로 종료하시겠습니까?")
            if not result:
                return
        
        self.cleanup_resources()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = PowerAnalyzerGUI(root)
    root.mainloop()