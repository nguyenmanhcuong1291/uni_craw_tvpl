import requests
from bs4 import BeautifulSoup
import json
import concurrent.futures
import os
import pandas as pd

# Đọc file CSV
list_file = "all_link_list.csv"
df = pd.read_csv(list_file, encoding='utf-8')

print(len(df))
print(df.head(5))
def detailinforequest(index, cntyCd, baseYy, reffNoNm, prlstClsfSrno):
    # URL của API
    url = 'https://unipass.customs.go.kr/clip/prlstclsfsrch/retrievePrlstClsfCaseDtl.do'

    # Headers
    headers = {
        'Accept': 'text/html, */*; q=0.01',
        'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8,vi-VN;q=0.7',
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Cookie': 'WMONID=N_4A3dINH0I; JSESSIONID=0001O2y8S-yyQQ_lga-knblPV6Lb2QN6662ivRFJ_jK2FPRlLOTKNEsnuhZe_QxBEKq-8U03_kah8EgUgb-_Exa4dmevvhJHEKeNuIq9prRxpJht6ugFASENgz3p_AdMPw4_:eul21',
        'DNT': '1',
        'Origin': 'https://unipass.customs.go.kr',
        'Referer': 'https://unipass.customs.go.kr/clip/index.do',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'isAjax': 'true',
        'sec-ch-ua': '"Google Chrome";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"'
    }

    # Dữ liệu trong body của yêu cầu
    payload = {
        'cntyCd': cntyCd,
        'baseYy': baseYy,
        'reffNoNm': reffNoNm,
        'prlstClsfSrno': prlstClsfSrno
    }

    # Gửi yêu cầu POST với headers và dữ liệu body
    response = requests.post(url, headers=headers, data=payload,timeout=60)

    # Kiểm tra phản hồi từ API
    if response.status_code == 200:
        return response.text, index
    else:
        print(f"Row {index} Lỗi")
        return None, index


def extract_data_from_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    result = {}
    for table_type in ('org','eng','kor'):
        table = soup.find("table", class_=table_type)
        # Tìm thẻ <p> chứa từ khóa "상세결과 항목 :"
        all_ths = table.findAll('th')
        for th in all_ths: 
            if th.get_text() == "관련 이미지":
                image_elements = table.find('th', text='관련 이미지').find_next_sibling('td').find_all('img')
                image_links = [img['src'] for img in image_elements]
                result[f"{th.get_text()}_{table_type}"] = image_links
            # print(f"Đang xử lý: {catalog}")
            else: 
                elems_html_info = table.find('th', text=th.get_text()).find_next_sibling('td')
                for elem in elems_html_info:
                    if elem.name == 'a':  # Thay đổi thẻ <a> thành văn bản
                        elem.replace_with(elem.text)
                    elif elem.name == 'br':  # Giữ lại thẻ <br>
                        continue
                elem_text = elems_html_info.decode_contents().replace('\r', '').replace('\t', '').replace('\n', '').strip()
                result[f"{th.get_text()}_{table_type}"] = elem_text
    print(result)
    return result


def save_state(states, thread_index):
    with open(state_file_template.format(thread_index), "w") as f:
        json.dump(states, f)


def load_state(thread_index):
    try:
        with open(state_file_template.format(thread_index), "r") as f:
            states = json.load(f)
            if isinstance(states, dict) and "start_index" in states:
                return states
            else:
                return {"start_index": 0}
    except FileNotFoundError:
        return {"start_index": 0}


def process_data_chunk(data_chunk, thread_index, start_index):

    all_detail_output = []
    error_stt_list = []
    current_index = start_index
    
    while True:
        try:
            for index, row in data_chunk.iloc[start_index:].iterrows():
                cntyCd = row['cntyCd']
                baseYy = row['baseYy']
                reffNoNm = row['reffNoNm']
                prlstClsfSrno = row['prlstClsfSrno']
                stt = row['stt']

                try:
                    html_content, index = detailinforequest(index, cntyCd, baseYy, reffNoNm, prlstClsfSrno)
                    if html_content:
                        detail_output = extract_data_from_html(html_content)
                        detail_output["stt"] = stt
                        all_detail_output.append(detail_output)

                        # Ghi kết quả vào file riêng cho thread
                        with open(output_file_template.format(thread_index), "a", encoding='utf-8') as f:
                            f.write(json.dumps(detail_output, ensure_ascii=False) + "\n")

                except Exception as e:
                    print(f"Error processing row {index}: {e}")
                    error_stt_list.append(stt)
                    
                    # Ghi lỗi vào file
                    with open(error_file_template.format(thread_index), "a", encoding='utf-8') as f:
                        f.write(json.dumps({"stt": stt, "error": str(e)}, ensure_ascii=False) + "\n")
                    
                finally:
                    # Cập nhật trạng thái đã xử lý
                    current_index = index + 1  
                    save_state({"start_index": current_index}, thread_index)

            return all_detail_output, current_index, error_stt_list
        except Exception as e:
            print(f"Thread {thread_index} encountered an error: {e}. Restarting...")
            time.sleep(5)  # Đợi 5 giây trước khi thử lại

# Thư mục để lưu trạng thái và kết quả
output_dir = "org"
os.makedirs(output_dir, exist_ok=True)

# File để lưu trạng thái của vòng lặp
state_file_template = os.path.join(output_dir, "loop_state_{}.json")
output_file_template = os.path.join(output_dir, "output_data_{}.txt")
error_file_template = os.path.join(output_dir, "error_stt_{}.txt")
final_output_file = "final_output_data_org.txt"  # File tổng kết quả

# Bắt đầu vòng lặp từ trạng thái đã lưu
chunk_size = 100000
df_chunks = [chunk.reset_index(drop=True) for chunk in [df[i:i + chunk_size] for i in range(0, len(df), chunk_size)]]

# Bắt đầu vòng lặp từ trạng thái đã lưu
saved_states = [load_state(i) for i in range(len(df_chunks))]

# Sử dụng multithreading để xử lý từng chunk
# all_results = []
# all_error_stts = []
states = {}

with concurrent.futures.ThreadPoolExecutor(max_workers=len(df_chunks)) as executor:
    futures = {
        executor.submit(process_data_chunk, chunk, idx, saved_states[idx]["start_index"]): idx
        for idx, chunk in enumerate(df_chunks)
    }
    for future in concurrent.futures.as_completed(futures):
        thread_index = futures[future]
        try:
            results, current_index, error_stts = future.result()
            # all_results.extend(results)
            # all_error_stts.extend(error_stts)
            states[thread_index] = {"start_index": current_index}
        except Exception as e:
            print(f"Thread {thread_index} encountered an error: {e}")
            save_state(states[thread_index], thread_index)

# # Ghi tất cả các lỗi vào file chung
# with open("final_error_stts.txt", "w", encoding='utf-8') as f:
#     for error_stt in all_error_stts:
#         f.write(f"{error_stt}\n")

# # Lưu kết quả cuối cùng
# with open(final_output_file, "w", encoding='utf-8') as f:
#     for result in all_results:
#         f.write(json.dumps(result, ensure_ascii=False) + "\n")

# Thư mục chứa các file TXT
directory = 'org/'  # Thay đổi thành đường dẫn thư mục chứa các file TXT của bạn

# Tạo danh sách các file theo mẫu tên
error_file_names = [f'error_stt_{i}.txt' for i in range(12)]

# Khởi tạo danh sách để chứa dữ liệu từ tất cả các file
all_error_data = []

# Đọc và xử lý từng file
for file_name in error_file_names:
    file_path = os.path.join(directory, file_name)
    with open(file_path, 'r', encoding='utf-8') as file:
        # Đọc từng dòng và chuyển đổi từ JSON thành dictionary
        data = [json.loads(line) for line in file]
        all_error_data.extend(data)  # Thêm dữ liệu từ file hiện tại vào danh sách tổng

# Chuyển tất cả dữ liệu thành DataFrame
error_df = pd.DataFrame(all_error_data)

# Lưu DataFrame ra file CSV nếu cần
error_df.to_csv('all_error_stt_2.csv', index=False, encoding='utf-8')

output_file_names = [f'output_data_{i}.txt' for i in range(12)]

# Khởi tạo danh sách để chứa dữ liệu từ tất cả các file
all_output_data = []

# Đọc và xử lý từng file
for file_name in output_file_names:
    file_path = os.path.join(directory, file_name)
    with open(file_path, 'r', encoding='utf-8') as file:
        # Đọc từng dòng và chuyển đổi từ JSON thành dictionary
        data = [json.loads(line) for line in file]
        all_output_data.extend(data)  # Thêm dữ liệu từ file hiện tại vào danh sách tổng

# Chuyển tất cả dữ liệu thành DataFrame
output_df = pd.DataFrame(all_output_data)

# Lưu DataFrame ra file CSV nếu cần
output_df.to_csv('all_output_data_2.csv', index=False, encoding='utf-8')
