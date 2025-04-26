# Nginx Steps:

1. Upload Frontend Build Files:

    Copy the entire contents of your local rag-frontend/dist folder to the chosen directory on your server (e.g., /var/www/rag-frontend/dist). You can use tools like scp or rsync.

          
> Example using scp (run from your local machine)

`scp -r /path/to/your/local/rag-frontend/dist/* your_user@129.212.132.41:/var/www/rag-frontend/dist/`

Ensure the web server user (often www-data on Debian/Ubuntu) has read permissions for these files.

```
# Example setting ownership and permissions (run on the server)
sudo chown -R www-data:www-data /var/www/rag-frontend/dist
sudo find /var/www/rag-frontend/dist -type d -exec chmod 755 {} \;
sudo find /var/www/rag-frontend/dist -type f -exec chmod 644 {} \;
```

Firewall Configuration

    Goal: Allow incoming HTTPS (port 443) and HTTP (port 80, needed for Certbot validation) traffic.

    Run these commands on your server (129.212.132.41):


```  
# Assuming you are using ufw (common on Ubuntu/Debian)
sudo ufw allow 80/tcp   # Allow HTTP
sudo ufw allow 443/tcp  # Allow HTTPS
# Or use the Nginx Full profile which includes both
# sudo ufw allow 'Nginx Full'
sudo ufw reload
sudo ufw status # Verify rules are active
```
        
    
2. Create Nginx Server Block Configuration:


Install Certbot and Nginx Plugin

```
sudo apt update # Or your distro's equivalent package manager update command
sudo apt install certbot python3-certbot-nginx -y
```   

Create a new Nginx configuration file for your site. Conventionally, this goes in /etc/nginx/sites-available/.

`sudo nano /etc/nginx/sites-available/rag-frontend`

```      
server {
    listen 80; # Listen on port 80 for HTTP requests
    listen [::]:80; # Listen on IPv6 as well

    # Replace with your actual server IP or domain name if you have one
    server_name cii.tektos-ai.com;

    # === Frontend Files ===
    # Set the root directory to your Vue app's build output
    root /var/www/rag-frontend/dist; # <--- IMPORTANT: CHANGE THIS PATH

    # Default file to serve for directory requests
    index index.html index.htm;

    # Handle requests for static assets (JS, CSS, images, etc.)
    # Optional: Add cache control headers here for better performance
    location ~* \.(?:js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1M; # Cache static assets for 1 month
        add_header Cache-Control "public";
        access_log off; # Optional: Don't log access for static files
    }

    # Handle routing for the Vue Single Page Application (SPA)
    # Try to serve the requested file/directory, otherwise fallback to index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # === Backend API Proxy ===
    # Forward requests starting with /api/ to your backend server
    location /api/ {
        # Remove the /api/ prefix before forwarding
        # Example: /api/query becomes /query
        rewrite ^/api/(.*)$ /$1 break;

        # Forward the request to your backend running on localhost:8000
        proxy_pass http://127.0.0.1:8000;

        # Set important headers for the backend application
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Optional: Increase timeouts if backend operations are long
        # proxy_connect_timeout       60s;
        # proxy_send_timeout          60s;
        # proxy_read_timeout          60s;
        # proxy_buffer_size           16k;
        # proxy_buffers               4 32k;
        # proxy_busy_buffers_size     64k;
    }

    # Optional: Custom error pages
    # error_page 500 502 503 504 /50x.html;
    # location = /50x.html {
    #     root /usr/share/nginx/html;
    # }
}
```

Save and close the file (Ctrl+X, then Y, then Enter in nano).

3. Enable the Site Configuration:

Create a symbolic link from sites-available to sites-enabled:

          
`sudo ln -s /etc/nginx/sites-available/rag-frontend /etc/nginx/sites-enabled/`


(Optional but Recommended): Remove the default Nginx site if it's enabled and might conflict:
      
`sudo rm /etc/nginx/sites-enabled/default`


4. Test Nginx Configuration:

Always test your Nginx configuration before reloading:
          
`sudo nginx -t`

If it shows syntax is ok and test is successful, proceed. If not, review the configuration file for typos.

5. Reload Nginx:

Apply the changes by reloading the Nginx service:

`sudo systemctl reload nginx`

(Use sudo systemctl restart nginx if reload doesn't work for some reason).

Run Certbot to Obtain Certificate and Configure Nginx
          
`sudo certbot --nginx -d cii.tektos-ai.com`


If successful, Certbot will confirm it obtained the certificate and modified your Nginx configuration (/etc/nginx/sites-available/rag-frontend).

Always test your Nginx configuration before reloading:
          
`sudo nginx -t`

Apply the changes by reloading the Nginx service:

`sudo systemctl reload nginx`




6. Update Frontend API URL:

Crucially, your Vue frontend now needs to send API requests to /api/... instead of directly to port 8000, because Nginx is handling the routing.

File: rag-frontend/.env.production (or .env if you don't have environment-specific files)

Change: Update VITE_API_BASE_URL.

```          
# Use HTTPS and your domain name
VITE_API_BASE_URL=https://cii.tektos-ai.com/api

VITE_APP_TITLE="CII LLM RAG"
```

Rebuild: You must rebuild your frontend after changing environment variables:

      
# In your local rag-frontend directory

`npm run build`
 
Re-upload: Upload the new contents of the dist folder to your server, replacing the old ones.
        

8. Verify:

Open your browser and navigate to https://cii.tektos-ai.com. You should see your Vue application load.

Now, Nginx serves your static Vue app files and forwards any requests starting with /api/ to your backend application running on port 8000.

9. Backend:

    Backend .env: No changes required based on the current configuration.

    Backend run.py: Ensure host is set to 0.0.0.0.

    Backend app/main.py: Ensure CORSMiddleware origins list includes https://cii.tektos-ai.com. 

    Frontend .env.production: Ensure VITE_API_BASE_URL is set to https://cii.tektos-ai.com/api. 

    Nginx Configuration: Ensure it proxies /api/ to http://127.0.0.1:8000 and handles HTTPS correctly.