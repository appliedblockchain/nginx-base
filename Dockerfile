ARG VERSION=alpine
FROM nginx:${VERSION}

# nginx:alpine contains NGINX_VERSION environment variable, like so:
# ENV NGINX_VERSION 1.21.1
WORKDIR /tmp

# Download sources
RUN wget "http://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz" -O nginx.tar.gz \
  && tar xzf nginx.tar.gz \
  && rm -f xzf nginx.tar.gz

# For latest build deps, see https://github.com/nginxinc/docker-nginx/blob/master/mainline/alpine/Dockerfile
# add compilation env, build required C based gems
RUN apk add --no-cache --virtual .build-deps \
  gcc \
  libc-dev \
  make \
  openssl-dev \
  pcre-dev \
  zlib-dev \
  linux-headers \
  curl \
  gnupg \
  libxslt-dev \
  gd-dev \
  geoip-dev \
  build-base \
  libressl-dev

COPY src ./nginx-$NGINX_VERSION/ngx_http_websocket_stat_module

RUN cd nginx-$NGINX_VERSION && ./configure \
      --prefix=/usr/share/nginx \
      --sbin-path=/usr/sbin/nginx \
      --conf-path=/etc/nginx/nginx.conf \
      --error-log-path=stderr \
      --http-log-path=/dev/stdout \
      --pid-path=/var/run/nginx.pid \
      --lock-path=/var/run/nginx.lock \
      --http-client-body-temp-path=/var/cache/nginx/client_temp \
      --http-proxy-temp-path=/var/cache/nginx/proxy_temp \
      --http-fastcgi-temp-path=/var/cache/nginx/fastcgi_temp \
      --http-uwsgi-temp-path=/var/cache/nginx/uwsgi_temp \
      --http-scgi-temp-path=/var/cache/nginx/scgi_temp \
      --user=nginx \
      --group=nginx \
      --add-module=./ngx_http_websocket_stat_module \
      --with-http_addition_module \
      --with-http_auth_request_module \
      --with-http_gunzip_module \
      --with-http_gzip_static_module \
      --with-http_realip_module \
      --with-http_ssl_module \
      --with-http_stub_status_module \
      --with-http_sub_module \
      --with-http_v2_module \
      --with-threads \
      --with-stream \
      --with-stream_ssl_module \
      --with-stream_ssl_module \
      --without-http_memcached_module \
      --without-mail_pop3_module \
      --without-mail_imap_module \
      --without-mail_smtp_module \
      --with-pcre-jit \
      --with-cc-opt='-g -O2 -fstack-protector-strong -Wformat -Werror=format-security' \
      --with-ld-opt='-Wl,-z,relro -Wl,--as-needed' \
    && make install \
    && cd .. && rm -rf nginx-$NGINX_VERSION \
    && if ! [ -d /var/cache/nginx ]; then mkdir /var/cache/nginx; fi \
    && rm /etc/nginx/*.default

# Reuse same cli arguments as the nginx:alpine image used to build
# RUN CONFARGS=$(nginx -V 2>&1 | sed -n -e 's/^.*arguments: //p') && \
#   sh -c "./configure \
#     --with-compat ${CUSTOM_CONFARGS:-${CONFARGS}} \
#     --add-module=./ngx_http_websocket_stat_module \
#     --with-http_stub_status_module \
#     --with-http_sub_module" \
#   && make install

WORKDIR /

# COPY ./docker/etc/nginx/nginx.conf /etc/nginx/nginx.conf

EXPOSE 80
STOPSIGNAL SIGTERM
CMD ["nginx", "-g", "daemon off;"]
