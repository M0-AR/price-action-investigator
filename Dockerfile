FROM python:3.12-slim
WORKDIR /work
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY tests/ ./tests/
ENV PYTHONPATH=/work
CMD ["python", "scripts/run_all.py"]
