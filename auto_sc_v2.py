import tkinter as tk
from tkinter import filedialog, messagebox
import pyvisa
import serial
import socket
import threading
import csv
import time
from datetime import datetime
import os

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
        self.save_folder = None
        self.build_gui()

    def build_gui(self):
        labels = ["Power Supply", "Electronic Load", "온도 센서", "Power Meter"]
        self.device_entries = {}
        for i, label in enumerate(labels):
            tk.Label(self.root, text=label).grid(row3=i, column=0)
            entry = tk.Entry(self.root, width=40)
            entry.grid(row=i, column=1, columnspan=3)
            self.device_entries[label] = entry

        self.connect_btn = tk.Button(self.root, text="장비 연결", command=self.connect_all)
        self.connect_btn.grid(row=0, column=4, rowspan=4, sticky="ns")

        tk.Label(self.root, text="전압 시퀀스 (V):").grid(row=4, column=0)
        self.voltage_entry = tk.Entry(self.root, width=30)
        self.voltage_entry.grid(row=4, column=1)
        self.voltage_entry.insert(0, "60,90")

        tk.Label(self.root, text="대기 시간 (s):").grid(row=5, column=0)
        self.wait_entry = tk.Entry(self.root, width=10)
        self.wait_entry.grid(row=5, column=1)
        self.wait_entry.insert(0, "300")

        tk.Label(self.root, text="샘플링 간격 (s):").grid(row=6, column=0)
        self.sampling_entry = tk.Entry(self.root, width=10)
        self.sampling_entry.grid(row=6, column=1)
        self.sampling_entry.insert(0, "5")

        tk.Label(self.root, text="부하 전류 (A):").grid(row=5, column=2)
        self.current_entry = tk.Entry(self.root, width=10)
        self.current_entry.grid(row=5, column=3)
        self.current_entry.insert(0, "11.0")

        self.folder_btn = tk.Button(self.root, text="폴더 지정", command=self.select_folder)
        self.folder_btn.grid(row=7, column=0)

        self.start_test_btn = tk.Button(self.root, text="테스트 시작", command=self.start_test)
        self.start_test_btn.grid(row=7, column=1)

        self.stop_test_btn = tk.Button(self.root, text="테스트 정지", command=self.stop_test)
        self.stop_test_btn.grid(row=7, column=2)

        self.log_box = tk.Text(self.root, height=15, width=100)
        self.log_box.grid(row=8, column=0, columnspan=5)

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

    def select_folder(self):
        self.save_folder = filedialog.askdirectory()
        if self.save_folder:
            self.log(f"저장 폴더 지정됨: {self.save_folder}")

    def start_test(self):
        if not self.instrument:
            self.log("연결된 장치가 없습니다.")
            messagebox.showerror("연결 오류", "연결된 장치가 없습니다.")
            return

        try:
            voltages = [float(v.strip()) for v in self.voltage_entry.get().split(",") if v.strip()]
            wait_time = float(self.wait_entry.get())
            sampling_interval = float(self.sampling_entry.get())
            load_current = float(self.current_entry.get())
            if not self.save_folder:
                messagebox.showwarning("경고", "저장 폴더가 지정되지 않았습니다.")
                return
        except Exception as e:
            self.log(f"입력값 오류: {e}")
            messagebox.showerror("입력값 오류", str(e))
            return

        self.voltages = voltages
        self.wait_time = wait_time
        self.sampling_interval = sampling_interval
        self.load_current = load_current

        self.open_log_file()
        self.is_testing = True
        self.test_thread = threading.Thread(target=self.run_test_sequence, daemon=True)
        self.test_thread.start()

    def stop_test(self):
        self.is_testing = False
        self.log("테스트 중지 요청됨.")

    def open_log_file(self):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(self.save_folder, f"result_{timestamp}.csv")
        self.csv_file = open(filename, "w", newline="")
        self.csv_writer = csv.writer(self.csv_file)
        header = ["Time", "Set_V", "Measured_V", "Current", "Power", "Temperature", "Supply_v", "PowerMeter"]
        self.csv_writer.writerow(header)
        self.log(f"CSV 파일 생성 완료: {filename}")

    def run_test_sequence(self):
        try:
            supply_label = "Power Supply"
            load_label = "Electronic Load"
            temp_label = "온도 센서"
            power_meter_label = "Power Meter"

            for v in self.voltages:
                if not self.is_testing:
                    break
                self.log(f"전압 {v}V 설정 및 테스트 시작")
                time.sleep(0.5)
                if supply_label in self.instrument:
                    try:
                        self.write(supply_label, "*RST")
                        time.sleep(1)
                        self.write(supply_label, "AR 1")
                        time.sleep(1)
                        self.write(supply_label, f"VOLT {v}")
                        time.sleep(1)
                        self.write(supply_label, "TEST")
                        time.sleep(1)
                    except Exception as e:
                        self.log(f"Power Supply 명령 오류: {e}")

                if load_label in self.instrument:
                    try:
                        self.write(load_label, ":MODE CC")
                        self.write(load_label, f":CURR {self.load_current}")
                        self.write(load_label, ":LOAD ON")
                    except Exception as e:
                        self.log(f"Electronic Load 명령 오류: {e}")

                start_time = time.time()
                while time.time() - start_time < self.wait_time:
                    if not self.is_testing:
                        break
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    supply_v = temperature = voltage_meas = current_meas = power_meas = power_meter_val = "N/A"
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
                        if power_meter_label in self.instrument:
                            val = self.query(power_meter_label, ":MEAS:POW?")
                            if val is None or val == "":
                                val = self.query(power_meter_label, ":MEAS:VOLT?")
                            if val is not None:
                                power_meter_val = float(val)
                    except Exception as e:
                        self.log(f"측정 오류: {e}")

                    self.csv_writer.writerow([timestamp, v, voltage_meas, current_meas, power_meas, temperature, supply_v, power_meter_val])
                    self.csv_file.flush()
                    self.log(f"[{timestamp}] V={voltage_meas}, I={current_meas}, P={power_meas}, T={temperature}, M={power_meter_val}")
                    time.sleep(self.sampling_interval)

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
