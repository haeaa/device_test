import tkinter as tk
from tkinter import filedialog, messagebox
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
        self.save_folder = None
        self.dl_currents = {}
        self.build_gui()
    def build_gui(self):
        labels = ["Power Supply", "Electronic Load", "온도 센서", "Power Meter"]
        self.device_entries = {}
        for i, label in enumerate(labels):
            tk.Label(self.root, text=label).grid(row=i, column=0)
            entry = tk.Entry(self.root, width=40)
            entry.grid(row=i, column=1, columnspan=3)
            self.device_entries[label] = entry

        self.connect_btn = tk.Button(self.root, text="장비 연결", command=self.connect_all)
        self.connect_btn.grid(row=0, column=4, rowspan=4, sticky="ns")

        # 전압 시퀀스, 주파수, 대기 시간, 샘플링 간격
        tk.Label(self.root, text="전압 시퀀스 (V):").grid(row=4, column=0)
        self.voltage_entry = tk.Entry(self.root, width=30)
        self.voltage_entry.grid(row=4, column=1)
        self.voltage_entry.insert(0, "90,264")

        tk.Label(self.root, text="주파수 (Hz):").grid(row=5, column=0)
        self.freq_entry = tk.Entry(self.root, width=10)
        self.freq_entry.grid(row=5, column=1)
        self.freq_entry.insert(0, "50")

        tk.Label(self.root, text="대기 시간 (s):").grid(row=6, column=0)
        self.wait_entry = tk.Entry(self.root, width=10)
        self.wait_entry.grid(row=6, column=1)
        self.wait_entry.insert(0, "300")

        tk.Label(self.root, text="샘플링 간격 (s):").grid(row=7, column=0)
        self.sampling_entry = tk.Entry(self.root, width=10)
        self.sampling_entry.grid(row=7, column=1)
        self.sampling_entry.insert(0, "5")

        # DL 다채널 전류 설정
        tk.Label(self.root, text="DL 채널별 전류 (A):").grid(row=8, column=0, sticky="w")
        self.dl_current_entries = {}
        for ch in range(1, 6):
            tk.Label(self.root, text=f"{ch}CH").grid(row=8, column=ch)
            entry = tk.Entry(self.root, width=6)
            entry.grid(row=9, column=ch)
            entry.insert(0, "5.0")
            self.dl_current_entries[ch] = entry

        # HR 온도센서 채널 설정
        tk.Label(self.root, text="온도센서 채널:").grid(row=10, column=0)
        self.hr_channel_entry = tk.Entry(self.root, width=5)
        self.hr_channel_entry.grid(row=10, column=1)
        self.hr_channel_entry.insert(0, "1")

        # Power Meter 표시 (측정된 값 실시간 보기용)
        self.pm_v_label = tk.Label(self.root, text="PM V: ---")
        self.pm_v_label.grid(row=11, column=0)
        self.pm_a_label = tk.Label(self.root, text="PM A: ---")
        self.pm_a_label.grid(row=11, column=1)
        self.pm_hz_label = tk.Label(self.root, text="PM Hz: ---")
        self.pm_hz_label.grid(row=11, column=2)

        # 폴더 지정 버튼
        self.folder_btn = tk.Button(self.root, text="폴더 지정", command=self.select_folder)
        self.folder_btn.grid(row=12, column=0)

        # 시작 / 중지 버튼
        self.start_test_btn = tk.Button(self.root, text="시작", command=self.start_test)
        self.start_test_btn.grid(row=12, column=1)

        self.stop_test_btn = tk.Button(self.root, text="중지", command=self.stop_test)
        self.stop_test_btn.grid(row=12, column=2)

        self.log_box = tk.Text(self.root, height=15, width=100)
        self.log_box.grid(row=13, column=0, columnspan=5)

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
            frequency = float(self.freq_entry.get())
            wait_time = float(self.wait_entry.get())
            sampling_interval = float(self.sampling_entry.get())
            hr_channel = self.hr_channel_entry.get().strip()

            dl_currents = {}
            for ch in range(1, 6):
                val = self.dl_current_entries[ch].get().strip()
                if val:
                    dl_currents[ch] = float(val)

            if not self.save_folder:
                messagebox.showwarning("경고", "저장 폴더가 지정되지 않았습니다.")
                return

        except Exception as e:
            self.log(f"입력값 오류: {e}")
            messagebox.showerror("입력값 오류", str(e))
            return

        self.voltages = voltages
        self.frequency = frequency
        self.wait_time = wait_time
        self.sampling_interval = sampling_interval
        self.hr_channel = hr_channel
        self.dl_currents = dl_currents

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
        header = ["Time", "Set_V", "Set_Hz"]
        for ch in range(1, 6):
            header.extend([f"DL{ch}_V", f"DL{ch}_A"])
        header.extend(["PM_V", "PM_A", "PM_Hz", "Temperature"])
        self.csv_writer.writerow(header)
        self.log(f"CSV 파일 생성 완료: {filename}")

    def run_test_sequence(self):
        try:
            ps_label = "Power Supply"
            dl_label = "Electronic Load"
            hr_label = "온도 센서"
            pm_label = "Power Meter"

            for v in self.voltages:
                if not self.is_testing:
                    break
                self.log(f"전압 {v}V, 주파수 {self.frequency}Hz 설정 중")
                time.sleep(0.5)
                if ps_label in self.instrument:
                    try:
                        self.write(ps_label, "*RST")
                        time.sleep(1)
                        self.write(ps_label, f"VOLT {v}")
                        self.write(ps_label, f"FREQ {self.frequency}")
                        self.write(ps_label, "TEST")
                        time.sleep(1)
                    except Exception as e:
                        self.log(f"Power Supply 설정 오류: {e}")

                if dl_label in self.instrument:
                    try:
                        self.write(dl_label, ":MODE CC")
                        for ch, current in self.dl_currents.items():
                            self.write(dl_label, f":CHAN {ch}")
                            self.write(dl_label, f":CURR {current}")
                            self.write(dl_label, ":LOAD ON")
                    except Exception as e:
                        self.log(f"Electronic Load 설정 오류: {e}")

                start_time = time.time()
                while time.time() - start_time < self.wait_time:
                    if not self.is_testing:
                        break
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    row = [timestamp, v, self.frequency]
                    try:
                        if dl_label in self.instrument:
                            for ch in range(1, 6):
                                self.write(dl_label, f":CHAN {ch}")
                                val_v = self.query(dl_label, ":MEAS:VOLT?")
                                val_a = self.query(dl_label, ":MEAS:CURR?")
                                row.append(float(val_v) if val_v else "N/A")
                                row.append(float(val_a) if val_a else "N/A")
                        else:
                            row.extend(["N/A", "N/A"] * 5)

                        pm_v = self.query(pm_label, ":MEAS:VOLT?") if pm_label in self.instrument else "N/A"
                        pm_a = self.query(pm_label, ":MEAS:CURR?") if pm_label in self.instrument else "N/A"
                        pm_hz = self.query(pm_label, ":MEAS:FREQ?") if pm_label in self.instrument else "N/A"

                        self.pm_v_label.config(text=f"PM V: {pm_v}")
                        self.pm_a_label.config(text=f"PM A: {pm_a}")
                        self.pm_hz_label.config(text=f"PM Hz: {pm_hz}")

                        row.append(float(pm_v) if pm_v else "N/A")
                        row.append(float(pm_a) if pm_a else "N/A")
                        row.append(float(pm_hz) if pm_hz else "N/A")

                        hr_val = self.query(hr_label, f":VAL{self.hr_channel}:VAL?") if hr_label in self.instrument else "N/A"
                        row.append(float(hr_val) if hr_val else "N/A")

                    except Exception as e:
                        self.log(f"측정 오류: {e}")
                        row.extend(["ERR"] * 13)

                    self.csv_writer.writerow(row)
                    self.csv_file.flush()
                    self.log(f"[{timestamp}] 측정 완료 → {row}")
                    time.sleep(self.sampling_interval)

                if dl_label in self.instrument:
                    for ch in range(1, 6):
                        self.write(dl_label, f":CHAN {ch}")
                        self.write(dl_label, ":LOAD OFF")
                if ps_label in self.instrument:
                    self.write(ps_label, "*RST")
                time.sleep(1)

            self.log("모든 테스트 완료")

        except Exception as e:
            self.log(f"테스트 시퀀스 오류: {e}")
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
