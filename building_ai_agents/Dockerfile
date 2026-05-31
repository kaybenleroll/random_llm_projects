FROM docker.io/pandoc/latex:latest

# Add Unicode-capable fonts so box-drawing and symbol-heavy code blocks render in PDF.
RUN apk add --no-cache \
    fontconfig \
    ttf-dejavu \
    font-noto \
    font-noto-cjk \
    nodejs \
    npm \
    chromium \
  && npm install -g @mermaid-js/mermaid-cli \
  && fc-cache -f

ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser
