Part 1: Setting up HTTPS with Let's Encrypt (on the Server)

This process adds a security layer (SSL/TLS) to encrypt traffic between your users' browsers and your server.

Prerequisites:

Domain Name: You must have a registered domain name (e.g., your-rag-app.com) pointing to your server's IP address (167.172.26.90). Let's Encrypt cannot issue certificates directly for IP addresses. Update your DNS records (usually an 'A' record) with your domain registrar or DNS provider.

Nginx Config: Your existing Nginx configuration (from the previous step) serving HTTP on port 80 should be working correctly.

Firewall: Ensure port 443 (HTTPS) is open on your server's firewall.

```          
sudo ufw allow 443/tcp
sudo ufw allow 'Nginx Full' # Often predefined rule for ports 80 & 443
sudo ufw reload
```
        

 
Steps using Certbot:

Install Certbot and the Nginx Plugin:

The commands might vary slightly depending on your Linux distribution. This is for Ubuntu/Debian:

```           
sudo apt update
sudo apt install certbot python3-certbot-nginx -y
```
            
Update Nginx Config with Domain Name:

    Edit your Nginx site configuration file:

          
```
sudo nano /etc/nginx/sites-available/rag-frontend
```

Change the server_name directive from the IP address to your actual domain name:

```
server {
    listen 80;
    listen [::]:80;

    # CHANGE THIS to your domain name
    server_name your-rag-app.com www.your-rag-app.com; # Include www if desired

    root /var/www/rag-frontend/dist; 
    index index.html index.htm;

    # ... rest of your existing configuration (locations for /, /api/, static assets) ...
}
```
Save and close the file.

Test the configuration: `sudo nginx -t`

Reload Nginx if the test is successful: `sudo systemctl reload nginx`

Run Certbot:

    Execute Certbot with the Nginx plugin, specifying your domain(s):

          
    # Replace with your actual domain(s) used in server_name
    `sudo certbot --nginx -d your-rag-app.com -d www.your-rag-app.com`

Certbot will ask for your email address (for renewal reminders) and ask you to agree to the terms of service.

It will then attempt to verify domain ownership.

Crucially, it will ask if you want to redirect HTTP traffic to HTTPS. Choose option 2 (Redirect). This is highly recommended for security.

If successful, Certbot will automatically obtain the certificate, install it, and modify your Nginx configuration file (/etc/nginx/sites-available/rag-frontend) to include the necessary SSL directives (listen 443 ssl, ssl_certificate, ssl_certificate_key, etc.) and the HTTP-to-HTTPS redirect.

Verify Nginx Configuration:

Test the configuration again to ensure Certbot made valid changes: `sudo nginx -t`

Reload Nginx one last time: `sudo systemctl reload nginx`


Verify Automatic Renewal:

    Certbot usually sets up automatic renewal via a systemd timer or cron job. You can test it:

```          
sudo certbot renew --dry-run
```
        
This simulates renewal without actually changing certificates. If it works, you're generally set.

Update Frontend API URL (Production):

    Since your site now uses HTTPS, you must update the production environment variable for your frontend.

    File: rag-frontend/.env.production

    Change:

```          
    # .env.production
    VITE_API_BASE_URL=https://your-rag-app.com/api # Use HTTPS and your domain
    VITE_APP_TITLE="CII LLM RAG"
```

Rebuild and Redeploy:

```      
# Local machine
npm run build
# Upload new dist/* contents to /var/www/rag-frontend/dist on the server
scp -r dist/* root@167.172.26.90:/var/www/rag-frontend/dist/
```
    


Update Backend CORS Configuration:

    Your backend needs to allow requests from the new HTTPS origin.

    File: rag_api/app/main.py

    Change: Add the HTTPS version of your domain to the origins list.

```          
    # app/main.py
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        # Add the HTTPS origin for your deployed frontend
        "https://your-rag-app.com",
        # Keep the HTTP IP if you still need it for direct access testing
        "http://167.172.26.90",
    ]
    # ... rest of CORS middleware setup ...
```

Restart your backend process (e.g., using systemctl restart your-backend-service).

Now, accessing https://your-rag-app.com should serve your Vue app over HTTPS, and API calls should correctly go to https://your-rag-app.com/api/.

Part 2: Local Testing without Nginx

This allows you to run npm run dev locally and have your frontend connect directly to the backend API (either running locally or on the remote server) without going through the Nginx proxy or using the /api prefix.

Steps:

    Use Environment-Specific .env Files: Vite automatically loads different .env files based on the command used:

        npm run dev: Loads .env and .env.development (if it exists). .env.development overrides .env.

        npm run build: Loads .env and .env.production (if it exists). .env.production overrides .env.

    Create/Modify .env.development:

        In the rag-frontend root directory, create or edit .env.development.

        Set VITE_API_BASE_URL to the direct URL of your backend API, without the /api prefix used by the Nginx proxy.

        Option A: Backend also running locally:

              
        # .env.development
        VITE_API_BASE_URL=http://localhost:8000
        VITE_APP_TITLE="CII LLM RAG (Dev)" # Optional: Different title for dev
         

        Option B: Connecting to the remote backend during local dev:

      
# .env.development
VITE_API_BASE_URL=http://167.172.26.90:8000 # Direct IP and port
VITE_APP_TITLE="CII LLM RAG (Dev)"

    

IGNORE_WHEN_COPYING_START

    Use code with caution. Dotenv
    IGNORE_WHEN_COPYING_END

Verify .env.production:

    Ensure your .env.production file still points to the production URL that uses the Nginx proxy (and HTTPS if you set it up):

          
    # .env.production
    VITE_API_BASE_URL=https://your-rag-app.com/api # Or http://167.172.26.90/api if no HTTPS/domain
    VITE_APP_TITLE="CII LLM RAG"


    Verify Backend CORS:

        Make sure your backend's CORSMiddleware in app/main.py still includes your local development origin ("http://localhost:5173", "http://127.0.0.1:5173") in the origins list. This is necessary for npm run dev to work, regardless of where the backend is running.

    No Code Changes Needed: Your apiClient.js uses import.meta.env.VITE_API_BASE_URL, so it will automatically use the correct URL based on whether you run npm run dev or npm run build.

How to Test Locally:

    Ensure your backend API is running (either locally on port 8000 or remotely on 167.172.26.90:8000).

    Ensure the backend CORS configuration allows http://localhost:5173.

    In your rag-frontend directory, run:

          
    npm run dev


Open http://localhost:5173 in your browser.

Use the chat. Check the Network tab in Developer Tools. API requests should now go directly to http://localhost:8000/query or http://167.172.26.90:8000/query (depending on your .env.development setting), not /api/query.