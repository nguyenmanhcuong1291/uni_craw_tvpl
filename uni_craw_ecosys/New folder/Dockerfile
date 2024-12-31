# Chọn base image Python
FROM python:3.9-slim

# Đặt thư mục làm việc trong container
WORKDIR /app

# Copy file Python và các file phụ thuộc vào container
COPY . /app

# Cài đặt các thư viện cần thiết
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Chạy ứng dụng Python
CMD ["python", "crawecosys.py"]
