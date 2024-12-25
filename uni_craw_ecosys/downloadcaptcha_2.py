import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pytesseract
from PIL import Image, ImageFilter
import cv2
from collections import Counter
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

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
        return "captcha_image.png"
    else:
        print(f"Lỗi khi tải captcha: {response.status_code}")
        return False
    
# Define a function to preprocess the image
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

def run_multiple_captcha_attempts(captcha_url, attempts=10):
    results = []
    
    for i in range(attempts):
        print(f"Attempt {i + 1}...")
        # Download captcha
        if download_captcha(captcha_url):  # This correctly downloads the captcha image
            # Read and process the captcha
            captcha_text = read_captcha("captcha_image.png")
            results.append(captcha_text)
            print(f"Extracted CAPTCHA (Attempt {i + 1}): {captcha_text}")
    
    # Determine the most repeated result
    most_common = Counter(results).most_common(1)
    if most_common:
        print(f"\nMost repeated CAPTCHA result: {most_common[0][0].replace(" ", "")}")
    
    return most_common[0][0].replace(" ", "")

# Bước 3: Nhập mã captcha và gửi yêu cầu đăng nhập
def login_with_captcha(id,pw,captcha_code,hidden_fields):
    login_url = "https://dichvucong.moit.gov.vn/Login.aspx"

    # Thêm thông tin đăng nhập và captcha vào hidden fields
    hidden_fields.update({
        "ctl00$cplhContainer$txtLoginName": id,
        "ctl00$cplhContainer$txtPassword": pw,
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


captcha_url, hidden_fields = get_captcha_url()

if download_captcha(captcha_url):
        # Read the CAPTCHA text
        result = run_multiple_captcha_attempts(captcha_url, attempts=10)
        print(f"\nAll CAPTCHA results: {result}")
        
login_with_captcha(id='2300956022',pw = '2300956022',captcha_code=result,hidden_fields=hidden_fields)