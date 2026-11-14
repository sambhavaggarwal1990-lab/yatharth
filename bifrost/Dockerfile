# Bifrost gateway for Render. All settings come from config.json + environment variables.
FROM maximhq/bifrost:latest
USER root
RUN mkdir -p /app/yatharth && chown 1000:1000 /app/yatharth
COPY --chown=1000:1000 config.json /app/yatharth/config.json
USER 1000:1000
ENV APP_DIR=/app/yatharth \
    APP_HOST=0.0.0.0 \
    APP_PORT=8080
EXPOSE 8080
