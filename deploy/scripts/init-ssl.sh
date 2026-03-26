#!/bin/bash
set -e

DOMAIN=$1
EMAIL=$2
COMPOSE_CMD="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo "Usage: ./deploy/scripts/init-ssl.sh <domain> <email>"
    echo "Example: ./deploy/scripts/init-ssl.sh app.example.com admin@example.com"
    exit 1
fi

echo "=== Phase 1: Starting temporary Nginx for ACME challenge ==="

# Create temporary Nginx config (HTTP only)
mkdir -p ./deploy/nginx/tmp
cat > ./deploy/nginx/tmp/init.conf << 'EOF'
server {
    listen 80;
    server_name _;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 200 'Waiting for SSL certificate...';
        add_header Content-Type text/plain;
    }
}
EOF

# Start temporary Nginx
docker run -d \
    --name temp_nginx_ssl \
    -p 80:80 \
    -v "$(pwd)/deploy/nginx/tmp/init.conf:/etc/nginx/conf.d/default.conf" \
    -v sitter_certbot_www:/var/www/certbot \
    nginx:1.27-alpine

echo "=== Phase 2: Requesting certificate from Let's Encrypt ==="

docker run --rm \
    -v sitter_certbot_conf:/etc/letsencrypt \
    -v sitter_certbot_www:/var/www/certbot \
    certbot/certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN"

echo "=== Phase 3: Cleanup ==="

docker stop temp_nginx_ssl && docker rm temp_nginx_ssl
rm -rf ./deploy/nginx/tmp

echo ""
echo "=== SSL certificate obtained for $DOMAIN ==="
echo ""
echo "Start the full stack with:"
echo "  $COMPOSE_CMD up -d"
