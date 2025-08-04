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
        self.dynamic_current_entries = {}  # {voltage: [(frame, label, entry)]}
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

        tk.Label(self.root, text="전압 시퀀스 설정 (V):").grid(row=4, column=0)
        self.voltage_entry = tk.Entry(self.root, width=30)
        self.voltage_entry.grid(row=4, column=1)
        self.voltage_entry.insert(0, "60,90")

        generate_btn = tk.Button(self.root, text="채널 설정 생성", command=self.generate_channel_fields)
        generate_btn.grid(row=4, column=2)

        tk.Label(self.root, text="대기 시간 (s):").grid(row=5, column=0)
        self.wait_entry = tk.Entry(self.root, width=10)
        self.wait_entry.grid(row=5, column=1)
        self.wait_entry.insert(0, "300")

        tk.Label(self.root, text="샘플링 간격 (s):").grid(row=6, column=0)
        self.sampling_entry = tk.Entry(self.root, width=10)
        self.sampling_entry.grid(row=6, column=1)
        self.sampling_entry.insert(0, "5")

        self.channel_frame = tk.Frame(self.root)
        self.channel_frame.grid(row=7, column=0, columnspan=5, sticky="w")

        self.start_test_btn = tk.Button(self.root, text="테스트 시작", command=self.start_test)
        self.start_test_btn.grid(row=8, column=0, columnspan=2)

        self.stop_test_btn = tk.Button(self.root, text="테스트 정지", command=self.stop_test)
        self.stop_test_btn.grid(row=8, column=2, columnspan=2)

        self.log_box = tk.Text(self.root, height=15, width=100)
        self.log_box.grid(row=9, column=0, columnspan=5)

    def generate_channel_fields(self):
        for widget in self.channel_frame.winfo_children():
            widget.destroy()
        self.dynamic_current_entries.clear()

        voltages = [v.strip() for v in self.voltage_entry.get().split(",") if v.strip()]
        for v in voltages:
            section_label = tk.Label(self.channel_frame, text=f"[{v}V] 채널 설정:")
            section_label.pack(anchor="w")

            # 가로 프레임 생성
            row_frame = tk.Frame(self.channel_frame)
            row_frame.pack(anchor="w", pady=2)

            add_btn = tk.Button(row_frame, text=f"{v}V 채널 +", command=lambda vv=v: self.add_channel_row(vv))
            add_btn.pack(side="left")

            self.dynamic_current_entries[v] = {
                "frame": row_frame,
                "entries": []  # list of (label, entry, button)
            }

    def add_channel_row(self, voltage):
        container = self.dynamic_current_entries[voltage]
        row_frame = container["frame"]
        ch_num = len(container["entries"]) + 1

        ch_label = tk.Label(row_frame, text=f"CH{ch_num}:")
        ch_label.pack(side="left", padx=2)

        current_entry = tk.Entry(row_frame, width=6)
        current_entry.pack(side="left", padx=2)

        del_btn = tk.Button(row_frame, text="-", command=lambda: self.remove_channel_entry(voltage, ch_label, current_entry, del_btn))
        del_btn.pack(side="left", padx=2)

        container["entries"].append((ch_label, current_entry, del_btn))
    def remove_channel_entry(self, voltage, label, entry, button):
        container = self.dynamic_current_entries[voltage]
        label.destroy()
        entry.destroy()
        button.destroy()
        container["entries"] = [triple for triple in container["entries"] if triple[0] != label]
        
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
        self.log("테스트 시작 로직을 여기에 구현하세요. self.dynamic_current_entries에서 설정값을 가져오세요.")

    def stop_test(self):
        self.is_testing = False
        self.log("테스트 중지 요청됨.")

if __name__ == "__main__":
    root = tk.Tk()
    app = PowerAnalyzerGUI(root)
    root.mainloop()
