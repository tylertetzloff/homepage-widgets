FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY public/ /usr/share/nginx/html/
ENV QBIT_UPSTREAM=http://qbittorrent:8080
RUN chmod -R a+rX /usr/share/nginx/html
