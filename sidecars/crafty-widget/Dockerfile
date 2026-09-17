FROM python:3.12-alpine
WORKDIR /app
COPY crafty-widget.py /app/crafty-widget.py
COPY public /public
ENV PUBLIC_DIR=/public
ENV PORT=8789
EXPOSE 8789
CMD ["python", "-u", "/app/crafty-widget.py"]
