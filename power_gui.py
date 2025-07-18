
# import tkinter as tk
# from tkinter import messagebox
# import pyvisa
# import serial
# import socket
# import csv
# import time
# import threading

# rm = pyvisa.ResourceManager()
# print(rm.list_resources())

# class PowerAnalyzerGUI:
#     def __init__(self, root):
#         self.root = root
#         self.root.title("Power Analyzer Test System")
#         self.connection_type = None
#         self.instrument = None
#         self.serial = None
#         self.socket = None
#         self.csv_file = None
#         self.csv_writer = None
#         self.has_temp = True  # 온도 센서 여부

#         self.rm = pyvisa.ResourceManager()

#         self.build_gui()

#     def build_gui(self):
#         tk.Label(self.root, text="장비 주소:").grid(row=0, column=0)
#         self.txt_resource = tk.Entry(self.root, width=40)
#         self.txt_resource.grid(row=0, column=1, columnspan=3)
#         self.txt_resource.insert(0, "USB0::0x2A8D::0x1301::INSTR")

#         self.connect_btn = tk.Button(self.root, text="연결", command=self.connect)
#         self.connect_btn.grid(row=0, column=4)

#         self.disconnect_btn = tk.Button(self.root, text="해제", state=tk.DISABLED, command=self.disconnect)
#         self.disconnect_btn.grid(row=0, column=5)

#         self.start_test_btn = tk.Button(self.root, text="테스트 시작", state=tk.DISABLED, command=self.start_test)
#         self.start_test_btn.grid(row=0, column=6)

#         tk.Label(self.root, text="전압 시퀀스 (V / s)").grid(row=1, column=0, columnspan=2)

#         tk.Label(self.root, text="Device Info:").grid(row=9, column=0, sticky="e")
#         self.device_info_var = tk.StringVar()
#         tk.Label(self.root, textvariable=self.device_info_var, width=50, anchor="w").grid(row=9, column=1, columnspan=4, sticky="w")

#         self.sequence_entries = []
#         for i in range(5):
#             volt_entry = tk.Entry(self.root, width=10)
#             time_entry = tk.Entry(self.root, width=10)
#             volt_entry.grid(row=i+2, column=0)
#             time_entry.grid(row=i+2, column=1)
#             self.sequence_entries.append((volt_entry, time_entry))

#         tk.Label(self.root, text="전압").grid(row=1, column=2)
#         tk.Label(self.root, text="전류").grid(row=1, column=3)
#         tk.Label(self.root, text="온도").grid(row=1, column=4)

#         self.voltage_var = tk.StringVar()
#         self.current_var = tk.StringVar()
#         self.temp_var = tk.StringVar()

#         tk.Label(self.root, textvariable=self.voltage_var, width=10).grid(row=2, column=2)
#         tk.Label(self.root, textvariable=self.current_var, width=10).grid(row=2, column=3)
#         tk.Label(self.root, textvariable=self.temp_var, width=10).grid(row=2, column=4)

#         # ───────────── 명령어 입력 및 실행 버튼 ─────────────
#         tk.Label(self.root, text="SCPI 명령어:").grid(row=7, column=0, sticky="e")

#         self.command_entry = tk.Entry(self.root, width=60)
#         self.command_entry.grid(row=7, column=1, columnspan=3, sticky="w")

#         self.send_btn = tk.Button(self.root, text="전송", command=self.send_command)
#         self.send_btn.grid(row=7, column=4)

#         self.log_box = tk.Text(self.root, height=10, width=80)
#         self.log_box.grid(row=8, column=0, columnspan=7)

#     def connect(self):
#         resource = self.txt_resource.get().strip()
#         try:
#             if resource.startswith("USB"):
#                 self.instrument = self.rm.open_resource(resource)
#                 self.connection_type = "USB"

#                 idn = self.instrument.query("*IDN?")
#                 self.device_info_var.set(idn.strip())
    
#             elif resource.startswith("COM"):
#                 self.serial = serial.Serial(resource, baudrate=9600, timeout=2)
#                 self.connection_type = "SERIAL"

#                 self.serial.write(b'*IDN?\n')
#                 time.sleep(0.5)
#                 idn = self.serial.readline().decode().strip()
#                 self.device_info_var.set(idn)
            
#             elif ":" in resource:
#                 ip, port = resource.split(":")
#                 self.socket = socket.create_connection((ip, int(port)), timeout=2)
#                 self.connection_type = "LAN"

#                 self.socket.sendall(b'*IDN?\n')
#                 idn = self.socket.recv(1024).decode().strip()
#                 self.device_info_var.set(idn)
            

#             self.connect_btn.config(state=tk.DISABLED)
#             self.disconnect_btn.config(state=tk.NORMAL)
#             self.start_test_btn.config(state=tk.NORMAL)
#             self.log("장비 연결 성공!")

        
#         except Exception as e:
#             messagebox.showerror("오류", f"연결 실패: {str(e)}")

#     def disconnect(self):
#         try:
#             if self.connection_type == "USB" and self.instrument:
#                 self.instrument.close()
#             elif self.connection_type == "SERIAL" and self.serial:
#                 self.serial.close()
#             elif self.connection_type == "LAN" and self.socket:
#                 self.socket.close()

#             self.connect_btn.config(state=tk.NORMAL)
#             self.disconnect_btn.config(state=tk.DISABLED)
#             self.start_test_btn.config(state=tk.DISABLED)
#             self.log("연결 해제 완료")
#         except Exception as e:
#             self.log(f"해제 오류: {e}")

#     def get_sequence(self):
#         sequence = []
#         for volt_entry, time_entry in self.sequence_entries:
#             v = volt_entry.get().strip()
#             t = time_entry.get().strip()
#             if v and t:
#                 sequence.append((float(v), float(t)))
#         return sequence

#     def start_test(self):
#         self.open_log_file()
#         threading.Thread(target=self.run_test_sequence, daemon=True).start()

#     def run_test_sequence(self):
#         try:
#             self.write("INP ON")
#             for voltage, duration in self.get_sequence():
#                 self.write(f"VOLT {voltage}")
#                 self.write("OUTP ON")
#                 self.log(f"{voltage}V 설정, {duration}초 측정 시작")

#                 start = time.time()
#                 while time.time() - start < duration:
#                     self.measure_and_log()
#                     time.sleep(0.5)

#             self.write("OUTP OFF")
#             self.write("INP OFF")
#             self.csv_file.close()
#             self.log("테스트 및 로깅 완료")
#         except Exception as e:
#             self.log(f"오류 발생: {e}")

#     def write(self, command):
#         if self.connection_type == "USB":
#             self.instrument.write(command)
#         elif self.connection_type == "SERIAL":
#             self.serial.write((command + "\n").encode())
#         elif self.connection_type == "LAN":
#             self.socket.sendall((command + "\n").encode())

#     def query(self, command):
#         self.write(command)
#         if self.connection_type == "USB":
#             return self.instrument.read().strip()
#         elif self.connection_type == "SERIAL":
#             return self.serial.readline().decode().strip()
#         elif self.connection_type == "LAN":
#             return self.socket.recv(1024).decode().strip()
#         return ""

#     def measure_and_log(self):
#         volt = self.query("MEAS:VOLT?")
#         curr = self.query("MEAS:CURR?")
#         temp = self.query("MEAS:TEMP?") if self.has_temp else "N/A"

#         timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
#         self.csv_writer.writerow([timestamp, volt, curr, temp])
#         self.voltage_var.set(volt)
#         self.current_var.set(curr)
#         self.temp_var.set(temp)

#     def open_log_file(self):
#         self.csv_file = open("result.csv", "w", newline="")
#         self.csv_writer = csv.writer(self.csv_file)
#         self.csv_writer.writerow(["Timestamp", "Voltage", "Current", "Temperature"])

#     def log(self, text):
#         self.log_box.insert(tk.END, text + "\n")
#         self.log_box.see(tk.END)

#     def send_command(self):
#         command = self.command_entry.get().strip()
#         if not command:
#             self.log("명령어를 입력하세요.")
#             return

#         try:
#         # 명령 전송 + 응답 받기
#             if self.connection_type == "USB":
#                 if command.endswith("?"):
#                     response = self.instrument.query(command)
#                 else:
#                     self.instrument.write(command)
#                     response = "명령 전송 완료"

#             elif self.connection_type == "SERIAL":
#                 self.serial.write((command + "\n").encode())
#                 if command.endswith("?"):
#                     time.sleep(0.3)
#                     response = self.serial.readline().decode().strip()
#                 else:
#                     response = "명령 전송 완료"

#             elif self.connection_type == "LAN":
#                 self.socket.sendall((command + "\n").encode())
#                 if command.endswith("?"):
#                     response = self.socket.recv(1024).decode().strip()
#                 else:
#                     response = "명령 전송 완료"

#             else:
#                 response = "장비가 연결되어 있지 않습니다."

#             self.log(f"> {command}\n{response}")

#         except Exception as e:
#             self.log(f"오류: {e}")


# if __name__ == "__main__":
#     root = tk.Tk()
#     app = PowerAnalyzerGUI(root)
#     root.mainloop()

import tkinter as tk
from tkinter import messagebox
import pyvisa
import serial
import socket
import csv
import time
import threading


class PowerAnalyzerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("APT-6020 Power Analyzer Test System")
        self.connection_type = None
        self.instrument = None
        self.serial = None
        self.socket = None
        self.csv_file = None
        self.csv_writer = None
        self.has_temp = False  # APT-6020은 온도 측정 기능 없음
        self.is_testing = False
        self.test_thread = None

        self.rm = pyvisa.ResourceManager()
        self.build_gui()

    def build_gui(self):
        # 연결 설정
        tk.Label(self.root, text="장비 주소:").grid(row=0, column=0)
        self.txt_resource = tk.Entry(self.root, width=40)
        self.txt_resource.grid(row=0, column=1, columnspan=3)
        self.txt_resource.insert(0, "USB0::0x2A8D::0x1301::INSTR")

        self.connect_btn = tk.Button(self.root, text="연결", command=self.connect)
        self.connect_btn.grid(row=0, column=4)

        self.disconnect_btn = tk.Button(self.root, text="해제", state=tk.DISABLED, command=self.disconnect)
        self.disconnect_btn.grid(row=0, column=5)

        self.start_test_btn = tk.Button(self.root, text="테스트 시작", state=tk.DISABLED, command=self.start_test)
        self.start_test_btn.grid(row=0, column=6)

        self.stop_test_btn = tk.Button(self.root, text="테스트 중지", state=tk.DISABLED, command=self.stop_test)
        self.stop_test_btn.grid(row=0, column=7)

        # 전압 시퀀스 설정
        tk.Label(self.root, text="전압 시퀀스 설정", font=("Arial", 12, "bold")).grid(row=1, column=0, columnspan=2)
        tk.Label(self.root, text="전압 (V)").grid(row=2, column=0)
        tk.Label(self.root, text="시간 (s)").grid(row=2, column=1)

        self.sequence_entries = []
        for i in range(5):
            volt_entry = tk.Entry(self.root, width=10)
            time_entry = tk.Entry(self.root, width=10)
            volt_entry.grid(row=i+3, column=0)
            time_entry.grid(row=i+3, column=1)
            self.sequence_entries.append((volt_entry, time_entry))

        # 샘플링 속도 설정
        tk.Label(self.root, text="샘플링 간격 (s):").grid(row=8, column=0)
        self.sampling_entry = tk.Entry(self.root, width=10)
        self.sampling_entry.grid(row=8, column=1)
        self.sampling_entry.insert(0, "0.5")

        # 실시간 측정값 표시
        tk.Label(self.root, text="실시간 측정값", font=("Arial", 12, "bold")).grid(row=1, column=2, columnspan=3)
        tk.Label(self.root, text="전압 (V)").grid(row=2, column=2)
        tk.Label(self.root, text="전류 (A)").grid(row=2, column=3)
        tk.Label(self.root, text="전력 (W)").grid(row=2, column=4)

        self.voltage_var = tk.StringVar(value="0.0")
        self.current_var = tk.StringVar(value="0.0")
        self.power_var = tk.StringVar(value="0.0")

        tk.Label(self.root, textvariable=self.voltage_var, width=12, relief="sunken").grid(row=3, column=2)
        tk.Label(self.root, textvariable=self.current_var, width=12, relief="sunken").grid(row=3, column=3)
        tk.Label(self.root, textvariable=self.power_var, width=12, relief="sunken").grid(row=3, column=4)

        # 장비 정보 표시
        tk.Label(self.root, text="장비 정보:").grid(row=9, column=0, sticky="e")
        self.device_info_var = tk.StringVar()
        tk.Label(self.root, textvariable=self.device_info_var, width=60, anchor="w").grid(row=9, column=1, columnspan=6, sticky="w")

        # 명령어 입력 및 실행
        tk.Label(self.root, text="SCPI 명령어:").grid(row=10, column=0, sticky="e")
        self.command_entry = tk.Entry(self.root, width=50)
        self.command_entry.grid(row=10, column=1, columnspan=4, sticky="w")
        self.send_btn = tk.Button(self.root, text="전송", command=self.send_command)
        self.send_btn.grid(row=10, column=5)

        # 로그 창
        self.log_box = tk.Text(self.root, height=12, width=100)
        self.log_box.grid(row=11, column=0, columnspan=8)

    def connect(self):
        resource = self.txt_resource.get().strip()
        try:
            if resource.startswith("USB"):
                self.instrument = self.rm.open_resource(resource)
                self.instrument.timeout = 5000  # 5초 타임아웃
                self.connection_type = "USB"

                # APT-6020 특화 초기화
                idn = self.instrument.query("*IDN?")
                self.device_info_var.set(idn.strip())
                
                # 초기 설정
                self.instrument.write("*RST")  # 리셋
                time.sleep(1)
                self.instrument.write("AR 1")  # MANUAL 모드로 설정
                
            elif resource.startswith("COM"):
                self.serial = serial.Serial(resource, baudrate=9600, timeout=5)
                self.connection_type = "SERIAL"
                
                self.serial.write(b'*IDN?\n')
                time.sleep(0.5)
                idn = self.serial.readline().decode().strip()
                self.device_info_var.set(idn)
                
                # 초기 설정
                self.serial.write(b'*RST\n')
                time.sleep(1)
                self.serial.write(b'AR 1\n')
            
            elif ":" in resource:
                ip, port = resource.split(":")
                self.socket = socket.create_connection((ip, int(port)), timeout=5)
                self.connection_type = "LAN"
                
                self.socket.sendall(b'*IDN?\n')
                idn = self.socket.recv(1024).decode().strip()
                self.device_info_var.set(idn)
                
                # 초기 설정
                self.socket.sendall(b'*RST\n')
                time.sleep(1)
                self.socket.sendall(b'AR 1\n')

            self.connect_btn.config(state=tk.DISABLED)
            self.disconnect_btn.config(state=tk.NORMAL)
            self.start_test_btn.config(state=tk.NORMAL)
            self.log("APT-6020 연결 성공!")
            self.log("MANUAL 모드로 설정됨")
            
        except Exception as e:
            messagebox.showerror("오류", f"연결 실패: {str(e)}")
            self.log(f"연결 실패: {str(e)}")

    def disconnect(self):
        try:
            if self.is_testing:
                self.stop_test()
                
            if self.connection_type == "USB" and self.instrument:
                self.instrument.write("RESET")  # 출력 종료
                self.instrument.close()
            elif self.connection_type == "SERIAL" and self.serial:
                self.serial.write(b'RESET\n')
                self.serial.close()
            elif self.connection_type == "LAN" and self.socket:
                self.socket.sendall(b'RESET\n')
                self.socket.close()

            self.connect_btn.config(state=tk.NORMAL)
            self.disconnect_btn.config(state=tk.DISABLED)
            self.start_test_btn.config(state=tk.DISABLED)
            self.stop_test_btn.config(state=tk.DISABLED)
            self.log("연결 해제 완료")
            
        except Exception as e:
            self.log(f"해제 오류: {e}")

    def get_sequence(self):
        sequence = []
        for volt_entry, time_entry in self.sequence_entries:
            v = volt_entry.get().strip()
            t = time_entry.get().strip()
            if v and t:
                try:
                    voltage = float(v)
                    duration = float(t)
                    if 0 <= voltage <= 300:  # APT-6020 전압 범위
                        sequence.append((voltage, duration))
                    else:
                        self.log(f"경고: 전압 {voltage}V는 범위를 벗어남 (0-300V)")
                except ValueError:
                    self.log(f"경고: 잘못된 값 - 전압: {v}, 시간: {t}")
        return sequence

    def start_test(self):
        sequence = self.get_sequence()
        if not sequence:
            messagebox.showwarning("경고", "전압 시퀀스를 설정해주세요.")
            return
            
        self.is_testing = True
        self.start_test_btn.config(state=tk.DISABLED)
        self.stop_test_btn.config(state=tk.NORMAL)
        
        self.open_log_file()
        self.test_thread = threading.Thread(target=self.run_test_sequence, args=(sequence,), daemon=True)
        self.test_thread.start()

    def stop_test(self):
        self.is_testing = False
        self.start_test_btn.config(state=tk.NORMAL)
        self.stop_test_btn.config(state=tk.DISABLED)
        
        try:
            self.write("RESET")  # 출력 종료
            self.log("테스트 중지됨")
        except Exception as e:
            self.log(f"테스트 중지 오류: {e}")

    def run_test_sequence(self, sequence):
        try:
            sampling_interval = float(self.sampling_entry.get()) if self.sampling_entry.get() else 0.5
            
            self.log("테스트 시퀀스 시작")
            
            for i, (voltage, duration) in enumerate(sequence):
                if not self.is_testing:
                    break
                    
                self.log(f"단계 {i+1}: {voltage}V, {duration}초")
                
                # 전압 설정
                self.write(f"VOLT {voltage}")
                time.sleep(0.5)
                
                # 출력 시작
                self.write("TEST")
                time.sleep(1)
                
                # 측정 시작
                start_time = time.time()
                while time.time() - start_time < duration and self.is_testing:
                    self.measure_and_log()
                    time.sleep(sampling_interval)
                
                # 출력 종료
                self.write("RESET")
                time.sleep(1)
                
            self.log("모든 테스트 시퀀스 완료")
            
        except Exception as e:
            self.log(f"테스트 오류: {e}")
        finally:
            self.is_testing = False
            self.start_test_btn.config(state=tk.NORMAL)
            self.stop_test_btn.config(state=tk.DISABLED)
            if self.csv_file:
                self.csv_file.close()
                self.log("결과 파일 저장 완료: result.csv")

    def write(self, command):
        try:
            if self.connection_type == "USB":
                self.instrument.write(command)
            elif self.connection_type == "SERIAL":
                self.serial.write((command + "\n").encode())
            elif self.connection_type == "LAN":
                self.socket.sendall((command + "\n").encode())
        except Exception as e:
            self.log(f"명령 전송 오류: {e}")

    def query(self, command):
        try:
            if self.connection_type == "USB":
                return self.instrument.query(command).strip()
            elif self.connection_type == "SERIAL":
                self.serial.write((command + "\n").encode())
                time.sleep(0.3)
                return self.serial.readline().decode().strip()
            elif self.connection_type == "LAN":
                self.socket.sendall((command + "\n").encode())
                return self.socket.recv(1024).decode().strip()
        except Exception as e:
            self.log(f"쿼리 오류: {e}")
            return "ERROR"

    def measure_and_log(self):
        try:
            # APT-6020 특화 측정 명령어 사용
            volt = self.query("TDVOLT?")
            curr = self.query("TDCURR?")
            power = self.query("TDP?")
            
            # GUI 업데이트
            self.voltage_var.set(f"{volt} V")
            self.current_var.set(f"{curr} A")
            self.power_var.set(f"{power} W")
            
            # CSV 로깅
            if self.csv_writer:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                self.csv_writer.writerow([timestamp, volt, curr, power])
                self.csv_file.flush()
                
        except Exception as e:
            self.log(f"측정 오류: {e}")

    def open_log_file(self):
        try:
        # 현재 시간으로 타임스탬프 생성
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"result_{timestamp}.csv"
        
            self.csv_file = open(filename, "w", newline="")
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow(["Timestamp", "Voltage(V)", "Current(A)", "Power(W)"])
        
            self.log(f"로그 파일 생성: {filename}")
        
        except Exception as e:
            self.log(f"로그 파일 생성 오류: {e}")

    def log(self, text):
        timestamp = time.strftime("%H:%M:%S")
        self.log_box.insert(tk.END, f"[{timestamp}] {text}\n")
        self.log_box.see(tk.END)
        self.root.update()

    def send_command(self):
        command = self.command_entry.get().strip()
        if not command:
            self.log("명령어를 입력하세요.")
            return

        try:
            if command.endswith("?"):
                response = self.query(command)
                self.log(f"> {command}")
                self.log(f"< {response}")
            else:
                self.write(command)
                self.log(f"> {command}")
                self.log("< 명령 전송 완료")
                
        except Exception as e:
            self.log(f"명령 전송 오류: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = PowerAnalyzerGUI(root)
    root.mainloop()


# :SOURCE:VOLTAGE <V> → 원하는 V 설정

# :OUTPUT ON → 부하 작동 시작

# 측정 → :MEASURE:VOLTAGE?, :MEASURE:CURRENT?, :MEASURE:TEMPERATURE?

# :OUTPUT OFF → 출력 종료

# (선택) :OUTPUT:STATe? → 출력 상태 확인

# # 1. 출력 전압 설정

# # :SOURce:VOLTage <value>
# # 예: :SOUR:VOLT 220 → 220V로 설정

# # 2. 출력 ON/OFF

# # :OUTPut ON
# # :OUTPut OFF
# # 3. 측정 명령어

# # :MEASure:VOLTage?
# # :MEASure:CURRent?
# # :MEASure:TEMPerature?