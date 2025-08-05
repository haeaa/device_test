import serial
import time

ser = serial.Serial(
    port='COM5',    # 사용 환경에 맞게 수정
    baudrate=9600, 
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    timeout=1
)

def send_command(cmd):
    ser.write((cmd + '\n').encode('ascii'))
    time.sleep(0.1)
    resp = ser.read_all().decode('ascii', errors='ignore')
    return resp

# 예시: 채널 1을 정전류 1.2A로, 채널 2를 정전류 2.5A로 각각 설정
print(send_command(' LOAD ON, @1'))
print(send_command(' MODE CC,@1'))
print(send_command(' CURR 1.2,@1'))

# print(send_command(' LOAD ON'))

print(send_command(' LOAD ON,@2'))
print(send_command(' MODE CC,@2'))
print(send_command(' CURR 2.5,@2'))
# print(send_command(' LOAD ON'))

# 각 채널의 측정값 읽기
print(send_command(' MEAS:CURR?,@1'))
print(send_command(' MEAS:CURR?,@2'))

ser.close()
