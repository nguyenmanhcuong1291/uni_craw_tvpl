
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

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

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
    response = session.get(captcha_url, headers=headers)
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
        print(f"\nMost repeated CAPTCHA result: {most_common[0][0].replace(" ", "")}")
    
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
                print("Đăng nhập thành công!")

                # Đăng nhập sang ecosys
                next_button = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_cplhContainer_grdViewDefault"]/tbody/tr[2]/td[4]/a')))
                next_button.click()

                # Lấy cookie
                cookie = f'{driver.get_cookies()[3]["name"]}={driver.get_cookies()[3]["value"]}'

                # Đóng driver và trả về cookie
                driver.quit()
                if os.path.exists("captcha_image.png"):
                    os.remove("captcha_image.png")
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
    response = requests.get(url, headers=headers)

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
    current_start = datetime.strptime(start_date, "%d/%m/%Y")
    current_end = datetime.strptime(end_date, "%d/%m/%Y")
    
    while current_start >= datetime.strptime("01/01/2022", "%d/%m/%Y"):
        quarters.append((current_start.strftime("%d/%m/%Y"), current_end.strftime("%d/%m/%Y")))
        # Lùi lại một quý
        current_end = current_start - timedelta(days=1)
        current_start = (current_end.replace(day=1) - timedelta(days=1)).replace(day=1)
    quarters.append(("01/01/2022", current_end.strftime("%d/%m/%Y")))
    return quarters

# Ngày bắt đầu và kết thúc cho quý hiện tại
start_date = "01/10/2024"
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
    all_id_info = []


    # Chạy vòng lặp for
    for item in data_list:
        id_info = get_id_details(cookie,item)
        all_id_info.append(id_info)
    df = pd.DataFrame(all_id_info)
    df.to_csv("all_co_id_info_new.csv",index=False, encoding='utf-8')

# %%
def import_co_details_to_db(company_name,username,password):
    # Đọc file CSV
    df = pd.read_csv("all_co_id_info_new.csv", quotechar='"', sep=",", encoding="utf-8")
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

    # Kết nối đến database master để tạo database mới
    connection = pyodbc.connect(f'DRIVER={{SQL Server}};SERVER={server};DATABASE=master;UID={username};PWD={password}')
    cursor = connection.cursor()

    # Tạo database nếu chưa tồn tại
    try:
        cursor.execute("IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'COData') "
                    "BEGIN "
                    "CREATE DATABASE COData; "
                    "END")
        connection.commit()  # Commit lệnh CREATE DATABASE
    except Exception as e:
        print("Lỗi khi tạo cơ sở dữ liệu:", e)

    # Đóng kết nối và mở lại kết nối tới database mới
    connection.close()

    # Kết nối đến database mới
    connection = pyodbc.connect(f'DRIVER={{SQL Server}};SERVER={server};DATABASE=COData;UID={username};PWD={password}')
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
    connection = pyodbc.connect(f'DRIVER={{SQL Server}};SERVER={server};DATABASE=COData;UID={username};PWD={password}')
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


        # Chèn dữ liệu vào bảng Transport
        cursor.execute("""
            INSERT INTO Transport (doc_id, transport_type, departure_date, vessel_aircraft_name, port_of_loading, port_of_discharge, transport_doc)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, record['doc_id'], record['transport_type'], str(record['Departure Date']), record['vessel_aircraft_name'], record['port_of_loading'], record['port_of_discharge'], record['transport_doc'])

        # Chèn dữ liệu vào bảng ExportDeclaration
        for export in record['ExportDeclaration']:
            export_invoice_date = convert_to_date(export.get('invoice_date', None))  # Kiểm tra ngày hóa đơn
            cursor.execute("""
                INSERT INTO ExportDeclaration (doc_id, item_num, invoice_number, invoice_date, invoice_link)
                VALUES (?, ?, ?, ?, ?)
            """, record['doc_id'], export['item_num'], export['invoice_number'], str(export_invoice_date), export['invoice_link'])

        # Chèn dữ liệu vào bảng Goods_info
        for idx, goods in enumerate(record['goods_info'][1:], 1):  # Bỏ qua dòng tiêu đề
            try:
                cursor.execute("""
                    INSERT INTO Goods_info (doc_id, item_num, item_number, item_id, Marks_and_numbers_on_packages, Goods_description, Origin_criterion, FOB_value, Invoice_number_and_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, record['doc_id'], idx, goods[0], goods[1], goods[2], goods[3], goods[4], goods[5], goods[6])
            except:
                True
        # Chèn dữ liệu vào bảng Remarks_info, nếu tồn tại
        remarks_info = record.get('remarks_info', [])  # Nếu không có 'remarks_info', gán giá trị mặc định là list rỗng
        for remark in remarks_info:
            cursor.execute("""
                INSERT INTO Remarks_info (doc_id, label, checked)
                VALUES (?, ?, ?)
            """, record['doc_id'], remark['label'], remark['checked'])

        # Chèn dữ liệu vào bảng from_to
        def split_address(address_list):
            name = address_list[0].strip() if address_list else ''
            address1 = address_list[1].strip() if len(address_list) > 1 else ''
            address2 = address_list[2].strip() if len(address_list) > 2 else ''
            return name, address1, address2

        # Tách dữ liệu và chèn vào bảngfrom_to
        name_export, address_export, address_export2 = split_address(record['Goods consigned from'])
        name_import, address_import, address_import2 = split_address(record['Goods consigned to'])

        # Chèn dữ liệu vào bảng from_to
        cursor.execute("""
            INSERT INTO from_to (doc_id, name_export, address_export, address_export2, name_import, address_import, address_import2)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, record['doc_id'], name_export, address_export, address_export2, name_import, address_import, address_import2)

        #chèn dữ liệu bảng origindoc
        for idx, docs in enumerate(record['origindoc'][0:]):  
            cursor.execute("""
                INSERT INTO origindoc (doc_id,origindoc )
                VALUES (?, ?)
            """, record['doc_id'], docs)
            
        #chèn dữ liệu bảng invoice_attached

        for idx, invoice_attached in enumerate(record['invoice_attached'][0:]):  
            cursor.execute("""
                INSERT INTO invoice_attached (doc_id,invoice_attached )
                VALUES (?, ?)
            """, record['doc_id'], invoice_attached)
        
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
        current_start = datetime.strptime(start_date, "%d/%m/%Y")
        current_end = datetime.strptime(end_date, "%d/%m/%Y")

        while current_start >= datetime.strptime("01/01/2022", "%d/%m/%Y"):
            periods.append((current_start.strftime("%d/%m/%Y"), current_end.strftime("%d/%m/%Y")))
            # Lùi lại một tuần
            current_end = current_start - timedelta(days=1)
            current_start = current_end - timedelta(days=29)
        periods.append(("01/01/2022", current_end.strftime("%d/%m/%Y")))

        return periods

    # Ngày bắt đầu là ngày hiện tại
    start_date = (datetime.now() - timedelta(days=28)).strftime("%d/%m/%Y")
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
    

    # Danh sách lưu thông tin hóa đơn
    all_invoice_info = []

    # Số lần thử lại tối đa
    MAX_RETRIES = 10
    RETRY_DELAY = 3  # Giây
    with open("output_invoice_ids.txt", "r", encoding="utf-8") as file:
        invoice_list = [line.strip() for line in file]  
        
    for invoice in invoice_list:
        retries = 0
        success = False
        
        while retries < MAX_RETRIES and not success:
            try:
                invoice_info = get_invoice_info(cookie, invoice)
                all_invoice_info.append(invoice_info)
                success = True  # Xử lý thành công, thoát vòng lặp retry
            except ConnectionError as e:
                retries += 1
                print(f"Connection error for invoice {invoice}. Retry {retries}/{MAX_RETRIES}. Error: {e}")
                time.sleep(RETRY_DELAY)
            except Exception as e:
                retries += 1
                print(f"Error processing invoice {invoice}. Retry {retries}/{MAX_RETRIES}. Error: {e}")
                time.sleep(RETRY_DELAY)

        if not success:
            print(f"Failed to process invoice {invoice} after {MAX_RETRIES} retries.")

    import pandas as pd
    df = pd.DataFrame(all_invoice_info)
    df.to_csv("all_invoice_info.csv",index=False, encoding='utf-8')

# %%
def import_invoice_details_to_db():
    # Đọc file CSV
    df = pd.read_csv("all_invoice_info.csv", quotechar='"', sep=",", encoding="utf-8")
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


    # Kết nối đến database master để tạo database mới
    connection = pyodbc.connect(f'DRIVER={{SQL Server}};SERVER={server};DATABASE=master;UID={dbusername};PWD={dbpassword}')
    cursor = connection.cursor()

    # Tạo database nếu chưa tồn tại
    try:
        cursor.execute("IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'COData') "
                    "BEGIN "
                    "CREATE DATABASE COData; "
                    "END")
        connection.commit()  # Commit lệnh CREATE DATABASE
    except Exception as e:
        print("Lỗi khi tạo cơ sở dữ liệu:", e)

    # Đóng kết nối và mở lại kết nối tới database mới
    connection.close()

    # Kết nối đến database mới
    connection = pyodbc.connect(f'DRIVER={{SQL Server}};SERVER={server};DATABASE=COData;UID={dbusername};PWD={dbpassword}')
    cursor = connection.cursor()

    # Tạo bảng C/O
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'invoice')
        BEGIN
            CREATE TABLE invoice (
                invoice_doc_id VARCHAR(50) PRIMARY KEY,
                status NVARCHAR(50),
                ordercode VARCHAR(20),
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
    #tạo bảng transport
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
    connection = pyodbc.connect(f'DRIVER={{SQL Server}};SERVER={server};DATABASE=COData;UID={dbusername};PWD={dbpassword}')
    cursor = connection.cursor()

    # Chèn dữ liệu vào bảng invoice
    for idx,record in df.iterrows():
        cursor.execute("""
            INSERT INTO invoice (invoice_doc_id,status,ordercode,companyname,companytaxcode,companyaddress,companyemail,amount,invoice_receip_no,invoice_address_label,another_email,created_at,last_modified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, record['doc_id'], record['status'], record['ordercode'], 
            record['companyname'], record['companytaxcode'], record['companyaddress'],record['companyemail'],
            record['amount'], record['invoice_receip_no'], record['invoice_address_label'],
            record['another_email'], str(record['created_at']), str(record['last_modified_at'])
            )

        # Chèn dữ liệu vào bảng invoice_co_info
        for idx, goods in enumerate(record['co_info'][1:], 1):  # Bỏ qua dòng tiêu đề
            cursor.execute("""
                INSERT INTO invoice_co_info (invoice_doc_id,item_num, co_num, fee_type, fee)
                VALUES (?, ?, ?, ?, ?)
            """, record['doc_id'], idx, goods[0], goods[2], goods[3])


    # Commit các thay đổi vào cơ sở dữ liệu
    connection.commit()

    # Đóng kết nối
    cursor.close()
    connection.close()

    print("Dữ liệu đã được chèn thành công.")



# %%
# Kết nối tới SQL Server
server = 'localhost,1434'
dbusername = 'sa'
dbpassword = '1234QWER@'

# %%
for account in account_list[5:]:
    print("Account: ",account['username'],account['password'])
    username = account['username']
    password = account['password']
    cookie = get_cookie(username,password)
    run_get_id_details()
    import_co_details_to_db(username,dbusername,dbpassword)
    run_get_invoice_details()
    import_invoice_details_to_db()
