# Nginx Setup with InCommon SSL Certificate

## Step 1: Download and Install Your SSL Certificate

### Download the Certificate
Use the "Certificate (w/ chain), PEM encoded" format from the email:
```bash
# Download the certificate with chain
curl -o /tmp/dev-chat.construction-institute.org.crt \
  "https://cert-manager.com/customer/InCommon/ssl?action=download&sslId=14875660&format=x509"
```

### Move Certificate Files to Proper Location
```bash
# Create SSL directory if it doesn't exist
sudo mkdir -p /etc/ssl/certs
sudo mkdir -p /etc/ssl/private

# Move the certificate and key to proper locations
sudo mv /tmp/dev-chat.construction-institute.org.crt /etc/ssl/certs/
sudo mv /etc/ssl/private/dev-chat.construction-institute.org.key /etc/ssl/private/

# Set proper permissions
sudo chmod 644 /etc/ssl/certs/dev-chat.construction-institute.org.crt
sudo chmod 600 /etc/ssl/private/dev-chat.construction-institute.org.key
```

## Step 2: Update Nginx Configuration

### Modified Server Block Configuration
Edit your Nginx configuration file:
```bash
sudo nano /etc/nginx/sites-available/rag-frontend
```

Replace with this configuration:
```nginx
# HTTP server block - redirects to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name dev-chat.construction-institute.org;
    
    # Redirect all HTTP traffic to HTTPS
    return 301 https://$server_name$request_uri;
}

# HTTPS server block
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name dev-chat.construction-institute.org;

    # SSL Configuration
    ssl_certificate /etc/ssl/certs/dev-chat.construction-institute.org.crt;
    ssl_certificate_key /etc/ssl/private/dev-chat.construction-institute.org.key;
    
    # SSL Settings (modern configuration)
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_stapling on;
    ssl_stapling_verify on;

    # Security Headers
    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;

    # === Frontend Files ===
    root /var/www/rag-frontend/dist;
    index index.html index.htm;

    # Handle requests for static assets (JS, CSS, images, etc.)
    location ~* \.(?:js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1M;
        add_header Cache-Control "public";
        access_log off;
    }

    # Handle routing for the Vue Single Page Application (SPA)
    location / {
        try_files $uri $uri/ /index.html;
    }

    # === Backend API Proxy ===
    location /api/ {
        rewrite ^/api/(.*)$ /$1 break;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Port $server_port;
    }
}
```

## Step 3: Test and Apply Configuration

### Test Nginx Configuration
```bash
sudo nginx -t
```

### Reload Nginx
```bash
sudo systemctl reload nginx
```

## Step 4: Update Frontend Configuration

### Update Environment Variables
Edit your frontend environment file:
```bash
# File: rag-frontend/.env.production
VITE_API_BASE_URL=https://dev-chat.construction-institute.org/api
VITE_APP_TITLE="CII LLM RAG"
```

### Rebuild and Deploy
```bash
# In your local rag-frontend directory
npm run build

# Upload to server (run from local machine)
scp -r /path/to/your/local/rag-frontend/dist/* azureuser@20.65.160.135:/var/www/rag-frontend/dist/
```

## Step 5: Update Backend Configuration

### Backend CORS Configuration
Ensure your backend (app/main.py) includes the new domain:
```python
# In your FastAPI app configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://dev-chat.construction-institute.org",
        # ... other origins
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Step 6: Firewall Configuration
```bash
# Allow HTTP and HTTPS traffic
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw reload
sudo ufw status
```

## Step 7: Verify Setup

### Test Certificate Installation
```bash
# Test SSL certificate
openssl s_client -connect dev-chat.construction-institute.org:443 -servername dev-chat.construction-institute.org

# Check certificate details
openssl x509 -in /etc/ssl/certs/dev-chat.construction-institute.org.crt -text -noout
```

### Test Website Access
1. Navigate to `https://dev-chat.construction-institute.org`
2. Verify SSL certificate is valid and trusted
3. Test that API calls work properly

## Important Notes

- **Certificate Renewal**: InCommon certificates expire after 398 days (August 14, 2026). You'll need to renew before this date.
- **Domain Name**: Make sure your DNS is pointing `dev-chat.construction-institute.org` to your server IP `129.212.132.41`
- **No Let's Encrypt**: This setup uses your InCommon certificate instead of Let's Encrypt/Certbot
- **Security**: The SSL configuration includes modern security settings and HSTS headers

## Troubleshooting

### If you get certificate errors:
1. Verify the certificate file contains the full chain
2. Check file permissions are correct
3. Ensure the private key matches the certificate

### If the site doesn't load:
1. Check DNS resolution: `nslookup dev-chat.construction-institute.org`
2. Verify Nginx is running: `sudo systemctl status nginx`
3. Check Nginx error logs: `sudo tail -f /var/log/nginx/error.log`