## 전압루프만 돌기 ^_______^ 


import pyvisa
import pandas as pd
import time
from datetime import datetime

# 설정
VOLTAGE_STEPS = [60.0, 90.0]
FREQUENCY = 60.0  # 주파수
DWELL = 300       # 5분
CURRENT_LIMIT = 18.0
MEASURE_INTERVAL = 5  # 5초 간격으로 

# 연결
rm = pyvisa.ResourceManager()
supply = rm.open_resource('')  #apt 장비 쓰기

# 초기화
supply.write('*RST')
supply.write('AR 0')  # Program mode

results = []

# 루프 돌기
for i, volt in enumerate(VOLTAGE_STEPS, start=1):
    print(f"\n Step {i}: {volt}V {FREQUENCY}Hz {DWELL}s 설정 및 실행")

    # step구성
    supply.write('STEPS 1')
    supply.write('EDIT 1')
    supply.write(f'VOLT {volt:.1f}')
    supply.write(f'FREQ {FREQUENCY:.1f}')
    supply.write(f'DWELL {DWELL}')
    supply.write(f'AHI {CURRENT_LIMIT:.2f}')
    supply.write('SAVE')
    supply.write('END')

    # 실행
    supply.write('TEST')
    start = time.time()

    while time.time() - start < DWELL:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        raw = supply.query('TD?').strip()
        fields = raw.split(',')  # td명령어의 답이 어떤지 몰라서 에러생길수도? 

        try:
            step_no = int(fields[0])
            status = fields[2]
            voltage = float(fields[3])
            freq = float(fields[4])
            current = float(fields[5])
            power = float(fields[6])
            peak_current = float(fields[7])
            pf = float(fields[8])
            timer = int(fields[9])

            results.append({
                'Time': timestamp,
                'Step': i,
                '전압': voltage,
                '전류': current,
                'Power': power,
                'PeakCurrent': peak_current,
                'PowerFactor': pf,
                'Elapsed': timer
            })

            print(f"[{timestamp}] Step {i} | V={voltage:.2f}V, I={current:.2f}A, P={power:.2f}W, PF={pf:.2f}")

        except Exception as e:
            print(f"TD? 파싱 오류: {raw}")

        time.sleep(MEASURE_INTERVAL)

# 저장
df = pd.DataFrame(results)
# filename = f"apt6020_step_test_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
# df.to_csv(filename, index=False)
df


## 여기서 부터는 power supply , power analyzer , 온도 측정 ^________^
'''
import pyvisa
import pandas as pd
import time
from datetime import datetime
from time import sleep

# 설정
voltages = [60.0, 90.0]   
wait_time = 300           # 5분
current_limit = 18.0      # 최대 전류 제한
frequency = 60.0          # 주파수
MEASURE_INTERVAL = 5      # 측정 간격 

# 장비연결
rm = pyvisa.ResourceManager()
supply = rm.open_resource('')     # APT6020
analyzer = rm.open_resource('')   # Power Analyzer
temp_meter = rm.open_resource('')  # 온도 센서 
#load = rm.open_resource('')       # 전자부하 ex) ITECH IT8511+

# 초기화
supply.write('*RST')
supply.write('AR 0')    # Program mode

results = []

# 전압 루프
for i, voltage in enumerate(voltages, start=1):
    print(f"\n설정 전압: {voltage}V, 유지 시간: {wait_time}초")

    # 스텝 구성
    supply.write('STEPS 1')
    supply.write('EDIT 1')
    supply.write(f'VOLT {voltage:.1f}')
    supply.write(f'FREQ {frequency:.1f}')
    supply.write(f'DWELL {wait_time}')
    supply.write(f'AHI {current_limit:.1f}')
    supply.write('SAVE')
    supply.write('END')
    # 전기 부하 설정
    #load.write("MODE CC") #정전류 모드? 모르겠음
    #load_current = 2.0 
    #load.write(f"CURR {load_current}")
    #load.write("INPUT ON") #부하 입력 시작

    # 테스트 실행
    supply.write('TEST')
    start_time = time.time()

    while time.time() - start_time < wait_time:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 온도 측정
        temp_meter.write('READ?') # 명령어 확인(틀릴 수도 있음)
        temperature = float(temp_meter.read().strip())

        # 전력 측정 (Power Analyzer) , 명령어 확인
        voltage_meas = float(analyzer.query('MEAS:VOLT?').strip()) #전압
        current_meas = float(analyzer.query('MEAS:CURR?').strip()) # 전류
        power_meas = float(analyzer.query('MEAS:POW?').strip()) # 유효 전력

        # 로그 출력
        print(f"[{timestamp}] V={voltage_meas:.2f}V, I={current_meas:.2f}A, P={power_meas:.2f}W, T={temperature:.2f}°C")

        results.append({
            'Time': timestamp,
            'Set_V': voltage,
            'Meas_V': voltage_meas,
            'Current': current_meas,
            'Power': power_meas,
            'Temperature': temperature
        })

        #load.write("INPUT OFF") #여기가 맞는지 모르겠음
        sleep(MEASURE_INTERVAL)

    
    sleep(2)  # 대기

# 결과
df = pd.DataFrame(results)
# filename = f"측정_test_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
# df.to_csv(filename, index=False)

'''