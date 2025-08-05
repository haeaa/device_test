# import serial
# import time

# # 시리얼 포트와 통신 설정
# ser = serial.Serial(
#     port='COM5',       # PC마다 다름 (예: '/dev/ttyUSB0' for Linux)
#     baudrate=9600,
#     bytesize=serial.EIGHTBITS,
#     parity=serial.PARITY_NONE,
#     stopbits=serial.STOPBITS_ONE,
#     timeout=1,
#     xonxoff=True,  # XON/XOFF 플로우 제어 사용
# )

# def send_cmd(cmd):
#     """SCPI 명령 전송 및 응답 출력"""
#     ser.write((cmd + '\n').encode())
#     time.sleep(0.1)
#     out = ser.read_all().decode().strip()
#     if out:
#         print(f'Response: {out}')
#     return out

# def set_current_mode(channel, current):
#     # 채널 선택 (채널은 1~5, INST:NSEL 1~5)
#     send_cmd(f'INST:NSEL {channel}')
#     # 동작 모드 CC(상수전류)
#     send_cmd('FUNC CC')
#     # RANGE HIGH (ex: 0: LOW, 1: MED, 2: HIGH 등 모델별 차이 있음)
#     send_cmd('CURR:RANG HIGH')
#     # 원하는 전류 설정 (Amp 단위)
#     send_cmd(f'CURR {current}')
#     # Load ON
#     send_cmd('INP ON')

# def measure(channel):
#     send_cmd(f'INST:NSEL {channel}')
#     v = send_cmd('MEAS:VOLT?')
#     a = send_cmd('MEAS:CURR?')
#     p = send_cmd('MEAS:POW?')
#     print(f'CH{channel} => V: {v}, I: {a}, P: {p}')

# def load_off(channel):
#     send_cmd(f'INST:NSEL {channel}')
#     send_cmd('INP OFF')

# # ---------- 예시 사용 ----------
# channels = [1, 2,3,4,5]    # 1번, 2번 채널 사용한다고 가정

# try:
#     # 각 채널별로 부하 설정 및 테스트
#     for ch in channels:
#         set_current_mode(channel=ch, current=1.23)   # 각 채널에 1.23A 흐르도록
#         time.sleep(5)
#         measure(ch)
#         time.sleep(5)
#         load_off(ch)
# finally:
#     ser.close()

# -----------------------


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
            tk.Label(self.root, text=label).grid(row=i, column=0, padx=5, pady=5, sticky="w")
            entry = tk.Entry(self.root, width=40)
            entry.grid(row=i, column=1, columnspan=3, padx=5, pady=5)
            self.device_entries[label] = entry
        
        self.connect_btn = tk.Button(self.root, text="장비 연결", command=self.connect_all)
        self.connect_btn.grid(row=0, column=4, rowspan=3, sticky="ns", padx=5, pady=5)
        
        tk.Label(self.root, text="전압 시퀀스 설정 (V):").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.voltage_entry = tk.Entry(self.root, width=30)
        self.voltage_entry.grid(row=3, column=1, padx=5, pady=5)
        self.voltage_entry.insert(0, "60,90")
        
        tk.Label(self.root, text="대기 시간 (s):").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.wait_entry = tk.Entry(self.root, width=10)
        self.wait_entry.grid(row=4, column=1, padx=5, pady=5, sticky="w")
        self.wait_entry.insert(0, "60")
        
        tk.Label(self.root, text="샘플링 간격 (s):").grid(row=5, column=0, padx=5, pady=5, sticky="w")
        self.sampling_entry = tk.Entry(self.root, width=10)
        self.sampling_entry.grid(row=5, column=1, padx=5, pady=5, sticky="w")
        self.sampling_entry.insert(0, "5")
        
        # 테스트 제어 버튼들
        button_frame = tk.Frame(self.root)
        button_frame.grid(row=6, column=0, columnspan=5, pady=10)
        
        self.start_test_btn = tk.Button(button_frame, text="테스트 시작", command=self.start_test)
        self.start_test_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_test_btn = tk.Button(button_frame, text="테스트 중지", command=self.stop_test, state=tk.DISABLED)
        self.stop_test_btn.pack(side=tk.LEFT, padx=5)
        
        # 연결 상태 표시
        self.status_label = tk.Label(self.root, text="연결 상태: 대기 중", bg="lightgray")
        self.status_label.grid(row=7, column=0, columnspan=5, sticky="ew", padx=5, pady=5)
        
        # 로그 박스
        self.log_box = tk.Text(self.root, height=15, width=100)
        self.log_box.grid(row=8, column=0, columnspan=5, padx=5, pady=5)
        
        # 스크롤바 추가
        scrollbar = tk.Scrollbar(self.root, command=self.log_box.yview)
        scrollbar.grid(row=8, column=5, sticky="ns", pady=5)
        self.log_box.config(yscrollcommand=scrollbar.set)

    def log(self, text):
        def append_log():
            timestamp = time.strftime("%H:%M:%S")
            self.log_box.insert(tk.END, f"[{timestamp}] {text}\n")
            self.log_box.see(tk.END)
            # 로그가 너무 많이 쌓이면 오래된 것 삭제
            if int(self.log_box.index('end-1c').split('.')[0]) > 1000:
                self.log_box.delete('1.0', '100.0')
        self.root.after(0, append_log)

    def update_status(self, text, color="lightgray"):
        def update():
            self.status_label.config(text=f"연결 상태: {text}", bg=color)
        self.root.after(0, update)

    def connect_all(self):
        self.update_status("연결 중...", "yellow")
        connected_count = 0
        
        for label, entry in self.device_entries.items():
            address = entry.get().strip()
            if not address:
                self.log(f"{label} 주소가 입력되지 않았습니다.")
                continue
                
            try:
                if address.upper().startswith("USB") or "::" in address:
                    inst = self.rm.open_resource(address)
                    inst.timeout = 5000  # 타임아웃 증가
                    response = inst.query("*IDN?")
                    self.instrument[label] = inst
                    self.connection_type[label] = "VISA"
                    self.log(f"{label} 연결 성공 (VISA) - {response.strip()}")
                    connected_count += 1
                elif address.upper().startswith("COM"):
                    ser = serial.Serial(address, baudrate=9600, timeout=5)
                    time.sleep(0.5)  # 시리얼 연결 안정화
                    self.instrument[label] = ser
                    self.connection_type[label] = "SERIAL"
                    self.log(f"{label} 연결 성공 (SERIAL)")
                    connected_count += 1
                elif ":" in address and not "::" in address:
                    try:
                        ip, port = address.split(":")
                        sock = socket.create_connection((ip, int(port)), timeout=5)
                        self.instrument[label] = sock
                        self.connection_type[label] = "LAN"
                        self.log(f"{label} 연결 성공 (LAN)")
                        connected_count += 1
                    except ValueError:
                        raise ValueError("IP:Port 형식이 올바르지 않습니다.")
                else:
                    raise ValueError("주소 형식을 인식할 수 없습니다. (USB, COM, IP:Port 형식 지원)")
                    
            except Exception as e:
                self.log(f"{label} 연결 실패: {e}")
                # 연결 실패한 경우 정리
                if label in self.instrument:
                    try:
                        self.instrument[label].close()
                    except:
                        pass
                    del self.instrument[label]
                if label in self.connection_type:
                    del self.connection_type[label]
        
        if connected_count == len(self.device_entries):
            self.update_status("모든 장비 연결됨", "lightgreen")
        elif connected_count > 0:
            self.update_status(f"{connected_count}/{len(self.device_entries)} 장비 연결됨", "orange")
        else:
            self.update_status("연결 실패", "lightcoral")

    def write(self, label, command):
        try:
            if label not in self.instrument:
                raise Exception(f"{label}가 연결되지 않음")
                
            conn_type = self.connection_type[label]
            inst = self.instrument[label]
            
            if conn_type == "VISA":
                inst.write(command)
            elif conn_type == "SERIAL":
                inst.write((command + "\n").encode())  # \r\n으로 변경
                inst.flush()
            elif conn_type == "LAN":
                inst.sendall((command + "\n").encode())
                
        except Exception as e:
            self.log(f"{label} 명령 전송 오류: {e}")
            raise

    def query(self, label, command):
        try:
            if label not in self.instrument:
                raise Exception(f"{label}가 연결되지 않음")
                
            conn_type = self.connection_type[label]
            inst = self.instrument[label]
            
            if conn_type == "VISA":
                return inst.query(command).strip()
            elif conn_type == "SERIAL":
                inst.flushInput()  # 입력 버퍼 클리어
                inst.write((command + "\n").encode())
                inst.flush()
                time.sleep(0.5)  # 응답 대기 시간 증가
                response = inst.readline().decode().strip()
                return response
            elif conn_type == "LAN":
                inst.sendall((command + "\n").encode())
                response = inst.recv(1024).decode().strip()
                return response
                
        except Exception as e:
            self.log(f"{label} 쿼리 오류: {e}")
            return "ERROR"

    def stop_test(self):
        """테스트 중지 함수"""
        self.is_testing = False
        self.log("테스트 중지 요청됨")
        self.start_test_btn.config(state=tk.NORMAL)
        self.stop_test_btn.config(state=tk.DISABLED)

    def start_test(self):
        # 연결된 장비 확인 (하나 이상 연결되어 있으면 진행)
        connected_labels = [label for label in self.device_entries if label in self.instrument]
        if not connected_labels:
            self.log("연결된 장비가 없습니다. 최소 1개 이상 연결하세요.")
            messagebox.showerror("연결 오류", "최소 1개 이상의 장비가 연결되어야 합니다.")
            return

        # 입력값 검증
        try:
            voltage_text = self.voltage_entry.get().strip()
            if not voltage_text:
                raise ValueError("전압 시퀀스를 입력하세요.")
            voltages = [float(v.strip()) for v in voltage_text.split(",") if v.strip()]
            if not voltages:
                raise ValueError("유효한 전압값을 입력하세요.")
            
            wait_time = float(self.wait_entry.get())
            sampling_interval = float(self.sampling_entry.get())
            
            if wait_time <= 0 or sampling_interval <= 0:
                raise ValueError("대기 시간과 샘플링 간격은 0보다 커야 합니다.")
            if sampling_interval >= wait_time:
                raise ValueError("샘플링 간격은 대기 시간보다 작아야 합니다.")
                
        except ValueError as e:
            self.log(f"입력값 오류: {e}")
            messagebox.showerror("입력값 오류", str(e))
            return
        except Exception as e:
            self.log(f"예상치 못한 오류: {e}")
            messagebox.showerror("오류", str(e))
            return
        
        self.voltages = voltages
        self.wait_time = wait_time
        self.sampling_interval = sampling_interval
        
        if not self.open_log_file():
            return
            
        self.is_testing = True
        self.start_test_btn.config(state=tk.DISABLED)
        self.stop_test_btn.config(state=tk.NORMAL)
        
        self.test_thread = threading.Thread(target=self.run_test_sequence, daemon=True)
        self.test_thread.start()

    def open_log_file(self):
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"result_{timestamp}.csv"
            self.csv_file = open(filename, "w", newline="", encoding="utf-8")
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow(["Time", "Set_V", "Measured_V", "Current", "Power", "Temperature"])
            self.csv_file.flush()
            self.log(f"CSV 파일 생성 완료: {filename}")
            return True
        except Exception as e:
            self.log(f"CSV 파일 생성 오류: {e}")
            messagebox.showerror("파일 오류", f"CSV 파일을 생성할 수 없습니다: {e}")
            return False

    def run_test_sequence(self):
        try:
            supply_label = "Power Supply"
            load_label = "Electronic Load"
            temp_label = "온도 센서"
            
            self.log(f"테스트 시퀀스 시작 - 전압: {self.voltages}V")
            
            for voltage_idx, v in enumerate(self.voltages):
                if not self.is_testing:
                    self.log("테스트가 중지되었습니다.")
                    break
                    
                self.log(f"전압 {v}V 설정 및 테스트 시작 ({voltage_idx+1}/{len(self.voltages)})")
                
                # Power Supply 설정
                if supply_label in self.instrument:
                    try:
                        self.write(supply_label, "*RST")
                        time.sleep(2)
                        self.write(supply_label, "AR 1")
                        time.sleep(1)
                        self.write(supply_label, f"VOLT {v}")
                        time.sleep(1)
                        #self.write(supply_label, "CURR 2.0")
                        #time.sleep(1)
                        self.write(supply_label, "TEST") # test가 아니라 outp on으로 해야할 수도?
                        time.sleep(1)
                        # self.write(supply_label, "VOLT:LEV:IMM:AMPL " + str(v))  # 표준 SCPI 명령 사용
                        # time.sleep(1)
                        # self.write(supply_label, "CURR:LEV:IMM:AMPL 5.0")  # 전류 제한 설정
                        # time.sleep(1)
                        # self.write(supply_label, "OUTP ON")  # 출력 켜기
                        # time.sleep(2)
                        self.log(f"Power Supply 설정 완료: {v}V")
                    except Exception as e:
                        self.log(f"Power Supply 설정 오류: {e}")
                        continue
                else:
                    self.log("Power Supply 미연결: 해당 단계 건너뜀")

                # Electronic Load 설정
                # if load_label in self.instrument:
                #     try:
                #         self.write(load_label, ":MODE CC")
                #         time.sleep(0.5)
                #         self.write(load_label, ":CURR 2.0")
                #         time.sleep(0.5)
                #         self.write(load_label, ":LOAD ON")
                #         time.sleep(1)
                #         self.log("Electronic Load 설정 완료: CC 2.0A")
                #     except Exception as e:
                #         self.log(f"Electronic Load 설정 오류: {e}")
                #         continue
                # else:
                #     self.log("Electronic Load 미연결: 해당 단계 건너뜀")
                
                if load_label in self.instrument:
                    try:
                        self.write(load_label, "MODE CC,@2")
                        time.sleep(0.5)
                        self.write(load_label, "CURR 2.0,@2")
                        time.sleep(0.5)
                        self.write(load_label, "LOAD ON,@2")
                        time.sleep(1)
                        self.log("Electronic Load 설정 완료: CC 2.0A")
                    except Exception as e:
                        self.log(f"Electronic Load 설정 오류: {e}")
                        continue
                else:
                    self.log("Electronic Load 미연결: 해당 단계 건너뜀")
                

                # 데이터 수집 시작
                start_time = time.time()
                sample_count = 0
                
                while (time.time() - start_time < self.wait_time) and self.is_testing:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    try:
                        # 측정값 읽기
                        if load_label in self.instrument:
                            try:
                                voltage_meas = float(self.query(load_label, ":MEAS:VOLT?"))
                            except Exception as e:
                                voltage_meas = 0.0
                                self.log(f"VOLT 측정 오류: {e}")
                            try:
                                current_meas = float(self.query(load_label, ":MEAS:CURR?"))
                            except Exception as e:
                                current_meas = 0.0
                                self.log(f"CURR 측정 오류: {e}")
                            try:
                                power_meas = float(self.query(load_label, ":MEAS:POW?"))
                            except Exception as e:
                                power_meas = 0.0
                                self.log(f"POW 측정 오류: {e}")
                        else:
                            voltage_meas = 0.0
                            current_meas = 0.0
                            power_meas = 0.0

                        # 온도 센서 읽기
                        if temp_label in self.instrument:
                            temp_response = self.query(temp_label, ":VAL1:VAL?")
                            try:
                                temperature = float(temp_response)
                            except:
                                temperature = 0.0  # 온도 읽기 실패시 기본값
                                self.log(f"온도 읽기 실패: {temp_response}")
                        else:
                            temperature = 0.0

                        # CSV에 데이터 저장
                        self.csv_writer.writerow([timestamp, v, voltage_meas, current_meas, power_meas, temperature])
                        self.csv_file.flush()
                        
                        sample_count += 1
                        elapsed_time = int(time.time() - start_time)
                        remaining_time = int(self.wait_time - elapsed_time)
                        
                        self.log(f"[{sample_count:03d}] V={voltage_meas:.2f}V, I={current_meas:.2f}A, P={power_meas:.2f}W, T={temperature:.1f}°C (남은시간: {remaining_time}s)")
                        
                    except Exception as e:
                        self.log(f"측정 오류: {e}")
                    
                    time.sleep(self.sampling_interval)
                
                # 각 전압 단계 완료 후 정리
                if load_label in self.instrument or supply_label in self.instrument:
                    try:
                        if load_label in self.instrument:
                            self.write(load_label, ":LOAD OFF")
                            time.sleep(1)
                        if supply_label in self.instrument:
                            self.write(supply_label, "*RST")
                            time.sleep(2)
                        self.log(f"전압 {v}V 테스트 완료")
                    except Exception as e:
                        self.log(f"테스트 종료 명령 오류: {e}")
                else:
                    self.log("테스트 종료 명령: 연결된 장비 없음")
                
                # 다음 전압으로 넘어가기 전 대기
                if voltage_idx < len(self.voltages) - 1:
                    time.sleep(5)
            
            if self.is_testing:
                self.log("모든 전압 시퀀스 테스트 완료!")
            else:
                self.log("테스트가 사용자에 의해 중지되었습니다.")
                
        except Exception as e:
            self.log(f"시퀀스 실행 중 심각한 오류: {e}")
            
        finally:
            self.is_testing = False
            
            # 모든 장비 출력 끄기
            try:
                if "Electronic Load" in self.instrument:
                    self.write("Electronic Load", ":LOAD OFF")
                if "Power Supply" in self.instrument:
                    # self.write("Power Supply", "OUTP OFF")
                    self.write("Power Supply", "*RST")
            except Exception as e:
                self.log(f"장비 종료 명령 오류: {e}")
            
            # CSV 파일 닫기
            if self.csv_file:
                try:
                    self.csv_file.close()
                    self.log("CSV 파일 저장 완료")
                except Exception as e:
                    self.log(f"CSV 파일 저장 오류: {e}")
            
            # GUI 버튼 상태 복원
            self.root.after(0, lambda: (
                self.start_test_btn.config(state=tk.NORMAL),
                self.stop_test_btn.config(state=tk.DISABLED)
            ))
    
    def __del__(self):
        try:
            if hasattr(self, 'csv_file') and self.csv_file:
                self.csv_file.close()
            
            if hasattr(self, 'instrument'):
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
            
            if hasattr(self, 'rm'):
                self.rm.close()
        except Exception:
            pass

if __name__ == "__main__":
    root = tk.Tk()
    app = PowerAnalyzerGUI(root)
    root.mainloop()