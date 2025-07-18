
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
import time
import csv
import serial
import socket

class PowerAnalyzerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Power Analyzer Test System")
        self.connection_type = None
        self.instrument = None
        self.serial = None
        self.socket = None
        self.csv_file = None
        self.csv_writer = None

        self.rm = pyvisa.ResourceManager()
        self.build_gui()

    def build_gui(self):
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

        tk.Label(self.root, text="전압 시퀀스 (V / s)").grid(row=1, column=0, columnspan=2)
        self.sequence_entries = []
        for i in range(5):
            volt_entry = tk.Entry(self.root, width=10)
            time_entry = tk.Entry(self.root, width=10)
            volt_entry.grid(row=i+2, column=0)
            time_entry.grid(row=i+2, column=1)
            self.sequence_entries.append((volt_entry, time_entry))

        tk.Label(self.root, text="전압").grid(row=1, column=2)
        tk.Label(self.root, text="전류").grid(row=1, column=3)
        tk.Label(self.root, text="온도").grid(row=1, column=4)

        self.voltage_var = tk.StringVar()
        self.current_var = tk.StringVar()
        self.temp_var = tk.StringVar()

        tk.Label(self.root, textvariable=self.voltage_var, width=10).grid(row=2, column=2)
        tk.Label(self.root, textvariable=self.current_var, width=10).grid(row=2, column=3)
        tk.Label(self.root, textvariable=self.temp_var, width=10).grid(row=2, column=4)

        self.log_box = tk.Text(self.root, height=10, width=80)
        self.log_box.grid(row=8, column=0, columnspan=7)

        # ───────────── 명령어 입력 및 실행 버튼 ─────────────
        tk.Label(self.root, text="SCPI 명령어:").grid(row=7, column=0, sticky="e")

        self.command_entry = tk.Entry(self.root, width=60)
        self.command_entry.grid(row=7, column=1, columnspan=3, sticky="w")

        self.send_btn = tk.Button(self.root, text="전송", command=self.send_command)
        self.send_btn.grid(row=7, column=4)

        self.log_box = tk.Text(self.root, height=10, width=80)
        self.log_box.grid(row=8, column=0, columnspan=7)

    def connect(self):
        resource = self.txt_resource.get()
        try:
            if resource.startswith("USB"):
                self.instrument = self.rm.open_resource(resource)
                self.connection_type = "USB"
            elif resource.startswith("COM"):
                self.serial = serial.Serial(resource, baudrate=9600, timeout=2)
                self.connection_type = "SERIAL"
            elif ":" in resource:
                ip, port = resource.split(":")
                self.socket = socket.create_connection((ip, int(port)), timeout=2)
                self.connection_type = "LAN"

            self.connect_btn.config(state=tk.DISABLED)
            self.disconnect_btn.config(state=tk.NORMAL)
            self.start_test_btn.config(state=tk.NORMAL)
            messagebox.showinfo("연결", "장비 연결 성공!")
        except Exception as e:
            messagebox.showerror("오류", f"연결 실패: {str(e)}")

    def disconnect(self):
        if self.connection_type == "USB" and self.instrument:
            self.instrument.close()
            self.instrument = None
        elif self.connection_type == "SERIAL" and self.serial:
            self.serial.close()
            self.serial = None
        elif self.connection_type == "LAN" and self.socket:
            self.socket.close()
            self.socket = None

        self.connect_btn.config(state=tk.NORMAL)
        self.disconnect_btn.config(state=tk.DISABLED)
        self.start_test_btn.config(state=tk.DISABLED)
        messagebox.showinfo("해제", "장비 연결 해제됨")

    def log(self, text):
        self.log_box.insert(tk.END, text + "\n")
        self.log_box.see(tk.END)

    def send_command(self, command):
        if self.connection_type == "USB":
            self.instrument.write(command)
        elif self.connection_type == "SERIAL":
            self.serial.write((command + "\n").encode())
        elif self.connection_type == "LAN":
            self.socket.sendall((command + "\n").encode())

    def query_command(self, command):
        if self.connection_type == "USB":
            return self.instrument.query(command).strip()
        elif self.connection_type == "SERIAL":
            self.serial.write((command + "\n").encode())
            return self.serial.readline().decode().strip()
        elif self.connection_type == "LAN":
            self.socket.sendall((command + "\n").encode())
            return self.socket.recv(1024).decode().strip()
        return "N/A"

    def start_test(self):
        if not (self.instrument or self.serial or self.socket):
            messagebox.showwarning("경고", "장비가 연결되어 있지 않습니다.")
            return

        try:
            with open("test_results.csv", mode="w", newline="") as file:
                self.csv_writer = csv.writer(file)
                self.csv_writer.writerow(["전압", "전류", "온도", "시간"])

                for volt_entry, time_entry in self.sequence_entries:
                    if volt_entry.get() and time_entry.get():
                        voltage = float(volt_entry.get())
                        duration = float(time_entry.get())

                        self.send_command(f":SOUR:VOLT {voltage}")
                        self.send_command(":OUTP ON")
                        start_time = time.time()

                        while time.time() - start_time < duration:
                            v = self.query_command(":MEAS:VOLT?")
                            c = self.query_command(":MEAS:CURR?")
                            t = self.query_command(":MEAS:TEMP?")

                            self.voltage_var.set(v)
                            self.current_var.set(c)
                            self.temp_var.set(t)

                            timestamp = time.strftime("%H:%M:%S")
                            self.csv_writer.writerow([v, c, t, timestamp])

                            self.log_box.insert(tk.END, f"[{timestamp}] V: {v}, I: {c}, T: {t}\n")
                            self.log_box.see(tk.END)
                            self.root.update()
                            time.sleep(1)

                        self.send_command(":OUTP OFF")

            messagebox.showinfo("완료", "테스트 완료 및 CSV 저장 완료")

        except Exception as e:
            messagebox.showerror("오류", f"테스트 중 오류 발생: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = PowerAnalyzerGUI(root)
    root.mainloop()

# 1. 출력 전압 설정

# :SOURce:VOLTage <value>
# 예: :SOUR:VOLT 220 → 220V로 설정

# 2. 출력 ON/OFF

# :OUTPut ON
# :OUTPut OFF
# 3. 측정 명령어

# :MEASure:VOLTage?
# :MEASure:CURRent?
# :MEASure:TEMPerature?