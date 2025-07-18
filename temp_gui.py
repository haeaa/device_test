import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import csv
import pyvisa
from pyvisa.resources import MessageBasedResource


# self.visa_resource: MessageBasedResource = self.rm.open_resource(addr)
# idn = self.visa_resource.query("*IDN?")

class DeviceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("장비 측정 GUI")
        self.is_measuring = False
        self.visa_resource = None
        self.rm = pyvisa.ResourceManager()
        self.csv_file = None
        self.csv_writer = None

        self.build_gui()

    def build_gui(self):
        
        
        # 리소스 주소 입력
        tk.Label(self.root, text="VISA 주소:").grid(row=0, column=0, sticky="e")
        self.address_entry = tk.Entry(self.root, width=40)
        self.address_entry.grid(row=0, column=1)
        self.address_entry.insert(0, "USB0::0x0B21::0x0025::4333534B313830313745::INSTR")

        # 연결 버튼
        self.connect_btn = tk.Button(self.root, text="연결", command=self.connect_device)
        self.connect_btn.grid(row=0, column=2, padx=5)

        # 장치 정보
        tk.Label(self.root, text="장치 정보:").grid(row=1, column=0, sticky="e")
        self.device_info = tk.Label(self.root, text="-", anchor="w", width=40)
        self.device_info.grid(row=1, column=1, columnspan=2, sticky="w")

        # 측정값 표시
        self.fields = {}
        for i, label in enumerate(["전압 (V)", "전류 (A)", "전력 (W)", "역률"]):
            tk.Label(self.root, text=label + ":").grid(row=i + 2, column=0, sticky="e")
            self.fields[label] = tk.Label(self.root, text="-", width=20, anchor="w")
            self.fields[label].grid(row=i + 2, column=1, sticky="w")

        # 측정 버튼
        self.measure_btn = tk.Button(self.root, text="측정 시작", command=self.toggle_measurement, state="disabled")
        self.measure_btn.grid(row=6, column=1, pady=10)

    def connect_device(self):
        try:
            addr = self.address_entry.get()
            self.visa_resource = self.rm.open_resource(addr)
            idn = self.visa_resource.query("*IDN?")
            self.device_info.config(text=idn.strip())
            self.measure_btn.config(state="normal")
            messagebox.showinfo("성공", f"연결됨:\n{idn}")
        except Exception as e:
            messagebox.showerror("연결 오류", str(e))

    def toggle_measurement(self):
        if not self.is_measuring:
            self.start_measurement()
        else:
            self.stop_measurement()

    def start_measurement(self):
        self.is_measuring = True
        self.measure_btn.config(text="측정 중지")
        self.csv_file = open("measurement_log.csv", "a", newline="")
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(["timestamp", "voltage", "current", "power", "power_factor"])

        threading.Thread(target=self.measure_loop, daemon=True).start()

    def stop_measurement(self):
        self.is_measuring = False
        self.measure_btn.config(text="측정 시작")
        if self.csv_file:
            self.csv_file.close()

    def measure_loop(self):
        self.visa_resource.write("INP ON")
        while self.is_measuring:
            try:
                voltage = self.visa_resource.query("MEAS:VOLT?").strip()
                current = self.visa_resource.query("MEAS:CURR?").strip()
                power = self.visa_resource.query("MEAS:POW?").strip()
                pf = self.visa_resource.query("MEAS:PF?").strip()

                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

                self.update_gui(voltage, current, power, pf)
                self.csv_writer.writerow([timestamp, voltage, current, power, pf])

                time.sleep(0.5)
            except Exception as e:
                self.is_measuring = False
                self.measure_btn.config(text="측정 시작")
                messagebox.showerror("측정 오류", str(e))
                break
        self.visa_resource.write("INP OFF")

    def update_gui(self, voltage, current, power, pf):
        self.fields["전압 (V)"].config(text=voltage)
        self.fields["전류 (A)"].config(text=current)
        self.fields["전력 (W)"].config(text=power)
        self.fields["역률"].config(text=pf)

if __name__ == "__main__":
    root = tk.Tk()
    app = DeviceApp(root)
    root.mainloop()