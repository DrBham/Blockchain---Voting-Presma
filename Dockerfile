FROM python:3.12-slim
WORKDIR /app
COPY node.py .
EXPOSE 5000
CMD ["python", "node.py", "5000", ""]