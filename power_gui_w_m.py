import tkinter as tk
from tkinter import messagebox
import pyvisa
import serial
import socket
import csv
import time
import threading

# 

class DeviceConn:
    """각 단일 계측기와 연결 및 명령수행 래퍼"""
    def __init__(self, resource=None, kind=""):
        self.resource = resource
        self.kind = kind # "PowerMeter", "ElectronicLoad", "TempSensor"
        self.mode = None   # "USB", "SERIAL", "LAN"
        self.conn = None   # actual connection
        self.rm = pyvisa.ResourceManager()
        self.connected = False
        self.idn = ""
        
    def connect(self):
        if not self.resource:
            return False
        try:
            if self.resource.startswith("USB") or "::" in self.resource:
                self.conn = self.rm.open_resource(self.resource)
                self.mode = "USB"
                self.idn = self.conn.query("*IDN?").strip()
            elif self.resource.startswith("COM"):
                self.conn = serial.Serial(self.resource, baudrate=9600, timeout=2)
                self.mode = "SERIAL"
                self.conn.write(b'*IDN?\n')
                time.sleep(0.2)
                self.idn = self.conn.readline().decode().strip()
            elif ":" in self.resource:
                ip, port = self.resource.split(":")
                self.conn = socket.create_connection((ip, int(port)), timeout=2)
                self.mode = "LAN"
                self.conn.sendall(b'*IDN?\n')
                self.idn = self.conn.recv(1024).decode().strip()
            else:
                return False
            self.connected = True
            return True
        except Exception as e:
            self.conn = None
            return False

    def disconnect(self):
        try:
            if not self.connected: return
            if self.mode == "USB": self.conn.close()
            elif self.mode == "SERIAL": self.conn.close()
            elif self.mode == "LAN": self.conn.close()
        except: pass
        self.connected = False

    def write(self, cmd):
        if not self.connected: return
        if self.mode == "USB":
            self.conn.write(cmd)
        elif self.mode == "SERIAL":
            self.conn.write((cmd + "\n").encode())
        elif self.mode == "LAN":
            self.conn.sendall((cmd + "\n").encode())

    def query(self, cmd):
        """cmd는 반드시 ? 포함된 쿼리 명령어여야 """
        if not self.connected: return ""
        if self.mode == "USB":
            return self.conn.query(cmd).strip()
        elif self.mode == "SERIAL":
            self.conn.write((cmd + "\n").encode())
            time.sleep(0.2)
            return self.conn.readline().decode().strip()
        elif self.mode == "LAN":
            self.conn.sendall((cmd + "\n").encode())
            return self.conn.recv(1024).decode().strip()
        return ""


class PowerAnalyzerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("멀티 계측장비 통합 테스트시스템(파워, 로드, 온도)")
        self.csv_file = None
        self.csv_writer = None
        self.is_testing = False
        self.test_thread = None

        # 각 계측기: 주소, DeviceConn 오브젝트
        self.device_infos = {
            "PowerMeter": {"label": "Power Meter  자원주소", "conn": None, "entry": None, "idn_var": tk.StringVar()},
            "ElectronicLoad": {"label": "Electronic ( Digital ) Load 자원주소", "conn": None, "entry": None, "idn_var": tk.StringVar()},
            "TempSensor": {"label": "온도센서 자원주소", "conn": None, "entry": None, "idn_var": tk.StringVar()},
            "PowerSupply": {"label": "Power Supply 자원주소", "conn": None, "entry": None, "idn_var": tk.StringVar()},
        }

        self.build_gui()

    def build_gui(self):
        row = 0
        for kind in self.device_infos:
            tk.Label(self.root, text=self.device_infos[kind]["label"]).grid(row=row, column=0)
            self.device_infos[kind]["entry"] = tk.Entry(self.root, width=40)
            self.device_infos[kind]["entry"].grid(row=row, column=1)
            tk.Label(self.root, textvariable=self.device_infos[kind]["idn_var"], width=30, anchor="w", fg="gray").grid(row=row, column=2, columnspan=2)
            row += 1

        self.connect_btn = tk.Button(self.root, text="장비 연결", command=self.connect_all)
        self.connect_btn.grid(row=row, column=0)
        self.disconnect_btn = tk.Button(self.root, text="연결 해제", state=tk.DISABLED, command=self.disconnect_all)
        self.disconnect_btn.grid(row=row, column=1)
        self.start_test_btn = tk.Button(self.root, text="테스트 시작", state=tk.DISABLED, command=self.start_test)
        self.start_test_btn.grid(row=row, column=2)
        self.stop_test_btn = tk.Button(self.root, text="테스트 중지", state=tk.DISABLED, command=self.stop_test)
        self.stop_test_btn.grid(row=row, column=3)
        row += 1

        # 전압 시퀀스
        tk.Label(self.root, text="전압 시퀀스(V/s)").grid(row=row, column=0, columnspan=2)
        row+=1
        self.sequence_entries = []
        for i in range(5):
            volt_entry = tk.Entry(self.root, width=10)
            time_entry = tk.Entry(self.root, width=10)
            volt_entry.grid(row=row + i, column=0)
            time_entry.grid(row=row + i, column=1)
            self.sequence_entries.append((volt_entry, time_entry))
        row += 5

        tk.Label(self.root, text="샘플링 간격(s)").grid(row=row, column=0)
        self.sampling_entry = tk.Entry(self.root, width=10)
        self.sampling_entry.grid(row=row, column=1)
        self.sampling_entry.insert(0,"0.5")
        row += 1

        # 실시간 측정값
        self.value_vars = {
            "PowerMeter": [tk.StringVar(), tk.StringVar(), tk.StringVar()], # [V,A,W]
            "ElectronicLoad": [tk.StringVar(), tk.StringVar()],             # [설정, 측정A]
            "TempSensor": [tk.StringVar()],                                 # [T]
        }

        tk.Label(self.root, text="PowerMeter[V, A, W]").grid(row=row, column=0)
        tk.Label(self.root, textvariable=self.value_vars["PowerMeter"][0]).grid(row=row,column=1)
        tk.Label(self.root, textvariable=self.value_vars["PowerMeter"][1]).grid(row=row,column=2)
        tk.Label(self.root, textvariable=self.value_vars["PowerMeter"][2]).grid(row=row,column=3)
        row += 1
        tk.Label(self.root, text="Electronic Load[설정A, 측정A]").grid(row=row,column=0)
        tk.Label(self.root, textvariable=self.value_vars["ElectronicLoad"][0]).grid(row=row,column=1)
        tk.Label(self.root, textvariable=self.value_vars["ElectronicLoad"][1]).grid(row=row,column=2)
        row += 1
        tk.Label(self.root, text="온도센서[C]").grid(row=row, column=0)
        tk.Label(self.root, textvariable=self.value_vars["TempSensor"][0]).grid(row=row,column=1)
        row += 1

        self.log_box = tk.Text(self.root, height=12, width=90)
        self.log_box.grid(row=row, column=0, columnspan=4)

    def log(self, txt):
        t = time.strftime("%H:%M:%S")
        self.log_box.insert(tk.END, f"[{t}] {txt}\n")
        self.log_box.see(tk.END)
        self.root.update()

    def connect_all(self):
        result = []
        any_connected = False
        # 시도
        for kind in self.device_infos:
            resource = self.device_infos[kind]["entry"].get().strip()
            if resource != "":
                conn = DeviceConn(resource, kind)
                if conn.connect():
                    self.device_infos[kind]["conn"] = conn
                    self.device_infos[kind]["idn_var"].set(conn.idn)
                    self.log(f"{kind} 연결: {conn.idn}")
                    any_connected = True
                else:
                    self.device_infos[kind]["conn"] = None
                    self.device_infos[kind]["idn_var"].set("연결실패")
            else:
                self.device_infos[kind]["conn"] = None
                self.device_infos[kind]["idn_var"].set("(미연결)")
        # 상태반영
        if any_connected:
            self.connect_btn.config(state=tk.DISABLED)
            self.disconnect_btn.config(state=tk.NORMAL)
            self.start_test_btn.config(state=tk.NORMAL)
            self.log("최소 1개 장비 연결됨. 테스트 준비완료.")
        else:
            messagebox.showinfo("오류", "최소 하나의 장비 주소는 입력되어야 합니다.")

    def disconnect_all(self):
        for kind in self.device_infos:
            conn = self.device_infos[kind]["conn"]
            if conn: conn.disconnect()
            self.device_infos[kind]["idn_var"].set("")
        self.connect_btn.config(state=tk.NORMAL)
        self.disconnect_btn.config(state=tk.DISABLED)
        self.start_test_btn.config(state=tk.DISABLED)
        self.stop_test_btn.config(state=tk.DISABLED)
        self.log("모든 연결 해제됨.")

    def get_sequence(self):
        seq = []
        for v_entry, t_entry in self.sequence_entries:
            v = v_entry.get().strip()
            t = t_entry.get().strip()
            if v and t: 
                try:
                    vnum = float(v)
                    tnum = float(t)
                    seq.append( (vnum, tnum) )
                except: continue
        return seq

    def start_test(self):
        self.is_testing = True
        self.start_test_btn.config(state=tk.DISABLED)
        self.stop_test_btn.config(state=tk.NORMAL)
        self.open_log_file()
        seq = self.get_sequence()
        if not seq:
            messagebox.showwarning("오류", "시퀀스를 입력하세요.")
            return
        self.log("테스트 시작")
        threading.Thread(target=self.run_sequence, args=(seq,), daemon=True).start()

    def stop_test(self):
        self.is_testing = False
        self.start_test_btn.config(state=tk.NORMAL)
        self.stop_test_btn.config(state=tk.DISABLED)
        self.log("테스트 강제중지.")

    def open_log_file(self):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"result_{timestamp}.csv"
        self.csv_file = open(filename, "w", newline="")
        headers = ["Timestamp"]
        if self.device_infos["PowerMeter"]["conn"]:
            headers += ["Pwr_V", "Pwr_A", "Pwr_W"]
        if self.device_infos["ElectronicLoad"]["conn"]:
            headers += ["Load_SetA", "Load_MeasA"]
        if self.device_infos["TempSensor"]["conn"]:
            headers += ["Temp(C)"]
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(headers)
        self.log(f"로그 파일 생성: {filename}")

    def run_sequence(self, seq):
        sampling = float(self.sampling_entry.get()) if self.sampling_entry.get() else 0.5
        try:
            for i, (voltage, duration) in enumerate(seq):
                if not self.is_testing: break
                self.log(f"{i+1}단계: {voltage}V, {duration}s")
                # 파워미터 연동되었으면 전압 설정 등
                pwr = self.device_infos["PowerMeter"]["conn"]
                if pwr: 
                    pwr.write(f"VOLT {voltage}")
                    pwr.write("TEST")
                    time.sleep(0.5)
                # 일렉트로닉 로드 : 필요시 부하 설정(여기선 예시상 생략함)
                # temp센서는 설정없음
                stime = time.time()
                while time.time() - stime < duration and self.is_testing:
                    row = [ time.strftime("%Y-%m-%d %H:%M:%S") ]
                    # 파워미터
                    v = a = w = ""
                    if pwr:
                        v = pwr.query("TDVOLT?")
                        a = pwr.query("TDCURR?")
                        w = pwr.query("TDP?")
                        self.value_vars["PowerMeter"][0].set(v)
                        self.value_vars["PowerMeter"][1].set(a)
                        self.value_vars["PowerMeter"][2].set(w)
                        row += [v, a, w]
                    # 로드
                    load = self.device_infos["ElectronicLoad"]["conn"]
                    l_set = l_meas = ""
                    if load:
                        try:
                            # 예: 설정 전류값 읽기 - "CURR?", 측정전류 - "MCURR?"
                            l_set = load.query("CURR?")
                            l_meas = load.query("MCURR?")  # 부하에 따라 명령 수정
                        except: pass
                        self.value_vars["ElectronicLoad"][0].set(l_set)
                        self.value_vars["ElectronicLoad"][1].set(l_meas)
                        row += [l_set, l_meas]
                    # 온도
                    tempconn = self.device_infos["TempSensor"]["conn"]
                    temp = ""
                    if tempconn:
                        temp = tempconn.query("MEAS:TEMP?")
                        self.value_vars["TempSensor"][0].set(temp)
                        row += [temp]
                    # 기록
                    if self.csv_writer:
                        self.csv_writer.writerow(row)
                        self.csv_file.flush()
                    time.sleep(sampling)
                # 스텝 후 파워, 로드 각각 OFF (필요시)
                if pwr:
                    pwr.write("RESET")
            self.log("테스트 끝")
        except Exception as e:
            self.log(f"에러:{e}")
        self.is_testing = False
        self.start_test_btn.config(state=tk.NORMAL)
        self.stop_test_btn.config(state=tk.DISABLED)
        try:
            self.csv_file.close()
        except: pass

if __name__ == "__main__":
    root = tk.Tk()
    app = PowerAnalyzerGUI(root)
    root.mainloop()
