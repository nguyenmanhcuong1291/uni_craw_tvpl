import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Tạo session
session = requests.Session()

# URL của trang đăng nhập
login_page_url = "https://dichvucong.moit.gov.vn/Login.aspx"

# Headers cơ bản
headers = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
}

# Hàm lấy các trường ẩn từ form HTML
def get_hidden_form_fields(soup):
    hidden_fields = {}
    for input_tag in soup.find_all("input", {"type": "hidden"}):
        name = input_tag.get("name")
        value = input_tag.get("value", "")
        if name:
            hidden_fields[name] = value
    return hidden_fields

# Bước 1: Tải trang đăng nhập và tìm đường dẫn captcha
def get_captcha_url():
    response = session.get(login_page_url, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        img_tag = soup.find("img", id="ctl00_cplhContainer_imgCaptcha")
        if img_tag:
            captcha_url = urljoin(login_page_url, img_tag.get("src"))
            hidden_fields = get_hidden_form_fields(soup)  # Lấy hidden fields
            return captcha_url, hidden_fields
        else:
            print("Không tìm thấy thẻ <img> captcha.")
            return None, None
    else:
        print(f"Lỗi khi tải trang đăng nhập: {response.status_code}")
        return None, None

# Bước 2: Tải ảnh captcha
def download_captcha(captcha_url):
    response = session.get(captcha_url, headers=headers)
    if response.status_code == 200:
        with open("captcha_image.png", "wb") as f:
            f.write(response.content)
        print("Captcha đã được lưu vào file captcha_image.png")
        return True
    else:
        print(f"Lỗi khi tải captcha: {response.status_code}")
        return False

# Bước 3: Nhập mã captcha và gửi yêu cầu đăng nhập
def login_with_captcha(hidden_fields):
    login_url = "https://dichvucong.moit.gov.vn/LoginHandler.ashx"

    # Hiển thị captcha để người dùng nhập
    captcha_code = input("Nhập mã captcha từ file captcha_image.png: ")

    # Thêm thông tin đăng nhập và captcha vào hidden fields
    hidden_fields.update({
        "ctl00$cplhContainer$txtLoginName": "2300956022",
        "ctl00$cplhContainer$txtPassword": "2300956022",
        "ctl00$cplhContainer$txtCaptcha": captcha_code,
        "ctl00$cplhContainer$btnLogin": "Đăng nhập"
    })

    # Gửi yêu cầu đăng nhập
    response = session.post(login_url, headers=headers, data=hidden_fields)
    if response.status_code == 200:
        try:
            data = response.json()
            
            print("Kết quả đăng nhập (JSON):", data)
            if data.get("status") == "success":
                print("Đăng nhập thành công!")
                return True
            else:
                print("Đăng nhập thất bại:", data.get("message", "Không rõ lý do"))
                return False
        except requests.JSONDecodeError:
            print("Phản hồi không phải JSON. Nội dung:")
            print(response.text)
            return False
    else:
        print(f"Lỗi HTTP: {response.status_code}")
        print("Nội dung lỗi:", response.text)
        return False

# Bước 4: Gửi yêu cầu đến trang cần thiết sau khi đăng nhập
def request_first_page(fromdate, todate):
    url = "https://ecosys.gov.vn/CertificatesUpgrade/Business/CertificateAdvanceSearch.aspx"
    params = {
        "CertificateDateFrom": fromdate,
        "CertificateDateTo": todate,
        "Status": "-1",
        "FormCOId": "0",
        "CountryId": "0",
        "CertificateNumber": "",
        "CustomsNumber": "",
        "ReceiverName": "",
        "TransportMethodId": "0"
    }
    cookies = session.cookies
    print(cookies)
    # In danh sách cookie
    for cookie in cookies:
        cokie_value= cookie.value
    print(f"Name: {cookie.name}, Value: {cookie.value}")
    headers2 = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8,vi-VN;q=0.7',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Cookie': cokie_value,
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
    response = session.get(url, headers=headers2, params=params)
    if response.status_code == 200:
        print(f"Request {fromdate} - {todate} thành công!")
        return response.text
    else:
        print(f"Request thất bại: {response.status_code}")
        return None


captcha_url, hidden_fields = get_captcha_url()
download_captcha(captcha_url)