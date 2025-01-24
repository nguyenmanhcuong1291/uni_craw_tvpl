
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pytesseract
from PIL import Image, ImageFilter
import cv2
from collections import Counter
import os
import time
import re
from datetime import datetime, timedelta
import pandas as pd
import csv
import ast
import pyodbc
import json
import concurrent.futures


pytesseract.pytesseract.tesseract_cmd = r"/usr/bin/tesseract"

def download_captcha(captcha_url, driver):
    # Tạo một session mới
    session = requests.Session()
    
    # Lấy cookies từ Selenium WebDriver
    selenium_cookies = driver.get_cookies()
    
    # Thêm cookies vào session
    for cookie in selenium_cookies:
        session.cookies.set(cookie['name'], cookie['value'])
    
    # Headers cho request
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    }
    
    # Gửi request để tải ảnh captcha
    response = session.get(captcha_url, headers=headers ,timeout=600)
    if response.status_code == 200:
        captcha_path = "captcha_image.png"
        with open(captcha_path, "wb") as f:
            f.write(response.content)
        print("Captcha đã được lưu vào file captcha_image.png")
        return captcha_path
    else:
        print(f"Lỗi khi tải captcha: {response.status_code}")
        return None

def preprocess_captcha(image_path):
    # Read the image
    image = cv2.imread(image_path)
    
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Apply thresholding (binarization)
    _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    
    # Optionally, apply noise removal (median filter)
    denoised = cv2.medianBlur(binary, 3)
    
    # Save the preprocessed image for debugging
    preprocessed_path = "preprocessed_captcha.png"
    cv2.imwrite(preprocessed_path, denoised)
    
    return preprocessed_path

def read_captcha(captcha_path):
    # Preprocess the captcha image
    preprocessed_path = preprocess_captcha(captcha_path)
    
    # Read the preprocessed image with pytesseract
    captcha_text = pytesseract.image_to_string(Image.open(preprocessed_path), config="--psm 7")
    
    return captcha_text.strip()

def run_multiple_captcha_attempts(captcha_path,attempts=10):
    results = []
    
    for i in range(attempts):
        # Read and process the captcha
        captcha_text = read_captcha(captcha_path)
        results.append(captcha_text)
        # print(f"Extracted CAPTCHA (Attempt {i + 1}): {captcha_text}")

    # Determine the most repeated result
    most_common = Counter(results).most_common(1)
    if most_common:
        print(f"\nMost repeated CAPTCHA result: {most_common[0][0].replace(' ', '')}")

    return most_common[0][0].replace(" ", "")
def get_cookie(user_name, password):
    while True:  # Vòng lặp để thử đăng nhập liên tục cho đến khi thành công
        # Cấu hình Selenium WebDriver với chế độ headless
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")  # Chế độ headless
        options.add_argument("--no-sandbox")  # Khắc phục lỗi sandbox trên Linux
        options.add_argument("--disable-dev-shm-usage")  # Tăng giới hạn bộ nhớ chia sẻ
        options.add_argument("--disable-gpu")  # Tắt GPU (không cần thiết trên server không có UI)
        options.add_argument("--window-size=1920x1080")  # Đặt kích thước màn hình để tránh lỗi định vị phần tử

        # Khởi tạo driver
        driver = webdriver.Chrome(options=options)

        try:
            # Mở trang đăng nhập
            url = "https://dichvucong.moit.gov.vn/Login.aspx"
            driver.get(url)

            # Chờ các phần tử cần thiết hiển thị
            wait = WebDriverWait(driver, 10)

            # Nhập username
            username_field = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_cplhContainer_txtLoginName"]')))
            username_field.send_keys(user_name)

            # Nhập password
            password_field = driver.find_element(By.XPATH, '//*[@id="ctl00_cplhContainer_txtPassword"]')
            password_field.send_keys(password)

            # Lấy URL của captcha từ Selenium
            captcha_image = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_cplhContainer_imgCaptcha"]')))
            captcha_src = captcha_image.get_attribute("src")
            print(f"Captcha URL: {captcha_src}")

            # Tải ảnh captcha bằng session từ Selenium WebDriver
            captcha_path = download_captcha(captcha_src, driver)

            # Đọc mã captcha bằng Tesseract OCR
            captcha_code = run_multiple_captcha_attempts(captcha_path,attempts=10)
            print(f"Mã captcha OCR: {captcha_code}")

            # Nhập mã captcha
            captcha_field = driver.find_element(By.XPATH, '//*[@id="ctl00_cplhContainer_txtCaptcha"]')
            captcha_field.send_keys(captcha_code)

            # Nhấn nút đăng nhập
            login_button = driver.find_element(By.XPATH, '//*[@id="ctl00_cplhContainer_btnLogin"]')
            login_button.click()

            # Chờ tải xong sau khi đăng nhập
            time.sleep(5)

            # Kiểm tra thông báo lỗi captcha (nếu có)
            try:
                captcha_notice = driver.find_element(By.XPATH, '//*[@id="ctl00_cplhContainer_lblMsg"]').text
                if captcha_notice:
                    print(f"Thông báo: {captcha_notice}")
                    continue  # Quay lại đầu vòng lặp nếu đăng nhập thất bại
            except:
                pass

            # Kiểm tra đăng nhập thành công hay không
            if "Dashboard" in driver.page_source:
                print("Đăng nhập dichvucong.moit.gov.vn thành công!")

                # Đăng nhập sang ecosys
                next_button = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_cplhContainer_grdViewDefault"]/tbody/tr[2]/td[4]/a')))
                next_button.click()

                # Lấy cookie
                cookie = f'{driver.get_cookies()[3]["name"]}={driver.get_cookies()[3]["value"]}'

                # Đóng driver và trả về cookie
                driver.quit()
                if os.path.exists("captcha_image.png"):
                    os.remove("captcha_image.png")
                print("Đăng nhập ecosys thành công!")    
                return cookie
            else:
                print("Đăng nhập thất bại. Thử lại...")

        except Exception as e:
            print(f"Lỗi xảy ra: {e}")

        finally:
            # Đóng trình duyệt nếu không thành công
            driver.quit()
            if os.path.exists("captcha_image.png"):
                os.remove("captcha_image.png")


# %%
with open("account.csv", "r", encoding="utf-8") as file:
    reader = csv.DictReader(file)
    account_list = [row for row in reader]

# %%
def request_first_page(fromdate,todate):
    # URL yêu cầu
    url = f'https://ecosys.gov.vn/CertificatesUpgrade/Business/CertificateAdvanceSearch.aspx?CertificateDateFrom={fromdate}&CertificateDateTo={todate}&Status=-1&FormCOId=0&CountryId=0&CertificateNumber=&CustomsNumber=&ReceiverName=&TransportMethodId=0'

    # Đặt headers
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8,vi-VN;q=0.7',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Cookie': cookie,
        'DNT': '1',
        'Referer': 'https://ecosys.gov.vn/CertificatesUpgrade/Business/CertificateAdvanceSearch.aspx?',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"'
    }

    # Gửi yêu cầu GET
    response = requests.get(url, headers=headers, timeout=600)

    if response.status_code == 200:
        print(f"Request {fromdate},{todate} thành công!")
        return response.text
    # print(response2.text)  # Nội dung HTML
    else:
        print(f"Request thất bại: {response.status_code}")
        return None


# %%
def request_more_page(eventvalidation,viewstate,page_index): 
    import requests

    # URL cần truy vấn
    more_page_url = "https://ecosys.gov.vn/CertificatesUpgrade/Business/CertificateAdvanceSearch.aspx"

    # Các headers sử dụng trong request
    headers2 = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9,vi;q=0.8,vi-VN;q=0.7",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Cookie": cookie,
        "DNT": "1",
        "Origin": "https://ecosys.gov.vn",
        "Referer": "https://ecosys.gov.vn/CertificatesUpgrade/Business/CertificateAdvanceSearch.aspx?CertificateDateFrom=01/01/2022&CertificateDateTo=31/03/2024&Status=-1&FormCOId=0&CountryId=0&CertificateNumber=&CustomsNumber=&ReceiverName=&TransportMethodId=0",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }

    # Dữ liệu form gửi kèm
    data2 = {
        
        "__EVENTVALIDATION": eventvalidation,
        "__VIEWSTATE":viewstate,
        "ctl00$cplhContainer$ddlChoiceIndexOfPage":page_index
    }

    # Gửi POST request
    response2 = requests.post(more_page_url, headers=headers2, data=data2)

    # Kiểm tra kết quả trả về
    if response2.status_code == 200:
        print(f"Request page {page_index} thành công!")
        return response2.text
        # print(response2.text)  # Nội dung HTML
    else:
        print(f"Request thất bại: {response2.status_code}")
        return None


# %%
def generate_dates(start_date, end_date):
    """Tạo danh sách các quý theo từng giai đoạn lùi."""
    quarters = []
    # current_start là end_date - 80 ngày
    current_end = datetime.strptime(end_date, "%d/%m/%Y")
    current_start = current_end - timedelta(days=80)
    
    while current_start >= datetime.strptime(start_date, "%d/%m/%Y"):
        quarters.append((current_start.strftime("%d/%m/%Y"), current_end.strftime("%d/%m/%Y")))
        # Lùi lại một quý
        current_end = current_start - timedelta(days=1)
        current_start = (current_end.replace(day=1) - timedelta(days=1)).replace(day=1)
    
    quarters.append((start_date, current_end.strftime("%d/%m/%Y")))
    return quarters

# Ngày bắt đầu và kết thúc (180 ngày)
start_date = (datetime.now() - timedelta(days=180)).strftime("%d/%m/%Y")
end_date = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")

# Tạo danh sách các quý
dates_list = generate_dates(start_date, end_date)

# %%
id_pattern = r"\b\d{8}\b"

# %%
def part_text(part,start,end):
    part_list = []
    for i in part[start:end]:
        part_list.append(i.get_text().replace('\r', '').replace('\n', '').strip())
        part_text = '\n'.join(part_list)
    return part_text
        

# %%
def get_id_details(cookie,doc_id):
    # URL cần gửi yêu cầu
    url = f"https://ecosys.gov.vn/CertificatesUpgrade/Business/CertificateDisplay.aspx?DocId={doc_id}"

    # Headers cần thiết
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9,vi;q=0.8,vi-VN;q=0.7",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Cookie": cookie,
        "DNT": "1",
        "Referer": "https://ecosys.gov.vn/CertificatesUpgrade/Business/CertificateAdvanceSearch.aspx",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }

    # Gửi yêu cầu GET
    response = requests.get(url, headers=headers,timeout= 600)

    # Kiểm tra phản hồi
    if response.status_code == 200:
        print("Request thành công!")
        # print(response.text)  # In nội dung HTML của trang
    else:
        print(f"Lỗi: {response.status_code}")
        # print(response.text)

    id_info = {}
    id_info["doc_id"] = doc_id
    if response.text:
        soup = BeautifulSoup(response.text,"html.parser")

    try:
        info_soup = soup.find('div',id = "ctl00_cplhContainer_rpvInfo") 
        all_div = info_soup.find_all('div', class_=re.compile(r"^row"))
        trang_thai_soup = all_div[0]
        try :
            tths = part_text(trang_thai_soup.find_all('span'),1,3)
            id_info["Trạng thái hồ sơ"] = tths
        except:
            print("not found Trạng thái hồ sơ")
        thong_tin_chung_soup = all_div[1]
        try:
            tax_code = thong_tin_chung_soup.find("span", id = "ctl00_cplhContainer_lblCompanyTaxCode").get_text().strip()
            id_info["Tax code"] = tax_code
        except:
            print("Not found tax_code")
        try:
            issuing_authority  = thong_tin_chung_soup.find("span", id = "ctl00_cplhContainer_lblDepartment").get_text().strip()
            id_info["Issuing Authority"] = issuing_authority
        except:
            print("Not found Issuing Authority")
        try:
            form  = thong_tin_chung_soup.find("span", id = "ctl00_cplhContainer_lblFormCO").get_text().strip()
            id_info["Form"] = form
        except:
            print("Not found form")
        try:
            ImportingCountry   = thong_tin_chung_soup.find("span", id = "ctl00_cplhContainer_lblMarket").get_text().strip()
            id_info["Importing_Country"] = ImportingCountry
        except:
            print("Not found Importing Country")
        try:
            Reference_no    = thong_tin_chung_soup.find("span", id = "ctl00_cplhContainer_lblCertificateNumber").get_text().strip()
            id_info["Reference No."] = Reference_no
        except:
            print("Not found Reference No.")
        try:
            Issuance_date = thong_tin_chung_soup.find("span", id = "ctl00_cplhContainer_lblCertificateDate").get_text().strip()
            id_info["Issuance date"] = Issuance_date
        except:
            print("Not found Issuance date ")
        try:
            Certified_date  = thong_tin_chung_soup.find("span", id = "ctl00_cplhContainer_lblReviewDateApprove").get_text().strip()
            id_info["Certified date"] = Certified_date
        except:
            print("Not found Certified date ")
            
        try:
            invoiceItems  = thong_tin_chung_soup.find('div',  id = "ctl00_cplhContainer_pnlCustomsNumber").find_all('div',class_ = "invoiceItem")
        except:
            invoiceItems = []
            
        ExportDeclaration = []
        item_num = 0
        for item in invoiceItems:
            invoiceitem_info = {}
            item_num += 1
            invoiceitem_info["item_num"] = item_num
            
            try: 
                invoice_number = item.find("span", id=lambda x: x and x.startswith("ctl00_cplhContainer_pnlCustomsNumber") and "lblInvoiceNumber" in x)
                invoiceitem_info['invoice_number'] = invoice_number.get_text() 
            except:
                invoiceitem_info['invoice_number'] = ""
                
            try:    
                invoice_date = item.find("span", id=lambda x: x and x.startswith("ctl00_cplhContainer_pnlCustomsNumber") and x.endswith("lblInvoiceDate"))
                invoiceitem_info['invoice_date'] = invoice_date.get_text() 
            except:
                invoiceitem_info['invoice_date'] = ""
                
            try: 
                invoice_link = item.find("a", id=lambda x: x and x.startswith("ctl00_cplhContainer_pnlCustomsNumber") and "hplInvoiceLink" in x)
                invoiceitem_info['invoice_link'] = invoice_link.get("href")
            except:
                invoiceitem_info['invoice_link'] = ""
                
            ExportDeclaration.append(invoiceitem_info)

        id_info["ExportDeclaration"] = ExportDeclaration
        from_to_soup = all_div[2]
        titles = from_to_soup.find_all('span', class_='titles')
        for title in titles:
            key = title.get_text(strip=True)
            div_content = title.find_parent('div').find_next_sibling('div')
            values = [span.get_text(strip=True) for span in div_content.find_all('span')]
            id_info[key] = values

        transport_info_soup = all_div[3]
        try:
            transport_type  = transport_info_soup.find("span", id = "ctl00_cplhContainer_lblTransportMethod").get_text().strip()
            id_info["transport_type"] = transport_type
        except:
            print("Not found transport_type")
        try:
            departure_date  = transport_info_soup.find("span", id = "ctl00_cplhContainer_lblTransportDate").get_text().strip()
            id_info["Departure Date"] = departure_date
        except:
            print("Not found Departure Date")
        try:
            vessel_aircraft_name  = transport_info_soup.find("span", id = "ctl00_cplhContainer_lblShipName").get_text().strip()
            id_info["vessel_aircraft_name"] = vessel_aircraft_name
        except:
            print("Not found Vessel’s Name/Aircraft")
        try:
            port_of_loading  = transport_info_soup.find("span", id = "ctl00_cplhContainer_lblSenderPlace").get_text().strip()
            id_info["port_of_loading"] = port_of_loading
        except:
            print("Not found port_of_loading")
        try:
            port_of_discharge  = transport_info_soup.find("span", id = "ctl00_cplhContainer_lblReceiverPlace").get_text().strip()
            id_info["port_of_discharge"] = port_of_discharge
        except:
            print("Not found port_of_discharge")
        try:
            transport_doc  = transport_info_soup.find("a", id = "ctl00_cplhContainer_hplTransportFileLink").get("href")
            id_info["transport_doc"] = transport_doc
        except:
            print("Not found transport_doc")
        try:
            goods_info_soup = all_div[4].find('table',class_ = 'rgMasterTable')
            # Lấy tiêu đề
            goods_info_header = [th.get_text(separator=" ", strip=True) for th in goods_info_soup.find('thead').find_all('th', class_ = "rgHeader")]

            # Lấy dữ liệu từng dòng trong bảng
            goods_info_rows = []
            for tr in goods_info_soup.find('tbody').find_all('tr'):
                row = [td.get_text(separator=" ", strip=True) for td in tr.find_all('td')]
                goods_info_rows.append(row)
        except:
            print("Not found goods_info")
        goods_info = [goods_info_header] + goods_info_rows
        id_info["goods_info"] = goods_info
        invoice_info_soup = all_div[5]
        try:
            total_value  = invoice_info_soup.find("span", id = "ctl00_cplhContainer_lblTotalItemFobValueTabCO").get_text().strip()
            id_info["total_value"] = total_value
        except:
            print("Not found total_value")
        try:
            total_quantity  = invoice_info_soup.find("span", id = "ctl00_cplhContainer_lblTotalItemQuantityTabCO").get_text().strip()
            id_info["total_quantity"] = total_quantity
        except:
            print("Not found total_quantity")
        try:
            total_weight  = invoice_info_soup.find("span", id = "ctl00_cplhContainer_lblTotalItemGrossWeightTabCO").get_text().strip()
            id_info["total_weight"] = total_weight
        except:
            print("Not found total_weight")
        try:
            show_invoi_checkbox = invoice_info_soup.find("input",  id = "ctl00_cplhContainer_ckbShowOnCO")
            checked = show_invoi_checkbox.has_attr("checked")
            id_info["is_show_fob_value"] = checked
        except:
            print("Not found show_invoi_checkbox")
        try:
            origindoc_soup = invoice_info_soup.find("div",id = "ctl00_cplhContainer_pnlFileCoriginalContent").find_all("a")
            origindoc = [a.get("href") for a in origindoc_soup]
            id_info["origindoc"] = origindoc
        except:
            print("Not found origindoc")
        try:
            invoice_attached_soup = invoice_info_soup.find("div",id = "ctl00_cplhContainer_pnlInvoice").find_all("a")
            invoice_attached = [a.get("href") for a in invoice_attached_soup]
            id_info["invoice_attached"] = invoice_attached
        except:
            print("Not found invoice_attached")
        other_info_soup = all_div[6]
        try:
            declaration_place = other_info_soup.find("span",id = "ctl00_cplhContainer_lblCountryCode").get_text().strip()
            id_info["declaration_place"] = declaration_place
        except:
            print("Not found declaration_place")
        try: 
            spans = other_info_soup.find('table', id = "ctl00_cplhContainer_pnlCertificateOptions_radGridOptions_ctl00").find_all("span",class_ = "chkOption")
            remarks_info = []

            for span in spans:
                label = span.find("label").text.strip()  # Lấy nội dung của thẻ label
                input_tag = span.find("input")          # Lấy thẻ input bên trong
                checked = input_tag.has_attr("checked") # Kiểm tra trạng thái 'checked'
                remarks_info.append({"label": label, "checked": checked})
            id_info["remarks_info"] = remarks_info
        except:
            print("Not found remarks_info")
        print(id_info)
        return id_info
    except:
        print(doc_id, "Lỗi")
# %%
def run_get_id_details():
    ids = []
    for start, end in dates_list:
        request_text = request_first_page(start, end)
        if request_text is not None:
            try:
                soup = BeautifulSoup(request_text, "html.parser")
                
                viewstate = soup.find("input", attrs={"type": "hidden", "name": "__VIEWSTATE", "id": "__VIEWSTATE"})["value"]
                eventvalidation = soup.find("input", attrs={"type": "hidden", "name": "__EVENTVALIDATION", "id": "__EVENTVALIDATION"})["value"]
                total_page = int(soup.find("span", attrs={"id": "ctl00_cplhContainer_lblTotalPage"}).string)
                
                if not viewstate or not eventvalidation or not total_page:
                    raise ValueError(f"Missing data for request from {start} to {end}. Stopping.")
                
                # print(f"VIEWSTATE: {viewstate}, EVENTVALIDATION: {eventvalidation}, TOTAL_PAGE: {total_page}")
                else: 
                    all_td = soup.find_all("td", style="display:none;")
                    for td in all_td:
                        if re.fullmatch(id_pattern, td.text.strip()):
                            print(td.text.strip())
                            ids.append(td.text.strip())
                    
                    for page_index in range(2,total_page+1):
                        request_text_2 = request_more_page(eventvalidation,viewstate,page_index)
                        if request_text_2:                                  
                            try:
                                soup2 = BeautifulSoup(request_text_2,"html.parser")
                                all_td2 = soup2.find_all("td", style="display:none;")
                                for td2 in all_td2:
                                    if re.fullmatch(id_pattern, td2.text.strip()):
                                        print(td2.text.strip())
                                        ids.append(td2.text.strip())
                            except Exception as e:
                                print(f"Error processing request from {start} to {end}, page{page_index}: {e}")
                                
            except Exception as e:
                print(f"Error processing request from {start} to {end}: {e}")

        else:
            print(f"Request failed for {start} to {end}.")
            
    with open("output_co_ids.txt", "w", encoding="utf-8") as file:
        for item in ids:
            file.write(f"{item}\n")  # Mỗi ID trên một dòng
            
    with open("output_co_ids.txt", "r", encoding="utf-8") as file:
        data_list = [line.strip() for line in file]  # Loại bỏ khoảng trắng và ký tự xuống dòng

    # Hàm lưu trạng thái
    def save_state(states, thread_index):
        file_path = state_file_template.format(thread_index)
        with open(file_path, "w") as f:
            json.dump(states, f, ensure_ascii=False, indent=4)  # Định dạng dễ đọc và tránh lỗi ghi

    # Hàm đọc trạng thái
    def load_state(thread_index):
        try:
            file_path = state_file_template.format(thread_index)
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:  # Kiểm tra file tồn tại và không trống
                with open(file_path, "r") as f:
                    states = json.load(f)
                    if isinstance(states, dict) and "start_index" in states:
                        return states
            # Nếu không hợp lệ hoặc không có 'start_index'
            return {"start_index": 0}
        except FileNotFoundError:
            return {"start_index": 0}
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON in file {file_path}: {e}")
            return {"start_index": 0}  # Khởi tạo lại nếu lỗi


    # Hàm xử lý từng chunk dữ liệu
    def process_data_chunk(data_chunk, thread_index, start_index):
        all_id_info = [] 
        error_stt_list = []
        current_index = start_index

        while True:
            try:
                for index, item in enumerate(data_chunk[start_index:], start=start_index):
                    try:
                        id_info = get_id_details(cookie, item)  # Hàm `get_id_details` cần được định nghĩa
                        all_id_info.append(id_info)

                        # Ghi kết quả vào file riêng cho thread
                        with open(output_file_template.format(thread_index), "a", encoding="utf-8") as f:
                            f.write(json.dumps(id_info, ensure_ascii=False) + "\n")
                    except Exception as e:
                        print(f"Error processing row {index}: {e}")
                        error_stt_list.append({"stt": index, "error": str(e)})

                        # Ghi lỗi vào file
                        with open(error_file_template.format(thread_index), "a", encoding="utf-8") as f:
                            f.write(json.dumps({"stt": index, "error": str(e)}, ensure_ascii=False) + "\n")
                    finally:
                        # Cập nhật trạng thái
                        current_index = index + 1
                        save_state({"start_index": current_index}, thread_index)
                return all_id_info, current_index, error_stt_list
            except Exception as e:
                print(f"Thread {thread_index} encountered an error: {e}. Restarting...")
                time.sleep(5)  # Đợi 5 giây trước khi thử lại

    # Thư mục để lưu trạng thái và kết quả
    output_dir = "org"
    os.makedirs(output_dir, exist_ok=True)

    state_file_template = os.path.join(output_dir, "loop_state_{}.json")
    output_file_template = os.path.join(output_dir, "output_data_{}.txt")
    error_file_template = os.path.join(output_dir, "error_stt_{}.txt")

    # Chia danh sách thành các chunk
    with open("output_co_ids.txt", "r", encoding="utf-8") as file:
        data_list = [line.strip() for line in file]

    # chia thành các luồng
    # Điều chỉnh chunk_count dựa trên độ dài của data_list
    if len(data_list) > 200:
        chunk_count = 20
    else:
        chunk_count = 10
    chunk_size = -(-len(data_list) // chunk_count)
    chunks = [data_list[i:i + chunk_size] for i in range(0, len(data_list), chunk_size)]

    # Tải trạng thái đã lưu
    saved_states = []
    for i in range(len(chunks)):
        state = load_state(i)
        if "start_index" not in state:  # Đảm bảo có key 'start_index'
            state = {"start_index": 0}
        saved_states.append(state)

    # Xử lý đa luồng
    states = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(chunks)) as executor:
        futures = {
            executor.submit(process_data_chunk, chunk, idx, saved_states[idx]["start_index"]): idx
            for idx, chunk in enumerate(chunks)
        }
        for future in concurrent.futures.as_completed(futures):
            thread_index = futures[future]
            try:
                results, current_index, error_stts = future.result()
                states[thread_index] = {"start_index": current_index}
            except Exception as e:
                print(f"Thread {thread_index} encountered an error: {e}")
                save_state({"start_index": 0}, thread_index)

    # Hợp nhất và lưu dữ liệu lỗi
    error_file_names = [error_file_template.format(i) for i in range(chunk_count)]
    all_error_data = []
    for file_name in error_file_names:
        if os.path.exists(file_name):
            with open(file_name, "r", encoding="utf-8") as file:
                all_error_data.extend(json.loads(line) for line in file)

    error_df = pd.DataFrame(all_error_data)
    error_df.to_csv("all_error_co_id_info.csv", index=False, encoding="utf-8")

    # Hợp nhất và lưu dữ liệu kết quả
    output_file_names = [output_file_template.format(i) for i in range(chunk_count)]
    all_output_data = []
    for file_name in output_file_names:
        if os.path.exists(file_name):
            with open(file_name, "r", encoding="utf-8") as file:
                all_output_data.extend(json.loads(line) for line in file)

    output_df = pd.DataFrame(all_output_data)
    output_df.to_csv("all_co_id_info_new.csv", index=False, encoding="utf-8")


# %%
def import_co_details_to_db(company_name,username,password):
    # Đọc file CSV
    df = pd.read_csv("all_co_id_info_new.csv", quotechar='"', sep=",", encoding="utf-8",dtype=str)
    def convert_to_date(date_str):
        try:
            if date_str and isinstance(date_str, str):  # Kiểm tra nếu date_str không rỗng và là chuỗi
                return datetime.strptime(date_str.strip(), '%d/%m/%Y').date()  # Định dạng dd/mm/yyyy
            return None  # Trả về None nếu không có ngày
        except ValueError:
            return None  # Trả về None nếu không thể chuyển đổi

        
    def split_address(address_list):
        name = address_list[0].strip() if address_list else ''
        address1 = address_list[1].strip() if len(address_list) > 1 else ''
        address2 = address_list[2].strip() if len(address_list) > 2 else ''
        return name, address1, address2
    df['Issuance date'] = df['Issuance date'].apply(convert_to_date)
    df['Certified date'] = df['Certified date'].apply(convert_to_date)
    df['Departure Date'] = df['Departure Date'].apply(convert_to_date)
    columns_to_convert = ['ExportDeclaration', 'goods_info', 'origindoc','invoice_attached','remarks_info','Goods consigned from','Goods consigned to']
    for col in columns_to_convert:
        if col in df.columns:  # Kiểm tra nếu cột tồn tại
            df[col] = df[col].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) and x.startswith('[') else x)
    df = df.fillna('')
    import pyodbc

    # # Kết nối đến database master để tạo database mới
    # connection = pyodbc.connect(f'DRIVER={{SQL Server}};SERVER={server};DATABASE=master;UID={username};PWD={password}')
    # cursor = connection.cursor()

    # # Tạo database nếu chưa tồn tại
    # try:
    #     cursor.execute("IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'COData') "
    #                 "BEGIN "
    #                 "CREATE DATABASE COData; "
    #                 "END")
    #     connection.commit()  # Commit lệnh CREATE DATABASE
    # except Exception as e:
    #     print("Lỗi khi tạo cơ sở dữ liệu:", e)

    # Đóng kết nối và mở lại kết nối tới database mới
    # connection.close()

    # Kết nối đến database mới
    connection = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE=COData;UID={username};PWD={password}')
    cursor = connection.cursor()

    # Tạo bảng C/O
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'CO')
        BEGIN
            CREATE TABLE CO (
                doc_id NVARCHAR(50) PRIMARY KEY,
                company_name varchar(20),
                Trạng_thái_hồ_sơ NVARCHAR(MAX),
                Tax_code NVARCHAR(50),
                Issuing_Authority NVARCHAR(100),
                Form NVARCHAR(50),
                Importing_Country NVARCHAR(100),
                Reference_No NVARCHAR(100),
                Issuance_date DATE,
                Certified_date DATE,
                total_value NVARCHAR(50),
                total_quantity NVARCHAR(50),
                total_weight NVARCHAR(50),
                declaration_place NVARCHAR(100),
                is_show_fob_value bit
            );
        END
    """)
    #tạo bảng transport
    cursor.execute("""

        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Transport')
        BEGIN
            CREATE TABLE Transport (
                doc_id NVARCHAR(50),
                transport_type NVARCHAR(50),
                departure_date DATE,
                vessel_aircraft_name NVARCHAR(100),
                port_of_loading NVARCHAR(100),
                port_of_discharge NVARCHAR(100),
                transport_doc NVARCHAR(MAX),
                CONSTRAINT FK_Transport_CO FOREIGN KEY (doc_id) REFERENCES CO(doc_id)
            );
        END               
                
    """)
    #tạo bảng from_to
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'from_to')
        BEGIN
            CREATE TABLE from_to (
                doc_id NVARCHAR(50),
                name_export NVARCHAR(300),
                address_export NVARCHAR(300),
                address_export2 NVARCHAR(300),
                name_import NVARCHAR(300),
                address_import NVARCHAR(300),
                address_import2 NVARCHAR(300),
                CONSTRAINT FK_from_to_CO FOREIGN KEY (doc_id) REFERENCES CO(doc_id)
            );
        END
    """)

    # Tạo bảng ExportDeclaration
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ExportDeclaration')
        BEGIN
            CREATE TABLE ExportDeclaration (
                doc_id NVARCHAR(50),
                item_num INT,
                invoice_number NVARCHAR(50),
                invoice_date DATE,
                invoice_link NVARCHAR(MAX),
                CONSTRAINT FK_ExportDeclaration_CO FOREIGN KEY (doc_id) REFERENCES CO(doc_id)
            );
        END
    """)

    # Tạo bảng Goods_info
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Goods_info')
        BEGIN
            CREATE TABLE Goods_info (
                doc_id NVARCHAR(50),
                item_num INT,
                item_number INT,
                item_id NVARCHAR(50),
                Marks_and_numbers_on_packages NVARCHAR(MAX),
                Goods_description NVARCHAR(MAX),
                Origin_criterion NVARCHAR(50),
                FOB_value NVARCHAR(100),
                Invoice_number_and_date NVARCHAR(100),
                CONSTRAINT FK_Goods_info_CO FOREIGN KEY (doc_id) REFERENCES CO(doc_id)
            );
        END
    """)

    # Tạo bảng Remarks_info
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Remarks_info')
        BEGIN
            CREATE TABLE Remarks_info (
                doc_id NVARCHAR(50),
                label NVARCHAR(100),
                checked BIT,
                CONSTRAINT FK_Remarks_info_CO FOREIGN KEY (doc_id) REFERENCES CO(doc_id)
            );
        END
    """)


    # Tạo bảng origindoc
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'origindoc')
        BEGIN
            CREATE TABLE origindoc (
                doc_id NVARCHAR(50),
                origindoc VARCHAR(max),
                
                CONSTRAINT FK_origindoc_CO FOREIGN KEY (doc_id) REFERENCES CO(doc_id)
            );
        END
    """)

    # Tạo bảng invoice_attached
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'invoice_attached')
        BEGIN
            CREATE TABLE invoice_attached (
                doc_id NVARCHAR(50),
                invoice_attached VARCHAR(max),
                
                CONSTRAINT FK_invoice_attached_CO FOREIGN KEY (doc_id) REFERENCES CO(doc_id)
            );
        END
    """)

    connection.commit()  # Commit các lệnh tạo bảng

    # Đóng kết nối
    cursor.close()
    connection.close()

    print("Cơ sở dữ liệu và các bảng đã được tạo thành công.")

    # Kết nối đến SQL Server
    connection = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE=COData;UID={username};PWD={password}')
    cursor = connection.cursor()

    # Chèn dữ liệu vào bảng CO
    for idx,record in df.iterrows():
        cursor.execute("""
            MERGE INTO CO AS target
            USING (VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)) AS source
                (doc_id,company_name, Trạng_thái_hồ_sơ, Tax_code, Issuing_Authority, Form, Importing_Country, Reference_No, Issuance_date, Certified_date, total_value, total_quantity, total_weight, is_show_fob_value, declaration_place)
            ON target.doc_id = source.doc_id
            WHEN MATCHED THEN 
                UPDATE SET 
                    Trạng_thái_hồ_sơ = source.Trạng_thái_hồ_sơ,
                    company_name = source.company_name,
                    Tax_code = source.Tax_code,
                    Issuing_Authority = source.Issuing_Authority,
                    Form = source.Form,
                    Importing_Country = source.Importing_Country,
                    Reference_No = source.Reference_No,
                    Issuance_date = source.Issuance_date,
                    Certified_date = source.Certified_date,
                    total_value = source.total_value,
                    total_quantity = source.total_quantity,
                    total_weight = source.total_weight,
                    is_show_fob_value = source.is_show_fob_value,
                    declaration_place = source.declaration_place
            WHEN NOT MATCHED THEN 
                INSERT (doc_id,company_name, Trạng_thái_hồ_sơ, Tax_code, Issuing_Authority, Form, Importing_Country, Reference_No, Issuance_date, Certified_date, total_value, total_quantity, total_weight, is_show_fob_value, declaration_place)
                VALUES (source.doc_id,company_name, source.Trạng_thái_hồ_sơ, source.Tax_code, source.Issuing_Authority, source.Form, source.Importing_Country, source.Reference_No, source.Issuance_date, source.Certified_date, source.total_value, source.total_quantity, source.total_weight, source.is_show_fob_value, source.declaration_place);
        """, (
            record['doc_id'],str(company_name), str(record['Trạng thái hồ sơ']), record['Tax code'], 
            record['Issuing Authority'], record['Form'], record['Importing_Country'],
            record['Reference No.'], str(record['Issuance date']), str(record['Certified date']),
            record['total_value'], record['total_quantity'], record['total_weight'], 
            record['is_show_fob_value'], record['declaration_place']
        ))


        # Chèn hoặc cập nhật dữ liệu bảng Transport
        cursor.execute("""
            MERGE INTO Transport AS target
            USING (VALUES (?, ?, ?, ?, ?, ?, ?)) AS source
                (doc_id, transport_type, departure_date, vessel_aircraft_name, port_of_loading, port_of_discharge, transport_doc)
            ON target.doc_id = source.doc_id
            WHEN MATCHED THEN 
                UPDATE SET 
                    transport_type = source.transport_type,
                    departure_date = source.departure_date,
                    vessel_aircraft_name = source.vessel_aircraft_name,
                    port_of_loading = source.port_of_loading,
                    port_of_discharge = source.port_of_discharge,
                    transport_doc = source.transport_doc
            WHEN NOT MATCHED THEN 
                INSERT (doc_id, transport_type, departure_date, vessel_aircraft_name, port_of_loading, port_of_discharge, transport_doc)
                VALUES (source.doc_id, source.transport_type, source.departure_date, source.vessel_aircraft_name, source.port_of_loading, source.port_of_discharge, source.transport_doc);
        """, (record['doc_id'], record['transport_type'], str(record['Departure Date']), record['vessel_aircraft_name'], record['port_of_loading'], record['port_of_discharge'], record['transport_doc']))

        # Chèn hoặc cập nhật dữ liệu bảng ExportDeclaration
        for export in record['ExportDeclaration']:
            export_invoice_date = convert_to_date(export.get('invoice_date', None))  # Kiểm tra ngày hóa đơn
            cursor.execute("""
                MERGE INTO ExportDeclaration AS target
                USING (VALUES (?, ?, ?, ?, ?)) AS source
                    (doc_id, item_num, invoice_number, invoice_date, invoice_link)
                ON target.doc_id = source.doc_id AND target.invoice_number = source.invoice_number
                WHEN MATCHED THEN 
                    UPDATE SET 
                        item_num = source.item_num,
                        invoice_date = source.invoice_date,
                        invoice_link = source.invoice_link
                WHEN NOT MATCHED THEN 
                    INSERT (doc_id, item_num, invoice_number, invoice_date, invoice_link)
                    VALUES (source.doc_id, source.item_num, source.invoice_number, source.invoice_date, source.invoice_link);
            """, (record['doc_id'], export['item_num'], export['invoice_number'], str(export_invoice_date), export['invoice_link']))

        # Chèn hoặc cập nhật dữ liệu bảng Goods_info
        for idx, goods in enumerate(record['goods_info'][1:], 1):  # Bỏ qua dòng tiêu đề
            try:
                cursor.execute("""
                    MERGE INTO Goods_info AS target
                    USING (VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)) AS source
                        (doc_id, item_num, item_number, item_id, Marks_and_numbers_on_packages, Goods_description, Origin_criterion, FOB_value, Invoice_number_and_date)
                    ON target.doc_id = source.doc_id AND target.item_id = source.item_id
                    WHEN MATCHED THEN 
                        UPDATE SET 
                            item_num = source.item_num,
                            item_number = source.item_number,
                            Marks_and_numbers_on_packages = source.Marks_and_numbers_on_packages,
                            Goods_description = source.Goods_description,
                            Origin_criterion = source.Origin_criterion,
                            FOB_value = source.FOB_value,
                            Invoice_number_and_date = source.Invoice_number_and_date
                    WHEN NOT MATCHED THEN 
                        INSERT (doc_id, item_num, item_number, item_id, Marks_and_numbers_on_packages, Goods_description, Origin_criterion, FOB_value, Invoice_number_and_date)
                        VALUES (source.doc_id, source.item_num, source.item_number, source.item_id, source.Marks_and_numbers_on_packages, source.Goods_description, source.Origin_criterion, source.FOB_value, source.Invoice_number_and_date);
                """, (record['doc_id'], idx, goods[0], goods[1], goods[2], goods[3], goods[4], goods[5], goods[6]))
            except:
                True
        # Chèn hoặc cập nhật dữ liệu bảng Remarks_info
        remarks_info = record.get('remarks_info', [])  # Nếu không có 'remarks_info', gán giá trị mặc định là list rỗng
        for remark in remarks_info:
            cursor.execute("""
                MERGE INTO Remarks_info AS target
                USING (VALUES (?, ?, ?)) AS source
                    (doc_id, label, checked)
                ON target.doc_id = source.doc_id AND target.label = source.label
                WHEN MATCHED THEN 
                    UPDATE SET 
                        checked = source.checked
                WHEN NOT MATCHED THEN 
                    INSERT (doc_id, label, checked)
                    VALUES (source.doc_id, source.label, source.checked);
            """, (record['doc_id'], remark['label'], remark['checked']))

        # Chèn hoặc cập nhật dữ liệu bảng from_to
        def split_address(address_list):
            name = address_list[0].strip() if address_list else ''
            address1 = address_list[1].strip() if len(address_list) > 1 else ''
            address2 = address_list[2].strip() if len(address_list) > 2 else ''
            return name, address1, address2

        # Tách dữ liệu và chèn vào bảngfrom_to
        name_export, address_export, address_export2 = split_address(record['Goods consigned from'])
        name_import, address_import, address_import2 = split_address(record['Goods consigned to'])
        
        cursor.execute("""
            MERGE INTO from_to AS target
            USING (VALUES (?, ?, ?, ?, ?, ?, ?)) AS source
                (doc_id, name_export, address_export, address_export2, name_import, address_import, address_import2)
            ON target.doc_id = source.doc_id
            WHEN MATCHED THEN 
                UPDATE SET 
                    name_export = source.name_export,
                    address_export = source.address_export,
                    address_export2 = source.address_export2,
                    name_import = source.name_import,
                    address_import = source.address_import,
                    address_import2 = source.address_import2
            WHEN NOT MATCHED THEN 
                INSERT (doc_id, name_export, address_export, address_export2, name_import, address_import, address_import2)
                VALUES (source.doc_id, source.name_export, source.address_export, source.address_export2, source.name_import, source.address_import, source.address_import2);
        """, (record['doc_id'], name_export, address_export, address_export2, name_import, address_import, address_import2))

        # Chèn hoặc cập nhật dữ liệu bảng origindoc
        for idx, docs in enumerate(record['origindoc'][0:]):  
            cursor.execute("""
                MERGE INTO origindoc AS target
                USING (VALUES (?, ?)) AS source
                    (doc_id, origindoc)
                ON target.doc_id = source.doc_id AND target.origindoc = source.origindoc
                WHEN MATCHED THEN 
                    UPDATE SET 
                        origindoc = source.origindoc
                WHEN NOT MATCHED THEN 
                    INSERT (doc_id, origindoc)
                    VALUES (source.doc_id, source.origindoc);
            """, (record['doc_id'], docs))

        # Chèn hoặc cập nhật dữ liệu bảng invoice_attached
        for idx, invoice_attached in enumerate(record['invoice_attached'][0:]):  
            cursor.execute("""
                MERGE INTO invoice_attached AS target
                USING (VALUES (?, ?)) AS source
                    (doc_id, invoice_attached)
                ON target.doc_id = source.doc_id AND target.invoice_attached = source.invoice_attached
                WHEN MATCHED THEN 
                    UPDATE SET 
                        invoice_attached = source.invoice_attached
                WHEN NOT MATCHED THEN 
                    INSERT (doc_id, invoice_attached)
                    VALUES (source.doc_id, source.invoice_attached);
            """, (record['doc_id'], invoice_attached))

        
    # Commit các thay đổi vào cơ sở dữ liệu
    connection.commit()

    # Đóng kết nối
    cursor.close()
    connection.close()

    print("Dữ liệu đã được chèn thành công.")


# %%
def get_invoice_info(cookie,doc_id):
    url = f"https://ecosys.gov.vn/CertificatesUpgrade/Business/OrderDisplay.aspx?DocId={doc_id}"

    # Headers cần thiết
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9,vi;q=0.8,vi-VN;q=0.7",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Cookie": cookie,
        "DNT": "1",
        "Referer": "https://ecosys.gov.vn/CertificatesUpgrade/Business/CertificateAdvanceSearch.aspx",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }

    # Gửi yêu cầu GET
    response = requests.get(url, headers=headers,timeout=600)

    # Kiểm tra phản hồi
    if response.status_code == 200:
        print("Request thành công!")
        # print(response.text)  # In nội dung HTML của trang
    else:
        print(f"Lỗi: {response.status_code}")
        # print(response.text)

    invoice_info = {}
    invoice_info["doc_id"] = doc_id

    if response.text:
        soup = BeautifulSoup(response.text,"html.parser")
        
    try:    
        info_soup = soup.find('div',id = "ctl00_cplhContainer_rpvRepresenter") 
        audit_info_soup = soup.find('div',id = "ctl00_cplhContainer_pnlAuditTrail") 


        try :
            tt = info_soup.find('span',id = "ctl00_cplhContainer_lblStatus").get_text().strip()
            invoice_info["status"] = tt
        except:
            print("not found status")
        try :
            ordercode = info_soup.find('span',id = "ctl00_cplhContainer_lblOrderCode").get_text().strip()
            invoice_info["ordercode"] = ordercode
        except:
            print("not found ordercode")
        try :
            companyname = info_soup.find('span',id = "ctl00_cplhContainer_lblCompanyName").get_text().strip()
            invoice_info["companyname"] = companyname
        except:
            print("not found companyname")
        try :
            companytaxcode = info_soup.find('span',id = "ctl00_cplhContainer_lblCompanyTaxcode").get_text().strip()
            invoice_info["companytaxcode"] = companytaxcode
        except:
            print("not found companytaxcode")
        try :
            companyaddress = info_soup.find('span',id = "ctl00_cplhContainer_lblCompanyAddress").get_text().strip()
            invoice_info["companyaddress"] = companyaddress
        except:
            print("not found companyaddress")
        try :
            companyemail = info_soup.find('span',id = "ctl00_cplhContainer_lblCompanyEmail").get_text().strip()
            invoice_info["companyemail"] = companyemail
        except:
            print("not found companyemail")
        try :
            amount = info_soup.find('span',id = "ctl00_cplhContainer_lblAmount").get_text().strip()
            invoice_info["amount"] = amount
        except:
            print("not found amount")
            
        try:
            co_table = info_soup.find('table',class_ = 'rgMasterTable')
            # Lấy tiêu đề
            co_table_header = [th.get_text(separator=" ", strip=True) for th in co_table.find('thead').find_all('th', class_ = "rgHeader")]

            # Lấy dữ liệu từng dòng trong bảng
            co_info_rows = []
            for tr in co_table.find('tbody').find_all('tr'):
                row = [td.get_text(separator=" ", strip=True) for td in tr.find_all('td')]
                co_info_rows.append(row)
        except:
            print("Not found goods_info")
        co_info = [co_table_header] + co_info_rows
        invoice_info["co_info"] = co_info
        
        try :
            invoice_code = info_soup.find('span',id = "ctl00_cplhContainer_lblInvoiceCode").get_text().strip()
            invoice_info["invoice_code"] = invoice_code
        except:
            print("not found amoinvoice_codeunt")
        try :
            invoice_receip_no = info_soup.find('span',id = "ctl00_cplhContainer_lblInvoiceReceiptNumber").get_text().strip()
            invoice_info["invoice_receip_no"] = invoice_receip_no
        except:
            print("not found invoice_receip_no")
        try :
            invoice_address_label = info_soup.find('span',id = "ctl00_cplhContainer_lblInvoiceAddressLabel")
            
            if invoice_address_label:
                try :
                    a_element = invoice_address_label.find_next('a')  
                    invoice_address_label = a_element['href'].strip()  
                    # print(invoice_address_label)
                except:
                    print("Thẻ <a> không tìm thấy hoặc không có thuộc tính href.") 
                
            invoice_info["invoice_address_label"] = invoice_address_label
        except:
            print("not found invoice_address_label")
        try :
            another_email = info_soup.find('span',id = "ctl00_cplhContainer_lblEmail01").get_text().strip()
            invoice_info["another_email"] = another_email
        except:
            print("not found another_email")    
            
        try :
            created_at = audit_info_soup.find('span',id = "ctl00_cplhContainer_AuditTrail1_lblCreatedAt").get_text().strip()
            invoice_info["created_at"] = created_at
        except:
            print("not found created_at")   
            
        try :
            last_modified_at = audit_info_soup.find('span',id = "ctl00_cplhContainer_AuditTrail1_lblLastModifiedAt").get_text().strip()
            invoice_info["last_modified_at"] = last_modified_at
        except:
            print("not found last_modified_at")   

        print(invoice_info)
        return invoice_info
    except:
        True
# %%
def run_get_invoice_details():
    def request_first_page(fromdate,todate):
        # URL yêu cầu
        url = f'https://ecosys.gov.vn/CertificatesUpgrade/Business/OrderView.aspx?CertificateDateFrom={fromdate}&CertificateDateTo={todate}&status=-1&CertificateNumber=&orderCode='

        # Đặt headers
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8,vi-VN;q=0.7',
            'Cache-Control': 'max-age=0',
            'Connection': 'keep-alive',
            'Cookie': cookie,
            'DNT': '1',
            'Referer': 'https://ecosys.gov.vn/CertificatesUpgrade/Business/CertificateAdvanceSearch.aspx?',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
        }

        # Gửi yêu cầu GET
        response = requests.get(url, headers=headers,timeout=600)

        if response.status_code == 200:
            print(f"Request {fromdate},{todate} thành công!")
            return response.text
        # print(response2.text)  # Nội dung HTML
        else:
            print(f"Request thất bại: {response.status_code}")
            return None

    def request_more_page(eventvalidation,viewstate,page_index): 
        import requests

        # URL cần truy vấn
        more_page_url = "https://ecosys.gov.vn/CertificatesUpgrade/Business/OrderView.aspx"

        # Các headers sử dụng trong request
        headers2 = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9,vi;q=0.8,vi-VN;q=0.7",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
            "Cookie": cookie,
            "DNT": "1",
            "Origin": "https://ecosys.gov.vn",
            "Referer": "https://ecosys.gov.vn/CertificatesUpgrade/Business/CertificateAdvanceSearch.aspx?CertificateDateFrom=01/01/2022&CertificateDateTo=31/03/2024&Status=-1&FormCOId=0&CountryId=0&CertificateNumber=&CustomsNumber=&ReceiverName=&TransportMethodId=0",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }

        # Dữ liệu form gửi kèm
        data2 = {
            
            "__EVENTVALIDATION": eventvalidation,
            "__VIEWSTATE":viewstate,
            "ctl00$cplhContainer$ddlChoiceIndexOfPage":page_index
        }

        # Gửi POST request
        response2 = requests.post(more_page_url, headers=headers2, data=data2,timeout=600)

        # Kiểm tra kết quả trả về
        if response2.status_code == 200:
            print(f"Request page {page_index} thành công!")
            return response2.text
            # print(response2.text)  # Nội dung HTML
        else:
            print(f"Request thất bại: {response2.status_code}")
            return None

    def generate_dates(start_date, end_date):
        periods = []
        current_end = datetime.strptime(end_date, "%d/%m/%Y")
        current_start = current_end - timedelta(days=10)
        
        while current_start >= datetime.strptime(start_date, "%d/%m/%Y"):
            periods.append((current_start.strftime("%d/%m/%Y"), current_end.strftime("%d/%m/%Y")))
            # Lùi lại một tuần
            current_end = current_start - timedelta(days=1)
            current_start = current_end - timedelta(days=10)
        periods.append((start_date, current_end.strftime("%d/%m/%Y")))

        return periods

    # Ngày bắt đầu là ngày hiện tại
    start_date = (datetime.now() - timedelta(days=180)).strftime("%d/%m/%Y")
    # Ngày kết thúc là ngày hiện tại + 1 ngày
    end_date = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")

    # Tạo danh sách các khoảng thời gian
    dates_list = generate_dates(start_date, end_date)

    len(dates_list)


    id_pattern = r"\b\d{5,7}\b"
    # Danh sách lưu các ID tìm được
    ids = []

    # Số lần thử lại tối đa
    MAX_RETRIES = 10
    RETRY_DELAY = 5  # Giây

    for start, end in dates_list:
        retries = 0
        success = False
        
        while retries < MAX_RETRIES and not success:
            try:
                request_text = request_first_page(start, end)
                if request_text is not None:
                    soup = BeautifulSoup(request_text, "html.parser")
                    
                    viewstate = soup.find("input", attrs={"type": "hidden", "name": "__VIEWSTATE", "id": "__VIEWSTATE"})["value"]
                    eventvalidation = soup.find("input", attrs={"type": "hidden", "name": "__EVENTVALIDATION", "id": "__EVENTVALIDATION"})["value"]
                    total_page = int(soup.find("span", attrs={"id": "ctl00_cplhContainer_lblTotalPage"}).string)
                    
                    if not viewstate or not eventvalidation or not total_page:
                        raise ValueError(f"Missing data for request from {start} to {end}. Stopping.")
                    
                    # Xử lý các ID trên trang đầu tiên
                    all_td = soup.find_all("td", style="display:none;")
                    for td in all_td:
                        if re.fullmatch(id_pattern, td.text.strip()):
                            print(td.text.strip())
                            ids.append(td.text.strip())
                    
                    # Xử lý các trang tiếp theo (nếu có)
                    if total_page > 1:
                        for page_index in range(2, total_page + 1):
                            retries_inner = 0
                            while retries_inner < MAX_RETRIES:
                                try:
                                    request_text_2 = request_more_page(eventvalidation, viewstate, page_index)
                                    if request_text_2:
                                        soup2 = BeautifulSoup(request_text_2, "html.parser")
                                        all_td2 = soup2.find_all("td", style="display:none;")
                                        for td2 in all_td2:
                                            if re.fullmatch(id_pattern, td2.text.strip()):
                                                print(td2.text.strip())
                                                ids.append(td2.text.strip())
                                    break  # Thoát vòng lặp retry nếu thành công
                                except Exception as e:
                                    retries_inner += 1
                                    print(f"Error processing page {page_index} for {start} to {end}. Retry {retries_inner}/{MAX_RETRIES}. Error: {e}")
                                    time.sleep(RETRY_DELAY)
                    success = True  # Đánh dấu xử lý thành công
                else:
                    print(f"Request failed for {start} to {end}. Retrying...")
                    retries += 1
                    time.sleep(RETRY_DELAY)
            except ConnectionError as e:
                retries += 1
                print(f"Connection error for {start} to {end}. Retry {retries}/{MAX_RETRIES}. Error: {e}")
                time.sleep(RETRY_DELAY)
            except Exception as e:
                print(f"Unexpected error for {start} to {end}: {e}")
                break  # Ngừng thử nếu gặp lỗi không mong muốn

        if not success:
            print(f"Failed to process request for {start} to {end} after {MAX_RETRIES} retries.")

    len(ids)
    with open("output_invoice_ids.txt", "w", encoding="utf-8") as file:
        for item in ids:
            file.write(f"{item}\n")  

    # Hàm lưu trạng thái
    def save_state(states, thread_index):
        file_path = state_file_template.format(thread_index)
        with open(file_path, "w") as f:
            json.dump(states, f, ensure_ascii=False, indent=4)  # Định dạng dễ đọc và tránh lỗi ghi

    # Hàm đọc trạng thái
    def load_state(thread_index):
        try:
            file_path = state_file_template.format(thread_index)
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:  # Kiểm tra file tồn tại và không trống
                with open(file_path, "r") as f:
                    states = json.load(f)
                    if isinstance(states, dict) and "start_index" in states:
                        return states
            # Nếu không hợp lệ hoặc không có 'start_index'
            return {"start_index": 0}
        except FileNotFoundError:
            return {"start_index": 0}
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON in file {file_path}: {e}")
            return {"start_index": 0}  # Khởi tạo lại nếu lỗi


    # Hàm xử lý từng chunk dữ liệu
    def process_data_chunk(data_chunk, thread_index, start_index):
        all_invoice_info = [] 
        error_stt_list = []
        current_index = start_index
        MAX_RETRIES = 10
        RETRY_DELAY = 3  # Giây

        while True:
            try:
                for index, item in enumerate(data_chunk[start_index:], start=start_index):
                    retries = 0
                    success = False

                    while retries < MAX_RETRIES and not success:
                        try:
                            invoice_info = get_invoice_info(cookie, item)
                            all_invoice_info.append(invoice_info)
                            success = True  # Xử lý thành công, thoát vòng lặp retry
                            
                            # Ghi kết quả vào file riêng cho thread
                            with open(output_file_template.format(thread_index), "a", encoding="utf-8") as f:
                                f.write(json.dumps(invoice_info, ensure_ascii=False) + "\n")
                        
                        except ConnectionError as e:
                            retries += 1
                            print(f"Connection error for invoice {item}. Retry {retries}/{MAX_RETRIES}. Error: {e}")
                            time.sleep(RETRY_DELAY)
                        
                        except Exception as e:
                            retries += 1
                            print(f"Error processing invoice {item}. Retry {retries}/{MAX_RETRIES}. Error: {e}")
                            time.sleep(RETRY_DELAY)

                    if not success:
                        print(f"Failed to process invoice {item} after {MAX_RETRIES} retries.")
                        error_stt_list.append({"stt": item, "error": "Max retries exceeded"})
                        
                        # Ghi lỗi vào file
                        with open(error_file_template.format(thread_index), "a", encoding="utf-8") as f:
                            f.write(json.dumps({"stt": item, "error": "Max retries exceeded"}, ensure_ascii=False) + "\n")

                    # Cập nhật trạng thái
                    current_index = index + 1
                    save_state({"start_index": current_index}, thread_index)

                # Hoàn thành chunk, trả về kết quả
                return all_invoice_info, current_index, error_stt_list

            except Exception as e:
                print(f"Thread {thread_index} encountered an error: {e}. Restarting...")
                time.sleep(5)  # Đợi 5 giây trước khi thử lại

                
    # Thư mục để lưu trạng thái và kết quả
    output_dir = "org"
    os.makedirs(output_dir, exist_ok=True)

    state_file_template = os.path.join(output_dir, "loop_state_invoice_{}.json")
    output_file_template = os.path.join(output_dir, "output_invoice_data_{}.txt")
    error_file_template = os.path.join(output_dir, "error_invoice_ids_{}.txt")

    # Chia danh sách thành các chunk
    with open("output_invoice_ids.txt", "r", encoding="utf-8") as file:
        invoice_list = [line.strip() for line in file]

    # Điều chỉnh chunk_count dựa trên độ dài của data_list
    if len(invoice_list) > 200:
        chunk_count = 20
    else:
        chunk_count = 10
        
    chunk_size = -(-len(invoice_list) // chunk_count)
    chunks = [invoice_list[i:i + chunk_size] for i in range(0, len(invoice_list), chunk_size)]

    # Tải trạng thái đã lưu
    saved_states = []
    for i in range(len(chunks)):
        state = load_state(i)
        if "start_index" not in state:  # Đảm bảo có key 'start_index'
            state = {"start_index": 0}
        saved_states.append(state)

    # Xử lý đa luồng
    states = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(chunks)) as executor:
        futures = {
            executor.submit(process_data_chunk, chunk, idx, saved_states[idx]["start_index"]): idx
            for idx, chunk in enumerate(chunks)
        }
        for future in concurrent.futures.as_completed(futures):
            thread_index = futures[future]
            try:
                results, current_index, error_stts = future.result()
                states[thread_index] = {"start_index": current_index}
            except Exception as e:
                print(f"Thread {thread_index} encountered an error: {e}")
                save_state({"start_index": 0}, thread_index)

    # Hợp nhất và lưu dữ liệu lỗi
    error_file_names = [error_file_template.format(i) for i in range(chunk_count)]
    all_error_data = []
    for file_name in error_file_names:
        if os.path.exists(file_name):
            with open(file_name, "r", encoding="utf-8") as file:
                all_error_data.extend(json.loads(line) for line in file)

    error_df = pd.DataFrame(all_error_data)
    error_df.to_csv("all_error_invoice_id.csv", index=False, encoding="utf-8")

    # Hợp nhất và lưu dữ liệu kết quả
    output_file_names = [output_file_template.format(i) for i in range(chunk_count)]
    all_output_data = []
    for file_name in output_file_names:
        if os.path.exists(file_name):
            with open(file_name, "r", encoding="utf-8") as file:
                all_output_data.extend(json.loads(line) for line in file)

    output_df = pd.DataFrame(all_output_data)
    output_df.to_csv("all_invoice_info.csv", index=False, encoding="utf-8")


# %%
def import_invoice_details_to_db():
    # Đọc file CSV
    df = pd.read_csv("all_invoice_info.csv", quotechar='"', sep=",", encoding="utf-8",dtype=str)
    def convert_to_datetime(date_str):
        try:
            if date_str and isinstance(date_str, str):  # Kiểm tra nếu date_str không rỗng và là chuỗi
                # Loại bỏ 3 ký tự cuối nếu chuỗi chứa "AM" hoặc "PM"
                cleaned_date_str = date_str[:-3].strip()
                # Chuyển đổi chuỗi thành datetime
                return datetime.strptime(cleaned_date_str, '%d/%m/%Y %H:%M:%S')  # Định dạng dd/mm/yyyy hh:mm:ss
            return None  # Trả về None nếu không có chuỗi hợp lệ
        except ValueError:
            return None  # Trả về None nếu không thể chuyển đổi
    df['created_at'] = df['created_at'].apply(convert_to_datetime)
    df['last_modified_at'] = df['last_modified_at'].apply(convert_to_datetime)
    import ast

    columns_to_convert = ['co_info']
    for col in columns_to_convert:
        if col in df.columns:  # Kiểm tra nếu cột tồn tại
            df[col] = df[col].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) and x.startswith('[') else x)
    df = df.fillna('')


    # # Kết nối đến database master để tạo database mới
    # connection = pyodbc.connect(f'DRIVER={{SQL Server}};SERVER={server};DATABASE=master;UID={dbusername};PWD={dbpassword}')
    # cursor = connection.cursor()

    # # Tạo database nếu chưa tồn tại
    # try:
    #     cursor.execute("IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'COData') "
    #                 "BEGIN "
    #                 "CREATE DATABASE COData; "
    #                 "END")
    #     connection.commit()  # Commit lệnh CREATE DATABASE
    # except Exception as e:
    #     print("Lỗi khi tạo cơ sở dữ liệu:", e)

    # Đóng kết nối và mở lại kết nối tới database mới
    # connection.close()

    # Kết nối đến database mới
    connection = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE=COData;UID={dbusername};PWD={dbpassword}')
    cursor = connection.cursor()

    # Tạo bảng invoice
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'invoice')
        BEGIN
            CREATE TABLE invoice (
                invoice_doc_id VARCHAR(50) PRIMARY KEY,
                status NVARCHAR(50),
                ordercode VARCHAR(20),
                invoice_code VARCHAR(50),
                companyname NVARCHAR(100),
                companytaxcode VARCHAR(50),
                companyaddress NTEXT,
                companyemail VARCHAR(100),
                amount VARCHAR(20),
                invoice_receip_no VARCHAR(50),
                invoice_address_label VARCHAR(50),
                another_email NVARCHAR(50),
                created_at DATETIME,
                last_modified_at DATETIME
            );
        END
    """)
    #tạo bảng invoice_co_info
    cursor.execute("""

        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'invoice_co_info')
        BEGIN
            CREATE TABLE invoice_co_info (
                invoice_doc_id VARCHAR(50),
                item_num smallint,
                co_num VARCHAR(50),
                fee_type NVARCHAR(50),
                fee NVARCHAR(50),
                CONSTRAINT FK_invoice_co_info FOREIGN KEY (invoice_doc_id) REFERENCES invoice(invoice_doc_id)
            );
        END                       
    """)

    connection.commit()  # Commit các lệnh tạo bảng

    # Đóng kết nối
    cursor.close()
    connection.close()

    print("Cơ sở dữ liệu và các bảng đã được tạo thành công.")

    # Kết nối đến SQL Server
    connection = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE=COData;UID={dbusername};PWD={dbpassword}')
    cursor = connection.cursor()

    # Chèn dữ liệu vào bảng invoice
    for idx,record in df.iterrows():
        # Chèn hoặc cập nhật dữ liệu vào bảng invoice
        cursor.execute("""
            MERGE INTO invoice AS target
            USING (VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)) AS source
                (invoice_doc_id, status, ordercode, invoice_code, companyname, companytaxcode, companyaddress, companyemail, amount, invoice_receip_no, invoice_address_label, another_email, created_at, last_modified_at)
            ON target.invoice_doc_id = source.invoice_doc_id
            WHEN MATCHED THEN
                UPDATE SET
                    status = source.status,
                    ordercode = source.ordercode,
                    invoice_code = source.invoice_code,
                    companyname = source.companyname,
                    companytaxcode = source.companytaxcode,
                    companyaddress = source.companyaddress,
                    companyemail = source.companyemail,
                    amount = source.amount,
                    invoice_receip_no = source.invoice_receip_no,
                    invoice_address_label = source.invoice_address_label,
                    another_email = source.another_email,
                    created_at = source.created_at,
                    last_modified_at = source.last_modified_at
            WHEN NOT MATCHED THEN
                INSERT (invoice_doc_id, status, ordercode, invoice_code, companyname, companytaxcode, companyaddress, companyemail, amount, invoice_receip_no, invoice_address_label, another_email, created_at, last_modified_at)
                VALUES (source.invoice_doc_id, source.status, source.ordercode, source.invoice_code, source.companyname, source.companytaxcode, source.companyaddress, source.companyemail, source.amount, source.invoice_receip_no, source.invoice_address_label, source.another_email, source.created_at, source.last_modified_at);
        """, (
            record['doc_id'], record['status'], record['ordercode'], record['invoice_code'],
            record['companyname'], record['companytaxcode'], record['companyaddress'], 
            record['companyemail'], record['amount'], record['invoice_receip_no'], 
            record['invoice_address_label'], record['another_email'], 
            str(record['created_at']), str(record['last_modified_at'])
        ))


        # Chèn hoặc cập nhật dữ liệu vào bảng invoice_co_info
        for idx, goods in enumerate(record['co_info'][1:], 1):  # Bỏ qua dòng tiêu đề
            cursor.execute("""
                MERGE INTO invoice_co_info AS target
                USING (VALUES (?, ?, ?, ?, ?)) AS source
                    (invoice_doc_id, item_num, co_num, fee_type, fee)
                ON target.invoice_doc_id = source.invoice_doc_id AND target.co_num = source.co_num
                WHEN MATCHED THEN
                    UPDATE SET
                        item_num = source.item_num,
                        fee_type = source.fee_type,
                        fee = source.fee
                WHEN NOT MATCHED THEN
                    INSERT (invoice_doc_id, item_num, co_num, fee_type, fee)
                    VALUES (source.invoice_doc_id, source.item_num, source.co_num, source.fee_type, source.fee);
            """, (
                record['doc_id'], idx, goods[0], goods[2], goods[3]
            ))


    # Commit các thay đổi vào cơ sở dữ liệu
    connection.commit()

    # Đóng kết nối
    cursor.close()
    connection.close()

    print("Dữ liệu đã được chèn thành công.")

def delete_org_folder():
    try:
        # Duyệt qua tất cả các file trong thư mục
        for filename in os.listdir('org'):
            file_path = os.path.join('org', filename)
            # Kiểm tra nếu là file thì xóa
            if os.path.isfile(file_path):
                os.remove(file_path)
                print(f"Đã xóa file: {file_path}")
            else:
                print(f"Bỏ qua thư mục hoặc file không hợp lệ: {file_path}")
        print("Đã xóa tất cả file trong thư mục org.")
    except Exception as e:
        print(f"Đã xảy ra lỗi: {e}")

# %%
# Kết nối tới SQL Server
server = '3.35.252.62,1433'
dbusername = 'sa'
dbpassword = '1234QWER@'

# %%
for account in account_list[:]:
    print("Account: ",account['username'],account['password'])
    username = account['username']
    password = account['password']
    try:

        # try:
        #     cookie = get_cookie(username, password)
        #     run_get_id_details()
        #     import_co_details_to_db(username, dbusername, dbpassword)
        # except Exception as e:
        #     print(f"Error {username}: {e}")

        try:
            cookie = get_cookie(username, password)
            run_get_invoice_details()
            # import_invoice_details_to_db()
        except Exception as e:
            print(f"Error {username}: {e}")
    except: 
        continue
    finally:
        delete_org_folder()
