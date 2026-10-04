FROM python:3.12-slim-bookworm

ARG BUILD_VERSION=0.3.1
ARG BUILD_ARCH
LABEL io.hass.version="${BUILD_VERSION}" \
      io.hass.type="app" \
      io.hass.arch="${BUILD_ARCH}"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:99 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

RUN apt-get update && apt-get install -y --no-install-recommends \
      xvfb x11vnc novnc websockify \
    && pip install --no-cache-dir playwright==1.63.0 pycryptodome==3.23.0 \
    && python -m playwright install --with-deps --no-shell chromium \
    && rm -rf /var/lib/apt/lists/* /root/.cache/pip

COPY index.html /usr/share/novnc/index.html
COPY run.sh worker.py mobile_parser.py account_store.py /app/
RUN chmod +x /app/run.sh
CMD ["/app/run.sh"]
