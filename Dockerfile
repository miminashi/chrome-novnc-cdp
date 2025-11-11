FROM debian:13-slim

LABEL Maintainer="Apurv Vyavahare <apurvvyavahare@gmail.com>"

# Locale
ENV LANG=ja_JP.UTF-8
ENV LANGUAGE=ja_JP.UTF-8
ENV LC_ALL=ja_JP.UTF-8
ENV TZ="Asia/Tokyo"

# VNC Server Title(w/o spaces)
ENV VNC_TITLE="Chromium"
# VNC Resolution(720p is preferable)
ENV VNC_RESOLUTION="1280x720"
# VNC Shared Mode
ENV VNC_SHARED=false
# Local Display Server Port
ENV DISPLAY=:0
# Port settings
ENV PORT=8080
ENV NOVNC_PORT=$PORT


RUN apt-get update && \
    export DEBIAN_FRONTEND=noninteractive && \
    apt-get install -y --no-install-recommends \
        supervisor \
        bash \
        python3 \
        python3-requests \
        sed \
        xvfb \
        x11vnc \
        novnc \
        openbox \
        chromium \
        libnss3 \
        libasound2 \
        fonts-noto-cjk \
        ca-certificates \
        tzdata \
        locales && \
    # Configure locale
    sed -i 's/^# *\(ja_JP.UTF-8\)/\1/' /etc/locale.gen && \
    locale-gen && \
    # Configure timezone
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone && \
    # Clean up
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY assets/ /

ENTRYPOINT ["supervisord", "-l", "/var/log/supervisord.log", "-c"]

CMD ["/config/supervisord.conf"]