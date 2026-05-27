FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

COPY logging_setup.py ./
COPY app/ ./app/

ENV OPSBRAIN_HOME=/var/lib/opsbrain

RUN mkdir -p ${OPSBRAIN_HOME}

EXPOSE 8000

CMD ["uvicorn", "app.__init__:app", "--host", "0.0.0.0", "--port", "8000"]
