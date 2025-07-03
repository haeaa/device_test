#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import os
import uuid
import json
import pandas as pd
import requests
from dotenv import load_dotenv
from openai import OpenAI

# OpenAI API Key 로드
load_dotenv()
openai_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_key)

# Clova OCR API 호출 함수
def call_clova_ocr(file_path: str, api_url: str, secret_key: str):
    request_json = {
        'images': [{'format': 'jpg', 'name': 'receipt'}],
        'requestId': str(uuid.uuid4()),
        'version': 'V2',
        'timestamp': 0
    }
    payload = {'message': json.dumps(request_json).encode('UTF-8')}
    files = {'file': open(file_path, 'rb')}
    headers = {'X-OCR-SECRET': secret_key}
    response = requests.post(api_url, headers=headers, data=payload, files=files)
    json_data= response.json()
    return json_data

#  OCR 결과 → 텍스트
def json_to_string(json_data: json):
    string_result= ''
    for i in json_data['images'][0]['fields']:
        if i['lineBreak'] == True: # 줄바꿈이 있으면 줄바꿈 해라
            linebreak = '\n'
        else:
            linebreak = ' '
        string_result = string_result + i['inferText'] + linebreak
    return string_result


# GPT 호출 → DataFrame
def string_to_dataframe(receipt_text: str, receipt_num: int):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo-1106",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant to analyze the receipt. "
                           "Please ensure that the receipt's data is correctly formatted in the JSON format as shown in this example: "
                           "{\"date\": \"yyyy/mm/dd\", \"items\": [{\"item_name\": \"Item_1\", \"price\": 100, \"quantity\": 3, \"amount\": 300}]}. "
                           "If an item is free, set its price to 0 and only count quantity."
                           "Be aware that 'price' refers to the cost per item, while 'amount' refers to the total cost of an item line (price multiplied by quantity)."
                           "Pay special attention to items that include the word '할인' in their item_name, as these represent discounts. "
                           "'면세 물품' items should not be included in the total calculation."
                           "For single-item purchases, ensure that the item's price reflects the receipt's final total."
            }
            ,
            {
                "role": "user",
                "content": f"Please analyze this receipt: \n{receipt_text}\n "
                           "Make sure to reflect any discounts or negative amounts in the final total."
            }

        ]
    )
    content = response.choices[0].message.content
    content = content.replace("null", "None")  # 추가
    data = json.loads(content)
    df = pd.DataFrame(data['items'])
    df['date'] = data['date']
    df['receipt_num'] = receipt_num
    return df


# In[ ]:


# ✅ Tkinter GUI 클래스
class ReceiptApp:
    def __init__(self, root):
        self.root = root
        self.root.title(" 영수증 자동화")
        self.image_paths = []
        self.all_data = pd.DataFrame()

        # OCR API 입력
        tk.Label(root, text="Clova OCR API URL").pack()
        self.ocr_url_entry = tk.Entry(root, width=80)
        self.ocr_url_entry.pack()

        tk.Label(root, text="Clova Secret Key").pack()
        self.ocr_secret_entry = tk.Entry(root, width=80)
        self.ocr_secret_entry.pack()

        # 폴더 선택 버튼
        tk.Button(root, text="이미지 폴더 선택", command=self.upload_folder).pack(pady=5)
        self.listbox = tk.Listbox(root, width=100, height=6)
        self.listbox.pack()

        # 분석 실행 버튼
        tk.Button(root, text="OCR + GPT 분석 실행", command=self.process_all_receipts).pack(pady=5)

        # 결과 출력 창
        self.text_output = tk.Text(root, height=25, width=100)
        self.text_output.pack(pady=10)

        # 엑셀 저장
        tk.Button(root, text="엑셀로 저장", command=self.save_excel).pack()

    def upload_folder(self):
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.image_paths = []
            for file_name in os.listdir(folder_path):
                if file_name.lower().endswith(('.jpg', '.jpeg', '.png')):
                    full_path = os.path.join(folder_path, file_name)
                    self.image_paths.append(full_path)

            self.listbox.delete(0, tk.END)
            for path in self.image_paths:
                self.listbox.insert(tk.END, os.path.basename(path))

    def process_all_receipts(self):
        api_url = self.ocr_url_entry.get().strip()
        secret_key = self.ocr_secret_entry.get().strip()
        if not (api_url and secret_key):
            messagebox.showerror("오류", "Clova API URL과 Secret Key를 입력하세요.")
            return

        if not self.image_paths:
            messagebox.showerror("오류", "이미지 폴더를 먼저 선택하세요.")
            return

        self.all_data = pd.DataFrame()
        self.text_output.delete(1.0, tk.END)

        for idx, path in enumerate(self.image_paths, 1):
            try:
                ocr_json = call_clova_ocr(path, api_url, secret_key)
                receipt_text = json_to_string(ocr_json)
                df = string_to_dataframe(receipt_text, idx)
                self.all_data = pd.concat([self.all_data, df], ignore_index=True)
                self.text_output.insert(tk.END, f"[{os.path.basename(path)}]\n{df.to_string(index=False)}\n\n")
            except Exception as e:
                self.text_output.insert(tk.END, f"[ 오류] {os.path.basename(path)} 처리 실패: {str(e)}\n\n")

        messagebox.showinfo(" 완료", f"{len(self.image_paths)}개의 영수증 처리가 완료되었습니다.")

    def save_excel(self):
        if self.all_data.empty:
            messagebox.showerror("오류", "저장할 데이터가 없습니다.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx")
        if path:
            self.all_data.to_excel(path, index=False)
            messagebox.showinfo("성공", f"엑셀 저장 완료: {path}")

# ✅ 실행
if __name__ == "__main__":
    root = tk.Tk()
    app = ReceiptApp(root)
    root.mainloop()

