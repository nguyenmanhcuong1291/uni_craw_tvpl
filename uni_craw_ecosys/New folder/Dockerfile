FROM python:3.9-slim

# Cài đặt các thư viện cần thiết cho Chromium, Tesseract, pyodbc và msodbcsql17
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libxss1 \
    libasound2 \
    libgbm1 \
    fonts-liberation \
    xdg-utils \
    tesseract-ocr \
    unixodbc \
    unixodbc-dev \
    curl \
    gnupg2 \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt msodbcsql17
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - && \
    curl https://packages.microsoft.com/config/debian/10/prod.list | tee /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y msodbcsql17 && \
    rm -rf /var/lib/apt/lists/*

# Cài đặt thư viện Python
COPY requirements.txt /app/requirements.txt
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt

# Copy mã nguồn
COPY crawecosys_2.py /app/crawecosys_2.py
COPY account.csv /app/account.csv


# Thiết lập biến môi trường để tesseract có thể tìm thấy tesseract.exe
ENV TESSERACT_CMD=/usr/bin/tesseract

# Chạy ứng dụng
CMD ["python", "crawecosys_2.py"]
