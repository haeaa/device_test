

import socket
import time

def yokogawa_basic_test_ascii(ip, port, channel=1):
    """YOKOGAWA MV2000 등 시리즈 소켓 통신 - 명령어를 아스키 bytes로 전송"""
    try:
        with socket.create_connection((ip, int(port)), timeout=5) as sock:
            # 1) 기기 식별 명령 - *IDN? (신형만 지원)
            try:
                # '*IDN?\n'을 아스키 코드로 변환 -> b'*IDN?\n'
                # _MFG
                # 19p 참고 - 
                # cmd_idn = bytes([ord(c) for c in '_COD\n'])
                cmd_idn = bytes([ord(c) for c in 'FData,0,0001,0106\n'])
                sock.sendall(cmd_idn)
                resp = sock.recv(1024).decode(errors="ignore").strip()
                print(f"[*IDN? 응답]: {resp}")
                if not resp or "YOKOGAWA" not in resp.upper():
                    raise Exception
            except Exception:
                # 구형에서는 RV\r 명령을 사용
                # 'RV\r'을 아스키 코드 배열로 변환
                cmd_rv = bytes([ord(c) for c in '_MFG\r'])
                sock.sendall(cmd_rv)
                resp = sock.recv(1024).decode(errors="ignore").strip()
                print(f"[RV 응답]: {resp}")

            time.sleep(0.2)  # 기기 처리 시간 고려

            # 2) 채널값 질의 (1채널 예시, RDSV0001\r 명령)
            cmd_str = f'RDSV{channel:04d}\r'  # 채널 번호 따라 문자열 생성
            # 문자열을 아스키 코드 리스트로 변환
            cmd_ascii = bytes([ord(c) for c in cmd_str])
            sock.sendall(cmd_ascii)

            # 응답 받기 (종료문자 \r 또는 수신 끝까지)
            data = b''
            for _ in range(10):
                part = sock.recv(1024)
                data += part
                if b'\r' in part or not part:  # 종료 문자 또는 데이터 끝
                    break
            print(f'[채널 {channel} 측정값]: {data.decode(errors="ignore").strip()}')

    except Exception as e:
        print(f"[에러]: {e}")


# 실제 사용 예시
yokogawa_basic_test_ascii('10.206.51.80', 34434, channel=1)


# import socket
# import time

# def yokogawa_read_temperature(ip, port, channel=1):
#     """
#     YOKOGAWA Hybrid Recorder TCP 통신 예시 - 온도(채널)의 최신 측정값 요청 및 출력
#     """
#     try:
#         with socket.create_connection((ip, int(port)), timeout=5) as sock:
#             # 1. 기기 식별 시도 (*IDN? 명령어 사용, 신형에 한함)
#             try:
#                 sock.sendall(b'*IDN?\r\n')  # 명령어 끝은 CR+LF
#                 resp = sock.recv(1024).decode(errors='ignore').strip()
#                 print(f'[IDN 응답]: {resp}')
#             except Exception:
#                 # 구형 기기는 *IDN? 미지원, 제조자 정보 출력 명령 사용
#                 sock.sendall(b'_MFG\r\n')
#                 resp = sock.recv(1024).decode(errors='ignore').strip()
#                 print(f'[_MFG 응답]: {resp}')

#             time.sleep(0.1)  # 명령 처리 대기

#             # 2. 온도 채널 데이터 읽기 요청
#             cmd = f'RDSV{channel:04d}\r'  # 예: 채널 1 -> RDSV0001\r
#             sock.sendall(cmd.encode('ascii'))

#             # 응답 수신 (종료 문자 CR 또는 LF 포함될 때까지 수신)
#             data = b''
#             for _ in range(10):
#                 part = sock.recv(1024)
#                 if not part:
#                     break
#                 data += part
#                 if b'\r' in part or b'\n' in part:
#                     break
#             result = data.decode(errors='ignore').strip()
#             print(f'[채널 {channel} 측정값 응답]: {result}')

#             return result

#     except Exception as e:
#         print(f'[에러 발생]: {e}')
#         return None

# # 실제 사용 예 (IP, 포트, 채널 번호는 실제 환경에 맞게 변경)
# if __name__ == '__main__':
#     ip_address = '10.206.51.80'
#     port_number = 34434
#     channel_number = 1  # 테스트할 온도 채널
#     yokogawa_read_temperature(ip_address, port_number, channel_number)
