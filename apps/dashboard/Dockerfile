# python:3.13-slim pinned by digest (the same base image as zulhardy-lab/homelab's hpa-demo, read 2026-11-26),
# so a rebuild can't silently pick up a different image.
FROM python@sha256:7249d5587b78209a006dc4a3b5340678f84ea729239193aa559962cd8c1fce50

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY main.py ./

# Run as a non-root user; the container also runs with a read-only filesystem and no capabilities (deploy/compose.yml).
RUN useradd --system --uid 10001 --no-create-home app
USER 10001

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)"]
CMD ["python", "main.py"]
