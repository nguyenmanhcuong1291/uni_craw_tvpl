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
    org_table = soup.find("table", class_='org')
    result = {}

    # Tìm thẻ <p> chứa từ khóa "상세결과 항목 :"
    p_tag = soup.find('p', text=lambda x: x and "상세결과 항목 :" in x)

    if p_tag:
        content = p_tag.text.split("상세결과 항목 :")[1].strip()
        result_set = set(content.split(', '))
        print(result_set)
    else:
        print("Không tìm thấy thẻ <p> phù hợp.")

    # Xử lý các catalog
    for catalog in result_set:
        # print(f"Đang xử lý: {catalog}")
        th_element = org_table.find('th', text=catalog)
        if th_element:
            elems_html_info = th_element.find_next_sibling('td')
            for elem in elems_html_info:
                if elem.name == 'a':  # Thay đổi thẻ <a> thành văn bản
                    elem.replace_with(elem.text)
                elif elem.name == 'br':  # Giữ lại thẻ <br>
                    continue
            elem_text = elems_html_info.decode_contents().replace('\r', '').replace('\t', '').replace('\n', '').strip()
            result[catalog] = elem_text
        else:
            print(f"Không tìm thấy thẻ <th> cho '{catalog}'")
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
    current_index = start_index

    for index, row in data_chunk.iterrows():
        cntyCd = row['cntyCd']
        baseYy = row['baseYy']
        reffNoNm = row['reffNoNm']
        prlstClsfSrno = row['prlstClsfSrno']
        html_content, index = detailinforequest(index, cntyCd, baseYy, reffNoNm, prlstClsfSrno)

        if html_content:
            try:
                detail_output = extract_data_from_html(html_content)
                detail_output["index"] = index
                all_detail_output.append(detail_output)

                # Ghi kết quả vào file riêng cho thread
                with open(output_file_template.format(thread_index), "a", encoding='utf-8') as f:
                    f.write(json.dumps(detail_output, ensure_ascii=False) + "\n")

                current_index = index + 1  # Cập nhật chỉ số đã xử lý

            except Exception as e:
                print(f"Error processing {index}: {e}")
                save_state({"start_index": current_index}, thread_index)
                break  # Dừng lại nếu có lỗi

        # Lưu trạng thái sau khi xử lý xong một phần tử
        save_state({"start_index": current_index}, thread_index)

    return all_detail_output, current_index



# Thư mục để lưu trạng thái và kết quả
output_dir = "org"
os.makedirs(output_dir, exist_ok=True)

# File để lưu trạng thái của vòng lặp
state_file_template = os.path.join(output_dir, "loop_state_{}.json")
output_file_template = os.path.join(output_dir, "output_data_{}.txt")
final_output_file = "final_output_data_org.txt"  # File tổng kết quả

# Bắt đầu vòng lặp từ trạng thái đã lưu
chunk_size = 200000
df_chunks = [df[i:i + chunk_size] for i in range(0, len(df), chunk_size)]

# Bắt đầu vòng lặp từ trạng thái đã lưu
saved_states = [load_state(i) for i in range(len(df_chunks))]

# Sử dụng multithreading để xử lý từng chunk
all_results = []
states = {}
with concurrent.futures.ThreadPoolExecutor(max_workers=len(df_chunks)) as executor:
    futures = {
        executor.submit(process_data_chunk, chunk, idx, saved_states[idx]["start_index"]): idx
        for idx, chunk in enumerate(df_chunks)
    }
    for future in concurrent.futures.as_completed(futures):
        thread_index = futures[future]
        try:
            results, current_index = future.result()
            all_results.extend(results)
            states[thread_index] = {"start_index": current_index}
        except Exception as e:
            print(f"Thread {thread_index} encountered an error: {e}")
            save_state(states[thread_index], thread_index)

# Lưu kết quả cuối cùng vào file
with open(final_output_file, "w", encoding='utf-8') as f:
    for result in all_results:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")
