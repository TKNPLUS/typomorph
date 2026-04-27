FROM python:3.11-slim

# Install system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-noto-cjk \
        fontconfig \
        libfreetype6 \
        libpng16-16 \
        libjpeg62-turbo \
    && fc-cache -fv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /work

EXPOSE 8501

CMD ["bash"]
