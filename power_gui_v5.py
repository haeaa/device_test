# 통합 전력/온도 테스트 시스템 - Flowchart 기반 리팩토링 코드

import tkinter as tk
from tkinter import messagebox,filedialog
import pyvisa
import serial
import socket
import threading
import csv
import time
import os
from datetime import datetime

class PowerTestSystem:
    def __init__(self, root):
        self.root = root
        self.root.title("통합 테스트 시스템")

        self.rm = pyvisa.ResourceManager()
        self.instrument = {}
        self.connection_type = {}

        self.is_testing = False
        self.csv_file = None
        self.csv_writer = None

        self.dynamic_current_entries = {}
        self.save_folder = os.getcwd()

        self.setup_ui()

    def setup_ui(self):
        # 장비 주소 입력
        self.device_entries = {}
        labels = ["Power Supply", "Electronic Load", "Power Meter", "Hybrid Recorder"]
        for i, label in enumerate(labels):
            tk.Label(self.root, text=label).grid(row=i, column=0)
            entry = tk.Entry(self.root, width=40)
            entry.grid(row=i, column=1, columnspan=3)
            self.device_entries[label] = entry
        tk.Button(self.root, text="장비 연결", command=self.connect_all).grid(row=0, column=4, rowspan=2)
        tk.Button(self.root, text="연결 해제", command=self.disconnect_all).grid(row=2, column=4, rowspan=2)

        # 전압/주파수 입력
        tk.Label(self.root, text="전압(Vac,콤마):").grid(row=4, column=0)
        self.voltage_entry = tk.Entry(self.root)
        self.voltage_entry.grid(row=4, column=1)
        self.voltage_entry.insert(0, "90,264")

        tk.Label(self.root, text="주파수(Hz,콤마):").grid(row=4, column=2)
        self.freq_entry = tk.Entry(self.root)
        self.freq_entry.grid(row=4, column=3)
        self.freq_entry.insert(0, "50,60")

        # 시퀀스 채널 설정
        tk.Button(self.root, text="채널 생성", command=self.generate_channel_fields).grid(row=4, column=4)

        # 대기/샘플링 시간
        tk.Label(self.root, text="대기시간(s):").grid(row=5, column=0)
        self.wait_entry = tk.Entry(self.root)
        self.wait_entry.grid(row=5, column=1)
        self.wait_entry.insert(0, "5")  # 3시간

        tk.Label(self.root, text="샘플링 간격(s):").grid(row=5, column=2)
        self.sampling_entry = tk.Entry(self.root)
        self.sampling_entry.grid(row=5, column=3)
        self.sampling_entry.insert(0, "5")

        # 저장 폴더 지정
        tk.Label(self.root, text="저장 폴더:").grid(row=6, column=0)
        self.folder_label = tk.Label(self.root, text=self.save_folder, anchor="w")
        self.folder_label.grid(row=6, column=1, columnspan=3, sticky="w")
        tk.Button(self.root, text="폴더 지정", command=self.select_folder).grid(row=6, column=4)

        # 채널별 설정
        self.channel_frame = tk.Frame(self.root)
        self.channel_frame.grid(row=7, column=0, columnspan=5, sticky="w")

        # 버튼
        tk.Button(self.root, text="테스트 시작", command=self.start_test).grid(row=8, column=0, columnspan=2)
        tk.Button(self.root, text="테스트 중지", command=self.stop_test).grid(row=8, column=2, columnspan=2)

        self.log_box = tk.Text(self.root, height=15, width=100)
        self.log_box.grid(row=9, column=0, columnspan=5)

    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.save_folder = folder
            self.folder_label.config(text=self.save_folder)

    def generate_channel_fields(self):
        for widget in self.channel_frame.winfo_children():
            widget.destroy()
        self.dynamic_current_entries.clear()
        voltages = [v.strip() for v in self.voltage_entry.get().split(",") if v.strip()]
        for v in voltages:
            frame = tk.Frame(self.channel_frame)
            frame.pack(anchor="w")
            tk.Label(frame, text=f"[{v}V] 채널:").pack(side="left")
            btn = tk.Button(frame, text="+", command=lambda vv=v: self.add_channel_row(vv))
            btn.pack(side="left")
            self.dynamic_current_entries[v] = {"frame": frame, "entries": []}

    def add_channel_row(self, voltage):
        container = self.dynamic_current_entries[voltage]
        frame = container["frame"]
        ch_num = len(container["entries"]) + 1
        label = tk.Label(frame, text=f"CH{ch_num}:")
        entry = tk.Entry(frame, width=6)
        btn = tk.Button(frame, text="-", command=lambda: self.remove_channel_entry(voltage, label, entry, btn))
        label.pack(side="left"); entry.pack(side="left"); btn.pack(side="left")
        container["entries"].append((label, entry, btn))

    def remove_channel_entry(self, v, l, e, b):
        l.destroy(); e.destroy(); b.destroy()
        self.dynamic_current_entries[v]["entries"] = [t for t in self.dynamic_current_entries[v]["entries"] if t[0] != l]

    def log(self, msg):
        self.root.after(0, lambda: (self.log_box.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n"), self.log_box.see(tk.END)))

    def connect_all(self):
        for label, entry in self.device_entries.items():
            addr = entry.get().strip()
            if not addr: continue
            try:
                if "USB" in addr or "::" in addr:
                    inst = self.rm.open_resource(addr); inst.timeout = 3000; inst.query("*IDN?")
                    self.instrument[label] = inst; self.connection_type[label] = "VISA"
                    self.log(f"{label} 연결 성공 (VISA)")
                elif addr.startswith("COM"):
                    ser = serial.Serial(addr, 9600, timeout=3)
                    self.instrument[label] = ser; self.connection_type[label] = "SERIAL"
                    self.log(f"{label} 연결 성공 (SERIAL)")
                elif ":" in addr:
                    ip, port = addr.split(":"); sock = socket.create_connection((ip, int(port)), timeout=3)
                    self.instrument[label] = sock; self.connection_type[label] = "LAN"
                    self.log(f"{label} 연결 성공 (LAN)")
            except Exception as e:
                self.log(f"{label} 연결 실패: {e}")

    def disconnect_all(self):
        for label, conn_type in self.connection_type.items():
            try:
                inst = self.instrument[label]
                if conn_type == "VISA": inst.close()
                elif conn_type == "SERIAL": inst.close()
                elif conn_type == "LAN": inst.shutdown(2); inst.close()
                self.log(f"{label} 연결 해제 완료")
            except Exception as e:
                self.log(f"{label} 연결 해제 실패: {e}")
        self.instrument.clear()
        self.connection_type.clear()


    def write(self, label, cmd):
        try:
            conn = self.connection_type.get(label)
            inst = self.instrument.get(label)
            if conn == "VISA": inst.write(cmd)
            elif conn == "SERIAL": inst.write((cmd + "\n").encode())
            elif conn == "LAN": inst.sendall((cmd + "\n").encode())
        except Exception as e:
            self.log(f"{label} 전송 오류: {e}")

    def query(self, label, cmd):
        try:
            conn = self.connection_type.get(label)
            inst = self.instrument.get(label)
            if conn == "VISA": return inst.query(cmd).strip()
            elif conn == "SERIAL": inst.write((cmd + "\n").encode()); return inst.readline().decode().strip()
            elif conn == "LAN": inst.sendall((cmd + "\n").encode()); return inst.recv(1024).decode().strip()
        except Exception as e:
            self.log(f"{label} 쿼리 오류: {e}"); return None

    def start_test(self):
        if self.is_testing:
            self.log("이미 테스트 중입니다."); return

        self.is_testing = True
        voltages = [v.strip() for v in self.voltage_entry.get().split(",") if v.strip()]
        freqs = [f.strip() for f in self.freq_entry.get().split(",") if f.strip()]
        wait_s = float(self.wait_entry.get())
        sample_s = float(self.sampling_entry.get())

        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.csv_file = open(f"result_{now}.csv", "w", newline="")
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(["시간", "전압", "채널", "설정A", "DL전류", "DL전압", "PM_V", "PM_A"])

        def _run():
            try:
                for v, hz in zip(voltages, freqs):
                    self.log(f"[PS 설정] {v}Vac, {hz}Hz")
                    self.write("Power Supply", f"VOLT {v}")
                    self.write("Power Supply", f"FREQ {hz}")
                    self.write("Power Supply", "OUTP ON")

                    self.write("Hybrid Recorder", "INIT")  # HR 기록 시작
                    self.write("Power Meter", "INIT")  # PM 기록 시작

                    container = self.dynamic_current_entries.get(v)
                    ch_settings = [(i+1, float(ent.get())) for i, (_, ent, _) in enumerate(container["entries"])]
                    for ch, setA in ch_settings:
                        self.query("Electronic Load", f"INST:NSEL {ch}")
                        self.write("Electronic Load", "FUNC CC")
                        self.write("Electronic Load", f"CURR {setA}")
                        self.write("Electronic Load", "INP ON")

                    st = time.time()
                    while self.is_testing and time.time() - st < wait_s:
                        for ch, setA in ch_settings:
                            self.query("Electronic Load", f"INST:NSEL {ch}")
                            curr = self.query("Electronic Load", "MEAS:CURR?")
                            volt = self.query("Electronic Load", "MEAS:VOLT?")
                            pm_v = self.query("Power Meter", "MEAS:VOLT?")
                            pm_a = self.query("Power Meter", "MEAS:CURR?")
                            row = [time.strftime("%H:%M:%S"), v, f"CH{ch}", setA, curr, volt, pm_v, pm_a]
                            self.csv_writer.writerow(row)
                        self.csv_file.flush()
                        time.sleep(sample_s)

                    self.write("Hybrid Recorder", "ABOR")
                    self.write("Power Meter", "ABOR")

                    for ch, _ in ch_settings:
                        self.query("Electronic Load", f"INST:NSEL {ch}")
                        self.write("Electronic Load", "INP OFF")
                    self.write("Power Supply", "OUTP OFF")
                    self.log(f"[{v}V] 테스트 종료")

            except Exception as e:
                self.log(f"오류 발생: {e}")
            finally:
                self.is_testing = False
                if self.csv_file: self.csv_file.close()

        threading.Thread(target=_run, daemon=True).start()

    def stop_test(self):
        self.is_testing = False
        self.log("테스트 중지 요청됨")

if __name__ == "__main__":
    root = tk.Tk()
    app = PowerTestSystem(root)
    root.mainloop()
