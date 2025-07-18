import pyvisa

rm = pyvisa.ResourceManager()
inst = rm.open_resource("USB0::...::INSTR")  # NI MAX 주소 입력
print(inst.query("*IDN?"))