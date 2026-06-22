FROM node:20-slim

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

# Watch-build into dist/. Load that dist/ folder as an unpacked extension in Chrome
# (chrome://extensions -> Developer mode -> Load unpacked). The volume mount in
# docker-compose surfaces dist/ on the host so Chrome picks up rebuilds.
CMD ["npm", "run", "dev"]
